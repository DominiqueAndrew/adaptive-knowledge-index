#!/usr/bin/env python3
"""Replay the original project's worker-handler fault with deterministic mocks.

Loads only the historical/current _workers method AST, never either script's
entrypoint. No processes except read-only git show; no VM/network/model calls.
"""
import ast
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest import mock
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aki.setup_accounting import AccountingError


def exercise(source):
    tree=ast.parse(source)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Accounting')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_workers')
    error=AccountingError('original deterministic ESRCH fixture');error.errno=3
    errors=[]
    scope={'AccountingError':AccountingError,'resource':mock.Mock(RUSAGE_CHILDREN=0),
           'children':mock.Mock(return_value=[7]),'owned_sample':mock.Mock(side_effect=error),
           'time':mock.Mock(monotonic_ns=lambda:120),'os':mock.Mock(getpid=lambda:1)}
    scope['resource'].getrusage.return_value=SimpleNamespace(ru_utime=0,ru_stime=0)
    scope['os'].kill.side_effect=ProcessLookupError
    exec(compile(ast.Module(body=[method],type_ignores=[]),'<original-project-worker-method>','exec'),scope)
    state=SimpleNamespace(worker_samples={},host_capacity=12,worker_max=0,
                          runner=SimpleNamespace(phase='cleanup'),_record=lambda kind,row:errors.append(kind))
    try:
        value=scope['_workers'](state)
        return {'raised':False,'returned_cpu_ns':value,'counter_errors_recorded':len(errors)}
    except AccountingError:
        return {'raised':True,'returned_cpu_ns':None,'counter_errors_recorded':len(errors)}


if __name__=='__main__':
    old=subprocess.check_output(['git','show','34e3767:scripts/run_task420_attempt.py'],cwd=ROOT,text=True)
    current=(ROOT/'scripts/run_task420_attempt.py').read_text()
    result={'scope':'original deterministic host mock; not live accounting',
            'historical_commit':'34e3767','historical':exercise(old),'current':exercise(current)}
    assert result['historical']['returned_cpu_ns']==0 and not result['historical']['raised']
    assert result['current']['raised']
    print(json.dumps(result,indent=2))
