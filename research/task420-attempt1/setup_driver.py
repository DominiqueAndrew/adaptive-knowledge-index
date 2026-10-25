#!/usr/bin/env python3
"""Load only staged verified artifacts and run one confined compatibility attempt."""
import hashlib,json,os,resource,subprocess,tarfile,time,sys
from pathlib import Path

ROOT=Path('scratch/pilot420-attempt').resolve()
DOCKER=['docker','--context','colima']
NAME='aki-task420-attempt1'
IMAGE='sha256:ca5c413738f01816ca17d523619e61c7e10489d299a5aa386f6076c7427393ea'
state={}

def run(args,timeout=30,**kwargs):
    return subprocess.run(args,check=True,timeout=timeout,**kwargs)

def guest_cpu():
    s=subprocess.check_output(['colima','ssh','--','cat','/proc/stat'],timeout=10).decode().splitlines()[0].split()[1:]
    return sum(int(s[i]) for i in [0,1,2,5,6,7])/100.0

def check():
    ledger=json.loads((ROOT/'ledger.json').read_text())
    cpu=resource.getrusage(resource.RUSAGE_CHILDREN)
    host=time.process_time()+cpu.ru_utime+cpu.ru_stime+ledger['host_cpu_seconds']+50 # conservative prior orchestration/startup allowance
    guest=guest_cpu()
    state.update(host_cpu_seconds=host,guest_busy_cpu_since_boot_seconds=guest,
                 setup_elapsed_seconds=time.time()-ledger['start_unix'])
    (ROOT/'setup-summary.json').write_text(json.dumps(state,indent=2)+'\n')
    if host+guest>300 or state['setup_elapsed_seconds']>600:
        raise RuntimeError('setup resource ceiling')

def main():
    resource.setrlimit(resource.RLIMIT_CPU,(290,300))
    state['status']='loading_verified_image';check()
    continuing = sys.argv[1:] == ['--continue-verified-import']
    if not continuing:
        raise RuntimeError('This attempt has already imported its image; no repeated load allowed')
    if subprocess.run(DOCKER+['container','inspect',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0:
        raise RuntimeError('attempt container already exists')
    inspect=json.loads(subprocess.check_output(DOCKER+['image','inspect','aki-task420-reviewed:attempt1']))[0]
    expected=json.loads((ROOT/'image'/('ca5c413738f01816ca17d523619e61c7e10489d299a5aa386f6076c7427393ea.json')).read_text())
    if inspect['Architecture']!='arm64' or inspect['Os']!='linux' or not json.loads((ROOT/'loaded-identity-verification.json').read_text())['exact_original_config_blob_verified'] or inspect['RootFS']['Layers']!=expected['rootfs']['diff_ids'] or inspect['Created']!=expected['created']:
        raise RuntimeError('loaded execution configuration or layer identities differ')
    global IMAGE
    IMAGE=inspect['Id']
    state['identity_note']='Docker 29 uses converted manifest ID; execution config and all uncompressed layers match pinned config'
    state['prior_host_orchestration_cpu_allowance_seconds']=50
    state['loaded_image_bytes']=inspect['Size'];state['loaded_image_id']=IMAGE
    staged=sum(f.stat().st_size for f in ROOT.rglob('*') if f.is_file())
    state['conservative_disk_bytes']=staged+inspect['Size']+json.loads((ROOT/'ledger.json').read_text())['download_bytes']
    if state['conservative_disk_bytes']>3*1024**3:raise RuntimeError('disk ceiling')
    check()
    control=ROOT/'control';packages=ROOT/'packages'
    args=DOCKER+['create','--name',NAME,'--label','org.aki.attempt=task420-1',
        '--network','none','--user','65534:65534','--read-only','--cap-drop','ALL',
        '--security-opt','no-new-privileges:true','--cpus','1','--memory','1g','--memory-swap','1g','--pids-limit','64',
        '--tmpfs','/env:rw,nosuid,nodev,size=256m,uid=65534,gid=65534',
        '--tmpfs','/workspace:rw,nosuid,nodev,size=64m,uid=65534,gid=65534',
        '--tmpfs','/tmp:rw,nosuid,nodev,size=128m,uid=65534,gid=65534',
        '--mount','type=bind,source='+str(control)+',target=/control,readonly',
        '--mount','type=bind,source='+str(packages)+',target=/packages,readonly',
        '--env','HOME=/tmp','--env','PYTHONDONTWRITEBYTECODE=1','--env','PIP_DISABLE_PIP_VERSION_CHECK=1',
        '--workdir','/workspace',IMAGE,'python3','/control/idle.py']
    state['container_id']=subprocess.check_output(args).decode().strip()
    run(DOCKER+['start',NAME],stdout=subprocess.DEVNULL)
    # Copy only the inert public base; tar ownership permits the confined user to edit it.
    source=Path('../replay-inputs/trees/Backblaze__B2_Command_Line_Tool--15a60ad1c71b75366061e4f742ef52eb9dcc23e7')
    p=subprocess.Popen(DOCKER+['cp','-a','-',NAME+':/workspace'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    count=0
    with tarfile.open(fileobj=p.stdin,mode='w|') as tar:
        for f in sorted(source.rglob('*')):
            rel=f.relative_to(source)
            if any(x.startswith('.') for x in rel.parts) or str(rel)=='_aki_manifest.json':continue
            if f.is_symlink():raise ValueError('unexpected source symlink')
            if not f.is_file():continue
            info=tar.gettarinfo(str(f),str(rel));info.uid=65534;info.gid=65534;info.uname='';info.gname=''
            with f.open('rb') as stream:tar.addfile(info,stream)
            count+=1
    p.stdin.close();rc=p.wait(timeout=30)
    if rc:raise RuntimeError('public source transfer failed')
    state['copied_source_files']=count;state['status']='offline_compatibility_running';check()
    with (ROOT/'compatibility.log').open('wb') as log:
        p=subprocess.Popen(DOCKER+['exec',NAME,'python3','/control/setup.py'],stdout=log,stderr=subprocess.STDOUT)
        while p.poll() is None:
            time.sleep(2)
            try:check()
            except BaseException:
                subprocess.run(DOCKER+['kill',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                p.wait(timeout=10);raise
        state['compatibility_exit']=p.returncode
    check()
    state['status']='compatibility_passed' if p.returncode==0 else 'compatibility_failed'
    (ROOT/'setup-summary.json').write_text(json.dumps(state,indent=2)+'\n')
    print(json.dumps(state,indent=2))

if __name__=='__main__':
    try:main()
    except BaseException as exc:
        state.update(status='failed',error_type=type(exc).__name__,error=str(exc)[:200])
        (ROOT/'setup-summary.json').write_text(json.dumps(state,indent=2)+'\n')
        raise
