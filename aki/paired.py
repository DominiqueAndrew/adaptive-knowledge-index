"""Interleaved lifecycle experiments: real commit-title tasks or labelled synthetic streams.

No future task, changed-file label, or correctness oracle is passed to a policy.
One source snapshot is shared as input; its measured acquisition cost is charged
equally. Every condition owns its own durable SQLite database and policy state.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import io
import json
from pathlib import Path
import random
import re
import subprocess
import tarfile
import tempfile
import time
from .benchmark import metadata, mutate, oracle, quantile, synthetic, workloads
from .policy import Policy, POLICIES
from .source import digest, parse, snapshot_id
from .store import Store, StaleRevision


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def archive_snapshot(repo, revision):
    start = time.perf_counter_ns()
    raw = subprocess.check_output(["git", "-C", str(repo), "archive", "--format=tar", revision])
    docs = {}
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for entry in archive:
            path = Path(entry.name)
            if entry.isfile() and path.suffix == ".py" and entry.size <= 1_000_000 and not any(p.startswith(".") for p in path.parts):
                docs[entry.name] = archive.extractfile(entry).read().decode("utf-8", errors="strict")
    return docs, time.perf_counter_ns()-start


def task_anchors(query: str, store: Store) -> list[str]:
    """Fixed gold-blind top-three routing: explicit paths, declared symbols, FTS.

    This is an intentionally simple task-derived access pattern, not an agent
    trace or a claim that a commit title specifies every necessary code location.
    """
    explicit = sorted((p for p in store.tokens if p in query), key=lambda p:(-len(p),p))
    terms = list(dict.fromkeys(re.findall(r"[A-Za-z_][A-Za-z_0-9]{2,80}", query)))[:64]
    symbol_paths = []
    for term in terms:
        symbol_paths.extend(p for (p,) in store.db.execute("SELECT DISTINCT path FROM symbols WHERE name=? ORDER BY path", (term,)))
    expression = " OR ".join('"'+t+'"' for t in terms)
    lexical = [p for (p,) in store.db.execute(
        "SELECT path FROM search WHERE search MATCH ? ORDER BY bm25(search,3.0,1.0),path LIMIT 3", (expression,))] if expression else []
    return list(dict.fromkeys(explicit + symbol_paths + lexical))[:3]


def conditions(history, ablation):
    result = []
    bases = ("full", "incremental") if history else ("incremental",)
    for base in bases:
        for invalidation in ("global", "selective") if history else ("selective",):
            for name in POLICIES:
                result.append((name, base, invalidation, True))
    if ablation:
        result.extend((name,"incremental","selective",False) for name in POLICIES)
    return result


def run(args):
    args.out.mkdir(parents=True, exist_ok=False)
    history = args.repo is not None
    seeds = [int(x) for x in args.seeds.split(",")]
    config = conditions(history,args.write_ablation)
    provenance = metadata() | {"experiment":"phase2 interleaved lifecycle", "seeds":seeds,
        "label":args.label, "budget":args.budget, "conditions":config,
        "workload":"actual commit titles on parent snapshots; deterministic routing; not agent traces" if history else "synthetic generated queries",
        "license":args.license, "timing_includes_shared_acquisition":history,
        "order":"seeded shuffle at setup, each refresh and each query", "source_ref":args.ref,
        "independent_repetitions":False, "note":"three paired timing repetitions; workload seeds differ only for synthetic streams"}
    if history:
        commits = list(reversed(git(args.repo,"rev-list","--first-parent",f"--max-count={args.tasks}",args.ref).splitlines()))
        events = []
        for commit in commits:
            # Read only actual current task title; its source is the parent, before its fix.
            parent = git(args.repo,"rev-parse",f"{commit}^1")
            title = git(args.repo,"show","-s","--format=%s",commit)
            events.append((commit,parent,title))
        provenance["tasks"] = [{"task_commit":c,"parent_commit":p,"query_sha256":digest(t)} for c,p,t in events]
    summaries = []
    with (args.out/"queries.jsonl").open("w") as query_file, (args.out/"refreshes.jsonl").open("w") as refresh_file:
        for seed in seeds:
            rng = random.Random(seed)
            with tempfile.TemporaryDirectory(prefix="aki-paired-") as tmp:
                states = {}
                setup_order = list(config); rng.shuffle(setup_order)
                for condition in setup_order:
                    name,base,mode,batch = condition
                    ident = ":".join(map(str,condition))
                    start = time.perf_counter_ns()
                    s = Store(Path(tmp)/(ident+".sqlite"),args.label,base,batch)
                    p = Policy(s,name,args.budget)
                    states[condition] = {"store":s,"policy":p,"setup_ns":time.perf_counter_ns()-start,
                        "query_ns":0,"refresh_ns":0,"acquisition_ns":0,"base_ns":0,"build_ns":0,
                        "optimizer_ns":0,"hits":0,"requests":0,"builds":0,"evictions":0,
                        "latencies":[],"noop":0,"invalidated":0,"retained":0,"stale_rejections":0}
                if history:
                    workload = [{"task_commit":c,"parent_commit":p,"text":t,"phase":"cold" if i==0 else "chronological","frozen":False}
                                for i,(c,p,t) in enumerate(events)]
                else:
                    initial = synthetic(500)
                    workload = workloads(initial,seed,args.count,args.scenario)
                previous_phase = None
                for index,query in enumerate(workload):
                    if history or previous_phase is None or query["phase"] == "post_mutation" and previous_phase != "post_mutation":
                        if history:
                            docs, acquisition_ns = archive_snapshot(args.repo,query["parent_commit"])
                        else:
                            docs = mutate(initial) if query["phase"] == "post_mutation" else initial
                            acquisition_ns = 0
                        source_hashes = {path:digest(text) for path,text in docs.items()}
                        fresh_edges = parse(docs).edges  # evaluator only, outside every service timer
                        order = list(config); rng.shuffle(order)
                        for condition in order:
                            state = states[condition]; s,p = state["store"],state["policy"]
                            previous_revision = s.revision
                            report = p.refresh(docs,query.get("parent_commit",query["phase"]),condition[2])
                            state["acquisition_ns"] += acquisition_ns
                            state["refresh_ns"] += report["total_refresh_ns"]
                            for field in ("noop","retained","invalidated"): state[field] += report[field]
                            if previous_revision and previous_revision != s.revision:
                                try: s.check(previous_revision)
                                except StaleRevision: state["stale_rejections"] += 1
                                else: raise AssertionError("stale revision accepted")
                            if dict(s.db.execute("SELECT path,hash FROM files")) != source_hashes:
                                raise AssertionError("source freshness mismatch")
                            refresh_file.write(json.dumps({"seed":seed,"condition":condition,"query":index,
                                "acquisition_ns":acquisition_ns,"report":report},sort_keys=True)+"\n")
                    previous_phase = query["phase"]
                    order = list(config); rng.shuffle(order)
                    expected_answers = {}
                    common_operations = None
                    for condition in order:
                        state = states[condition]; s,p = state["store"],state["policy"]
                        p.frozen = query["frozen"]
                        start = time.perf_counter_ns()
                        if history:
                            anchors = task_anchors(query["text"],s)
                            operations = [(root,kind,8000) for root in anchors for kind in ("dependencies","tests")]
                        else:
                            operations = [(query["root"],query["kind"],query["budget"])]
                        answers, costs = [], []
                        for root,kind,budget in operations:
                            answer,cost = p.query(root,kind,s.revision,query["text"],budget)
                            answers.append(answer); costs.append(cost)
                        total_ns = time.perf_counter_ns()-start
                        if common_operations is None: common_operations = operations
                        if operations != common_operations: raise AssertionError("routing parity failure")
                        for operation,answer in zip(operations,answers):
                            root,kind,budget = operation
                            if operation not in expected_answers:
                                expected_answers[operation] = oracle(docs,fresh_edges,root,kind,query["text"],budget)
                            if answer != expected_answers[operation]: raise AssertionError("answer parity failure")
                        state["query_ns"] += total_ns
                        state["latencies"].append(total_ns)
                        state["requests"] += len(costs)
                        for field in ("base_ns","build_ns","optimizer_ns"): state[field] += sum(c[field] for c in costs)
                        for target,field in (("hits","hit"),("builds","built"),("evictions","evicted")):
                            state[target] += sum(c[field] for c in costs)
                        if condition[0] != "static_full" and s.usage() > args.budget: raise AssertionError("budget")
                        answer_hash = digest(json.dumps([[(path,source_hashes[path]) for path in a] for a in answers]))
                        query_file.write(json.dumps({"seed":seed,"condition":condition,"query":index,
                            "phase":query["phase"],"query_sha256":digest(query["text"]),"source_revision":s.revision,
                            "operations":operations,"costs":costs,"total_ns":total_ns,"answer_hash":answer_hash,
                            "correct":True,"frozen":p.frozen},sort_keys=True)+"\n")
                    if history: print(json.dumps({"seed":seed,"task":index+1,"of":len(workload)}),flush=True)
                for condition,state in states.items():
                    s,p = state.pop("store"),state.pop("policy")
                    latencies = state.pop("latencies")
                    total = sum(state[k] for k in ("setup_ns","refresh_ns","acquisition_ns","query_ns"))
                    row = state | {"seed":seed,"condition":condition,"lifecycle_ns":total,
                        "service_excluding_acquisition_ns":total-state["acquisition_ns"],
                        "queries":len(workload),"p50_ns":quantile(latencies,.5),"p95_ns":quantile(latencies,.95),
                        "peak_logical_bytes":p.peak_bytes,"storage":s.storage(),"parity":True}
                    summaries.append(row); s.close()
                print(json.dumps({"seed_completed":seed,"conditions":len(config)}),flush=True)
    (args.out/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    (args.out/"summary.json").write_text(json.dumps(summaries,indent=2)+"\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--repo",type=Path)
    p.add_argument("--label",required=True)
    p.add_argument("--license",default="original synthetic")
    p.add_argument("--ref",default="HEAD")
    p.add_argument("--tasks",type=int,default=30)
    p.add_argument("--count",type=int,default=160)
    p.add_argument("--scenario",choices=("locality","low_reuse"),default="locality")
    p.add_argument("--seeds",default="70,71,72")
    p.add_argument("--budget",type=int,default=16384)
    p.add_argument("--write-ablation",action="store_true")
    p.add_argument("--out",type=Path,required=True)
    run(p.parse_args())
