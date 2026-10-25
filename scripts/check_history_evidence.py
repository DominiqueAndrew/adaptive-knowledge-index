#!/usr/bin/env python3
"""Untimed real-history source/evidence audit, independent of benchmark summaries."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aki.paired import archive_snapshot
from aki.source import digest,parse,source_lines,snapshot_id
from aki.store import Store,StaleRevision


def run(args):
    provenance=json.loads((args.run/"provenance.json").read_text())
    s=Store(":memory:",provenance["label"],"incremental")
    records=[]
    for task in provenance["tasks"]:
        docs,_=archive_snapshot(args.repo,task["parent_commit"])
        previous=s.revision
        report=s.refresh(docs,task["parent_commit"],"selective")
        assert s.revision==snapshot_id(docs)
        fresh=parse(docs)
        assert set(s.db.execute("SELECT src,dst FROM edges"))==fresh.edges
        expected={}
        for path,text in docs.items():
            lines=source_lines(text)
            for start in range(0,len(lines),80):
                expected[path,start+1]=(min(start+80,len(lines)),"".join(lines[start:start+80]))
        observed={}
        for path,start,end,sha,text in s.db.execute("SELECT a.path,s.start,s.end,s.hash,s.text FROM active_spans a JOIN spans s ON a.span_id=s.id"):
            assert sha==digest(text)
            observed[path,start]=(end,text)
        assert observed==expected
        evidence=set()
        for src,dst in fresh.edges:
            rows=s.edge_evidence(src,dst,s.revision)
            assert rows
            for e in rows:
                assert e["path"]==src
                assert e["start"]<=e["line"]<=e["end"]
                assert (e["end"],e["text"])==expected[src,e["start"]]
                assert e["sha256"]==digest(e["text"])
                assert e["current_revision"]==s.revision
                evidence.add((src,dst,e["line"]))
        assert evidence==set(fresh.evidence)
        if previous and previous!=s.revision:
            try:s.edge_evidence("unused","unused",previous)
            except StaleRevision:pass
            else:raise AssertionError("stale evidence revision accepted")
        records.append({"source_commit":task["parent_commit"],"source_revision":s.revision,
            "files":len(docs),"active_spans_checked":len(observed),"edges_checked":len(fresh.edges),
            "evidence_links_checked":len(evidence),"noop":report["noop"],"parse_errors":len(fresh.errors)})
    s.close()
    args.out.write_text(json.dumps({"run":args.run.name,"passed":True,"snapshots":records,
        "limitations":"extractor equivalence and exact source membership, not semantic sufficiency or exhaustive dependency truth"},indent=2)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--run",type=Path,required=True)
    p.add_argument("--repo",type=Path,required=True);p.add_argument("--out",type=Path,required=True);run(p.parse_args())
