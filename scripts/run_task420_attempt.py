#!/usr/bin/env python3
"""Explicit single live attempt; no dry run silently starts a runtime.

Use only with separate authorization. Records numeric/provenance output locally.
All work, including any pilot, shares a stricter 600s/300 CPU-s outer envelope.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import threading
import time
import uuid

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT));sys.path.insert(0,str(PROJECT/'scripts'))
from aki.setup_accounting import AccountingError, CpuLedger, darwin_process_cpu, guest_cpu_snapshot
from aki.setup_watchdog import SetupWatchdog, Command
from aki.setup_tls import verified_context
from prepare_task420_controls import prepare
from task420_live_worker import save, read, COLIMA


def children(pid):
    lib=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True)
    function=lib.proc_listchildpids;function.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_int];function.restype=ctypes.c_int
    values=(ctypes.c_int*256)();count=function(pid,values,ctypes.sizeof(values))
    # Unlike proc_listpids, proc_listchildpids returns a count of PIDs, not bytes.
    if count<0 or count>=len(values):raise AccountingError('owned child inventory unavailable/overflow')
    return [p for p in values[:count] if p>0]


class Accounting:
    def __init__(self,root):
        self.root=root;self.started=time.monotonic_ns();self.host_capacity=os.cpu_count()
        self.ledger=CpuLedger();self.runner=None;self.stop=threading.Event();self.lock=threading.Lock()
        for name in self.ledger.REQUIRED:
            self.ledger.register(name,name,4 if name=='guest' else self.host_capacity,0,self.started,active=True)
        self.worker_max=0;self.runtime={};self.runtime_first=None;self.vm_start=None
        self.guest=None;self.guest_error=None;self.final=None
        self.observations=[];self.max_cpu=0;self.max_disk=0
        self.vm_dir=Path.home()/'.colima/_lima/colima'
        self.disks={p.name:p.stat().st_blocks*512 for p in self.vm_dir.glob('*disk') if p.is_file()}
        self.thread=threading.Thread(target=self._guest_loop,daemon=True);self.thread.start()

    def _vm(self):
        path=self.root/'vm-state.json'
        return read(path) if path.exists() else {'state':'not_started'}

    def _guest_loop(self):
        while not self.stop.wait(0.5):
            vm=self._vm()
            if vm['state'] not in ('starting','ready'):continue
            p=None
            try:
                p=subprocess.Popen([COLIMA,'ssh','--','sh','-c','cat /proc/stat; cat /proc/sys/kernel/random/boot_id; getconf CLK_TCK'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,start_new_session=True)
                raw=p.communicate(timeout=3)[0]
                if p.returncode:continue
                lines=raw.decode().splitlines();value=guest_cpu_snapshot(lines[0],int(lines[-1]),lines[-2])
                with self.lock:
                    if self.guest and (value['identity']!=self.guest['identity'] or value['cpu_ns']<self.guest['cpu_ns']):raise AccountingError('guest reboot/reset')
                    self.guest={**value,'observed_ns':time.monotonic_ns()}
            except AccountingError as exc:self.guest_error=str(exc)
            except Exception:pass  # Unsampled time is bounded at all four guest CPUs.
            finally:
                if p:
                    try:os.killpg(p.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    if p.poll() is None:p.wait(timeout=1)

    def _workers(self):
        used=resource.getrusage(resource.RUSAGE_CHILDREN);total=int((used.ru_utime+used.ru_stime)*1e9)
        queue=children(os.getpid());seen=set()
        while queue:
            pid=queue.pop()
            if pid in seen:continue
            seen.add(pid)
            if len(seen)>256:raise AccountingError('owned worker count')
            try:
                sample=darwin_process_cpu(pid);total+=sample['cpu_ns']+sample['reaped_children_cpu_ns'];queue.extend(children(pid))
            except AccountingError:
                # A process may have just reaped. Its CPU enters RUSAGE_CHILDREN.
                try:os.kill(pid,0)
                except ProcessLookupError:continue
                raise
        self.worker_max=max(self.worker_max,total)
        return self.worker_max

    def snapshot(self):
        if self.final:return self.final
        now=time.monotonic_ns();vm=self._vm()
        if vm['state'] in ('starting','ready') and self.vm_start is None:self.vm_start=vm['at_monotonic_ns']
        if self.guest_error:raise AccountingError(self.guest_error)
        self.ledger.update('supervisor','supervisor',time.process_time_ns(),now)
        self.ledger.update('workers','workers',self._workers(),now)
        # Only PID files belonging to this already-existing, explicitly started VM.
        if self.vm_start is not None:
            for path in self.vm_dir.glob('*.pid'):
                try:pid=int(path.read_text().strip())
                except (ValueError,FileNotFoundError):continue
                if pid<=0:raise AccountingError('invalid VM PID')
                try:sample=darwin_process_cpu(pid)
                except AccountingError:
                    if vm['state']=='stopped':continue
                    raise
                if self.runtime_first is None:self.runtime_first=now
                identity=sample['identity'];previous=self.runtime.get(identity)
                if previous and sample['cpu_ns']<previous['cpu_ns']:raise AccountingError('runtime CPU reset')
                self.runtime[identity]={**sample,'observed_ns':now,'pid':pid}
        host=0
        for sample in self.runtime.values():
            host+=sample['cpu_ns']+sample['reaped_children_cpu_ns']
            if vm['state']=='stopped':
                host+=max(0,vm['at_monotonic_ns']-sample['observed_ns'])*self.host_capacity
            elif sample['observed_ns']<now:host+=(now-sample['observed_ns'])*self.host_capacity
        if self.vm_start is not None:
            host+=( (self.runtime_first or now)-self.vm_start)*self.host_capacity
        old=self.ledger.counters['runtime_host'].value_ns
        self.ledger.update('runtime_host','runtime_host',max(old,host),now)
        with self.lock:g=dict(self.guest) if self.guest else None
        if self.vm_start is None:guest=0
        elif g:
            boundary=vm['at_monotonic_ns'] if vm['state']=='stopped' else now
            guest=g['cpu_ns']+max(0,boundary-g['observed_ns'])*4
        else:guest=max(0,now-self.vm_start)*4
        old=self.ledger.counters['guest'].value_ns
        self.ledger.update('guest','guest',max(old,guest),now)
        # Accounting is finalized only after confirmed VM shutdown and the final
        # cleanup worker exits. One CPU-second covers report serialization tail.
        finalized=(self.runner is not None and self.runner.phase=='cleanup' and self.runner.current is None
                   and (self.root/'local-cleanup.json').exists() and vm['state'] in ('stopped','not_started'))
        if finalized:
            self.stop.set();self.thread.join(timeout=3.5)
            if self.thread.is_alive():raise AccountingError('CPU collector termination pending')
            now=time.monotonic_ns()
            self.ledger.update('supervisor','supervisor',time.process_time_ns(),now)
            self.ledger.update('workers','workers',self._workers(),now)
            for name in self.ledger.REQUIRED:self.ledger.finalize(name,now,confirmed=True)
            # Keep this allowance separate from actual observed CPU counters.
            self.ledger.counters['supervisor'].terminal_bound_ns+=1_000_000_000
        value=self.ledger.snapshot(now);self.max_cpu=max(self.max_cpu,value['conservative_cpu_ns'])
        # Reserve VM unpacked image + bounded tmpfs/capture space before download.
        local=0
        for p in self.root.rglob('*'):
            try:
                if p.is_file() and not p.is_symlink():local+=p.stat().st_size
            except FileNotFoundError:pass  # Atomic ledger replacement/deletion; reserved space covers writers.
        vm_growth=sum(max(0,p.stat().st_blocks*512-self.disks.get(p.name,p.stat().st_blocks*512)) for p in self.vm_dir.glob('*disk') if p.is_file())
        disk=local+max(vm_growth,1024**3 if vm['state'] in ('starting','ready') else 0)+448*1024**2+384*1024**2
        self.max_disk=max(self.max_disk,disk)
        if disk>3*1024**3:raise AccountingError('additional disk reservation ceiling')
        if finalized:self.final=value
        return value


def config_hashes():
    names=['.colima/default/colima.yaml','.colima/_lima/colima/lima.yaml','.docker/config.json','.ssh/config']
    return {name:hashlib.sha256((Path.home()/name).read_bytes()).hexdigest() if (Path.home()/name).exists() else None for name in names}


def main():
    main_started=time.monotonic()
    parser=argparse.ArgumentParser();parser.add_argument('--execute-approved-single-attempt',action='store_true');args=parser.parse_args()
    if not args.execute_approved_single_attempt:raise SystemExit('No action; separate live-attempt authorization required.')
    tls,tls_proof=verified_context()  # Local only, before allocating a live attempt.
    # This precondition does not start or stop anything.
    status=subprocess.run([COLIMA,'list','--json'],capture_output=True,check=True,timeout=10)
    profiles=[json.loads(row) for row in status.stdout.splitlines()]
    if not any(r.get('name')=='default' and r.get('status')=='Stopped' for r in profiles):raise SystemExit('existing default VM must be stopped')
    attempt=uuid.uuid4().hex;root=PROJECT/'scratch'/('task420-live-'+attempt)
    prepare(root,attempt);(root/'control/backend.py').write_bytes((PROJECT/'runtime/task420/backend.py').read_bytes())
    save(root/'tls-preflight.json',tls_proof)
    before=config_hashes();save(root/'supervisor.json',{'pid':os.getpid(),'attempt':attempt,'started_unix':time.time(),'single_attempt':True})
    accounting=Accounting(root);runner=SetupWatchdog(cpu_snapshot=accounting.snapshot,total_s=600-(time.monotonic()-main_started))
    accounting.runner=runner
    def cmd(phase,timeout):return Command(phase,(sys.executable,'-I',str(PROJECT/'scripts/task420_live_worker.py'),phase,str(root)),timeout_s=timeout)
    print(json.dumps({'attempt_directory':str(root),'status':'starting_one_bounded_attempt'}),flush=True)
    try:
        result=runner.run([cmd('stage',120),cmd('start',70),cmd('import',120),cmd('setup',180),cmd('pilot',180)],
                          [cmd('cleanup-container',15),cmd('cleanup-image',15),cmd('cleanup-vm',45),cmd('cleanup-local',10)])
    finally:accounting.stop.set();accounting.thread.join(timeout=4)
    result.update({'config_hashes_unchanged':config_hashes()==before,'peak_conservative_cpu_ns':accounting.max_cpu,
                   'peak_disk_reserved_bytes':accounting.max_disk,'root_name':root.name,
                   'total_including_preparation_wall_s':time.monotonic()-main_started,
                   'interpretation':'Live setup/fixture only unless pilot record separately confirms dispatch; counters are conservative with overlapping host/guest costs.'})
    save(root/'result.json',result)
    print(json.dumps({k:result.get(k) for k in ('status','reason','elapsed_s','accounting_complete','cleanup_pending','config_hashes_unchanged','peak_conservative_cpu_ns','peak_disk_reserved_bytes')}),flush=True)


if __name__=='__main__':main()
