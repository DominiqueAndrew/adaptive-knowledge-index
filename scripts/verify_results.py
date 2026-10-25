#!/usr/bin/env python3
"""Independent raw-output accounting/parity audit (no engine imports)."""
from collections import defaultdict
import json
from pathlib import Path


def main():
    report={}
    for path in sorted(Path("results").iterdir()):
        if not path.is_dir() or not (path/"queries.jsonl").exists(): continue
        rows=[json.loads(x) for x in (path/"queries.jsonl").read_text().splitlines()]
        summary=json.loads((path/"summary.json").read_text())
        provenance=json.loads((path/"provenance.json").read_text())
        hashes=defaultdict(set)
        budget=provenance.get("logical_byte_budget",provenance.get("budget"))
        for row in rows:
            assert row["correct"]
            assert row["total_ns"]==row["retrieval_ns"]+row["optimizer_ns"]+row["build_ns"]
            if row["policy"]!="static_full": assert row["logical_bytes"]<=budget
            if "answer_sha256" in row: hashes[row["seed"],row["index"]].add(row["answer_sha256"])
        assert all(len(x)==1 for x in hashes.values())
        for s in summary:
            if "ingest_ms" not in s: continue
            measured=sum(r["total_ns"] for r in rows if r["policy"]==s["policy"] and r["seed"]==s["seed"])/1e6
            assert abs(measured-s["query_total_ms"])<1e-6
            expected=s["ingest_ms"]+s["static_build_ms"]+s["refresh_ms"]+measured
            assert abs(expected-s["lifecycle_ms"])<1e-6
        report[path.name]={"raw_queries":len(rows),"accounting":"passed","budget":"passed",
                           "cross_policy_answer_hashes":"passed" if hashes else "harness BFS assertions; no output hashes saved"}
    arb=[json.loads(x) for x in Path("results/arb-v1/rankings.jsonl").read_text().splitlines()]
    grouped=defaultdict(list)
    for r in arb:
        if r["method"].startswith("graph_"): grouped[r["sample_id"]].append(r["top_files"])
    assert len(grouped)==183
    assert all(len(v)==3 and v[0]==v[1]==v[2] for v in grouped.values())
    report["arb"]={"sample_rank_parity":183,"passed":True}
    Path("results/verification.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__": main()
