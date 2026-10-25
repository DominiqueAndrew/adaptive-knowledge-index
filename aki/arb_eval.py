"""Static ARB retrieval-only adapter. Policies never receive gold or future queries.

Uses the pinned upstream ranking and canonical BCY functions directly. Inputs
stay outside this repository; published outputs contain IDs, ranks and metrics,
not source text or failure traces. No model or remote API is called.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
import tempfile
import time
from .benchmark import metadata
from .policy import Policy
from .store import Store


def read_jsonl(path):
    with Path(path).open() as f:
        return [json.loads(line) for line in f if line.strip()]


class FileCache:
    def __init__(self,docs): self.docs=docs
    def file_text(self,repo,commit,path): return self.docs.get(path)


def retrieve(query: str, store: Store, policy: Policy, graph: bool):
    """Gold-blind interface. Fixed rules before reading any benchmark scores."""
    terms = list(dict.fromkeys(re.findall(r"[A-Za-z_][A-Za-z_0-9]{1,80}",query.lower())))[:256]
    expression = " OR ".join('"'+x+'"' for x in terms)
    lexical = store.db.execute("SELECT path,bm25(search,3.0,1.0) AS s FROM search WHERE search MATCH ? ORDER BY s,path",(expression,)).fetchall() if expression else []
    scores = {path: 1/(60+i+1) for i,(path,_) in enumerate(lexical)}
    anchors = sorted((p for p in store.tokens if p in query),key=lambda p:(-len(p),p))[:3] if graph else []
    events=[]
    for anchor in anchors:
        paths,event=policy.query(anchor,"dependencies",store.revision,budget=10**12)
        events.append(event)
        for path in paths:
            scores[path]=scores.get(path,0)+.25/61
    ranked=sorted(scores,key=lambda p:(-scores[p],p))
    return ranked,{"anchors":len(anchors),"relationship_requests":len(events),
                   "hits":sum(e["hit"] for e in events),"builds":sum(e["built"] for e in events),
                   "operator_ns":sum(e["total_ns"] for e in events)}


def run(args):
    sys.path.insert(0,str(args.upstream/"src"))
    from agent_retrieval_bench.baseline import (query_text_for_eval,query_has_leakage,target_gold_files,
            rank_chunks_for_ranker,unique_ranked_paths,reciprocal_rank,recall_at)
    from agent_retrieval_bench.repomap_eval import build_repomap_index,rank_files_for_sample
    from agent_retrieval_bench.bcy_curve import evaluate_sample
    args.out.mkdir(parents=True,exist_ok=False)
    provenance=metadata() | {"benchmark":"ARB static retrieval-only SUBSETS", "subsets":args.subsets.split(","),
        "upstream_commit":"2c773139dd86003ec6defffa28bff1688c4af768",
        "dataset_revision":"5901e1ee3aff048290db72edf9c63bc498b79ea3",
        "candidate_filter":"all_files","keep_list":None,"tokenizer":"regex_code_tokenizer_v1",
        "tuning":"no gold-label tuning; method fixed before score inspection",
        "inference_calls":0,"sample_hashes":{},"corpus_manifest_hashes":{}}
    import subprocess
    actual=subprocess.check_output(["git","-C",str(args.upstream),"rev-parse","HEAD"],text=True).strip()
    if actual != provenance["upstream_commit"]: raise ValueError("upstream evaluator pin mismatch")
    manifest={}
    samples=[]
    for subset in args.subsets.split(","):
        sample_file=args.data/"benchmark"/subset/"samples.jsonl"
        manifest_file=args.data/"corpus"/subset/"corpus_manifest.jsonl"
        provenance["sample_hashes"][subset]=hashlib.sha256(sample_file.read_bytes()).hexdigest()
        provenance["corpus_manifest_hashes"][subset]=hashlib.sha256(manifest_file.read_bytes()).hexdigest()
        samples.extend(read_jsonl(sample_file))
        for row in read_jsonl(manifest_file):
            suffix=Path(row["chunks_path"]).parts
            if suffix[0]=="data": suffix=suffix[1:]
            manifest[row["repo"],row["base_commit"]]=args.data.joinpath(*suffix)
    pending=defaultdict(list)
    for sample in samples:
        text=query_text_for_eval(sample)
        if query_has_leakage(sample,text): raise ValueError("upstream query leakage gate")
        pending[sample["repo"],sample["base_commit"]].append(sample)
    output=[]
    costs=[]
    raw=args.out/"rankings.jsonl"
    with raw.open("w") as f:
        for group_number,((repo,commit),group) in enumerate(sorted(pending.items())):
            load_t=time.perf_counter_ns()
            chunks=read_jsonl(manifest[repo,commit])
            docs={c["path"]:c.get("text","") for c in chunks if c.get("kind")=="file"}
            load_ns=time.perf_counter_ns()-load_t
            positive=any(target_gold_files(s) for s in group)
            setup={}
            with tempfile.TemporaryDirectory(prefix="aki-arb-") as tmp:
                begin=time.perf_counter_ns()
                store=Store(Path(tmp)/"base.sqlite",repo)
                parse_report=store.refresh(docs,f"ARB:{repo}@{commit}")
                setup["aki_base_ns"]=time.perf_counter_ns()-begin
                policies={name:Policy(store,name,65536) for name in ("disabled","lru","aki")}
                # Separate stores prevent one policy from changing another's cache.
                extra=[]
                for name in ("lru","aki"):
                    other=Store(Path(tmp)/(name+".sqlite"),repo)
                    store.db.backup(other.db)
                    other.revision=store.revision
                    other.tokens=dict(store.tokens)
                    policies[name]=Policy(other,name,65536)
                    extra.append(other)
                repomap=None
                if positive and not args.skip_baselines:
                    begin=time.perf_counter_ns()
                    repomap=build_repomap_index(chunks)
                    setup["repomap_build_ns"]=time.perf_counter_ns()-begin
                for sample in group:
                    # Only query/task fields cross the retrieval interface below.
                    text=query_text_for_eval(sample)
                    ranks={}
                    timing={}
                    diagnostics={}
                    methods=("fts", "graph_disabled", "graph_lru", "graph_aki")
                    for method in methods:
                        name=method.removeprefix("graph_") if method!="fts" else "disabled"
                        begin=time.perf_counter_ns()
                        ranks[method],diagnostics[method]=retrieve(text,policies[name].store,policies[name],method!="fts")
                        timing[method]=time.perf_counter_ns()-begin
                    if not (ranks["graph_disabled"]==ranks["graph_lru"]==ranks["graph_aki"]):
                        raise AssertionError("physical design changed retrieval semantics")
                    if positive and not args.skip_baselines:
                        for method in ("lexical","bm25"):
                            begin=time.perf_counter_ns()
                            ranks[method]=unique_ranked_paths(rank_chunks_for_ranker(text,chunks,method))
                            timing[method]=time.perf_counter_ns()-begin
                        begin=time.perf_counter_ns()
                        # RepoMap gets only query/task fields; no gold given_files shortcut.
                        public_query={"query":sample["query"],"task_type":sample["task_type"]}
                        ranks["repomap"]=[r[0] for r in rank_files_for_sample(public_query,text,repomap,set(repomap.nodes),.65,.25,.10)]
                        timing["repomap"]=time.perf_counter_ns()-begin
                    gold=target_gold_files(sample)  # evaluator-only after ranking
                    no_gold_type="positive" if gold else ("natural" if sample.get("metadata",{}).get("organic") else "counterfactual")
                    for method,ranked in ranks.items():
                        detail={"sample_id":sample["id"],"task_type":sample["task_type"],"repo":repo,
                                "base_commit":commit,"top_files":ranked[:20]}
                        bcy=evaluate_sample(detail,gold,FileCache(docs),(4000,8000,16000,32000)) if gold else None
                        row=detail | {"method":method,"stratum":no_gold_type,"query_sha256":hashlib.sha256(text.encode()).hexdigest(),
                            "candidate_count":len(docs),"ranked_count":len(ranked),"query_ns":timing[method],
                            "diagnostics":diagnostics.get(method,{}),"abstained":not ranked,
                            "gold_ranks":{p:ranked.index(p)+1 if p in ranked else None for p in gold},
                            "MRR":reciprocal_rank(set(gold),ranked) if gold else None,
                            "Recall@20":recall_at(set(gold),ranked,20) if gold else None,
                            "BCY":{str(b):v["bcy"] for b,v in bcy["packed"].items()} if bcy else None}
                        output.append(row)
                        f.write(json.dumps(row,sort_keys=True)+"\n")
                        f.flush()
                costs.append({"repo":repo,"commit":commit,"samples":len(group),"files":len(docs),
                              "load_ns":load_ns,"setup":setup,"edges":parse_report["edges"],
                              "parse_error_count":len(parse_report["parse_errors"]),"storage":store.storage()})
                for other in extra: other.close()
                store.close()
            print(json.dumps({"snapshot":group_number+1,"of":len(pending),"repo":repo,"samples":len(group)}),flush=True)
    summaries={}
    for method in sorted({r["method"] for r in output}):
        rows=[r for r in output if r["method"]==method]
        pos=[r for r in rows if r["stratum"]=="positive"]
        metric=lambda rs,key:statistics.mean(r[key] for r in rs) if rs else None
        by_repo={repo:{"n":len(group),"MRR":metric(group,"MRR"),"Recall@20":metric(group,"Recall@20"),
                       "BCY@8k":statistics.mean(r["BCY"]["8000"] for r in group)}
                 for repo in sorted({r["repo"] for r in pos}) if (group:=[r for r in pos if r["repo"]==repo])}
        summaries[method]={"positive_samples":len(pos),"MRR":metric(pos,"MRR"),"Recall@20":metric(pos,"Recall@20"),
            "BCY":{str(b):statistics.mean(r["BCY"][str(b)] for r in pos) for b in (4000,8000,16000,32000)} if pos else {},
            "by_repo":by_repo,"macro_repo_MRR":statistics.mean(r["MRR"] for r in by_repo.values()) if by_repo else None,
            "query_ms":sum(r["query_ns"] for r in rows)/1e6,
            "abstention":{s:{"n":len(group),"correct_abstention_rate":metric(group,"abstained")}
                for s in ("natural","counterfactual") if (group:=[r for r in rows if r["stratum"]==s])},
            "relationship_requests":sum(r["diagnostics"].get("relationship_requests",0) for r in rows),
            "relationship_hits":sum(r["diagnostics"].get("hits",0) for r in rows)}
    (args.out/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    (args.out/"summary.json").write_text(json.dumps(summaries,indent=2)+"\n")
    (args.out/"snapshot_costs.json").write_text(json.dumps(costs,indent=2)+"\n")
    print(json.dumps(summaries,indent=2))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--upstream",type=Path,required=True)
    parser.add_argument("--data",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--subsets",default="v2_trace2code,v2_abstention")
    parser.add_argument("--skip-baselines",action="store_true")
    run(parser.parse_args())
