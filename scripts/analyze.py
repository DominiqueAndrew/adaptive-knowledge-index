#!/usr/bin/env python3
"""Deterministically summarize raw runs and render standalone research figures."""
from collections import defaultdict
import json
import math
import os
from pathlib import Path
import random
import statistics


def bootstrap(values,seed=981,n=5000):
    rng=random.Random(seed)
    means=sorted(statistics.mean(rng.choices(values,k=len(values))) for _ in range(n))
    return [means[int(.025*n)],means[int(.975*n)]]


def summarize(path):
    rows=json.loads((path/"summary.json").read_text())
    groups={p:[r for r in rows if r["policy"]==p] for p in sorted({r["policy"] for r in rows})}
    means={p:statistics.mean(r["lifecycle_ms"] for r in rs) for p,rs in groups.items()}
    # Choose one comparator by aggregate measured cost, not an impossible per-seed oracle.
    best=min((p for p in means if p not in {"aki","static_full"}),key=means.get)
    aki={r["seed"]:r for r in groups["aki"]}
    relative=[aki[r["seed"]]["lifecycle_ms"]/r["lifecycle_ms"] for r in groups[best]]
    output={"best_matched_baseline":best,"aki_over_best_ratios":relative,
            "aki_over_best_mean":statistics.mean(relative),"bootstrap_95_seed_mean":bootstrap(relative),
            "bootstrap_caveat":"descriptive only: five generated seeds on one machine, not population generalization",
            "policies":{p:{"mean_lifecycle_ms":means[p],
                            "mean_query_ms":statistics.mean(r["query_total_ms"] for r in rs),
                            "mean_peak_logical_bytes":statistics.mean(r["peak_logical_bytes"] for r in rs),
                            "sustained_break_even_queries":[r["sustained_break_even_query"] for r in rs],
                            "mean_phase_p95_ms":{phase:statistics.mean(r["phases"][phase]["p95_ms"] for r in rs)
                                                 for phase in rs[0]["phases"]}}
                        for p,rs in groups.items()}}
    return output,groups


def main():
    root=Path("results")
    analysis={}
    grouped={}
    for label in ("final-synthetic-v2","final-low-reuse"):
        analysis[label],grouped[label]=summarize(root/label)
    for dataset in ("click-history","pytest-history"):
        history=json.loads((root/dataset/"summary.json").read_text())
        analysis[dataset]={f"{p}/{mode}":{
            "mean_lifecycle_ms":statistics.mean(r["lifecycle_ms"] for r in history if r["policy"]==p and r["mode"]==mode),
            "retained":sum(r["retained"] for r in history if r["policy"]==p and r["mode"]==mode),
            "invalidated":sum(r["invalidated"] for r in history if r["policy"]==p and r["mode"]==mode)}
            for p in sorted({r["policy"] for r in history}) for mode in ("global","selective")}
    (root/"analysis.json").write_text(json.dumps(analysis,indent=2)+"\n")
    # matplotlib is optional, already present on the original machine.
    os.environ.setdefault("MPLCONFIGDIR","/tmp/aki-matplotlib")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size":10,"svg.fonttype":"none"})
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout="constrained")
    order=["disabled","static_bounded","static_full","lru","frequency","gds","aki"]
    for ax,label in zip(axes,("final-synthetic-v2","final-low-reuse")):
        groups=grouped[label]
        values=[statistics.mean(r["lifecycle_ms"] for r in groups[p]) for p in order]
        ax.bar(range(len(order)),values,color=["#4477aa"]*6+["#228833"])
        for i,p in enumerate(order):
            ax.scatter([i]*len(groups[p]),[r["lifecycle_ms"] for r in groups[p]],s=12,color="black")
        ax.set_xticks(range(len(order)),[x.replace("_","\n") for x in order],rotation=25)
        ax.set_ylabel("Total lifecycle wall time (ms)")
        ax.set_title("Generated locality workload" if "synthetic" in label else "Generated low-reuse workload")
        ax.grid(axis="y",alpha=.2)
    fig.suptitle("AKI prototype: five held-out seeds, 626 synthetic files\nFull materialization is an unbounded reference; others use 64 KiB logical budgets")
    fig.savefig(root/"lifecycle.svg")
    fig.savefig(root/"lifecycle.png",dpi=150)
    plt.close(fig)
    # Cumulative curves include initial indexing, builds and the mutation refresh.
    raw=[json.loads(x) for x in (root/"final-synthetic-v2/queries.jsonl").read_text().splitlines()]
    fig,ax=plt.subplots(figsize=(8,4.8),layout="constrained")
    for policy in ("disabled","lru","frequency","gds","aki"):
        runs=[]
        for s in grouped["final-synthetic-v2"][policy]:
            total=s["ingest_ms"]+s["static_build_ms"]
            ys=[]
            previous=None
            for r in (r for r in raw if r["seed"]==s["seed"] and r["policy"]==policy):
                if r["phase"]=="post_mutation" and previous!="post_mutation": total+=s["refresh_ms"]
                total+=r["total_ns"]/1e6
                ys.append(total)
                previous=r["phase"]
            runs.append(ys)
        mean=[statistics.mean(xs) for xs in zip(*runs)]
        ax.plot(range(1,len(mean)+1),mean,label=policy)
    for x,label in ((160,"heldout"),(320,"unseen roots"),(480,"drift"),(640,"mutation")):
        ax.axvline(x,color="gray",alpha=.3)
        ax.text(x+4,30,label,rotation=90,fontsize=8)
    ax.set(xlabel="Query number",ylabel="Cumulative lifecycle wall time (ms)",title="Mean across five generated-workload seeds; no inference calls")
    ax.legend()
    fig.savefig(root/"cumulative.svg")
    fig.savefig(root/"cumulative.png",dpi=150)
    plt.close(fig)
    print(json.dumps({k:{key:value for key,value in v.items() if key!="policies"} for k,v in analysis.items()},indent=2))


if __name__=="__main__": main()
