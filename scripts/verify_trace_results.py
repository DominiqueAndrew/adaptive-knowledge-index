#!/usr/bin/env python3
"""Independent published-record accounting, without downloading raw traces."""
from collections import Counter
import hashlib
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'results/phase3'
summary=json.loads((p/'summary.json').read_text())
source=json.loads((p/'source_manifest.json').read_text())
assert source['sample_sha256']==summary['sample_sha256']
assert source['transfer_bytes']<=150*1024**2
checked=0
for condition in ('all_shell_barriers','literal_read_screen','shell_exact'):
 rows=[json.loads(line) for line in (p/(condition+'.jsonl')).open()]
 assert len(rows)==128 and len({r['trajectory_sha256'] for r in rows})==128
 counts=Counter()
 for row in rows:
  c=row['counts']
  assert c.get('peak_lru_bytes',0)<=256*1024
  assert c.get('lru_equal_hits',0)<=c.get('exact_equal_hits',0)
  assert c.get('equal_overlap_line_bytes',0)<=c.get('numbered_line_bytes',0)
  assert c.get('beyond_exact_overlap_line_bytes',0)<=c.get('equal_overlap_line_bytes',0)
  counts.update({k:v for k,v in c.items() if k!='peak_lru_bytes'})
 counts['max_lru_bytes']=max(r['counts'].get('peak_lru_bytes',0) for r in rows)
 expected=summary['literal_shell_exact_cache']['counts'] if condition=='shell_exact' else summary['conditions'][condition]['counts']
 assert dict(counts)==expected,condition
 checked+=len(rows)
for name,value in summary['code_sha256'].items():
 assert hashlib.sha256((root/name).read_bytes()).hexdigest()==value,name
print(json.dumps({'passed':True,'trajectory_condition_records':checked,'source_hash_matches':True}))
