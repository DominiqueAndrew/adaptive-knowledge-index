#!/usr/bin/env python3
"""Cross-check adapter against the unmodified upstream lexical evaluation entrypoint."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

p=argparse.ArgumentParser()
p.add_argument("--upstream",type=Path,required=True)
p.add_argument("--data",type=Path,required=True)
p.add_argument("--results",type=Path,default=Path("results/arb-v1"))
a=p.parse_args()
sys.path.insert(0,str(a.upstream/"src"))
from agent_retrieval_bench.baseline import evaluate_lexical_baseline
with tempfile.TemporaryDirectory(prefix="aki-official-crosscheck-") as tmp:
    root=Path(tmp)
    manifest=[]
    for line in (a.data/"corpus/v2_trace2code/corpus_manifest.jsonl").read_text().splitlines():
        r=json.loads(line)
        r["chunks_path"]=str((a.data/Path(r["chunks_path"]).relative_to("data")).resolve())
        manifest.append(r)
    (root/"corpus_manifest.jsonl").write_text("".join(json.dumps(r)+"\n" for r in manifest))
    result=evaluate_lexical_baseline([a.data/"benchmark/v2_trace2code/samples.jsonl"],root,
                                   details_path=root/"details.jsonl",candidate_filter="all_files")
    official={r["sample_id"]:r for r in map(json.loads,(root/"details.jsonl").read_text().splitlines())}
    ours=[r for r in map(json.loads,(a.results/"rankings.jsonl").read_text().splitlines())
          if r["method"]=="lexical" and r["stratum"]=="positive"]
    assert len(official)==len(ours)==101
    for r in ours:
        ref=official[r["sample_id"]]
        assert r["top_files"]==ref["top_files"]
        assert abs(r["MRR"]-ref["metrics"]["MRR"])<1e-12
        assert abs(r["Recall@20"]-ref["metrics"]["Recall@20"])<1e-12
    output={"unmodified_official_entrypoint":"evaluate_lexical_baseline",
            "samples":101,"identical_top20":101,"MRR_and_Recall20":"identical",
            "skipped":result["skipped"],"passed":True}
    (a.results/"official_crosscheck.json").write_text(json.dumps(output,indent=2)+"\n")
    print(output)
