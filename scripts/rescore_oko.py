#!/usr/bin/env python3
"""Offline rescore of a pinned third-party ranking on our exact trace2code subset."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--upstream",type=Path,required=True)
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--rankings",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    expected="c5a7f218fe1c1aead870acef2d8939da1884e0e4d30cec78f23cef41f05420cf"
    if hashlib.sha256(a.rankings.read_bytes()).hexdigest()!=expected: raise ValueError("ranking checksum mismatch")
    sys.path.insert(0,str(a.upstream/"src"))
    from agent_retrieval_bench.baseline import reciprocal_rank,recall_at,target_gold_files
    from agent_retrieval_bench.bcy_curve import CorpusFileCache,evaluate_sample
    def rows(path): return [json.loads(x) for x in path.read_text().splitlines() if x]
    samples={s["id"]:s for s in rows(a.data/"benchmark/v2_trace2code/samples.jsonl")}
    manifest={(r["repo"],r["base_commit"]):a.data/Path(r["chunks_path"]).relative_to("data")
              for r in rows(a.data/"corpus/v2_trace2code/corpus_manifest.jsonl")}
    cache=CorpusFileCache(manifest)
    result=[]
    for r in rows(a.rankings):
        if r["sample_id"] not in samples: continue
        s=samples[r["sample_id"]]
        gold=target_gold_files(s)
        ranked=r["ranked_files"]
        mrr=reciprocal_rank(set(gold),ranked)
        recall=recall_at(set(gold),ranked,20)
        if abs(mrr-r["metrics"]["MRR"])>1e-9 or abs(recall-r["metrics"]["Recall@20"])>1e-9:
            raise AssertionError("stored Oko metrics disagree")
        bcy=evaluate_sample(r,gold,cache,(4000,8000,16000,32000))
        result.append({"sample_id":r["sample_id"],"repo":s["repo"],"MRR":mrr,"Recall@20":recall,
                       "BCY":{str(b):v["bcy"] for b,v in bcy["packed"].items()}})
    assert len(result)==len(samples)==101
    summary={"source":"bartlomein/oko@9a8094edef23f0c3cb6d31ea511aa6597f430dfd",
             "ranking_sha256":expected,"method":"Oko 0.9.1 run 1 OFFLINE RESCORE ONLY",
             "not_reproduced":"retrieval runtime, API cost and ranking generation",
             "caveat":"nominal heldout samples were seen during Oko development regression checks",
             "samples":len(result),"MRR":statistics.mean(r["MRR"] for r in result),
             "Recall@20":statistics.mean(r["Recall@20"] for r in result),
             "BCY":{str(b):statistics.mean(r["BCY"][str(b)] for r in result) for b in (4000,8000,16000,32000)},
             "rows":result}
    a.out.write_text(json.dumps(summary,indent=2)+"\n")
    print({k:v for k,v in summary.items() if k!="rows"})


if __name__=="__main__": main()
