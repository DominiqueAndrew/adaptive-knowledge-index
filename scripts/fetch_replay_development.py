#!/usr/bin/env python3
"""Fetch frozen development rows and inert pinned source archives only."""
import argparse
import gc
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import time
from replay_inputs import Budget, RemoteParquet
TRACE_URL='https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories/resolve/35455389ab51bf5e2306bfd436ef72d0f98bf882/trajectories.parquet'


def project(trajectory):
    messages=[]
    for m in trajectory:
        if m['role']=='assistant' and m.get('tool_calls'):
            calls=[]
            for c in m['tool_calls']:
                f=c['function'];name=f['name']
                args=json.loads(f['arguments']) if name in ('str_replace_editor','execute_bash') else {}
                calls.append({**c,'function':{'name':name,'arguments':json.dumps(args)}})
            messages.append({'role':'assistant','tool_calls':calls})
        elif m['role']=='tool':
            messages.append({k:(m.get(k) if k!='content' or m.get('name') in ('str_replace_editor','execute_bash') else '') for k in ['role','name','tool_call_id','content']})
    return messages


def unpack_inert(data, destination):
    """No extractall, links, permissions, imports, hooks or source execution."""
    rows=[]; total=0; licenses=[];seen=set()
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        for member in archive:
            raw=PurePosixPath(member.name)
            if raw.is_absolute() or '..' in raw.parts:raise ValueError('unsafe archive member')
            if len(raw.parts)<2:
                if member.isdir():continue
                raise ValueError('archive member lacks root prefix')
            rel=PurePosixPath(*raw.parts[1:]); name=str(rel)
            if member.isdir():continue
            if name in seen or name=='_aki_manifest.json':raise ValueError('duplicate or reserved archive path')
            seen.add(name)
            if len(rows)>=50000:raise ValueError('archive member cap')
            if member.issym() or member.islnk():
                rows.append({'path':name,'kind':'unfollowed-link','target_sha256':hashlib.sha256(member.linkname.encode()).hexdigest()});continue
            if not member.isfile():raise ValueError('unsupported archive entry')
            total+=member.size
            if total>256*1024**2:raise ValueError('expanded snapshot exceeds 256 MiB')
            payload=archive.extractfile(member).read()
            target=destination/str(rel)
            if not target.resolve().is_relative_to(destination.resolve()):raise ValueError('unsafe archive path')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload);target.chmod(0o644)
            rows.append({'path':name,'kind':'file','bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()})
            if len(rel.parts)==1 and rel.name.lower() in ('license','license.txt','license.md','copying','copying.txt'):
                text=payload.decode('utf-8',errors='replace')
                recognized=any(s in text for s in ['Permission is hereby granted','Apache License','Redistribution and use','Mozilla Public License','Permission to use, copy, modify'])
                licenses.append({'path':name,'sha256':hashlib.sha256(payload).hexdigest(),'recognized_permissive_family':recognized})
    if not any(x['recognized_permissive_family'] for x in licenses):raise ValueError('expected upstream source license not found')
    fingerprint=hashlib.sha256(json.dumps(sorted(rows,key=lambda r:r['path']),sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'tree_manifest_sha256':fingerprint,'regular_file_bytes':total,'entries':rows,'licenses':licenses}


def main():
    import pyarrow.parquet as pq
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--cohort',type=Path,required=True);a=p.parse_args()
    cohort=json.loads(a.cohort.read_text()); selected=[r for r in cohort['cohort'] if r['split']=='development']
    assert len(selected)==12
    budget=Budget(a.inputs)
    if 'source_review_allowance_bytes' not in budget.state:
        # Conservative allowance for small primary-source connector reads outside
        # this downloader (OpenHands/ACI tree and implementation review).
        budget.state['source_review_allowance_bytes']=2*1024**2
        budget.state['downloaded_bytes']+=2*1024**2;budget.save()
    parquet=pq.ParquetFile(RemoteParquet(budget,TRACE_URL))
    trajectory_dir=a.inputs/'development';trajectory_dir.mkdir(exist_ok=True)
    for group in sorted({r['row_group'] for r in selected}):
        table=parquet.read_row_group(group,columns=['trajectory_id','trajectory'])
        for r in [r for r in selected if r['row_group']==group]:
            row=table.slice(r['row_index'],1).to_pylist()[0]
            assert row['trajectory_id']==r['trajectory_id']
            row['trajectory']=project(row['trajectory'])
            (trajectory_dir/(r['instance_id']+'.json')).write_text(json.dumps(row,ensure_ascii=False)+'\n')
        del table;gc.collect();budget.save()
        print(json.dumps({'development_row_group':group,'budgeted_download_bytes':budget.state['downloaded_bytes']}),flush=True)
    records=[]
    for r in selected:
        repo,commit=r['repo'],r['base_commit']
        assert re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo) and re.fullmatch('[a-f0-9]{40}',commit)
        destination=a.inputs/'trees'/(repo.replace('/','__')+'--'+commit)
        start=time.perf_counter_ns();before=budget.state['downloaded_bytes']
        try:
            data=budget.fetch(f'https://codeload.github.com/{repo}/tar.gz/{commit}')
            acquired=time.perf_counter_ns()
            manifest=unpack_inert(data,destination)
            elapsed=time.perf_counter_ns()-start
            (destination/'_aki_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
            records.append({k:r[k] for k in ['instance_id','repo','base_commit','environment_setup_commit']} | {'success':True,'source_download_bytes':budget.state['downloaded_bytes']-before,'acquisition_ns':acquired-start,'unpack_hash_ns':elapsed-(acquired-start),'tree_manifest_sha256':manifest['tree_manifest_sha256'],'regular_file_bytes':manifest['regular_file_bytes'],'licenses':manifest['licenses']})
        except Exception as e:
            records.append({'instance_id':r['instance_id'],'success':False,'error_type':type(e).__name__,'reason':str(e)[:200]})
        budget.save()
    (a.inputs/'source_records.json').write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps({'source_snapshots':len(records),'succeeded':sum(r['success'] for r in records),'budget':{k:v for k,v in budget.state.items() if k!='requests'}}))

if __name__=='__main__':main()
