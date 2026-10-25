import base64,hashlib,importlib.util,json,subprocess,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('setup',Path('scripts/pilot420_setup.py'));s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
s.state.update(json.loads((s.ROOT/'setup-summary.json').read_text()));s.state['source_transfer_note']='docker archive transfer made no writes; validated non-root JSON transfer into the same writable tmpfs'
s.check()
source=Path('../replay-inputs/trees/Backblaze__B2_Command_Line_Tool--15a60ad1c71b75366061e4f742ef52eb9dcc23e7');rows=[]
for f in sorted(source.rglob('*')):
 rel=f.relative_to(source)
 if any(p.startswith('.') for p in rel.parts) or str(rel)=='_aki_manifest.json':continue
 if f.is_symlink():raise ValueError('unexpected symlink')
 if f.is_file():
  b=f.read_bytes();rows.append({'path':str(rel),'sha256':hashlib.sha256(b).hexdigest(),'data':base64.b64encode(b).decode(),'mode':f.stat().st_mode&0o777})
p=subprocess.run(s.DOCKER+['exec','-i',s.NAME,'python3','/control/populate.py'],input=json.dumps(rows).encode(),capture_output=True,timeout=30)
(s.ROOT/'source-transfer.json').write_bytes(p.stdout)
if p.returncode:raise RuntimeError(p.stderr.decode()[:400])
s.state['copied_source_files']=len(rows);s.state['status']='offline_compatibility_running';s.check()
with (s.ROOT/'compatibility.log').open('wb') as log:
 p=subprocess.Popen(s.DOCKER+['exec',s.NAME,'python3','/control/setup.py'],stdout=log,stderr=subprocess.STDOUT)
 while p.poll() is None:
  time.sleep(2)
  try:s.check()
  except BaseException:
   subprocess.run(s.DOCKER+['kill',s.NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);p.wait(timeout=10);raise
 s.state['compatibility_exit']=p.returncode
s.check();s.state['status']='compatibility_passed' if p.returncode==0 else 'compatibility_failed'
(s.ROOT/'setup-summary.json').write_text(json.dumps(s.state,indent=2)+'\n');print(json.dumps(s.state,indent=2))
