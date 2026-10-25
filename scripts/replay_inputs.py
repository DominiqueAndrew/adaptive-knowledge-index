"""Bounded inert public-data IO shared by phase-four scripts."""
import hashlib
import io
import json
from pathlib import Path
import resource
import time
import urllib.request

CAP = 2 * 1024**3
CPU_CAP = 30 * 60


class Budget:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root / 'budget.json'
        self.state = json.loads(self.file.read_text()) if self.file.exists() else {'downloaded_bytes': 0, 'cpu_seconds': 0, 'requests': []}
        self.started = time.process_time()
        remaining = max(1, int(CPU_CAP - self.state['cpu_seconds']))
        current = int(resource.getrusage(resource.RUSAGE_SELF).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_stime)
        resource.setrlimit(resource.RLIMIT_CPU, (current + remaining, current + remaining + 1))

    def check(self):
        if self.state['downloaded_bytes'] > CAP or self.state['cpu_seconds'] + time.process_time() - self.started >= CPU_CAP:
            raise RuntimeError('registered resource cap reached')

    def save(self):
        self.check()
        state = dict(self.state)
        state['cpu_seconds'] += time.process_time() - self.started
        self.file.write_text(json.dumps(state, indent=2) + '\n')

    def fetch(self, url, *, start=None, count=None, limit=64*1024**2):
        key = hashlib.sha256((url + f'|{start}|{count}').encode()).hexdigest()
        path = self.root / 'http-cache' / key
        if path.exists(): return path.read_bytes()
        self.check()
        limit = min(limit, CAP - self.state['downloaded_bytes'])
        if count is not None and count > limit: raise RuntimeError('download would exceed registered cap')
        headers = {}
        if start is not None:
            headers['Range'] = f'bytes={start}-{start+count-1}'
            url += ('&' if '?' in url else '?') + f'range={start}-{start+count-1}'
        body = bytearray()
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
            if start is not None and (response.status != 206 or not response.headers.get('Content-Range','').startswith(f'bytes {start}-{start+count-1}/')):
                raise ValueError('range not honored')
            while True:
                allowed = min(1024**2, limit - len(body))
                if allowed <= 0:
                    # Do not consume another byte outside the cap.
                    if count is not None and len(body)==count: break
                    raise RuntimeError('per-file or global byte cap reached')
                chunk = response.read(allowed)
                if not chunk: break
                body.extend(chunk); self.state['downloaded_bytes'] += len(chunk)
                self.save()
        if count is not None and len(body) != count: raise ValueError('short range')
        self.state['requests'].append({'key':key,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body);self.save()
        return bytes(body)


class RemoteParquet(io.RawIOBase):
    def __init__(self, budget, url):
        self.budget, self.url, self.pos = budget, url, 0
        with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=60) as r:
            self.size = int(r.headers['Content-Length'])
    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self,n,w=0):
        self.pos = n if w==0 else self.pos+n if w==1 else self.size+n
        if not 0<=self.pos<=self.size: raise ValueError('seek outside file')
        return self.pos
    def read(self,n=-1):
        n=self.size-self.pos if n<0 else min(n,self.size-self.pos)
        if not n:return b''
        data=self.budget.fetch(self.url,start=self.pos,count=n,limit=150*1024**2)
        self.pos+=len(data);return data
