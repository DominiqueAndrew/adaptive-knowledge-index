"""Pure ownership/isolation gates. No VM, Docker, shell, network or file writes."""
from dataclasses import dataclass
from pathlib import Path
import re


class OwnershipError(ValueError):pass


@dataclass(frozen=True)
class RuntimeLease:
    profile:str
    attempt:str
    endpoint:str
    readonly_mounts:tuple[str,...]
    cpus:int=2
    memory_bytes:int=2*1024**3
    runtime:str='docker'


def propose_lease(*,profile,attempt,endpoint,attempt_root,workspace,existing_profiles,runtime='docker'):
    if runtime not in ('docker','none'):raise OwnershipError('unsupported runtime')
    if not re.fullmatch(r'aki-[a-z0-9-]{1,40}',profile) or profile in existing_profiles:
        raise OwnershipError('new dedicated AKI profile required')
    if not re.fullmatch(r'[a-f0-9]{32}',attempt):raise OwnershipError('fresh attempt identity required')
    if not endpoint.startswith('unix:///') or '..' in Path(endpoint[7:]).parts or profile not in Path(endpoint[7:]).parts:
        raise OwnershipError('dedicated local socket required')
    root=Path(attempt_root)
    if not root.is_absolute() or '..' in root.parts:raise OwnershipError('explicit attempt root required')
    if root.resolve()==Path(workspace).resolve()/'scratch' or not root.resolve().is_relative_to(Path(workspace).resolve()/'scratch'):
        raise OwnershipError('mounts must remain inside dedicated project scratch')
    mounts=tuple(str(root/name) for name in ('control','packages')) if runtime=='docker' else ()
    return RuntimeLease(profile,attempt,endpoint,mounts,runtime=runtime)


def verify_runtime(lease,observed,*,created_container_ids=frozenset()):
    expected={'profile':lease.profile,'owner':'adaptive-knowledge-index','attempt':lease.attempt,
              'endpoint':lease.endpoint,'runtime':lease.runtime,'arch':'aarch64','cpus':lease.cpus,'memory_bytes':lease.memory_bytes,
              'readonly_mounts':list(lease.readonly_mounts),'writable_mounts':[],
              'ssh_agent':False,'rosetta':False,'binfmt_handlers':[],
              'public_address':False,'port_forwarder':'none','template':False,'kubernetes':False}
    if any(observed.get(k)!=v for k,v in expected.items()):raise OwnershipError('runtime ownership/isolation mismatch')
    containers=observed.get('containers')
    if not isinstance(containers,list) or any(not isinstance(c,dict) for c in containers):raise OwnershipError('complete container inventory required')
    if lease.runtime=='none' and (containers or created_container_ids):raise OwnershipError('runtime none must have no containers')
    ids=[c.get('id') for c in containers]
    if any(not isinstance(i,str) or not re.fullmatch(r'[a-f0-9]{64}',i) for i in ids):raise OwnershipError('invalid container identity')
    if len(ids)!=len(set(ids)):raise OwnershipError('duplicate inventory identity')
    for c in containers:
        if not isinstance(c,dict) or not re.fullmatch(r'[a-f0-9]{64}',c.get('id','')) or c.get('id') not in created_container_ids or c.get('attempt')!=lease.attempt:
            raise OwnershipError('foreign or unproven container; no engine cleanup authorized')
    return True


def cleanup_plan(lease,observed,*,created_container_ids):
    verify_runtime(lease,observed,created_container_ids=created_container_ids)
    return {'profile':lease.profile,'endpoint':lease.endpoint,'container_ids':sorted(created_container_ids),
            'may_stop_owned_profile':True,'may_stop_default_profile':False,'executable':False}
