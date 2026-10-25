#!/usr/bin/env python3
"""Publication-sized figures from raw measured phase-two data (optional matplotlib)."""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import statistics
os.environ.setdefault("MPLCONFIGDIR",str(Path(".cache/matplotlib").resolve()))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=Path("results/phase2"));a=p.parse_args()
    root=a.root;output=root/"figures";output.mkdir(exist_ok=True)
    analysis={r["directory"]:r for r in json.loads((root/"analysis.json").read_text())}
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    fig,ax=plt.subplots(figsize=(8,4.6),layout="constrained")
    labels,acq,refresh,query=[],[],[],[]
    for repo in ("click","pytest","flask"):
        for base in ("full","incremental"):
            row=analysis[repo]["means"][f"disabled:{base}:selective:True"]
            labels.append(repo+"\n"+base);acq.append(row["acquisition_ns"]/1e9)
            refresh.append(row["refresh_ns"]/1e9);query.append((row["query_ns"]+row["setup_ns"])/1e9)
    xs=list(range(len(labels)))
    ax.bar(xs,acq,label="Source acquisition (equally charged)",color="#9ab7cc")
    ax.bar(xs,refresh,bottom=acq,label="Hash, parse, update, invalidation",color="#2c618b")
    ax.bar(xs,query,bottom=[x+y for x,y in zip(acq,refresh)],label="Setup and task queries",color="#d18b35")
    ax.set_xticks(xs,labels);ax.set_ylabel("Complete service cost, seconds (mean of 3 repetitions)")
    ax.set_title("Incremental source maintenance: all policies share the optimization\n30 commit-title tasks per repository; identical no-op fast path")
    ax.legend(fontsize=8);fig.savefig(output/"maintenance.png",dpi=180);fig.savefig(output/"maintenance.svg");plt.close(fig)

    fig,axes=plt.subplots(1,2,figsize=(10,4),layout="constrained")
    for axis,dataset,title in zip(axes,("synthetic","flask"),("Synthetic locality (800 generated queries)","Flask (30 real commit-title tasks)")):
        rows=json.loads((root/dataset/"summary.json").read_text())
        selected=[r for r in rows if r["condition"][1:]==["incremental","selective",True]]
        disabled={r["seed"]:r["lifecycle_ns"] for r in selected if r["condition"][0]=="disabled"}
        names=("disabled","lru","frequency","gds","aki")
        values=[[r["lifecycle_ns"]/disabled[r["seed"]] for r in selected if r["condition"][0]==name] for name in names]
        means=[statistics.mean(v) for v in values]
        axis.bar(names,means,color=["#9ab7cc"]*4+["#d18b35"])
        axis.errorbar(range(len(names)),means,yerr=[[m-min(v) for m,v in zip(means,values)],[max(v)-m for m,v in zip(means,values)]],fmt="none",color="black",capsize=3)
        axis.axhline(1,color="grey",linestyle="--",linewidth=1);axis.set_title(title);axis.tick_params(axis="x",rotation=30)
        axis.set_ylabel("Lifecycle cost / disabled")
    fig.supxlabel("Bars: paired mean ratio. Whiskers: range across three seeds/repetitions.",fontsize=9)
    fig.savefig(output/"policy_comparison.png",dpi=180);fig.savefig(output/"policy_comparison.svg");plt.close(fig)

    folder=root/"synthetic";costs=defaultdict(lambda:defaultdict(int))
    for line in (folder/"refreshes.jsonl").open():
        row=json.loads(line);key=(row["seed"],tuple(row["condition"]))
        costs[key][row["query"]]+=row["report"]["total_refresh_ns"]+row["acquisition_ns"]
    for line in (folder/"queries.jsonl").open():
        row=json.loads(line);costs[row["seed"],tuple(row["condition"])][row["query"]]+=row["total_ns"]
    for row in json.loads((folder/"summary.json").read_text()):
        costs[row["seed"],tuple(row["condition"])][0]+=row["setup_ns"]
    fig,ax=plt.subplots(figsize=(8,4.3),layout="constrained")
    for name in ("disabled","lru","frequency","gds","aki"):
        runs=[]
        for (seed,condition),series in costs.items():
            if condition!=(name,"incremental","selective",True):continue
            running=0;curve=[]
            for i in sorted(series):running+=series[i]/1e6;curve.append(running)
            runs.append(curve)
        mean=[statistics.mean(v) for v in zip(*runs)]
        ax.plot(range(1,len(mean)+1),mean,label=name)
    ax.set_xlabel("Generated query number");ax.set_ylabel("Cumulative service milliseconds, mean of 3 seeds")
    ax.set_title("Synthetic lifecycle includes initialization, writes and mutation refresh")
    ax.legend(ncol=5);fig.savefig(output/"synthetic_cumulative.png",dpi=180);fig.savefig(output/"synthetic_cumulative.svg")


if __name__=="__main__":main()
