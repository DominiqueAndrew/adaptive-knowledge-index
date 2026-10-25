#!/usr/bin/env python3
"""Post-hoc cost and reuse diagnosis of already-exposed phase-one data only."""
import argparse
from collections import Counter,defaultdict,deque
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aki.source import parse


def read(path):
    with Path(path).open() as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    report={"scope":"already-exposed phase-one data; diagnosis, not fresh evaluation","cost":{}}
    for name in ("final-synthetic-v2","click-history","pytest-history"):
        rows=read(Path("results")/name/"queries.jsonl")
        summaries=json.loads((Path("results")/name/"summary.json").read_text())
        result={}
        for policy in ("disabled","lru","frequency","aki"):
            group=[r for r in rows if r["policy"]==policy and r.get("mode","selective")=="selective"]
            runs=[s for s in summaries if s["policy"]==policy and s.get("mode","selective")=="selective"]
            total=sum(r["total_ns"] for r in group)
            lifecycle=sum(s["lifecycle_ms"]*1e6 for s in runs)
            result[policy]={"queries":len(group),"lifecycle_ms":lifecycle/1e6,
                "refresh_and_initial_fraction":1-total/lifecycle,
                "free_all_traversal_savings_upper_bound":sum(r["base_ns"] for r in group)/lifecycle,
                "base_fraction_of_query":sum(r["base_ns"] for r in group)/total,
                "optimizer_fraction_of_query":sum(r["optimizer_ns"] for r in group)/total,
                "build_fraction_of_query":sum(r["build_ns"] for r in group)/total,
                "rank_pack_and_wrapper_fraction":sum(r["retrieval_ns"]-r["base_ns"]-r["lookup_ns"] for r in group)/total,
                "base_when_missed_p50_us":statistics.median(r["base_ns"]/1000 for r in group if not r["hit"]),
                "hits":sum(r["hit"] for r in group),"builds":sum(r.get("built",False) for r in group),
                "evictions":sum(r.get("evicted",0) for r in group)}
        report["cost"][name]=result
    manifest={}
    pending=defaultdict(list)
    for subset in ("v2_trace2code","v2_abstention"):
        for r in read(a.data/"corpus"/subset/"corpus_manifest.jsonl"):
            manifest[r["repo"],r["base_commit"]]=a.data/Path(r["chunks_path"]).relative_to("data")
        for s in read(a.data/"benchmark"/subset/"samples.jsonl"):
            pending[s["repo"],s["base_commit"]].append((s["id"],json.dumps(s["query"],ensure_ascii=False,sort_keys=True)))
    counts=Counter()
    by_repo=defaultdict(Counter)
    anchor_rows=[]
    for (repo,commit),queries in pending.items():
        chunks=read(manifest[repo,commit])
        docs={c["path"]:c.get("text","") for c in chunks if c.get("kind")=="file"}
        parsed=parse(docs)
        adjacency=defaultdict(set)
        for src,dst in parsed.edges:adjacency[src].add(dst)
        prior={}
        for sample_id,query in queries:
            anchors=sorted((p for p in docs if p in query),key=lambda p:(-len(p),p))[:3]
            counts["queries"]+=1
            counts["queries_without_explicit_path"]+=not anchors
            for root in anchors:
                visited={root};queue=deque([root])
                while queue:
                    for node in adjacency[queue.popleft()]-visited:
                        visited.add(node);queue.append(node)
                visited.discard(root)
                subpaths=[p for p,closure in prior.items() if p!=root and p in visited and closure]
                row={"sample_id":sample_id,"repo":repo,"base_commit":commit,
                     "root":root,"python":root.endswith(".py"),"closure_size":len(visited),
                     "exact_prior":root in prior,"nonempty_exact_prior":root in prior and bool(prior[root]),
                     "reusable_nonempty_subpaths":len(subpaths)}
                anchor_rows.append(row)
                for c,v in {"requests":1,"python_anchors":row["python"],"empty_closures":not visited,
                            "exact_prior":row["exact_prior"],"nonempty_exact_prior":row["nonempty_exact_prior"],
                            "requests_with_reusable_subpaths":bool(subpaths)}.items():
                    counts[c]+=v;by_repo[repo][c]+=v
                prior[root]=visited
    report["arb_reuse"]={"counts":dict(counts),"by_repo":dict(by_repo),"requests":anchor_rows}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({"cost":report["cost"],"arb_reuse_counts":dict(counts)},indent=2))


if __name__=="__main__":main()
