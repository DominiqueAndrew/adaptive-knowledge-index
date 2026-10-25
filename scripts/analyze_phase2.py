#!/usr/bin/env python3
"""Independent raw accounting/parity checks and descriptive paired comparisons."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics


def analyze(root):
    summary=json.loads((root/"summary.json").read_text())
    totals=defaultdict(lambda:defaultdict(int))
    hashes={}
    curves=defaultdict(list)
    refresh_costs=defaultdict(int)
    time_series=defaultdict(dict)
    query_count=request_count=0
    for line in (root/"refreshes.jsonl").open():
        r=json.loads(line); key=(r["seed"],tuple(r["condition"]))
        totals[key]["refresh_ns"]+=r["report"]["total_refresh_ns"]
        totals[key]["acquisition_ns"]+=r["acquisition_ns"]
        refresh_costs[key,r["query"]]+=r["report"]["total_refresh_ns"]+r["acquisition_ns"]
    for line in (root/"queries.jsonl").open():
        r=json.loads(line); key=(r["seed"],tuple(r["condition"]))
        pair=(r["seed"],r["query"])
        assert r["correct"]
        if pair in hashes: assert hashes[pair]==r["answer_hash"], pair
        hashes[pair]=r["answer_hash"]
        totals[key]["query_ns"]+=r["total_ns"]
        curves[key].append(r["total_ns"])
        time_series[key][r["query"]]=r["total_ns"]+refresh_costs[key,r["query"]]
        query_count+=1;request_count+=len(r["costs"])
    grouped=defaultdict(list)
    for row in summary:
        key=(row["seed"],tuple(row["condition"]))
        for field in ("query_ns","refresh_ns","acquisition_ns"):
            assert row[field]==totals[key][field], (key,field)
        assert row["lifecycle_ns"]==sum(row[k] for k in ("setup_ns","query_ns","refresh_ns","acquisition_ns"))
        if row["condition"][0]!="static_full":
            assert row["peak_logical_bytes"]<=json.loads((root/"provenance.json").read_text())["budget"]
        grouped[tuple(row["condition"])].append(row)
        time_series[key][0]+=row["setup_ns"]
    means={":".join(map(str,k)):{field:statistics.mean(r[field] for r in rows)
        for field in ("lifecycle_ns","service_excluding_acquisition_ns","setup_ns","acquisition_ns","refresh_ns",
                      "query_ns","base_ns","build_ns","optimizer_ns","p50_ns","p95_ns","requests","hits","builds","evictions","noop","retained","invalidated")}
           for k,rows in grouped.items()}
    ratios=[]
    for k,rows in grouped.items():
        name,base,mode,batch=k
        if base=="incremental" and (name,"full",mode,batch) in grouped:
            controls={r["seed"]:r for r in grouped[name,"full",mode,batch]}
            values=[r["lifecycle_ns"]/controls[r["seed"]]["lifecycle_ns"] for r in rows]
            ratios.append({"comparison":"incremental/full","policy":name,"invalidation":mode,
                "mean_ratio":statistics.mean(values),"paired_ratios":values})
    candidates=[k for k in grouped if k[1:]==("incremental","selective",True) and k[0] in ("lru","frequency","gds")]
    strongest=min(candidates,key=lambda k:statistics.mean(r["lifecycle_ns"] for r in grouped[k])) if candidates else None
    admission={}
    if strongest:
        controls={r["seed"]:r for r in grouped[strongest]}
        ratios_aki=[r["lifecycle_ns"]/controls[r["seed"]]["lifecycle_ns"] for r in grouped["aki","incremental","selective",True]]
        admission={"strongest_simple":strongest[0],"aki_over_simple_paired_ratios":ratios_aki,
            "aki_over_simple_mean_ratio":statistics.mean(ratios_aki),"criterion_20pct_met":statistics.mean(ratios_aki)<=.8}
    disabled=grouped.get(("disabled","incremental","selective",True),[])
    opportunity={"impossible_free_all_traversal_service_fraction":statistics.mean(r["base_ns"]/r["lifecycle_ns"] for r in disabled),
        "warning":"diagnostic upper bound; includes non-repeating operations and assumes zero cache overhead"} if disabled else {}
    temporal=[]
    for key,series in time_series.items():
        seed,condition=key
        disabled_key=(seed,("disabled",condition[1],condition[2],condition[3]))
        reference=time_series[disabled_key]
        cumulative=baseline=0
        differences=[]
        for i in sorted(series):
            cumulative+=series[i];baseline+=reference[i]
            differences.append(cumulative-baseline)
        # Sustained crossover: a prefix improvement followed by a later regression
        # is not called break-even. None if the condition never stays ahead.
        last_loss=max((i for i,x in enumerate(differences) if x>0),default=-1)
        break_even=last_loss+2 if last_loss<len(differences)-1 and any(x<0 for x in differences) else None
        latencies=sorted(series.values())
        temporal.append({"seed":seed,"condition":condition,"sustained_break_even_query_vs_disabled":break_even,
            "end_to_end_p50_ns":latencies[int((len(latencies)-1)*.5)],
            "end_to_end_p95_ns":latencies[int((len(latencies)-1)*.95)],
            "final_cumulative_delta_ns":differences[-1]})
    return {"directory":root.name,"checked_query_rows":query_count,"checked_operator_rows":request_count,
        "checked_unique_answers":len(hashes),"raw_accounting_and_answer_parity":True,"means":means,
        "maintenance_comparisons":ratios,"admission":admission,"opportunity":opportunity,
        "temporal":temporal,
        "uncertainty":"paired repetitions and ratios are descriptive; shared host and few repositories limit inference"}


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("directories",nargs="+",type=Path);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();result=[analyze(root) for root in a.directories]
    a.out.write_text(json.dumps(result,indent=2)+"\n")
    for r in result: print(json.dumps({k:v for k,v in r.items() if k not in ("means","maintenance_comparisons","temporal")}))
