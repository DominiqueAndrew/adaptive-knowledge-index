#!/usr/bin/env python3
import argparse
from collections import Counter
import hashlib,json
from pathlib import Path
import platform,sys,shlex
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aki.replay import reconstruct
from replay_inputs import Budget
p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
budget=Budget(a.inputs);cohort=json.loads(a.cohort.read_text());sources={r['instance_id']:r for r in json.loads((a.inputs/'source_records.json').read_text())}
roots=json.loads((a.inputs/'source_roots.json').read_text())
rows=[]
for r in cohort['cohort']:
 if r['split']!='development':continue
 source=sources[r['instance_id']]
 if not source['success']:
  rows.append({'instance_id':r['instance_id'],'qualifies':False,'stop':{'reason':'source_acquisition_failure'},'events':[]});continue
 root=a.inputs/'trees'/(r['repo'].replace('/','__')+'--'+r['base_commit'])
 trace=json.loads((a.inputs/'development'/(r['instance_id']+'.json')).read_text())
 manifest=json.loads((root/'_aki_manifest.json').read_text())
 result=reconstruct(trace,root,manifest,roots[r['instance_id']]['root'])
 if result['stop'] and result['stop']['reason']=='opaque_shell_state_transition':
  call=trace['trajectory'][result['stop']['message_index']]['tool_calls'][0]
  args=json.loads(call['function']['arguments']);tokens=shlex.split(args.get('command',''))
  if 'python' in tokens:
   following=tokens[tokens.index('python')+1:]
   kind='python_setup_script' if following and following[0]=='setup.py' else 'python_module_'+following[1] if len(following)>1 and following[0]=='-m' and following[1] in ('pip','pytest') else 'other_python_execution'
  elif 'pip' in tokens:kind='pip_execution'
  else:kind='other_opaque_shell'
  result['stop']['operation_class']=kind
 rows.append({'instance_id':r['instance_id'],'repo':r['repo'],'base_commit':r['base_commit'],'setup_commit_differs':r['base_commit']!=r['environment_setup_commit'],'source_acquisition_ns':source['acquisition_ns'],'source_unpack_hash_ns':source['unpack_hash_ns'],**result})
 budget.save()
summary={'development_tasks':len(rows),'qualifying_tasks':sum(r['qualifies'] for r in rows),'required_qualifying_tasks':8,
         'matched_views':sum(r.get('counts',{}).get('matched_views',0) for r in rows),'mismatched_views':sum(not e['matched'] for r in rows for e in r['events']),
         'stop_reasons':dict(Counter(r['stop']['reason'] if r['stop'] else 'completed' for r in rows)),
         'evaluation_actions_inspected':False,'python':platform.python_version(),
         'timing_scope':'Local UTF8 source read/hash/decode/view selection only; original tool latency and skipped shell work unavailable.',
         'code_sha256':{f:hashlib.sha256(Path(f).read_bytes()).hexdigest() for f in ['aki/replay.py','scripts/reconstruct_development.py']}}
summary['reconstruction_gate_passed']=summary['qualifying_tasks']>=8 and summary['mismatched_views']==0
summary['timed_view_wall_ns']=sum(e['wall_ns'] for r in rows for e in r['events'] if e['matched'])
summary['timed_view_cpu_ns']=sum(e['cpu_ns'] for r in rows for e in r['events'] if e['matched'])
summary['stop_operations']=dict(Counter(r['stop'].get('operation_class','other') for r in rows if r['stop']))
summary['repeated_valid_view_signatures']=sum(len(r['events'])-len({(e['tree_sha256'],e['view_signature_sha256']) for e in r['events']}) for r in rows)
a.output.mkdir(parents=True,exist_ok=True)
(a.output/'development.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');budget.save()
print(json.dumps(summary,indent=2))
