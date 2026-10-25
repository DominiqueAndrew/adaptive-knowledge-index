"""Real source-history episodes with explicitly generated (not agent) queries."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import random
import subprocess
import tempfile
import time
from .benchmark import metadata,oracle
from .policy import Policy,POLICIES
from .source import is_test,parse,snapshot_id
from .store import Store,StaleRevision


def git(repo,*args):
    return subprocess.check_output(["git","-C",str(repo),*args],text=True)


def load_snapshot(repo,commit):
    files=git(repo,"ls-tree","-r","--name-only",commit).splitlines()
    return {p:git(repo,"show",f"{commit}:{p}") for p in files
            if p.endswith(".py") and not any(x.startswith(".") for x in Path(p).parts)}


def run(args):
    commits=list(reversed(git(args.repo,"rev-list","--first-parent",f"--max-count={args.snapshots}",args.ref).splitlines()))
    # No future snapshot enters a policy: these are harness/evaluator storage only.
    snapshots=[(c,load_snapshot(args.repo,c)) for c in commits]
    args.out.mkdir(parents=True,exist_ok=False)
    meta=metadata() | {"repo":"pallets/click", "license":"BSD-3-Clause", "commits":commits,
                      "source_manifests":[snapshot_id(d) for c,d in snapshots],
                      "workload":"generated random query sequence on real chronological source revisions",
                      "seeds":args.seeds,"queries_per_snapshot":args.count,"budget":args.budget,
                      "warning":"not observed agent tasks or repair-success evaluation"}
    (args.out/"provenance.json").write_text(json.dumps(meta,indent=2)+"\n")
    results=[]
    events=[]
    for seed in map(int,args.seeds.split(",")):
        rng=random.Random(seed)
        workloads=[]
        for commit,docs in snapshots:
            sources=sorted(p for p in docs if not is_test(p))
            queries=[(rng.choice(sources),rng.choice(("dependencies","tests","ripple")),rng.choice((1000,4000,8000))) for _ in range(args.count)]
            edges=parse(docs).edges
            gold=[oracle(docs,edges,r,k,"",b) for r,k,b in queries]
            workloads.append((queries,gold))
        conditions=[(name,mode) for name in POLICIES for mode in ("global","selective")]
        rng.shuffle(conditions)
        for name,mode in conditions:
            with tempfile.TemporaryDirectory(prefix="aki-history-") as temp:
                store=Store(Path(temp)/"db.sqlite","pallets/click")
                policy=Policy(store,name,args.budget)
                total_ns,stale,retained,invalidated=0,0,0,0
                for episode,((commit,docs),(queries,gold)) in enumerate(zip(snapshots,workloads)):
                    previous=store.revision
                    report=policy.refresh(docs,f"pallets/click@{commit}",mode)
                    total_ns+=report["total_refresh_ns"]
                    retained+=report["retained"]
                    invalidated+=report["invalidated"]
                    if previous and previous!=store.revision:
                        try: store.check(previous)
                        except StaleRevision: stale+=1
                        else: raise AssertionError("stale history accepted")
                    for i,(root,kind,budget) in enumerate(queries):
                        answer,event=policy.query(root,kind,store.revision,budget=budget)
                        if answer!=gold[i]: raise AssertionError((name,mode,commit,i))
                        total_ns+=event["total_ns"]
                        events.append(event | {"seed":seed,"policy":name,"mode":mode,"episode":episode,
                                               "query":i,"correct":True})
                row={"seed":seed,"policy":name,"mode":mode,"lifecycle_ms":total_ns/1e6,
                     "retained":retained,"invalidated":invalidated,"stale_rejections":stale,
                     "queries":args.count*len(commits),"parity":True,"peak_logical_bytes":policy.peak_bytes,
                     "storage":store.storage()}
                results.append(row)
                store.close()
                print(json.dumps(row),flush=True)
    with (args.out/"queries.jsonl").open("w") as f:
        for event in events: f.write(json.dumps(event,sort_keys=True)+"\n")
    (args.out/"summary.json").write_text(json.dumps(results,indent=2)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--repo",type=Path,required=True)
    p.add_argument("--ref",default="2247b35ea1c47c727d7a06e51fa280e12a863ff6")
    p.add_argument("--snapshots",type=int,default=8)
    p.add_argument("--seeds",default="20,21,22")
    p.add_argument("--count",type=int,default=120)
    p.add_argument("--budget",type=int,default=16384)
    p.add_argument("--out",type=Path,required=True)
    run(p.parse_args())
