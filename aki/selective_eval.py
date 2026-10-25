"""Pinned ARB canonical quality scoring of an opt-in gate, without inference.

The identical official lexical ranker is evaluated with/without the gate. This
is quality-only; no lifecycle runtime comparison against upstream is claimed.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics
import subprocess
import sys
from .arb_eval import FileCache, read_jsonl
from .benchmark import metadata
from .selective import EvidenceGate
from .source import digest

PIN = "2c773139dd86003ec6defffa28bff1688c4af768"
HELDOUT_REPOS = {"fastapi/fastapi","huggingface/transformers","mockito/mockito",
                "spring-projects/spring-boot","vuejs/core"}


def run(args):
    if subprocess.check_output(["git","-C",str(args.upstream),"rev-parse","HEAD"],text=True).strip() != PIN:
        raise ValueError("upstream evaluator mismatch")
    sys.path.insert(0,str(args.upstream/"src"))
    from agent_retrieval_bench.baseline import (query_text_for_eval,query_has_leakage,target_gold_files,
        rank_chunks_for_ranker,unique_ranked_paths,reciprocal_rank,recall_at)
    from agent_retrieval_bench.repomap_eval import GENERIC_SYMBOLS
    from agent_retrieval_bench.bcy_curve import evaluate_sample
    args.out.mkdir(parents=True,exist_ok=False)
    provenance = metadata() | {"upstream_commit":PIN,"dataset_revision":"5901e1ee3aff048290db72edf9c63bc498b79ea3",
        "split":args.split,"gate":"explicit path or unique basename or unambiguous released symbol hint",
        "ranker":"official lexical","candidate_filter":"all_files","keep_list":None,
        "tokenizer":"regex_code_tokenizer_v1","quality_only":True,"sample_hashes":{},"manifest_hashes":{},
        "generic_symbols":sorted(GENERIC_SYMBOLS),"natural_negative_holdout":False,
        "symbol_warning":"released symbol metadata are heuristic hints, not verified semantic declarations"}
    subsets = ("v2_trace2code","v2_abstention") if args.split == "development" else ("v2_code2test",)
    groups,manifest = defaultdict(list),{}
    for subset in subsets:
        sf=args.data/"benchmark"/subset/"samples.jsonl"
        mf=args.data/"corpus"/subset/"corpus_manifest.jsonl"
        import hashlib
        provenance["sample_hashes"][subset]=hashlib.sha256(sf.read_bytes()).hexdigest()
        provenance["manifest_hashes"][subset]=hashlib.sha256(mf.read_bytes()).hexdigest()
        for sample in read_jsonl(sf):
            if args.split == "heldout" and sample["repo"] not in HELDOUT_REPOS: continue
            groups[sample["repo"],sample["base_commit"]].append(sample)
        for item in read_jsonl(mf):
            parts=Path(item["chunks_path"]).parts
            manifest[item["repo"],item["base_commit"]]=args.data.joinpath(*(parts[1:] if parts[0]=="data" else parts))
    output=[]
    with (args.out/"rankings.jsonl").open("w") as raw:
        for number,((repo,commit),samples) in enumerate(sorted(groups.items())):
            chunks=read_jsonl(manifest[repo,commit])
            docs={c["path"]:c.get("text","") for c in chunks if c.get("kind")=="file"}
            gate=EvidenceGate(chunks,GENERIC_SYMBOLS)
            for sample in samples:
                query=query_text_for_eval(sample)
                if query_has_leakage(sample,query): raise AssertionError("upstream leakage gate")
                decision=gate.check(query)
                ranked=unique_ranked_paths(rank_chunks_for_ranker(query,chunks,"lexical"))
                gold=target_gold_files(sample)  # evaluator only, after both retrieval decisions
                stratum="positive" if gold else "natural" if sample.get("metadata",{}).get("organic") else "counterfactual"
                language="python" if any(p.endswith(".py") for p in gold) else "other" if gold else "no_gold"
                for method,paths in (("lexical",ranked),("lexical_gate",ranked if decision["allowed"] else [])):
                    detail={"sample_id":sample["id"],"repo":repo,"base_commit":commit,"task_type":sample["task_type"],"top_files":paths[:20]}
                    bcy=evaluate_sample(detail,gold,FileCache(docs),(4000,8000,16000,32000)) if gold else None
                    row=detail | {"method":method,"stratum":stratum,"language":language,"query_sha256":digest(query),
                        "decision":decision,"abstained":not paths,"candidate_count":len(docs),"ranked_count":len(paths),
                        "MRR":reciprocal_rank(set(gold),paths) if gold else None,
                        "Recall@20":recall_at(set(gold),paths,20) if gold else None,
                        "BCY":{str(b):v["bcy"] for b,v in bcy["packed"].items()} if bcy else None}
                    output.append(row);raw.write(json.dumps(row,sort_keys=True)+"\n")
            print(json.dumps({"snapshot":number+1,"of":len(groups),"repo":repo}),flush=True)
    summaries={}
    for method in ("lexical","lexical_gate"):
        rows=[r for r in output if r["method"]==method]
        def metrics(group):
            return {"n":len(group),"MRR":statistics.mean(r["MRR"] for r in group),
                "Recall@20":statistics.mean(r["Recall@20"] for r in group),
                "BCY@8k":statistics.mean(r["BCY"]["8000"] for r in group),
                "abstention_rate":statistics.mean(r["abstained"] for r in group)} if group else {"n":0}
        pos=[r for r in rows if r["stratum"]=="positive"]
        summaries[method]=metrics(pos) | {"by_repo":{repo:metrics([r for r in pos if r["repo"]==repo]) for repo in sorted({r["repo"] for r in pos})},
            "by_language":{lang:metrics([r for r in pos if r["language"]==lang]) for lang in ("python","other")},
            "negative_abstention":{s:{"n":len(group),"rate":statistics.mean(r["abstained"] for r in group)}
                for s in ("natural","counterfactual") if (group:=[r for r in rows if r["stratum"]==s])}}
    (args.out/"summary.json").write_text(json.dumps(summaries,indent=2)+"\n")
    (args.out/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    print(json.dumps(summaries,indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--upstream",type=Path,required=True)
    p.add_argument("--data",type=Path,required=True)
    p.add_argument("--split",choices=("development","heldout"),required=True)
    p.add_argument("--out",type=Path,required=True)
    run(p.parse_args())
