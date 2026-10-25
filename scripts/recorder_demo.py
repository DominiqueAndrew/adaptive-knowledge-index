#!/usr/bin/env python3
"""Original synthetic fixture only. Instrumentation test, never agent evaluation."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aki.recorder import Recorder,verify
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
root=a.output/'fixture';root.mkdir();(root/'src').mkdir();(root/'tests').mkdir()
(root/'src'/'example.py').write_text('def answer():\n    return 1\n')
(root/'tests'/'test_example.py').write_text('# Original instrumentation fixture; no third-party code.\n')
start=time.perf_counter_ns()
r=Recorder(root=root,scopes=['src','tests'],output=a.output/'capture',allow_collection=True,source_kind='synthetic_fixture',store_source_blobs=True,store_tool_requests=True)
try:
 with r.operation('source_read',b'{"path":"src/example.py"}') as op:
  op.output((root/'src'/'example.py').read_bytes())
 with r.operation('source_edit',b'{"fixture_change":2}') as op:
  (root/'src'/'example.py').write_text('def answer():\n    return 2\n');op.output(b'changed')
 with r.operation('source_edit',b'{"add_fixture":true}') as op:
  (root/'src'/'new.py').write_text('VALUE = 3\n');op.output(b'created')
 with r.operation('source_edit',b'{"delete_fixture":true}') as op:
  (root/'src'/'new.py').unlink();op.output(b'deleted')
 with r.operation('source_read',b'{"path":"src/example.py"}') as op:
  op.output((root/'src'/'example.py').read_bytes())
finally:metrics=r.close()
summary={'purpose':'project-owned synthetic instrumentation test, not agent evaluation',
         'session_total_wall_ns':time.perf_counter_ns()-start,'recorder_metrics':metrics,
         'verification':verify(a.output/'capture')}
(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
