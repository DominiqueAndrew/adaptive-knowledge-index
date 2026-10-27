#!/usr/bin/env python3
"""Original fixtures only: sealed development/holdout, matched caches, no model."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from aki.task_benefit import encoded,sha,save_new,develop,evaluate_holdout


def cases(prefix):
    out=[]
    for i in range(3):
        docs={'pkg/__init__.py':'','pkg/a.py':'from .b import b\ndef a(): return b()\n','pkg/b.py':'def b(): return 1\n',
              'tests/test_a.py':'from pkg.a import a\ndef test_a(): assert a()==1\n'}
        changed=docs|{'tests/test_new.py':'from pkg.b import b\ndef test_b(): assert b()==1\n'}
        op={'root':'pkg/b.py','kind':'tests','text':str(i)}
        out.append({'kind':'synthetic_fixture','task_id':prefix+str(i),'events':[
            {'phase':'cold','documents':docs,'operation':op},{'phase':'repeat','documents':docs,'operation':op},
            {'phase':'mutation','documents':changed,'operation':op},
            {'phase':'abstention','documents':changed,'operation':{'root':'missing.py','kind':'tests'}}]})
    return out


def prepare(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    development=encoded(cases('development-'));heldout=encoded(cases('fixture-holdout-'))
    (root/'development.json').write_bytes(development);(root/'heldout.json').write_bytes(heldout)
    save_new(root/'manifest.json',{'label':'original synthetic fixtures; no real held-out inputs','development_sha256':sha(development),'heldout_sha256':sha(heldout)})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    prepare(a.out);development=develop(a.out);heldout=evaluate_holdout(a.out)
    print(encoded({'label':heldout['label'],'baseline':heldout['frozen_baseline'],'summaries':heldout['summaries']}).decode())
