"""Python-3.5-compatible offline controls. Importing this file performs no work.

Only the immutable base interpreter executes. /env holds Python library data;
all writable mounts stay noexec. Host approval/isolation checks are still required.
"""
import base64
import hashlib
import json
import os
import re
import stat
import sys

PYTHON = '/usr/local/bin/python3'
BOOT = '/env/bootstrap'
SITE = '/env/site'
META = '/env/project-metadata'
MAX_FILE = 2 * 1024 * 1024
MAX_SOURCE = 64 * 1024 * 1024


def paths(mode):
    if mode == 'base':
        return []
    if mode == 'bootstrap':
        return [BOOT]
    if mode == 'runtime':
        return [SITE, BOOT, META, '/workspace']
    raise ValueError('unsupported import profile')


def module_command(module, arguments, mode='runtime'):
    if module not in ('pip', 'pytest'):
        raise ValueError('unsupported module dispatch')
    code = ('import runpy,sys; sys.path[:0]=' + repr(paths(mode)) + '; '
            'sys.argv=[' + repr(module) + ']+sys.argv[1:]; '
            'runpy.run_module(' + repr(module) + ',run_name="__main__")')
    return [PYTHON, '-I', '-B', '-c', code] + list(arguments)


def setup_steps():
    """Fixed commands; never invoke /env/bin, pip wrappers, venv or a shell."""
    pip = ['install', '--no-index', '--no-deps', '--no-cache-dir', '--no-compile',
           '--disable-pip-version-check', '--require-hashes', '--find-links=/packages']
    project = ('import runpy,sys; sys.path[:0]=' + repr(paths('runtime')) + '; '
               'sys.argv=["/workspace/setup.py","egg_info","--egg-base",' + repr(META) + ']; '
               'runpy.run_path("/workspace/setup.py",run_name="__main__")')
    cli = ('import sys; sys.path[:0]=' + repr(paths('runtime')) + '; '
           'sys.argv=["b2","version"]; from b2.console_tool import main; main()')
    imports = ('import sys; sys.path[:0]=' + repr(paths('runtime')) + '; '
               'import arrow,logfury,requests,six,tqdm,pytest,mock,pyflakes,yapf; '
               'print("AKI_DEPENDENCY_IMPORTS_OK")')
    return [
        ('bootstrap', module_command('pip', pip + ['--target', BOOT, '-r', '/control/bootstrap.lock'], 'base')),
        ('dependencies', module_command('pip', pip + ['--no-build-isolation', '--no-use-pep517',
                         '--target', SITE, '-r', '/control/runtime.lock'], 'bootstrap')),
        ('dependency_check', module_command('pip', ['check'])),
        ('imports', [PYTHON, '-I', '-B', '-c', imports]),
        ('project_metadata', [PYTHON, '-I', '-B', '-c', project]),
        ('project_dependency_check', module_command('pip', ['check'])),
        ('cli_version', [PYTHON, '-I', '-B', '-c', cli]),
        ('unit_collection', module_command('pytest', ['--collect-only', '-q', '-p', 'no:cacheprovider', 'test'])),
    ]


def clean_environment():
    # Explicitly constructed; never forward owner/model/service credentials.
    return {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': '/tmp', 'TMPDIR': '/tmp',
            'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONPATH': BOOT,  # Only for pip's subprocess build of the reviewed Arrow archive.
            'PIP_CONFIG_FILE': '/dev/null', 'PIP_NO_INDEX': '1',
            'PIP_DISABLE_PIP_VERSION_CHECK': '1', 'PIP_NO_CACHE_DIR': '1',
            'B2_ACCOUNT_INFO': '/tmp/aki-empty-account.sqlite'}


def check_mounts(lines, uid, version):
    if uid != 65534 or tuple(version[:3]) != (3, 5, 10):
        raise ValueError('wrong runtime user or Python version')
    mounts = {}
    for line in lines:
        fields = line.split()
        if len(fields) < 4:
            raise ValueError('malformed mount record')
        name = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), fields[1])
        mounts[name] = set(fields[3].split(','))
    if '/' not in mounts or 'ro' not in mounts['/']:
        raise ValueError('root must be read-only')
    for name in ('/env', '/workspace', '/tmp'):
        if not {'rw', 'nosuid', 'nodev', 'noexec'}.issubset(mounts.get(name, set())):
            raise ValueError('writable tmpfs restrictions missing: ' + name)
    covering = [m for m in mounts if PYTHON == m or PYTHON.startswith(m.rstrip('/') + '/')]
    if not covering or 'noexec' in mounts[max(covering, key=len)]:
        raise ValueError('base interpreter cannot execute')
    return True


def validate_source(rows):
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('source inventory cap')
    output = []; seen = set(); total = 0
    for row in rows:
        name = row['path']; parts = name.split('/')
        if name.startswith('/') or any(p in ('', '.', '..') or p.startswith('.') for p in parts):
            raise ValueError('invalid source path')
        if '\\' in name or '\x00' in name or name.casefold() in seen:
            raise ValueError('duplicate or ambiguous source path')
        data = base64.b64decode(row['data'].encode('ascii'), validate=True)
        total += len(data)
        if len(data) > MAX_FILE or total > MAX_SOURCE:
            raise ValueError('source byte cap')
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('source hash mismatch')
        mode = row['mode']
        if not isinstance(mode, int) or mode & ~0o777:
            raise ValueError('unsafe source mode')
        seen.add(name.casefold()); output.append((name, data, mode & 0o755))
    for name, _, _ in output:
        parts = name.casefold().split('/')
        if any('/'.join(parts[:i]) in seen for i in range(1, len(parts))):
            raise ValueError('source file/directory collision')
    return output


def populate(root, rows):
    files = validate_source(rows)  # Validate the entire request before any write.
    if os.path.islink(root) or os.listdir(root):
        raise ValueError('source root must be an empty real directory')
    for name, data, mode in files:
        target = os.path.join(root, name); parent = os.path.dirname(target)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        with open(target, 'xb') as stream:
            stream.write(data)
        os.chmod(target, mode)
    return {'files': len(files), 'bytes': sum(len(data) for _, data, _ in files)}


def verify_artifacts(directory, records):
    expected = set()
    for record in records:
        name = record['filename']
        if os.path.basename(name) != name or name in expected:
            raise ValueError('invalid artifact name')
        expected.add(name); path = os.path.join(directory, name)
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size != record['size']:
            raise ValueError('artifact type or size mismatch')
        h = hashlib.sha256()
        with open(path, 'rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(block)
        if h.hexdigest() != record['sha256']:
            raise ValueError('artifact hash mismatch')
    if set(os.listdir(directory)) != expected:
        raise ValueError('unapproved artifact in mounted directory')
    return True


def prepare_directories():
    for name in (BOOT, SITE, META):
        if os.path.exists(name):
            raise ValueError('partial environment must not be reused')
    for name in (BOOT, SITE, META):
        os.mkdir(name)


if __name__ == '__main__':
    if sys.argv[1:] in ([], ['plan']):
        print(json.dumps({'steps': setup_steps(), 'environment': clean_environment()}, indent=2))
    elif sys.argv[1:] in (['preflight'], ['populate']):
        with open('/proc/mounts') as stream:
            check_mounts(stream.read().splitlines(), os.getuid(), sys.version_info)
        if set(os.listdir('/sys/class/net')) != {'lo'}:
            raise ValueError('unexpected network interface')
        if sys.argv[1] == 'preflight':
            with open('/control/approved-artifacts.json') as stream:
                records = json.load(stream)
            verify_artifacts('/packages', records)
            prepare_directories()
            print(json.dumps({'status': 'preflight_passed', 'artifacts': len(records)}))
        else:
            payload = sys.stdin.read(2*1024*1024+1)
            if len(payload) > 2*1024*1024:
                raise ValueError('source transfer request cap')
            print(json.dumps(populate('/workspace', json.loads(payload))))
    else:
        raise ValueError('unsupported control operation')
