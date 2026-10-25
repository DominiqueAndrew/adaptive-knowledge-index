#!/usr/bin/env python3
"""Diagnostic free/unlimited cache upper bound, never an achievable policy result.

Replays only disabled-policy operations. Independent adjacency BFS reconstructs
closures; edge-boundary changes invalidate old cached path sets. All cache writes,
validation, reads and space are optimistically free. Actual measured traversal
time on valid repeats is the most this idealized demand cache could avoid.
"""
import argparse
from collections import defaultdict, deque
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aki.benchmark import synthetic,mutate
from aki.paired import archive_snapshot
from aki.source import parse,snapshot_id


def closure(edges,root,direction):
    adjacency=defaultdict(set)
    for a,b in edges:
        if direction=="reverse":a,b=b,a
        adjacency[a].add(b)
    seen={root};q=deque([root])
    while q:
        for p in adjacency[q.popleft()]-seen:seen.add(p);q.append(p)
    seen.discard(root)
    return seen


def run(args):
    provenance=json.loads((args.run/"provenance.json").read_text())
    summary=json.loads((args.run/"summary.json").read_text())
    selected={r["seed"]:r for r in summary if r["condition"]==["disabled","incremental","selective",True]}
    snapshots={};by_query={}
    if args.repo:
        for index,task in enumerate(provenance["tasks"]):
            docs,_=archive_snapshot(args.repo,task["parent_commit"])
            revision=snapshot_id(docs);by_query[index]=revision
            if revision not in snapshots:snapshots[revision]=(set(docs),parse(docs).edges)
    else:
        initial=synthetic(500)
        for docs in (initial,mutate(initial)):
            snapshots[snapshot_id(docs)]=(set(docs),parse(docs).edges)
    states={seed:{"revision":None,"files":set(),"edges":set(),"cache":{},"requests":0,"valid_repeats":0,
                  "repeated_traversal_ns":0,"all_traversal_ns":0} for seed in selected}
    for line in (args.run/"queries.jsonl").open():
        event=json.loads(line)
        if event["condition"]!=["disabled","incremental","selective",True]:continue
        state=states[event["seed"]];revision=event["source_revision"]
        files,edges=snapshots[revision]
        if state["revision"]!=revision:
            delta=state["edges"].symmetric_difference(edges)
            removed=state["files"]-files
            changed={"forward":{a for a,b in delta},"reverse":{b for a,b in delta}}
            state["cache"]={key:rows for key,rows in state["cache"].items()
                if not (rows|{key[0]}).intersection(changed[key[1]]|removed)}
            state.update(revision=revision,files=files,edges=edges)
        for (root,kind,budget),cost in zip(event["operations"],event["costs"]):
            direction="forward" if kind=="dependencies" else "reverse"
            key=(root,direction);rows=closure(edges,root,direction)
            state["requests"]+=1;state["all_traversal_ns"]+=cost["base_ns"]
            if key in state["cache"]:
                assert state["cache"][key]==rows, "invalid diagnostic retention"
                state["valid_repeats"]+=1;state["repeated_traversal_ns"]+=cost["base_ns"]
            state["cache"][key]=rows
    result=[]
    for seed,state in states.items():
        row={k:v for k,v in state.items() if k not in ("cache","files","edges","revision")}
        row.update(seed=seed,lifecycle_ns=selected[seed]["lifecycle_ns"],
            free_valid_repeat_fraction=row["repeated_traversal_ns"]/selected[seed]["lifecycle_ns"],
            free_all_traversal_fraction=row["all_traversal_ns"]/selected[seed]["lifecycle_ns"])
        result.append(row)
    args.out.write_text(json.dumps({"run":args.run.name,"upper_bound_only":True,
        "assumptions":"unlimited cache, free admission/write/read/validation, no size or invalidation overhead", "seeds":result},indent=2)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--run",type=Path,required=True);p.add_argument("--repo",type=Path)
    p.add_argument("--out",type=Path,required=True);run(p.parse_args())
