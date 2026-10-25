#!/usr/bin/env python3
"""Independent verification of published replay counts, hashes and stop gate."""
from collections import Counter
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];p=root/'results/phase4'
cohort=json.loads((p/'cohort.json').read_text())['cohort'];s=json.loads((p/'summary.json').read_text());r=json.loads((p/'resource_provenance.json').read_text())
rows=[json.loads(x) for x in (p/'development.jsonl').open()]
dev={c['instance_id'] for c in cohort if c['split']=='development'};held={c['instance_id'] for c in cohort if c['split']=='evaluation'}
assert len(dev)==len(held)==12 and dev.isdisjoint(held)
assert {x['repo'] for x in cohort if x['split']=='development'}.isdisjoint({x['repo'] for x in cohort if x['split']=='evaluation'})
assert {x['instance_id'] for x in rows}==dev
assert s['qualifying_tasks']==sum(x['qualifies'] for x in rows)==0
assert s['matched_views']==sum(e['matched'] for x in rows for e in x['events'])==21
assert s['mismatched_views']==0
for row in rows:
 for e in row['events']:
  assert e['output_sha256']==e['observed_output_sha256']
  assert e['wall_ns']>=0 and e['cpu_ns']>=0
assert s['timed_view_wall_ns']==sum(e['wall_ns'] for x in rows for e in x['events'])
assert s['timed_view_cpu_ns']==sum(e['cpu_ns'] for x in rows for e in x['events'])
assert not s['reconstruction_gate_passed'] and not s['evaluation_actions_inspected']
assert r['evaluation_action_objects_created']==0
assert r['downloaded_bytes']<=r['limits']['download_bytes'] and r['cpu_seconds']<=r['limits']['cpu_seconds']
assert sum(q['bytes'] for q in r['requests'])==r['measured_script_download_bytes']
assert r['measured_script_download_bytes']+r['source_review_allowance_bytes']==r['downloaded_bytes']
assert r['measured_script_cpu_seconds']+r['validation_cpu_allowance_seconds']==r['cpu_seconds']
for name,value in s['code_sha256'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==value,name
print(json.dumps({'passed':True,'development_tasks':len(rows),'evidence_comparisons':21,'held_out_actions_inspected':False,'resource_caps_passed':True}))
