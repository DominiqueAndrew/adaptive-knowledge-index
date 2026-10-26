"""Bounded Python 3.5 guest adapter. No shell or arbitrary command dispatch."""
import base64
import hashlib
import json
import os
import resource
import signal
import stat
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, '/control')
import control


def assert_quiescent(proc_root='/proc',current_pid=None):
    """Check this container's PID namespace only; reject surviving tool children."""
    current_pid=os.getpid() if current_pid is None else current_pid
    for name in os.listdir(proc_root):
        if not name.isdigit() or int(name) in (1,current_pid):continue
        try:
            with open(os.path.join(proc_root,name,'stat')) as stream:text=stream.read()
        except IOError:raise ValueError('process inventory unstable')
        fields=text.rsplit(')',1)[-1].split()
        if not fields or fields[0]!='Z':raise ValueError('unexpected live process at source boundary')


def source_path(root, name):
    if not isinstance(name, str) or any(p.startswith('.') or not p for p in name.split('/')) or '\\' in name:
        raise ValueError('invalid source path')
    path = os.path.join(root, name)
    current = root
    for part in name.split('/'):
        current = os.path.join(current, part)
        if os.path.islink(current): raise ValueError('source symlink')
    if not os.path.abspath(path).startswith(root+'/'): raise ValueError('scope escape')
    return path


def snapshot(root):
    rows = []; total = 0
    for directory, directories, files in os.walk(root):
        if any(os.path.islink(os.path.join(directory, d)) for d in directories): raise ValueError('directory symlink')
        directories[:] = sorted(d for d in directories if not d.startswith('.') and d != '__pycache__')
        for filename in sorted(files):
            if filename.startswith('.') or filename.endswith(('.pyc', '.pyo')): continue
            path = os.path.join(directory, filename); info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or info.st_size > control.MAX_FILE: raise ValueError('source type/size')
            with open(path, 'rb') as stream: data = stream.read(control.MAX_FILE+1)
            total += len(data)
            if total > control.MAX_SOURCE or len(rows) >= 10000: raise ValueError('snapshot cap')
            rows.append({'path': os.path.relpath(path, root), 'data': base64.b64encode(data).decode('ascii'),
                         'sha256': hashlib.sha256(data).hexdigest(), 'mode': info.st_mode & 0o777})
    return rows


def execute(root, fixture):
    if fixture:
        code = 'import runpy; assert runpy.run_path("/tmp/aki-fixture/example.py")["VALUE"] == 2; print("FIXTURE_OK")'
        argv = [control.PYTHON, '-I', '-B', '-c', code]
    else:
        argv = control.module_command('pytest', ['--collect-only', '-q', '-p', 'no:cacheprovider', 'test'])
    # Output is a bounded regular temporary file, never an unbounded pipe buffer.
    with tempfile.TemporaryFile() as output:
        def limits(): resource.setrlimit(resource.RLIMIT_FSIZE, (1024*1024, 1024*1024))
        p = subprocess.Popen(argv, cwd=root, env=control.clean_environment(), stdout=output,
                             stderr=subprocess.STDOUT, preexec_fn=limits,start_new_session=True)
        try:
            code = p.wait(timeout=25)
        except subprocess.TimeoutExpired:
            raise ValueError('execute timeout')
        finally:
            try:os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            if p.poll() is None:p.wait(timeout=2)
        output.seek(0); data = output.read(1024*1024+1)
        if len(data) > 1024*1024: raise ValueError('execute output cap')
    return {'exit_code': code, 'output': data.decode('utf-8', 'replace')}


def dispatch(request, root, fixture):
    op = request['op']
    if op == 'snapshot': return snapshot(root)
    if op == 'read':
        path = source_path(root, request['path'])
        with open(path, 'rb') as stream: data = stream.read(control.MAX_FILE+1)
        if len(data) > control.MAX_FILE: raise ValueError('read cap')
        lines = data.decode('utf-8').splitlines(True)
        start = request.get('start', 1); end = request.get('end', min(len(lines), 200))
        if type(start) is not int or type(end) is not int or not 1 <= start <= end or end-start >= 200: raise ValueError('line cap')
        return {'path': request['path'], 'sha256': hashlib.sha256(data).hexdigest(), 'text': ''.join(lines[start-1:end])}
    if op == 'edit':
        path = source_path(root, request['path']); old = request['old']; new = request['new']
        if not old or len(new.encode('utf-8')) > 65536: raise ValueError('edit cap')
        with open(path) as stream: text = stream.read(control.MAX_FILE+1)
        if len(text.encode('utf-8')) > control.MAX_FILE or text.count(old) != 1: raise ValueError('edit must match once')
        text = text.replace(old, new, 1)
        if len(text.encode('utf-8')) > control.MAX_FILE: raise ValueError('file cap')
        with open(path, 'w') as stream: stream.write(text)
        return {'path': request['path'], 'changed': True}
    if op == 'execute': return execute(root, fixture)
    raise ValueError('unsupported operation')


if __name__ == '__main__':
    fixture = sys.argv[1:] == ['fixture']
    if not fixture and sys.argv[1:] != ['public']: raise ValueError('explicit scope required')
    with open('/proc/mounts') as stream: control.check_mounts(stream.read().splitlines(), os.getuid(), sys.version_info)
    root = '/tmp/aki-fixture' if fixture else '/workspace'
    payload = sys.stdin.read(2*1024*1024+1)
    if len(payload) > 2*1024*1024: raise ValueError('request cap')
    request = json.loads(payload)
    assert_quiescent()
    if fixture and request == {'op': 'initialize'}:
        os.mkdir(root)
        with open(root+'/example.py', 'w') as stream: stream.write('VALUE = 1\n')
        request = {'op': 'snapshot'}
    started = time.monotonic(); cpu = time.process_time(); child = resource.getrusage(resource.RUSAGE_CHILDREN)
    value = dispatch(request, root, fixture)
    assert_quiescent()
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {'result': value, 'wall_ns': int((time.monotonic()-started)*1e9),
              'cpu_ns': int((time.process_time()-cpu+after.ru_utime+after.ru_stime-child.ru_utime-child.ru_stime)*1e9)}
    encoded = json.dumps(result)
    if len(encoded.encode('utf-8')) > 2*1024*1024: raise ValueError('response cap')
    print(encoded)
