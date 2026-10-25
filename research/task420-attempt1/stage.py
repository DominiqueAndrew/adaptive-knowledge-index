#!/usr/bin/env python3
"""One-shot, bounded artifact staging; never installs or executes fetched code."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import time
import urllib.request

ROOT = Path('scratch/pilot420-attempt')
CAP = 512 * 1024**2
DISK = 3 * 1024**3
START = time.monotonic()


def main():
    ROOT.mkdir(mode=0o700, exist_ok=False)
    proposal = json.loads(Path('results/runtime/task420-setup-proposal.json').read_text())
    state = {'status': 'staging', 'download_bytes': 0, 'files': [],
             'start_unix': time.time(), 'host_cpu_seconds': 0, 'expanded_layer_bytes': 0}
    resource.setrlimit(resource.RLIMIT_CPU, (295, 300))

    def save():
        state['elapsed_seconds'] = time.monotonic() - START
        state['host_cpu_seconds'] = time.process_time()
        (ROOT/'ledger.json').write_text(json.dumps(state, indent=2)+'\n')
        if state['elapsed_seconds'] > 600 or state['host_cpu_seconds'] > 290:
            raise RuntimeError('setup time ceiling')

    def fetch(url, *, expected=None, size=None, dest=None, headers=None, cap=1024*1024):
        limit = min(size if size is not None else cap, CAP-state['download_bytes'])
        if size is not None and limit < size:
            raise RuntimeError('transfer ceiling')
        data = bytearray() if dest is None else None
        out = dest.open('xb') if dest else None
        h = hashlib.sha256(); count = 0
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=30) as response:
                while count < limit:
                    block = response.read(min(1024*1024, limit-count))
                    if not block:
                        break
                    count += len(block); state['download_bytes'] += len(block); h.update(block)
                    if out: out.write(block)
                    else: data.extend(block)
                    save()
                if size is None and count == limit:
                    raise RuntimeError('metadata ceiling')
            if size is not None and count != size:
                raise RuntimeError('artifact size mismatch')
            if expected and h.hexdigest() != expected.removeprefix('sha256:'):
                raise RuntimeError('artifact digest mismatch')
        finally:
            if out: out.close()
        state['files'].append({'url': url, 'bytes': count, 'sha256': h.hexdigest()})
        save()
        return bytes(data) if data is not None else None

    try:
        # Anonymous registry bearer stays in memory and is never recorded.
        token = json.loads(fetch('https://auth.docker.io/token?service=registry.docker.io&scope=repository:library/python:pull'))['token']
        headers = {'Authorization': 'Bearer '+token,
                   'Accept': 'application/vnd.docker.distribution.manifest.v2+json'}
        digest = proposal['image']['manifest_digest']
        manifest = json.loads(fetch('https://registry-1.docker.io/v2/library/python/manifests/'+digest,
                                    expected=digest, headers=headers))
        conf = manifest['config']
        config_bytes = fetch('https://registry-1.docker.io/v2/library/python/blobs/'+conf['digest'],
                             expected=conf['digest'], size=conf['size'], headers=headers)
        config = json.loads(config_bytes)
        assert config['architecture'] == 'arm64' and config['os'] == 'linux'
        assert sum(x['size'] for x in manifest['layers']) == proposal['image']['compressed_layer_bytes']
        image = ROOT/'image'; image.mkdir()
        config_name = conf['digest'].split(':')[1]+'.json'
        (image/config_name).write_bytes(config_bytes)
        layer_names = []
        for index, layer in enumerate(manifest['layers']):
            compressed = ROOT/'current-layer.gz'
            fetch('https://registry-1.docker.io/v2/library/python/blobs/'+layer['digest'],
                  expected=layer['digest'], size=layer['size'], dest=compressed, headers=headers)
            name = str(index)+'/layer.tar'; target = image/name; target.parent.mkdir()
            h = hashlib.sha256()
            with gzip.open(compressed, 'rb') as source, target.open('xb') as out:
                while True:
                    block = source.read(1024*1024)
                    if not block: break
                    state['expanded_layer_bytes'] += len(block)
                    if state['expanded_layer_bytes'] > 1024**3:
                        raise RuntimeError('expanded image exceeds reserved disk allocation')
                    out.write(block); h.update(block); save()
            assert 'sha256:'+h.hexdigest() == config['rootfs']['diff_ids'][index]
            compressed.unlink(); layer_names.append(name)
        # Docker-save format; the approved importer streams it without a second disk copy.
        (image/'manifest.json').write_text(json.dumps([{'Config':config_name,
            'RepoTags':['aki-task420-reviewed:attempt1'], 'Layers':layer_names}]))
        packages = ROOT/'packages'; packages.mkdir()
        for row in proposal['candidate_dependencies']['packages']:
            f = row['artifact']
            if not f['url'].startswith('https://files.pythonhosted.org/'):
                raise ValueError('artifact source outside approved host')
            fetch(f['url'], expected=f['sha256'], size=f['size'], dest=packages/f['filename'])
        state['status'] = 'staged_verified_not_executed'
        state['image_config_id'] = conf['digest']
        state['image_manifest_digest'] = digest
        save()
    except BaseException as exc:
        state['status']='failed';state['error_type']=type(exc).__name__;state['error']=str(exc)[:200]
        save();raise
    print(json.dumps({k:v for k,v in state.items() if k!='files'},indent=2))


if __name__ == '__main__':
    main()
