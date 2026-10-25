#!/usr/bin/env python3
"""Recompute derived break-even fields from unchanged raw costs.

Paired subtraction avoids floating-point cancellation that could classify a
disabled-vs-itself equality as a tiny negative. Does not rerun measurements.
"""
import json
from pathlib import Path

for directory in sorted(Path("results").iterdir()):
    if not directory.is_dir() or not (directory/"queries.jsonl").exists(): continue
    summaries=json.loads((directory/"summary.json").read_text())
    if not summaries or "ingest_ms" not in summaries[0]: continue
    rows=[json.loads(x) for x in (directory/"queries.jsonl").read_text().splitlines()]
    by_run={}
    for row in rows: by_run.setdefault((row["seed"],row["policy"]),[]).append(row)
    for summary in summaries:
        base=next(s for s in summaries if s["seed"]==summary["seed"] and s["policy"]=="disabled")
        delta=(summary["ingest_ms"]-base["ingest_ms"])+(summary["static_build_ms"]-base["static_build_ms"])
        own=by_run[summary["seed"],summary["policy"]]
        ref=by_run[summary["seed"],"disabled"]
        differences=[]
        for i,(a,b) in enumerate(zip(own,ref)):
            if a["phase"]=="post_mutation" and (i==0 or own[i-1]["phase"]!="post_mutation"):
                delta+=summary["refresh_ms"]-base["refresh_ms"]
            delta+=(a["total_ns"]-b["total_ns"])/1e6
            differences.append(delta)
        summary["first_break_even_query"]=next((i+1 for i,d in enumerate(differences) if d<0),None)
        summary["sustained_break_even_query"]=next((i+1 for i in range(len(differences)) if max(differences[i:])<0),None)
        if summary["policy"]=="disabled": assert all(x==0 for x in differences)
    (directory/"summary.json").write_text(json.dumps(summaries,indent=2)+"\n")
    print(directory.name,"derived break-even recalculated")
