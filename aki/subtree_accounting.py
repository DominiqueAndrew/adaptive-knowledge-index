"""Exit-independent accounting primitives; no process or runtime control.

A durable kernel subtree counter survives descendant exits. Where no such counter
is available, an entire-lifetime capacity envelope is safe but intentionally costly.
Neither a parent exit nor a missing PID proves subtree quiescence. The Linux reader
is exercised on original filesystem fixtures; there is no live adapter here.
"""
from dataclasses import dataclass
from pathlib import Path
import re
import time
from .setup_accounting import AccountingError


@dataclass(frozen=True)
class SubtreeSample:
    identity: str
    observed_ns: int
    usage_ns: int
    populated: bool


class SubtreeLedger:
    def __init__(self, baseline, capacity, *, durable_counter, containment_verified, quantum_ns=1000):
        if containment_verified is not True or type(durable_counter) is not bool:raise AccountingError('subtree containment/mode is unverified')
        if type(capacity) is not int or capacity<1 or type(quantum_ns) is not int or quantum_ns<0:
            raise AccountingError('invalid capacity or counter resolution')
        self._valid(baseline)
        if baseline.populated:raise AccountingError('enroll an empty scope before dispatch')
        self.base=self.last=baseline;self.capacity=capacity;self.quantum=quantum_ns
        self.durable=durable_counter;self.sealed_ns=None;self.final=None;self.fault=None

    @staticmethod
    def _valid(sample):
        if (not isinstance(sample,SubtreeSample) or not sample.identity or type(sample.populated) is not bool
            or type(sample.usage_ns) is not int or sample.usage_ns<0
            or type(sample.observed_ns) is not int or sample.observed_ns<0):
            raise AccountingError('incomplete subtree observation')

    def observe(self,sample):
        try:
            if self.final is not None:raise AccountingError('finalized scope cannot reopen')
            self._valid(sample)
            if (sample.identity!=self.base.identity or sample.observed_ns<self.last.observed_ns
                or sample.usage_ns<self.last.usage_ns):raise AccountingError('subtree reset, reuse or clock regression')
            self.last=sample
        except AccountingError as exc:
            self.fault=str(exc);raise

    def upper_bound(self,now_ns):
        if self.fault:raise AccountingError(self.fault)
        if type(now_ns) is not int or now_ns<self.last.observed_ns:raise AccountingError('invalid accounting clock')
        if self.final is not None:return self.final
        if self.durable:
            measured=self.last.usage_ns-self.base.usage_ns
            bound=(now_ns-self.last.observed_ns)*self.capacity+2*self.quantum
        else:
            measured=0;bound=(now_ns-self.base.observed_ns)*self.capacity
        return {'observed_subtree_delta_ns':measured,'capacity_and_resolution_bound_ns':bound,
                'conservative_cpu_ns':measured+bound,'finalized':False,
                'mode':'durable_subtree' if self.durable else 'whole_lifetime_capacity'}

    def seal_dispatch(self,now_ns):
        if self.sealed_ns is not None or self.final is not None or now_ns<self.last.observed_ns:
            raise AccountingError('invalid dispatch boundary')
        self.sealed_ns=now_ns

    def finalize(self,sample):
        self.observe(sample)
        if self.sealed_ns is None or sample.observed_ns<self.sealed_ns or sample.populated:
            self.fault='subtree is not confirmed empty after dispatch sealed';raise AccountingError(self.fault)
        result=self.upper_bound(sample.observed_ns);result['finalized']=True;self.final=result
        return result


def read_cgroup_v2(directory,boot_id,*,clock=time.monotonic_ns):
    """Read one already-owned domain cgroup, before deletion; never discover groups.

    Caller must prove unprivileged descendants cannot leave/reconfigure the group,
    validate its ownership, and close dispatch before accepting populated=0.
    Missing files, symlinks or group replacement are errors, never empty scopes.
    """
    root=Path(directory)
    if not re.fullmatch(r'[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}',boot_id):raise AccountingError('boot identity required')
    if root.is_symlink():raise AccountingError('cgroup link rejected')
    try:
        before=root.stat();values={}
        for name in ('cgroup.type','cgroup.events','cpu.stat'):
            path=root/name
            if path.is_symlink():raise AccountingError('counter link rejected')
            if name=='cpu.stat':observed_ns=clock()
            with path.open() as stream:values[name]=stream.read(4097)
            if len(values[name])>4096:raise AccountingError('counter size cap')
        after=root.stat()
        if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):raise AccountingError('cgroup replaced during read')
        if values['cgroup.type'].strip()!='domain':raise AccountingError('domain cgroup required')
        def fields(text):
            rows=[line.split() for line in text.splitlines()]
            if any(len(row)!=2 for row in rows) or len({r[0] for r in rows})!=len(rows):raise AccountingError('invalid counter fields')
            return dict(rows)
        usage=int(fields(values['cpu.stat'])['usage_usec']);pop=fields(values['cgroup.events'])['populated']
        event_path=root/'cgroup.events'
        if event_path.is_symlink():raise AccountingError('counter link rejected')
        with event_path.open() as stream:post_text=stream.read(4097)
        if len(post_text)>4096:raise AccountingError('counter size cap')
        post=fields(post_text)['populated']
        final=root.stat()
        if root.is_symlink() or (before.st_dev,before.st_ino)!=(final.st_dev,final.st_ino):
            raise AccountingError('cgroup replaced during final read')
        if usage<0 or pop not in ('0','1') or post not in ('0','1'):raise AccountingError('invalid subtree counters')
        # A transition 1 -> 0 needs another sample: the CPU read may precede exit.
        return SubtreeSample(f'{boot_id}:{before.st_dev}:{before.st_ino}',observed_ns,usage*1000,pop=='1' or post=='1')
    except (OSError,KeyError,ValueError) as exc:raise AccountingError('subtree observation unavailable') from exc
