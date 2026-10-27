"""Reviewable launcher controller: emits intents; contains no OS execution shim.

All receipts below must be obtained by a trusted platform adapter, not synthesized
from PID absence, socket deletion, a successful stop command, or caller preference.
Fixture receipts exercise the protocol but never authorize or certify a live run.
The installed Darwin/Lima backend is rejected because complete helper containment
and shutdown evidence is unavailable. No VM or download entrypoint is provided.
"""
from dataclasses import dataclass
from copy import deepcopy
from pathlib import PurePosixPath
import re
from .runtime_ownership import RuntimeLease, verify_runtime, OwnershipError
from .platform_accounting import capacity_plan


class LaunchError(RuntimeError):pass


@dataclass(frozen=True)
class Limits:
    download_bytes:int=256*1024**2
    disk_bytes:int=8*1024**3
    work_wall_s:int=240
    teardown_wall_s:int=60
    host_cpus:int=12
    cpu_reservation_s:int=3600

    def validate(self):
        if any(type(v) is not int or v<=0 for v in vars(self).values()):raise LaunchError('invalid limits')
        plan=capacity_plan(self.host_cpus,self.work_wall_s,self.teardown_wall_s,budget_cpu_s=self.cpu_reservation_s)
        if not plan['fits']:raise LaunchError('whole-machine capacity reservation is insufficient')
        return plan


def host_backend_readiness(platform,backend,*,coverage,external_services):
    """Strict capability whitelist. No live Darwin backend currently qualifies."""
    problems=[]
    if (platform,backend)!=('linux','owned-cgroup-v2'):
        problems.append('no complete kernel host subtree backend for this platform')
    if coverage!='all_vm_and_helper_execution':problems.append('incomplete VM/helper execution coverage')
    if external_services is not False:problems.append('uncontained external service work')
    return {'ready':not problems,'reasons':problems,
            'required':'owned kernel domain before every spawn; no migration or external launch service'}


class IsolatedLauncher:
    """One monotonic attempt. Only typed, non-executable intents leave this class.

    Independent guest/host final receipts are mandatory. The event adapter must
    retain kernel domains through the final counter read, and supply a terminal
    VM state bound to this instance and boot identity. Neither final receipt is a
    substitute for the other. Denial/errors are sticky; cleanup is owner-scoped.
    """
    STAGES=('preflight','artifact','runtime','guest','fixture','guest_final','vm_stop','host_final','cleanup')

    def __init__(self,lease:RuntimeLease,image_pin,*,limits=Limits(),evidence_kind='fixture'):
        if lease.runtime!='none' or lease.readonly_mounts:raise LaunchError('no Docker or host mounts permitted')
        if (not re.fullmatch(r'aki-[a-z0-9-]{1,40}',lease.profile)
            or not re.fullmatch(r'[a-f0-9]{32}',lease.attempt)
            or not lease.endpoint.startswith('unix:///') or '..' in PurePosixPath(lease.endpoint[7:]).parts
            or lease.profile not in PurePosixPath(lease.endpoint[7:]).parts
            or lease.cpus!=2 or lease.memory_bytes!=2*1024**3):
            raise LaunchError('dedicated identity/socket and fixed VM resources required')
        if evidence_kind not in ('fixture','live'):raise LaunchError('unknown evidence kind')
        self.lease=lease;self.pin=dict(image_pin);self.limits=limits;self.capacity=limits.validate()
        for key,length in [('sha256',64),('sha512',128)]:
            if not re.fullmatch('[a-f0-9]{'+str(length)+'}',self.pin.get(key,'')):raise LaunchError('pinned image digest required')
        if type(self.pin.get('size')) is not int or not 0<self.pin['size']<=limits.download_bytes:
            raise LaunchError('pinned image exceeds download ceiling')
        self.kind=evidence_kind;self.stage=0;self.errors=[];self.receipts={};self.intents=[]
        self.elapsed_ns=0;self.download=0;self.disk=0;self.disk_peak=0
        self.start_requested=False;self.owned=False;self.work_closed=False

    def _fail(self,reason):
        self.errors.append(reason);self.work_closed=True
        raise LaunchError(reason)

    def resources(self,*,elapsed_ns,download_bytes,disk_bytes):
        values=(elapsed_ns,download_bytes,disk_bytes)
        if any(type(v) is not int or v<0 for v in values):self._fail('invalid resource observation')
        if elapsed_ns<self.elapsed_ns or download_bytes<self.download:self._fail('resource counter regression')
        self.elapsed_ns=elapsed_ns;self.download=download_bytes;self.disk=disk_bytes
        self.disk_peak=max(self.disk_peak,disk_bytes)
        if download_bytes>self.limits.download_bytes or disk_bytes>self.limits.disk_bytes:self._fail('resource cap exceeded')
        if elapsed_ns>(self.limits.work_wall_s+self.limits.teardown_wall_s)*10**9:self._fail('teardown deadline exceeded; lifecycle uncertified')
        if elapsed_ns>=self.limits.work_wall_s*10**9:self.work_closed=True

    def intent(self,stage):
        if self.errors:self._fail('failed attempt cannot dispatch another stage')
        if self.stage>=len(self.STAGES) or stage!=self.STAGES[self.stage]:self._fail('stage ordering violation')
        if stage in ('artifact','runtime','guest','fixture') and self.work_closed:self._fail('work deadline closed dispatch')
        if any(i['stage']==stage for i in self.intents):self._fail('duplicate or uncertain action; inspect rather than retry')
        if stage=='runtime':self.start_requested=True
        intent={'stage':stage,'attempt':self.lease.attempt,'profile':self.lease.profile,
                'endpoint':self.lease.endpoint,'executable':False,'evidence_kind':self.kind}
        self.intents.append(intent);return dict(intent)

    def observe(self,stage,r):
        if self.errors:self._fail('cannot turn failed evidence into success')
        if self.stage>=len(self.STAGES) or stage!=self.STAGES[self.stage] or not any(i['stage']==stage for i in self.intents):
            self._fail('unsolicited or reordered receipt')
        if not isinstance(r,dict) or r.get('attempt')!=self.lease.attempt or r.get('evidence_kind')!=self.kind:
            self._fail('receipt ownership or provenance mismatch')
        def require(fields):
            if any(r.get(k)!=v or type(r.get(k)) is not type(v) for k,v in fields.items()):
                self._fail('incomplete '+stage+' evidence')
        if stage=='preflight':
            require({'fresh_namespace':True,'global_configuration_unchanged':True,'kernel_domain_enrolled_before_spawn':True,
                     'migration_denied':True,'external_dispatch_denied':True,'counter_retained_until_final':True,
                     'host_logical_cpus':self.limits.host_cpus})
            ready=host_backend_readiness(r.get('platform'),r.get('backend'),coverage=r.get('coverage'),external_services=r.get('external_services'))
            if not ready['ready']:self._fail('; '.join(ready['reasons']))
            if not r.get('host_scope'):self._fail('stable host scope identity required')
        elif stage=='artifact':
            require(self.pin|{'expanded_size_checked':True,'maximum_expanded_bytes':3*1024**3,'no_extra_artifacts':True})
            if self.download<self.pin['size']:self._fail('artifact transfer was not charged')
            expanded=r.get('expanded_bytes')
            if type(expanded) is not int or not 0<expanded<=3*1024**3:self._fail('expanded image size unavailable or over cap')
            reservation=self.pin['size']+expanded+4*1024**3+256*1024**2
            if r.get('disk_reservation_bytes')!=reservation or reservation>self.limits.disk_bytes:
                self._fail('complete base/writable-root/log disk reservation missing')
        elif stage=='runtime':
            try:verify_runtime(self.lease,r['runtime'])
            except (KeyError,TypeError,OwnershipError) as exc:self._fail('runtime isolation rejected: '+str(exc))
            require({'all_helpers_in_host_scope':True,'runtime_config_read_back':True})
            if not r.get('vm_identity') or not r.get('boot_identity'):self._fail('stable VM/boot identity required')
            self.owned=True
        elif stage=='guest':
            require({'enrolled_before_exec':True,'nonroot':True,'no_new_privileges':True,'capabilities_empty':True,
                     'network_namespace_private':True,'network_routes':[],'host_mounts':[],
                     'source_readonly':True,'data_noexec':True,'cgroup_write_denied':True,'devices_denied':True})
            if not r.get('guest_scope'):self._fail('guest scope identity missing')
            if r.get('boot_identity')!=self.receipts['runtime']['boot_identity']:self._fail('guest boot changed')
        elif stage=='fixture':
            require({'only_original_fixture':True,'model_calls':0,'benchmark_operations':0,'heldout_reads':0,'complete_recorder_boundaries':True})
        elif stage=='guest_final':
            require({'dispatch_sealed':True,'stop_acknowledged':True,'populated':False,'counter_final_before_removal':True,'read_error':False})
            if r.get('guest_scope')!=self.receipts['guest']['guest_scope']:self._fail('guest scope changed at shutdown')
            if r.get('boot_identity')!=self.receipts['runtime']['boot_identity']:self._fail('guest boot changed at shutdown')
            if type(r.get('cpu_ns')) is not int or r['cpu_ns']<0:self._fail('missing final guest counter')
        elif stage=='vm_stop':
            require({'stop_acknowledged':True,'terminal_state_observed':True,'state':'stopped'})
            if r.get('vm_identity')!=self.receipts['runtime']['vm_identity']:self._fail('wrong VM terminal receipt')
        elif stage=='host_final':
            require({'dispatch_sealed':True,'populated':False,'all_registered_helpers_terminal':True,
                     'counter_final_before_removal':True,'event_loss':False,'read_error':False,'late_spawns':0})
            if r.get('host_scope')!=self.receipts['preflight']['host_scope']:self._fail('host scope changed at shutdown')
            # Missing, inferred-zero or regressing final counters cannot certify.
            if (type(r.get('cpu_ns')) is not int or type(r.get('baseline_cpu_ns')) is not int
                or not 0<=r['baseline_cpu_ns']<=r['cpu_ns']):self._fail('invalid final host counter')
        elif stage=='cleanup':
            require({'only_attempt_resources':True,'runtime_removed':True,'temporary_credentials_removed':True,
                     'original_cache_unchanged':True,'global_configuration_unchanged':True,'private_mounts_used':False})
        self.receipts[stage]=deepcopy(r);self.stage+=1

    def failure_cleanup_intent(self,ownership_readback=None):
        """A failure never authorizes stopping unknown or merely named resources."""
        if not self.errors:raise LaunchError('failure cleanup requires a failed attempt')
        if not self.start_requested:return {'action':'no_runtime_action','executable':False}
        if ownership_readback is None:return {'action':'read_ownership_only','profile':self.lease.profile,'executable':False}
        try:verify_runtime(self.lease,ownership_readback)
        except (TypeError,OwnershipError):return {'action':'no_runtime_action','reason':'ownership unresolved','executable':False}
        return {'action':'request_owned_teardown','profile':self.lease.profile,'endpoint':self.lease.endpoint,
                'may_stop_default':False,'may_delete_unverified_state':False,'executable':False}

    def report(self):
        passed=not self.errors and self.stage==len(self.STAGES)
        return {'contract_passed':passed,'live_certified':False,
                'evidence_kind':self.kind,'complete_vm_and_helper_evidence':False,
                'modeled_finalization_contract_passed':passed,
                'errors':list(self.errors),'stages_accepted':list(self.receipts),
                'download_bytes':self.download,'peak_disk_bytes':self.disk_peak,
                'whole_machine_cpu_window_bound_ns':self.elapsed_ns*self.limits.host_cpus,
                'lifecycle_cpu_certified':False,
                'cpu_cap_enforced':False,'reservation_kind':'capacity-times-wall bound, not an OS CPU limit',
                'executable_entrypoint_available':False}
