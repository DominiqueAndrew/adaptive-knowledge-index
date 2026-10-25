#!/usr/bin/env python3
"""Select a frozen cohort using metadata only; never load action/outcome columns."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import re
import pyarrow.parquet as pq
from replay_inputs import Budget, RemoteParquet

TRACE_REV='35455389ab51bf5e2306bfd436ef72d0f98bf882'
TASK_REV='89cdfbab4ab1bd8f5a658bb212d1b63624f4f881'
TRACE_URL=f'https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories/resolve/{TRACE_REV}/trajectories.parquet'
def order(salt,value):return hashlib.sha256((salt+value).encode()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--exposed',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
budget=Budget(a.inputs)
exposed={json.loads(line)['repo'] for line in a.exposed.open()}
tasks={};conflicts=set()
for name in ['data/filtered-00000-of-00001.parquet','data/test-00000-of-00002.parquet','data/test-00001-of-00002.parquet']:
 url=f'https://huggingface.co/datasets/nebius/SWE-rebench/resolve/{TASK_REV}/{name}'
 table=pq.ParquetFile(RemoteParquet(budget,url)).read(columns=['instance_id','repo','base_commit','environment_setup_commit','license_name'])
 for row in table.to_pylist():
  key=row['instance_id']
  if key in tasks and tasks[key]!=row:conflicts.add(key)
  tasks[key]=row
 budget.save()
traces=defaultdict(lambda:defaultdict(list))
pqfile=pq.ParquetFile(RemoteParquet(budget,TRACE_URL))
for group in range(pqfile.num_row_groups):
 table=pqfile.read_row_group(group,columns=['trajectory_id','instance_id','repo'])
 for index,row in enumerate(table.to_pylist()):
  task=tasks.get(row['instance_id'])
  if not task or row['instance_id'] in conflicts or task['repo']!=row['repo']:continue
  if not re.match(r'^(MIT|Apache|BSD|ISC|Mozilla)',task.get('license_name') or '',re.I):continue
  if not re.fullmatch('[a-f0-9]{40}',task['base_commit']):continue
  traces[row['repo']][row['instance_id']].append({**row,'row_group':group,'row_index':index})
 budget.save()
eligible=sorted([repo for repo,v in traces.items() if len(v)>=4],key=lambda s:order('aki-phase4-repo:',s))
cohort=[]
for split in ['development','evaluation']:
 repos=[r for r in eligible if (r in exposed)==(split=='development')][:3]
 if len(repos)!=3:raise ValueError(f'not enough eligible {split} repositories')
 for repo in repos:
  for task_id in sorted(traces[repo],key=lambda s:order('aki-phase4-task:',s))[:4]:
   selected=min(traces[repo][task_id],key=lambda r:order('aki-phase4-traj:',r['trajectory_id']))
   cohort.append({**selected,**tasks[task_id],'split':split})
result={'trace_revision':TRACE_REV,'task_revision':TASK_REV,'exposed_repository_count':len(exposed),'eligible_repository_count':len(eligible),'ambiguous_task_metadata_excluded':len(conflicts),'cohort':cohort}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');budget.save()
print(json.dumps({'eligible_repositories':len(eligible),'cohort':{s:sorted({r['repo'] for r in cohort if r['split']==s}) for s in ['development','evaluation']},'downloaded_bytes':budget.state['downloaded_bytes']}))
