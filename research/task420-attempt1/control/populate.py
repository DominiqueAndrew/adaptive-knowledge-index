import base64,hashlib,json,os,sys
rows=json.loads(sys.stdin.read(2*1024*1024));total=0
if os.listdir('/workspace'):raise RuntimeError('workspace must be empty')
for r in rows:
 name=r['path'];parts=name.split('/')
 if name.startswith('/') or any(p in ('','..','.') or p.startswith('.') for p in parts):raise ValueError('invalid public source path')
 data=base64.b64decode(r['data']);total+=len(data)
 if len(data)>2*1024*1024 or total>64*1024*1024:raise ValueError('source cap')
 if hashlib.sha256(data).hexdigest()!=r['sha256']:raise ValueError('source digest')
 target='/workspace/'+name;parent=os.path.dirname(target)
 if not os.path.isdir(parent):os.makedirs(parent)
 with open(target,'xb') as f:f.write(data)
 os.chmod(target,r['mode']&0o777)
print(json.dumps({'files':len(rows),'bytes':total,'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()}))
