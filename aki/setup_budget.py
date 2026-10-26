"""Durable, single-owner resource allowance shared by authorized setup retries."""
import fcntl
import json
from pathlib import Path


class SharedBudget:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.lock=(self.root/'budget.lock').open('a')
        fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.path=self.root/'budget.json'
        if self.path.exists():self.state=json.loads(self.path.read_text())
        else:
            self.state={'download_limit':512*1024**2,'disk_limit':3*1024**3,'cpu_limit_ns':300*10**9,
                        'download_bytes':0,'cpu_charged_ns':0,'active_wall_s':0,'attempts':[],'pending_attempt':None,'closed':False}
            self.save()

    def save(self):
        path=self.path.with_suffix('.tmp');path.write_text(json.dumps(self.state,indent=2)+'\n');path.replace(self.path)

    def begin(self,attempt):
        if self.state['closed'] or self.state['pending_attempt']:raise RuntimeError('closed or unaccounted campaign')
        if (self.root/'pilot-started.json').exists():raise RuntimeError('single pilot already started')
        remaining=self.state['cpu_limit_ns']-self.state['cpu_charged_ns']
        if remaining<=120*10**9:raise RuntimeError('shared CPU budget cannot cover work and teardown reserve')
        if self.state['active_wall_s']>=510:raise RuntimeError('shared active wall budget cannot cover teardown')
        self.state['pending_attempt']=attempt;self.save();return remaining

    def finish(self,attempt,result):
        if self.state['pending_attempt']!=attempt:raise RuntimeError('attempt identity mismatch')
        transfer=self.root/'transfer.json'
        if transfer.exists():self.state['download_bytes']=json.loads(transfer.read_text())['download_bytes']
        if not result.get('accounting_complete') or result.get('cleanup_pending'):
            self.state['closed']=True  # Unknown cost or cleanup never grants another retry.
        charged=max(result.get('peak_conservative_cpu_ns',0),result.get('cpu',{}).get('conservative_cpu_ns',0))
        self.state['cpu_charged_ns']+=charged
        self.state['active_wall_s']+=result.get('total_including_preparation_wall_s',result['elapsed_s'])
        self.state['attempts'].append({'attempt':attempt,'cpu_charged_ns':charged,'status':result['status']})
        self.state['pending_attempt']=None;self.save()

    def close(self):
        fcntl.flock(self.lock,fcntl.LOCK_UN);self.lock.close()
