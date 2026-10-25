"""Static, side-effect-free validation and construction of the next setup plan."""
import hashlib
import json
from pathlib import Path
import re


class PlanError(ValueError):
    pass


def sha(value):
    return 'sha256:'+hashlib.sha256(value).hexdigest()


def verify_loaded_image(expected_config, expected_digest, exported_config, inspect):
    if sha(expected_config) != expected_digest or sha(exported_config) != expected_digest:
        raise PlanError('original config blob does not match its pinned digest')
    config = json.loads(expected_config)
    if (config.get('architecture') != 'arm64' or config.get('os') != 'linux'
            or inspect.get('Architecture') != 'arm64' or inspect.get('Os') != 'linux'
            or inspect.get('RootFS', {}).get('Layers') != config.get('rootfs', {}).get('diff_ids')
            or not re.fullmatch(r'sha256:[a-f0-9]{64}', inspect.get('Id', ''))):
        raise PlanError('loaded image architecture, layers or identity is invalid')
    # Docker 29 may report a newly converted manifest ID and omit legacy defaults.
    # Exact exported config and layer identities are the authoritative checks.
    return {'pinned_config': expected_digest, 'local_manifest': inspect['Id']}


def render_locks(proposal):
    bootstrap = []; runtime = []; approved = []; seen = set()
    for row in proposal['candidate_dependencies']['packages']:
        name = row['name']; version = row['version']; artifact = row['artifact']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', name):
            raise PlanError('invalid package name')
        key = re.sub(r'[-_.]+', '-', name).lower()
        if key in seen or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.!+_-]*', version):
            raise PlanError('duplicate package or invalid version')
        seen.add(key)
        filename = artifact['filename']
        if Path(filename).name != filename or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.+-]*', filename):
            raise PlanError('artifact path is not a safe basename')
        if not re.fullmatch(r'[a-f0-9]{64}', artifact['sha256']) or type(artifact['size']) is not int or artifact['size'] <= 0:
            raise PlanError('artifact identity missing')
        line = name+'=='+version+' --hash=sha256:'+artifact['sha256']
        (bootstrap if key in {'pip', 'setuptools', 'wheel'} else runtime).append(line)
        approved.append({k: artifact[k] for k in ('filename', 'sha256', 'size')})
    if len(bootstrap) != 3:
        raise PlanError('all three pinned bootstrap tools are required')
    return {'bootstrap.lock': '\n'.join(bootstrap)+'\n', 'runtime.lock': '\n'.join(runtime)+'\n',
            'approved-artifacts.json': json.dumps(approved, sort_keys=True)}


def expected_container_environment(config_blob, config_digest, overrides):
    """Include public image defaults only after checking the pinned config blob.

    Docker merges image Env with explicit --env flags. Comparing only overrides
    would incorrectly reject the frozen image's version metadata. Client-injected
    proxy settings still fail the exact actual-container comparison.
    """
    if sha(config_blob) != config_digest:
        raise PlanError('unverified image environment')
    environment = {}
    for item in json.loads(config_blob).get('config', {}).get('Env', []):
        if not isinstance(item, str) or '=' not in item:
            raise PlanError('invalid image environment')
        key, value = item.split('=', 1)
        if key in environment or not re.fullmatch('[A-Z_][A-Z_0-9]*', key):
            raise PlanError('duplicate or invalid image environment key')
        environment[key] = value
    environment.update(overrides)
    return environment


def container_command(attempt, image, root, workspace, environment):
    if not re.fullmatch(r'[a-f0-9]{32}', attempt) or not re.fullmatch(r'sha256:[a-f0-9]{64}', image):
        raise PlanError('explicit immutable image and attempt identity required')
    root = Path(root).resolve(); workspace = Path(workspace).resolve()
    if root == workspace or not root.is_relative_to(workspace):
        raise PlanError('mount sources must be inside a dedicated attempt directory')
    if ',' in str(root) or '\n' in str(root):
        raise PlanError('ambiguous mount source')
    args = ['docker', '--context', 'colima', 'create', '--name', 'aki420-'+attempt,
            '--label', 'org.aki.attempt='+attempt, '--network', 'none', '--user', '65534:65534',
            '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
            '--cpus', '1', '--memory', '1g', '--memory-swap', '1g', '--pids-limit', '64']
    for path, size in [('/env', '256m'), ('/workspace', '64m'), ('/tmp', '128m')]:
        args += ['--tmpfs', path+':rw,nosuid,nodev,noexec,size='+size+',uid=65534,gid=65534']
    for name in ('control', 'packages'):
        args += ['--mount', 'type=bind,source='+str(root/name)+',target=/'+name+',readonly']
    for key, value in sorted(environment.items()):
        if not re.fullmatch('[A-Z_][A-Z_0-9]*', key) or '\x00' in value or '\n' in value:
            raise PlanError('invalid explicit guest environment')
        args += ['--env', key+'='+value]
    args += ['--workdir', '/workspace', image, '/usr/local/bin/python3', '-I', '-B', '/control/idle.py']
    return args


def verify_container(info, attempt, image, root, expected_environment):
    root = Path(root).absolute(); host = info.get('HostConfig', {}); config = info.get('Config', {})
    if (config.get('Labels', {}).get('org.aki.attempt') != attempt or info.get('Image') != image
            or config.get('User') != '65534:65534' or host.get('Privileged') is not False
            or host.get('ReadonlyRootfs') is not True or host.get('NetworkMode') != 'none'
            or host.get('CapAdd') or {s.upper() for s in host.get('CapDrop', [])} != {'ALL'}
            or not any(s in ('no-new-privileges:true', 'no-new-privileges=true') for s in host.get('SecurityOpt', []))
            or any(s not in ('no-new-privileges:true', 'no-new-privileges=true') for s in host.get('SecurityOpt', []))
            or host.get('PidMode') == 'host' or host.get('IpcMode') == 'host'
            or host.get('UTSMode') == 'host' or host.get('Devices') or host.get('DeviceRequests')
            or host.get('PortBindings') or host.get('RestartPolicy', {}).get('Name', '') not in ('', 'no')
            or host.get('NanoCpus') != 1_000_000_000 or host.get('Memory') != 1024**3
            or host.get('MemorySwap') != 1024**3 or host.get('PidsLimit') != 64):
        raise PlanError('container ownership or confinement mismatch')
    expected = {('/'+name, str(root/name), False, 'bind') for name in ('control', 'packages')}
    actual = {(m.get('Destination'), m.get('Source'), m.get('RW'), m.get('Type'))
              for m in info.get('Mounts', []) if m.get('Type') != 'tmpfs'}
    if actual != expected:
        raise PlanError('unexpected or writable host mount')
    environment = {}
    for item in config.get('Env', []):
        if '=' not in item or item.split('=', 1)[0] in environment:
            raise PlanError('invalid or duplicate guest environment')
        key, value = item.split('=', 1); environment[key] = value
    if environment != expected_environment:
        raise PlanError('unexpected guest environment; values are not logged')
    tmpfs = host.get('Tmpfs', {})
    if set(tmpfs) != {'/env', '/workspace', '/tmp'}:
        raise PlanError('unexpected tmpfs inventory')
    for path, size in [('/env', '256m'), ('/workspace', '64m'), ('/tmp', '128m')]:
        options = tmpfs[path].split(','); keys = [o.split('=')[0] for o in options]
        if len(set(keys)) != len(keys) or {'exec', 'suid', 'dev', 'ro'} & set(options):
            raise PlanError('contradictory tmpfs flags')
        size_option = next((o.split('=', 1)[1] for o in options if o.startswith('size=')), '')
        match = re.fullmatch(r'(\d+)([kmg]?)', size_option.lower())
        size_bytes = int(match[1]) * {'': 1, 'k': 1024, 'm': 1024**2, 'g': 1024**3}[match[2]] if match else None
        if (not {'rw', 'nosuid', 'nodev', 'noexec', 'uid=65534', 'gid=65534'}.issubset(set(options))
                or size_bytes != int(size[:-1])*1024**2):
            raise PlanError('tmpfs restrictions missing')
    return True


def owned_container_removal(info, attempt, created_ids):
    if (info.get('Config', {}).get('Labels', {}).get('org.aki.attempt') != attempt
            or not re.fullmatch('[a-f0-9]{64}', info.get('Id', ''))
            or info['Id'] not in created_ids):
        raise PlanError('cleanup ownership is not proven')
    return ['docker', '--context', 'colima', 'rm', '-f', info['Id']]
