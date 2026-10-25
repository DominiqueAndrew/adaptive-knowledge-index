#!/usr/bin/env python3
"""Emit aggregates and opaque per-trajectory counts, never raw traces."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aki.trace_audit import audit_row, audit_shell_repeats, digest

p=argparse.ArgumentParser()
p.add_argument('--input',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
root=Path(__file__).resolve().parents[1]
summary={'sample_sha256': hashlib.sha256(a.input.read_bytes()).hexdigest(),
         'python':platform.python_version(),
         'code_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                        for name in ['aki/trace_audit.py','scripts/audit_agent_traces.py','scripts/fetch_trace_sample.py']},
         'explicit_action_timing_available':False,'per_action_source_tree_hash_available':False,
         'base_commit_in_trace_columns':False,'base_commit_available_in_separate_task_metadata':True,
         'interpretation':'Observed output reuse only; no cost or correctness guarantee.', 'conditions':{}}
for mode in ('all_shell_barriers','literal_read_screen'):
 rows=[]
 with a.input.open() as f:
  for line in f: rows.append(audit_row(json.loads(line), all_shell_barriers=mode=='all_shell_barriers'))
 counts=Counter(); functions=Counter(); boundaries=Counter()
 for row in rows:
  counts.update({k:v for k,v in row['counts'].items() if k!='peak_lru_bytes'})
  functions.update(row['functions']);boundaries.update(row['boundaries'])
 counts['max_lru_bytes']=max(r['counts'].get('peak_lru_bytes',0) for r in rows)
 summary['conditions'][mode]={'trajectories':len(rows),'repositories':len({r['repository_sha256'] for r in rows}), 'counts':dict(counts),'functions':dict(functions),'boundaries':dict(boundaries)}
 with (a.output/(mode+'.jsonl')).open('w') as f:
  for row in rows:f.write(json.dumps(row,sort_keys=True)+'\n')
shell_rows=[]; shell_counts=Counter()
with a.input.open() as f:
 for line in f:
  row=json.loads(line); c=audit_shell_repeats(row)
  shell_rows.append({'trajectory_sha256':digest(row['trajectory_id']),'counts':c})
  shell_counts.update({k:v for k,v in c.items() if k!='peak_lru_bytes'})
shell_counts['max_lru_bytes']=max(r['counts'].get('peak_lru_bytes',0) for r in shell_rows)
summary['literal_shell_exact_cache']={'counts':dict(shell_counts), 'budget_bytes':256*1024,
 'note':'Separate diagnostic cache from views; explicit absolute cd prefix required.'}
with (a.output/'shell_exact.jsonl').open('w') as f:
 for row in shell_rows:f.write(json.dumps(row,sort_keys=True)+'\n')
(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
