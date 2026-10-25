#!/usr/bin/env python3
"""Join version metadata to declared OpenHands workspace names; no action search."""
import argparse,json
from pathlib import Path
import pyarrow.parquet as pq
from replay_inputs import Budget,RemoteParquet
p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);a=p.parse_args()
b=Budget(a.inputs);cohort=json.loads(a.cohort.read_text());selected={r['instance_id']:r for r in cohort['cohort'] if r['split']=='development'};roots={}
for name in ['data/filtered-00000-of-00001.parquet','data/test-00000-of-00002.parquet','data/test-00001-of-00002.parquet']:
 url=f'https://huggingface.co/datasets/nebius/SWE-rebench/resolve/{cohort["task_revision"]}/{name}'
 for row in pq.ParquetFile(RemoteParquet(b,url)).read(columns=['instance_id','version']).to_pylist():
  if row['instance_id'] in selected:
   task=selected[row['instance_id']];version=str(row['version'])
   if '/' in version or '..' in version:raise ValueError('unsafe version')
   roots[row['instance_id']]={'version':version,'root':'/workspace/'+task['repo'].replace('/','__')+'__'+version}
b.save();(a.inputs/'source_roots.json').write_text(json.dumps(roots,indent=2)+'\n');print('Joined roots for',len(roots),'development tasks')
