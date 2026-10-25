"""Reproducible generated-workload lifecycle experiment; never agent success."""
from __future__ import annotations
import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import sqlite3
import statistics
import subprocess
import tempfile
import time
from .policy import POLICIES, Policy
from .source import digest, is_test, module_name, parse, read_python_tree, snapshot_id, token_count
from .store import Store, StaleRevision


def synthetic(n: int = 500, seed: int = 0) -> dict[str, str]:
    rng = random.Random(seed)
    docs = {"pkg/__init__.py": ""}
    for i in range(n):
        # Local chains + wider links; directed cyclic graphs arise after mutation.
        targets = {max(0, i-1)} | set(rng.sample(range(max(i, 1)), min(i, 3)))
        targets.discard(i)
        text = "".join(f"from pkg.m{j:04d} import f{j}\n" for j in sorted(targets))
        docs[f"pkg/m{i:04d}.py"] = text + f"def f{i}(value):\n    return value + {i}\n"
        if i % 4 == 0:
            docs[f"tests/test_m{i:04d}.py"] = f"from pkg.m{i:04d} import f{i}\ndef test_{i}():\n    assert f{i}(1) == {i+1}\n"
    return docs


def oracle(documents: dict[str, str], edges: set | frozenset, root: str, kind: str,
           text: str, budget: int) -> list[str]:
    """Independent in-memory BFS and packing; never used by a policy."""
    adjacency = defaultdict(set)
    for a, b in edges:
        a, b = (a, b) if kind == "dependencies" else (b, a)
        adjacency[a].add(b)
    seen, queue = {root}, deque([root])
    while queue:
        for nxt in adjacency[queue.popleft()] - seen:
            seen.add(nxt)
            queue.append(nxt)
    seen.discard(root)
    terms = set(text.lower().split())
    ordered = sorted((p for p in seen if kind != "tests" or is_test(p)),
                     key=lambda p: (-sum(t in p.lower() for t in terms), p))
    result = []
    for p in ordered:
        size = token_count(documents[p])
        if size <= budget:
            result.append(p)
            budget -= size
    return result


def workloads(docs: dict[str, str], seed: int, count: int, scenario: str):
    rng = random.Random(seed)
    roots = sorted(p for p in docs if not is_test(p))
    rng.shuffle(roots)
    hot = roots[:max(2, min(8, len(roots)//4))]
    train_pool = roots[:max(len(hot),len(roots)//2)]
    other = roots[len(train_pool):] or roots
    drift = other[:len(hot)]
    result = []
    for phase, pool, frozen in (("cold_adapt", hot, False), ("warm_heldout", hot, True),
                                ("unseen_roots", other, True), ("drift", drift, False),
                                ("post_mutation", drift, False)):
        for i in range(count):
            if scenario == "low_reuse":
                root = roots[(i + (len(result)//count)*count) % len(roots)]
            else:
                if phase == "unseen_roots":
                    root = rng.choice(other)
                elif phase in {"cold_adapt","warm_heldout"}:
                    root = rng.choice(pool if rng.random() < .85 else train_pool)
                else:
                    root = rng.choice(pool if rng.random() < .85 else roots)
            # Distinct query strings across phases; structure can still be reused.
            kind = rng.choice(("dependencies", "ripple", "tests"))
            text = f"{phase} variant{i} " + rng.choice(("test", "core", "m00", ""))
            budget = rng.choice((1024, 4096, 8192))
            result.append({"phase": phase, "root": root, "kind": kind, "text": text,
                           "budget": budget, "frozen": frozen})
    return result


def mutate(docs: dict[str, str]) -> dict[str, str]:
    result = dict(docs)
    sources = sorted(p for p in result if p.endswith(".py") and not is_test(p) and not p.endswith("__init__.py"))
    anchor = sources[len(sources)//2]
    # Introduce new incoming edge, modify outgoing edge, delete a source.
    result["tests/test_aki_added.py"] = f"import {module_name(anchor)}\ndef test_added():\n    pass\n"
    result[anchor] = f"import {module_name(sources[-1])}\ndef changed():\n    return 42\n"
    if len(sources) > 10:
        result.pop(sources[2])
    return result


def quantile(xs: list[float], q: float) -> float:
    return sorted(xs)[min(len(xs)-1, int((len(xs)-1)*q))] if xs else 0


def metadata() -> dict:
    files = list(Path("aki").glob("*.py")) + list(Path("tests").glob("*.py"))
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except subprocess.CalledProcessError:
        commit = None
    return {"utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
            "sqlite": sqlite3.sqlite_version, "machine": platform.machine(), "os": platform.system(),
            "os_release": platform.release(), "cpu_count": os.cpu_count(), "git_commit": commit,
            "code_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},
            "clock": "perf_counter_ns", "cold_definition": "new DB; OS page cache NOT flushed",
            "timing_excludes": "benchmark oracle, workload generation and result serialization",
            "timing_includes": "source ingestion, candidate generation, retrieval, optimizer, builds, eviction, refresh",
            "background_work_ns": 0, "paid_inference_calls": 0}


def run(docs: dict[str, str], label: str, seeds: list[int], count: int, budget: int,
        out: Path, scenario: str = "locality", invalidation: str = "global") -> dict:
    out.mkdir(parents=True, exist_ok=False)
    meta = metadata() | {"dataset": label, "workload": "synthetic generated sequence on " + label,
                         "source_manifest_sha256": snapshot_id(docs), "seeds": seeds,
                         "queries_per_phase": count, "logical_byte_budget": budget, "scenario": scenario,
                         "invalidation": invalidation}
    (out / "provenance.json").write_text(json.dumps(meta, indent=2)+"\n")
    summaries, all_rows = [], []
    for seed in seeds:
        queries = workloads(docs, seed, count, scenario)
        after = mutate(docs)
        before_edges, after_edges = parse(docs).edges, parse(after).edges
        gold = [oracle(after if q["phase"] == "post_mutation" else docs,
                       after_edges if q["phase"] == "post_mutation" else before_edges,
                       q["root"], q["kind"], q["text"], q["budget"]) for q in queries]
        order = list(POLICIES)
        random.Random(seed+1000).shuffle(order)
        for name in order:
            with tempfile.TemporaryDirectory(prefix="aki-bench-") as temp:
                start = time.perf_counter_ns()
                store = Store(Path(temp)/"index.sqlite", "benchmark:"+label)
                ingested = store.refresh(docs, label)
                ingest_ns = time.perf_counter_ns() - start
                policy = Policy(store, name, budget)
                static_ns = policy.initialize()
                initial_storage = store.storage()
                rows, refresh_ns, stale_checks = [], 0, 0
                refresh = {}
                old_revision = store.revision
                for i, query in enumerate(queries):
                    if query["phase"] == "post_mutation" and (i == 0 or queries[i-1]["phase"] != "post_mutation"):
                        refresh = policy.refresh(after, label + ":generated-mutation", invalidation)
                        refresh_ns += refresh["total_refresh_ns"]
                        try:
                            policy.query(query["root"], query["kind"], old_revision)
                            raise AssertionError("stale revision accepted")
                        except StaleRevision:
                            stale_checks += 1
                    policy.frozen = query["frozen"]
                    answer, event = policy.query(query["root"], query["kind"], store.revision,
                                                 query["text"], query["budget"])
                    if answer != gold[i]:
                        raise AssertionError((label, name, seed, i, answer, gold[i]))
                    rows.append(event | {"seed": seed, "policy": name, "index": i, "phase": query["phase"],
                                         "query_sha256": digest(json.dumps(query, sort_keys=True)),
                                         "answer_sha256": digest(json.dumps(answer)), "correct": True,
                                         "token_budget": query["budget"]})
                phases = {}
                for phase in dict.fromkeys(q["phase"] for q in queries):
                    group = [r for r in rows if r["phase"] == phase]
                    times = [r["total_ns"]/1e6 for r in group]
                    phases[phase] = {"total_ms": sum(times), "p50_ms": statistics.median(times),
                                     "p95_ms": quantile(times,.95), "hit_rate": statistics.mean(r["hit"] for r in group),
                                     "abstention_rate": statistics.mean(r["abstained"] for r in group)}
                total_ns = ingest_ns + static_ns + refresh_ns + sum(r["total_ns"] for r in rows)
                summary = {"seed": seed, "policy": name, "files": ingested["files"], "edges": ingested["edges"],
                           "parse_errors": ingested["parse_errors"], "queries": len(rows), "exact_matches": len(rows),
                           "stale_revision_rejections": stale_checks, "ingest_ms": ingest_ns/1e6,
                           "static_build_ms": static_ns/1e6, "refresh_ms": refresh_ns/1e6,
                           "query_total_ms": sum(r["total_ns"] for r in rows)/1e6,
                           "lifecycle_ms": total_ns/1e6, "peak_logical_bytes": policy.peak_bytes,
                           "initial_storage": initial_storage, "final_storage": store.storage(), "phases": phases}
                summary["refresh_report"] = refresh
                summaries.append(summary)
                all_rows.extend(rows)
                store.close()
                print(json.dumps({k: summary[k] for k in ("seed","policy","lifecycle_ms","query_total_ms")}), flush=True)
    # First crossing and sustained crossing relative to paired disabled run.
    for summary in summaries:
        base = next(s for s in summaries if s["seed"] == summary["seed"] and s["policy"] == "disabled")
        own = [r for r in all_rows if r["seed"] == summary["seed"] and r["policy"] == summary["policy"]]
        ref = [r for r in all_rows if r["seed"] == summary["seed"] and r["policy"] == "disabled"]
        delta = (summary["ingest_ms"] - base["ingest_ms"]) + (summary["static_build_ms"] - base["static_build_ms"])
        differences = []
        for i,(a,b) in enumerate(zip(own,ref)):
            if a["phase"] == "post_mutation" and (i == 0 or own[i-1]["phase"] != "post_mutation"):
                delta += summary["refresh_ms"] - base["refresh_ms"]
            delta += (a["total_ns"]-b["total_ns"])/1e6
            differences.append(delta)
        summary["relative_lifecycle"] = summary["lifecycle_ms"]/base["lifecycle_ms"]
        summary["first_break_even_query"] = next((i+1 for i,d in enumerate(differences) if d < 0), None)
        summary["sustained_break_even_query"] = next((i+1 for i in range(len(differences)) if max(differences[i:]) < 0), None)
    with (out/"queries.jsonl").open("w") as f:
        for row in all_rows:
            f.write(json.dumps(row,sort_keys=True)+"\n")
    (out/"summary.json").write_text(json.dumps(summaries,indent=2)+"\n")
    return {"runs": len(summaries), "queries": len(all_rows), "exact_match": 1.0}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path)
    p.add_argument("--label", default="original-synthetic-python")
    p.add_argument("--nodes", type=int, default=500)
    p.add_argument("--seeds", default="0,1,2,3,4")
    p.add_argument("--count", type=int, default=160)
    p.add_argument("--budget", type=int, default=65536)
    p.add_argument("--scenario", choices=("locality","low_reuse"), default="locality")
    p.add_argument("--invalidation", choices=("global","selective"), default="global")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    docs = read_python_tree(args.repo) if args.repo else synthetic(args.nodes)
    print(run(docs,args.label,list(map(int,args.seeds.split(","))),args.count,args.budget,args.out,args.scenario,args.invalidation))


if __name__ == "__main__":
    main()
