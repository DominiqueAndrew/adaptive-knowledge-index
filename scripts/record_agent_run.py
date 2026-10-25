#!/usr/bin/env python3
"""Opt-in bridge for an explicitly reviewed adapter in an approved executor.

Not an agent/scaffold implementation. Never discovers sessions or credentials.
An adapter module must expose run(recorder, config); it must wrap every source
operation, provide executor metrics, and enforce its model/tool budget itself.
"""
import argparse,importlib,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from aki.recorder import Recorder,verify
p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--adapter',required=True);p.add_argument('--allow-reviewed-adapter',action='store_true');a=p.parse_args()
if not a.allow_reviewed_adapter:raise SystemExit('Explicit reviewed-adapter opt-in required; run only in the approved isolated executor.')
c=json.loads(a.config.read_text())
if c.get('allow_collection') is not True or c.get('source_kind')!='public_repository':raise SystemExit('Explicit public-source enrollment required.')
start=time.perf_counter_ns()
r=Recorder(root=Path(c['root']),scopes=c['scopes'],output=Path(c['output']),allow_collection=True,
           source_kind=c['source_kind'],repository=c.get('repository'),declared_revision=c.get('declared_revision'),
           store_source_blobs=c.get('store_source_blobs',False),store_tool_requests=c.get('store_tool_requests',False))
try:importlib.import_module(a.adapter).run(r,c)
finally:metrics=r.close()
print(json.dumps({'session_total_wall_ns':time.perf_counter_ns()-start,'recorder_metrics':metrics,'verification':verify(Path(c['output']))}))
