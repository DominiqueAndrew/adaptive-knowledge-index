import json,os,subprocess,sys,time

def run(args):
    subprocess.check_call(args, cwd='/workspace', timeout=60)

start=time.monotonic()
run([sys.executable,'-m','venv','--copies','/env'])
py='/env/bin/python'
run([py,'-m','pip','install','--no-index','--no-deps',
     '/packages/pip-20.2.3-py2.py3-none-any.whl',
     '/packages/setuptools-50.3.2-py3-none-any.whl',
     '/packages/wheel-0.35.1-py2.py3-none-any.whl'])
run([py,'-m','pip','install','--no-index','--find-links=/packages','--no-deps',
     '--no-build-isolation','--no-use-pep517','--require-hashes','-r','/control/requirements.txt'])
run([py,'-m','pip','check'])
run([py,'-c','import arrow,logfury,requests,six,tqdm,pytest,mock,pyflakes,yapf; print("DEPENDENCY_IMPORTS_OK")'])
run(['gcc','--version'])
run([py,'-m','pip','install','--no-index','--no-deps','--no-build-isolation','--no-use-pep517','-e','/workspace'])
run([py,'-m','pip','check'])
run([py,'-m','b2.console_tool','--help'])
run([py,'-m','pytest','--collect-only','-q','-p','no:cacheprovider','test'])
print('AKI_SETUP_OK '+json.dumps({'elapsed_seconds':time.monotonic()-start,'python':sys.version}),flush=True)
