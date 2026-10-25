"""Opt-in local tool-boundary recorder; no discovery, execution engine or uploads.

Snapshots cover only explicitly enrolled scopes. The adapter must serialize tool
calls and quiesce other writers; stable sequential reads are not atomic snapshots.
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import time
import uuid

SCHEMA = 'aki-observation-v1'
KINDS = {'source_read','source_search','source_edit','source_execute'}
MAX_FILE = 2 * 1024**2
MAX_TOTAL = 64 * 1024**2
MAX_FILES = 10000
MAX_RETAINED = 256 * 1024**2
MAX_JOURNAL = 64 * 1024**2
MAX_OPERATIONS = 200


class CaptureError(RuntimeError): pass


def sha(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def signature(st): return st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns

def sensitive(parts):
    return any(p.startswith('.') or p.lower() in ('credentials','secrets','id_rsa','id_ed25519')
               or p.lower().endswith(('.pem','.key','.sqlite','.sqlite3')) for p in parts)


class Observation:
    def __init__(self):
        self.output_bytes = None
        self.output_sha256 = None
        self.executor_wall_ns = None
        self.executor_cpu_ns = None
    def output(self, value: bytes):
        if not isinstance(value,bytes):raise TypeError('output must be explicit bytes')
        self.output_bytes=len(value);self.output_sha256=sha(value)
    def executor_metrics(self, *, wall_ns=None, cpu_ns=None):
        for value in (wall_ns,cpu_ns):
            if value is not None and (type(value) is not int or value<0):raise ValueError('nonnegative integer timing required')
        self.executor_wall_ns=wall_ns;self.executor_cpu_ns=cpu_ns


class Recorder:
    def __init__(self, *, root: Path, scopes: list[str], output: Path,
                 allow_collection: bool=False, source_kind: str,
                 declared_revision: str | None=None, store_source_blobs: bool=False,
                 store_tool_requests: bool=False, repository: str | None=None):
        if allow_collection is not True:raise PermissionError('explicit collection opt-in required')
        if os.name!='posix':raise NotImplementedError('recorder requires POSIX directory descriptors')
        if source_kind not in ('synthetic_fixture','public_repository'):raise ValueError('explicit source kind required')
        if source_kind=='public_repository' and (not isinstance(repository,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository)):
            raise ValueError('explicit public owner/repository identity required')
        if declared_revision is not None and not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}',declared_revision):
            raise ValueError('revision must be a commit/tree hash, not free text')
        if root.is_symlink():raise CaptureError('source root may not be a symlink')
        self.root=root.resolve(strict=True)
        if not self.root.is_dir():raise CaptureError('source root must be a directory')
        self.scopes=[]
        for value in scopes:
            p=PurePosixPath(value)
            if p.is_absolute() or '..' in p.parts or not p.parts or str(p)=='.' or sensitive(p.parts):
                raise CaptureError('scope must name an explicit nonsensitive relative file/directory')
            self.scopes.append(str(p))
        if not self.scopes:raise CaptureError('at least one explicit scope is required')
        self.scopes=sorted(set(self.scopes))
        self.output=output.resolve()
        if self.output==self.root or self.output.is_relative_to(self.root):raise CaptureError('logs must be outside source root')
        self.output.mkdir(mode=0o700,parents=True,exist_ok=False)
        self.root_fd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        self.retained_bytes=0
        self.retained_request_bytes=0
        self.store_source_blobs=store_source_blobs
        self.store_tool_requests=store_tool_requests
        self.previous={};self.paths={};self.active=False;self.sequence=0;self.closed=False
        self.journal=self.output/'events.jsonl';self.chain='0'*64;self.metrics={'snapshot_wall_ns':0,'snapshot_cpu_ns':0,'journal_wall_ns':0,'journal_cpu_ns':0,'snapshots':0}
        self._append({'event':'session','schema':SCHEMA,'session_id':uuid.uuid4().hex,
                      'source_kind':source_kind,'repository':repository,'declared_revision':declared_revision,
                      'scope_ids':[sha(p.encode()) for p in self.scopes],
                      'source_blobs_retained':store_source_blobs,'raw_outputs_retained':False,
                      'tool_requests_retained':store_tool_requests,
                      'consistency':'serialized_tools_and_quiescent_source_required',
                      'limits':{'file_bytes':MAX_FILE,'snapshot_bytes':MAX_TOTAL,'files':MAX_FILES,
                                'retained_bytes':MAX_RETAINED,'journal_bytes':MAX_JOURNAL,'operations':MAX_OPERATIONS}})

    def _write_private(self,path,payload):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(payload)

    def _append(self,event):
        wall=time.perf_counter_ns();cpu=time.process_time_ns()
        body={**event,'previous_event_sha256':self.chain};body['event_sha256']=sha(canonical(body))
        payload=canonical(body)+b'\n'
        if (self.journal.stat().st_size if self.journal.exists() else 0)+len(payload)>MAX_JOURNAL:raise CaptureError('journal byte cap exceeded')
        fd=os.open(self.journal,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
        with os.fdopen(fd,'ab') as stream:
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
        self.chain=body['event_sha256']
        self.metrics['journal_wall_ns']+=time.perf_counter_ns()-wall
        self.metrics['journal_cpu_ns']+=time.process_time_ns()-cpu

    def _open_relative(self,rel,*,directory=False):
        parts=PurePosixPath(rel).parts;parent=os.dup(self.root_fd)
        try:
            for part in parts[:-1]:
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
                os.close(parent);parent=child
            return os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|(os.O_DIRECTORY if directory else 0),dir_fd=parent)
        finally:os.close(parent)

    def _inventory(self):
        files={}
        def visit(rel):
            if sensitive(PurePosixPath(rel).parts):raise CaptureError('sensitive/hidden path in scope; narrow enrollment')
            try:fd=self._open_relative(rel)
            except FileNotFoundError:return
            except OSError as exc:raise CaptureError('unreadable or symlink scope') from exc
            try:
                st=os.fstat(fd)
                if stat.S_ISREG(st.st_mode):
                    if st.st_size>MAX_FILE:raise CaptureError('file byte cap exceeded')
                    files[rel]=st
                    if len(files)>MAX_FILES:raise CaptureError('file count cap exceeded')
                elif stat.S_ISDIR(st.st_mode):
                    with os.scandir(fd) as entries:names=sorted(e.name for e in entries)
                    for name in names:visit(rel+'/'+name)
                else:raise CaptureError('special file in enrolled scope')
            finally:os.close(fd)
        for value in self.scopes:visit(value)
        if sum(s.st_size for s in files.values())>MAX_TOTAL:raise CaptureError('snapshot byte cap exceeded')
        return files

    def _snapshot(self):
        wall=time.perf_counter_ns();cpu=time.process_time_ns()
        try:
            inventory=self._inventory();manifest={}
            for rel,expected in sorted(inventory.items()):
                fd=self._open_relative(rel)
                with os.fdopen(fd,'rb') as stream:
                    before=os.fstat(stream.fileno())
                    if signature(before)!=signature(expected):raise CaptureError('source changed during capture')
                    payload=stream.read(MAX_FILE+1);after=os.fstat(stream.fileno())
                if len(payload)>MAX_FILE or signature(before)!=signature(after):raise CaptureError('source changed during capture')
                path_id=sha(rel.encode());content_id=sha(payload)
                manifest[path_id]={'sha256':content_id,'bytes':len(payload),'executable':bool(after.st_mode & 0o111)}
                if self.store_source_blobs:
                    directory=self.output/'source-blobs';directory.mkdir(mode=0o700,exist_ok=True)
                    blob=directory/content_id
                    if not blob.exists():
                        if self.retained_bytes+self.retained_request_bytes+len(payload)>MAX_RETAINED:raise CaptureError('retained-data byte cap exceeded')
                        self._write_private(blob,payload);self.retained_bytes+=len(payload)
                    self.paths[path_id]=rel
            final=self._inventory()
            if inventory.keys()!=final.keys() or any(signature(inventory[p])!=signature(final[p]) for p in inventory):
                raise CaptureError('source changed during capture')
            changed={p:v for p,v in manifest.items() if self.previous.get(p)!=v}
            deleted=sorted(set(self.previous)-set(manifest))
            result={'scoped_tree_sha256':sha(canonical(manifest)),'files':len(manifest),
                    'bytes':sum(v['bytes'] for v in manifest.values()),'changed':changed,'deleted':deleted,
                    'scope_complete':True}
            self.previous=manifest;self.metrics['snapshots']+=1
            return result
        finally:
            self.metrics['snapshot_wall_ns']+=time.perf_counter_ns()-wall
            self.metrics['snapshot_cpu_ns']+=time.process_time_ns()-cpu

    @contextmanager
    def operation(self,kind: str, request: bytes):
        if self.closed or self.active:raise CaptureError('recorder is closed or another tool is active')
        if self.sequence>=MAX_OPERATIONS:raise CaptureError('operation cap exceeded')
        if kind not in KINDS or not isinstance(request,bytes):raise ValueError('supported operation and explicit request bytes required')
        if len(request)>MAX_FILE:raise CaptureError('request byte cap exceeded')
        self.active=True;self.sequence+=1;number=self.sequence;observation=Observation()
        try:
            if self.store_tool_requests:
                directory=self.output/'requests';directory.mkdir(mode=0o700,exist_ok=True)
                path=directory/sha(request)
                if not path.exists():
                    if self.retained_bytes+self.retained_request_bytes+len(request)>MAX_RETAINED:raise CaptureError('retained-data cap exceeded')
                    self._write_private(path,request);self.retained_request_bytes+=len(request)
            try:before=self._snapshot()
            except (CaptureError,OSError):
                self._append({'event':'capture_aborted','operation_id':number,'reason':'source_capture_failed'})
                raise
            if number>1 and (before['changed'] or before['deleted']):
                self._append({'event':'capture_aborted','operation_id':number,'reason':'unobserved_change_between_tools'})
                raise CaptureError('source changed outside a recorded operation')
            self._append({'event':'begin','operation_id':number,'kind':kind,'request_sha256':sha(request),
                          'request_bytes':len(request),'before':before})
            start=time.perf_counter_ns();cpu=time.process_time_ns();error=None
            try:
                yield observation
            except BaseException as exc:
                error=type(exc).__name__
                raise
            finally:
                end=time.perf_counter_ns();observer_cpu=time.process_time_ns()-cpu
                after=None;capture_error=None
                try:after=self._snapshot()
                except (CaptureError,OSError):capture_error='source_capture_failed'
                self._append({'event':'end','operation_id':number,'status':'error' if error else 'ok',
                              'error_type':error,'capture_error':capture_error,'after':after,
                              'observer_start_monotonic_ns':start,'observer_end_monotonic_ns':end,
                              'observer_wall_ns':end-start,'observer_process_cpu_ns':observer_cpu,
                              'output_sha256':observation.output_sha256,'output_bytes':observation.output_bytes,
                              'executor_wall_ns':observation.executor_wall_ns,'executor_cpu_ns':observation.executor_cpu_ns})
                if capture_error and error is None:raise CaptureError(capture_error)
        finally:self.active=False

    def close(self):
        if self.active:raise CaptureError('cannot close during an operation')
        if self.closed:return dict(self.metrics)
        self._append({'event':'session_end','operations_started':self.sequence,
                      'overhead_before_final_event':dict(self.metrics)})
        wall=time.perf_counter_ns();cpu=time.process_time_ns()
        if self.store_source_blobs:self._write_private(self.output/'private-path-map.json',canonical(self.paths))
        os.close(self.root_fd)
        self.metrics['finalization_wall_ns']=time.perf_counter_ns()-wall
        self.metrics['finalization_cpu_ns']=time.process_time_ns()-cpu
        self.metrics['retained_source_bytes']=self.retained_bytes
        self.metrics['retained_request_bytes']=self.retained_request_bytes
        self.closed=True
        return dict(self.metrics)  # includes final journal write; excludes caller serialization


def verify(directory: Path):
    """Validate chain, deltas, evidence references and complete tool boundaries."""
    previous='0'*64;state={};active=None;events=0;closed=False;operations=0;referenced=set();retain=False;requests=False
    if any((directory/name).is_symlink() for name in ('events.jsonl','source-blobs','requests')):raise CaptureError('capture symlink rejected')
    if (directory/'events.jsonl').stat().st_size>MAX_JOURNAL:raise CaptureError('journal byte cap exceeded')
    with (directory/'events.jsonl').open() as stream:
        for line in stream:
            if closed:raise CaptureError('events after session close')
            row=json.loads(line);digest=row.pop('event_sha256')
            if events==0:
                if row.get('event')!='session' or row.get('schema')!=SCHEMA:raise CaptureError('missing schema header')
                retain=row['source_blobs_retained']
                requests=row['tool_requests_retained']
            elif row['event']=='session':raise CaptureError('duplicate session header')
            if row['event']=='capture_aborted':raise CaptureError('source capture aborted')
            if row['previous_event_sha256']!=previous or sha(canonical(row))!=digest:raise CaptureError('journal integrity failure')
            previous=digest;events+=1
            for field in ('before','after'):
                snap=row.get(field)
                if snap is None:continue
                if len(snap['changed'])>MAX_FILES or not all(re.fullmatch('[a-f0-9]{64}',p) for p in [*snap['changed'],*snap['deleted']]):raise CaptureError('invalid source path IDs')
                if not all(re.fullmatch('[a-f0-9]{64}',v['sha256']) and type(v['bytes']) is int and 0<=v['bytes']<=MAX_FILE for v in snap['changed'].values()):raise CaptureError('invalid source entries')
                for path in snap['deleted']:state.pop(path,None)
                state.update(snap['changed'])
                referenced.update(v['sha256'] for v in snap['changed'].values())
                if sha(canonical(state))!=snap['scoped_tree_sha256']:raise CaptureError('source delta mismatch')
                if len(state)!=snap['files'] or sum(v['bytes'] for v in state.values())!=snap['bytes']:raise CaptureError('source counts mismatch')
            if row['event']=='begin':
                if active is not None:raise CaptureError('overlapping operations')
                active=row['operation_id']
                if not re.fullmatch('[a-f0-9]{64}',row['request_sha256']):raise CaptureError('invalid request digest')
                if requests:
                    path=directory/'requests'/row['request_sha256']
                    if path.is_symlink() or not path.is_file() or path.stat().st_size>MAX_FILE or sha(path.read_bytes())!=row['request_sha256'] or path.stat().st_size!=row['request_bytes']:
                        raise CaptureError('missing or corrupt request blob')
            elif row['event']=='end':
                if row['operation_id']!=active:raise CaptureError('unmatched operation end')
                if row['observer_end_monotonic_ns']-row['observer_start_monotonic_ns']!=row['observer_wall_ns']:raise CaptureError('invalid observer timing')
                if row['capture_error'] or row['after'] is None:raise CaptureError('incomplete source boundary')
                if row['status']=='ok' and row['output_sha256'] is None:raise CaptureError('successful tool omitted output identity')
                active=None;operations+=1
            elif row['event']=='session_end':
                if row['operations_started']!=operations:raise CaptureError('operation count mismatch')
                closed=True
    if active is not None or not closed:raise CaptureError('incomplete/crashed session')
    if retain and any(not (directory/'source-blobs'/h).is_file() for h in referenced):raise CaptureError('missing source blob')
    for blob in (directory/'source-blobs').glob('*'):
        if blob.is_symlink() or not blob.is_file() or blob.stat().st_size>MAX_FILE:raise CaptureError('invalid source blob')
        if sha(blob.read_bytes())!=blob.name:raise CaptureError('source blob mismatch')
    return {'schema':SCHEMA,'events':events,'complete_operations':operations,'final_scoped_tree_sha256':sha(canonical(state)),'integrity_verified':True}
