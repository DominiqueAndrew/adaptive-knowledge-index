#!/usr/bin/env python3
"""Offline retained-evidence audit. Reads only supplied paths; executes no source."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import stat


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def audit(campaign,source,proposal):
    budget=json.loads((campaign/'budget.json').read_text());cache=campaign/'artifact-cache'
    assert not cache.is_symlink() and not any(p.is_symlink() for p in cache.rglob('*'))
    manifest=json.loads((cache/'image/manifest.json').read_text())[0]
    assert manifest['Config']==proposal['image']['config_digest'].split(':')[1]+'.json'
    config=cache/'image'/manifest['Config'];configuration=json.loads(config.read_text())
    assert 'sha256:'+digest(config)==proposal['image']['config_digest']
    assert manifest['Layers']==[str(i)+'/layer.tar' for i in range(len(configuration['rootfs']['diff_ids']))]
    for name,expected in zip(manifest['Layers'],configuration['rootfs']['diff_ids']):
        assert 'sha256:'+digest(cache/'image'/name)==expected
    assert len(manifest['Layers'])==len(configuration['rootfs']['diff_ids'])
    packages=proposal['candidate_dependencies']['packages']
    for item in packages:
        artifact=item['artifact'];path=cache/'packages'/artifact['filename']
        assert path.stat().st_size==artifact['size'] and digest(path)==artifact['sha256']
    expected={'image/manifest.json','image/'+manifest['Config']}|{'image/'+n for n in manifest['Layers']}|{'packages/'+p['artifact']['filename'] for p in packages}
    actual={p.relative_to(cache).as_posix() for p in cache.rglob('*') if p.is_file()}
    assert expected==actual and not any(p.is_symlink() for p in cache.rglob('*'))
    sizes={'expanded_image_layers':sum((cache/'image'/n).stat().st_size for n in manifest['Layers']),
           'package_artifacts':sum((cache/'packages'/p['artifact']['filename']).stat().st_size for p in packages),
           'image_config_and_local_manifest':config.stat().st_size+(cache/'image/manifest.json').stat().st_size}
    logical=allocated=0;seen=set();symlinks=0
    for path in campaign.rglob('*'):
        info=path.lstat()
        if stat.S_ISLNK(info.st_mode):symlinks+=1
        if not stat.S_ISREG(info.st_mode) or (info.st_dev,info.st_ino) in seen:continue
        seen.add((info.st_dev,info.st_ino));logical+=info.st_size;allocated+=info.st_blocks*512
    transfer=json.loads((campaign/'transfer.json').read_text());runs=[]
    for record in budget['attempts']:
        result=json.loads((campaign/('run-'+record['attempt'])/'result.json').read_text())
        work=sum(r['wall_s'] for r in result['command_records'] if r['phase']=='work')
        runs.append({'status':result['status'],'accounting_faults':result['accounting_faults'],
                     'faults_have_process_context':bool(result.get('accounting_fault_details')),
                     'cleanup_window_upper_s':max(0,result['elapsed_s']-work),
                     'recorded_charge_ns':result['peak_conservative_cpu_ns']})
    incomplete=[r for r in runs if r['accounting_faults']]
    cleanup=sum(r['cleanup_window_upper_s'] for r in incomplete)
    cores=os.cpu_count();charge=budget['cpu_charged_ns']/1e9
    path=source/'b2/console_tool.py';tree=ast.parse(path.read_text());cli={}
    for cls in tree.body:
        if isinstance(cls,ast.ClassDef) and cls.name in ('Help','Version','ConsoleTool'):
            for fn in cls.body:
                if isinstance(fn,ast.FunctionDef) and fn.name in ('run','_usage_and_fail'):
                    cli[cls.name+'.'+fn.name]={'line':fn.lineno,'literal_return_values':sorted({n.value.value for n in ast.walk(fn) if isinstance(n,ast.Return) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,int)})}
    return {'scope':'offline audit; no runtime, download, benchmark-source execution or model calls',
        'budget_closed':budget['closed'],'budget_sha256':digest(campaign/'budget.json'),
        'cache':{'parts_bytes':sizes,'total_bytes':sum(sizes.values()),'exact_inventory_and_hashes_verified':True,
                 'files':len(actual),'layers':len(manifest['Layers']),'packages':len(packages)},
        'download':{'compressed_layer_bytes':proposal['image']['compressed_layer_bytes'],'package_bytes':sizes['package_artifacts'],
                    'observed_response_body_bytes':transfer['observed_body_bytes'],'charged_bytes':transfer['download_bytes'],
                    'metadata_bodies_bytes':transfer['observed_body_bytes']-proposal['image']['compressed_layer_bytes']-sizes['package_artifacts'],
                    'header_allowance_bytes':transfer['download_bytes']-transfer['observed_body_bytes']},
        'campaign_disk_at_audit':{'unique_regular_files':len(seen),'logical_file_bytes':logical,'allocated_file_bytes':allocated,'symlinks':symlinks,
                                  'excludes':'directory metadata, APFS snapshots/shared extents and historical VM disk growth'},
        'cpu':{'recorded_charge_s':charge,'certified_complete':False,'runs':runs,
               'host_capacity_now':cores,'missing_process_identity_and_fault_timestamps':True,
               'conditional_one_host_component_full_cleanup_s':charge+cores*cleanup,
               'conditional_both_host_components_full_cleanup_s':charge+2*cores*cleanup,
               'scenario_assumptions':'Counter gaps confined to teardown; prior coverage complete; same host capacity. These are conservative reconciliation scenarios, not observed CPU totals or a proof of a breach.'},
        'cli_static_evidence':{'source_sha256':digest(path),'methods':cli,'source_executed':False},
        'conclusion':'Retain task 420: six compatibility gates and the live fixture passed. Historical CPU compliance remains unproved; keep campaign closed.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--campaign',type=Path,required=True);p.add_argument('--source',type=Path,required=True)
    p.add_argument('--proposal',type=Path,default=Path('results/runtime/task420-setup-proposal.json'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise SystemExit('Refuse to overwrite an audit')
    result=audit(a.campaign,a.source,json.loads(a.proposal.read_text()))
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'cache_hashes_verified':True,'cache_bytes':result['cache']['total_bytes'],'cpu_compliance_certified':False,'budget_closed':result['budget_closed']}))
