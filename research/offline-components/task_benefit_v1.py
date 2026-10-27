"""Sealed evaluation plumbing, exercised only on original synthetic fixtures.

Seals prevent accidental pre-freeze reads and detect changes; they are not access
control against a malicious host. No model, shell task or third-party code runs.
"""
import hashlib
import json
from pathlib import Path
import random
import re
import tempfile
import time
from .benchmark import oracle
from .policy import Policy
from .source import parse,digest
from .store import Store

BASELINES=('disabled','frequency','lru','gds','static_bounded')
DEFAULTS={'storage_bytes':4096,'token_budget':2048,'seed':104}


def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def save_new(path,value):
    with Path(path).open('xb') as stream:stream.write(encoded(value)+b'\n')


def code_hashes():
    root=Path(__file__).parent
    return {name:sha((root/name).read_bytes()) for name in ('task_benefit.py','policy.py','store.py','source.py','benchmark.py')}


def aggregate_attempts(rows):
    if not rows:raise ValueError('empty cohort is not a successful result')
    ids=[r['task_id'] for r in rows]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate attempt identities')
    real=[r for r in rows if r['kind']=='executable_task']
    fixture=[r for r in rows if r['kind']=='synthetic_fixture']
    if len(real)+len(fixture)!=len(rows):raise ValueError('unknown outcome kind')
    for r in rows:
        if type(r['lifecycle_ns']) is not int or r['lifecycle_ns']<0 or r['cost_complete'] is not True:
            raise ValueError('incomplete or invalid attempt cost')
        if r['kind']=='executable_task':
            if r.get('status') not in ('completed','failed','cancelled'):raise ValueError('explicit attempt status required')
            receipt=r.get('test_receipt',{})
            if r['status']=='completed' and (receipt.get('verified') is not True
                or not re.fullmatch('[a-f0-9]{64}',receipt.get('protocol_sha256',''))
                or not re.fullmatch('[a-f0-9]{64}',receipt.get('output_sha256','')) or receipt.get('tests_collected',0)<=0):
                raise ValueError('actual test receipt required; tool feedback is not task success')
    resolved=sum(r['status']=='completed' and r['test_receipt']['exit_code']==0 and r['correct'] and r['fresh'] for r in real)
    return {'attempts':len(rows),'real_task_attempts':len(real),'resolved_tasks':resolved if real else None,
            'resolved_rate':resolved/len(real) if real else None,
            'fixture_pass_rate':sum(r['correct'] and r['fresh'] for r in fixture)/len(fixture) if fixture else None,
            'stale_attempts':sum(not r['fresh'] for r in rows),'abstentions':sum(r['abstentions'] for r in rows),
            'total_lifecycle_ns':sum(r['lifecycle_ns'] for r in rows),
            'cost_per_attempt_ns':sum(r['lifecycle_ns'] for r in rows)/len(rows),
            'cost_per_resolved_task_ns':sum(r['lifecycle_ns'] for r in real)/resolved if resolved else None}


def run_fixtures(cases,policies,config,*,policy_factory=Policy):
    """Gold/oracles remain evaluator-only. Each task/condition owns a fresh store."""
    if not cases or any(c.get('kind')!='synthetic_fixture' for c in cases):raise ValueError('only original fixture execution is implemented')
    if any(p not in BASELINES+('aki',) for p in policies):raise ValueError('unmatched policy')
    order=[(c,p) for c in cases for p in policies];random.Random(config['seed']).shuffle(order)
    results={p:[] for p in policies}
    for case,name in order:
        cpu=time.process_time_ns();start=time.perf_counter_ns()
        with tempfile.TemporaryDirectory(prefix='aki-task-fixture-') as tmp:
            store=Store(Path(tmp)/'state.sqlite','original-synthetic-fixture')
            policy=policy_factory(store,name,config['storage_bytes']);service=time.perf_counter_ns()-start
            correct=fresh=True;abstentions=0;steps=[]
            try:
                for event in case['events']:
                    docs=event['documents'];op=event['operation']
                    edges=parse(docs).edges
                    expected=oracle(docs,edges,op['root'],op['kind'],op.get('text',''),config['token_budget'])
                    valid=set(oracle(docs,edges,op['root'],op['kind'],op.get('text',''),10**9))
                    started=time.perf_counter_ns()
                    policy.refresh(docs,'original fixture current step','selective')
                    revision=store.revision
                    answer,cost=policy.query(op['root'],op['kind'],revision,op.get('text',''),config['token_budget'])
                    elapsed=time.perf_counter_ns()-started;service+=elapsed
                    step_fresh=set(answer)<=valid and dict(store.db.execute('SELECT path,hash FROM files'))=={p:digest(t) for p,t in docs.items()}
                    fresh &= step_fresh;correct &= answer==expected;abstentions+=int(not answer)
                    if store.usage()>config['storage_bytes']:raise ValueError('matched storage budget exceeded')
                    steps.append({'phase':event['phase'],'revision':revision,'answer_sha256':sha(encoded(answer)),
                                  'correct':answer==expected,'fresh':step_fresh,'service_ns':elapsed,'returned_files':len(answer),'cost':cost})
            finally:
                start=time.perf_counter_ns();store.close();service+=time.perf_counter_ns()-start
            results[name].append({'kind':'synthetic_fixture','task_id':case['task_id'],'correct':correct,'fresh':fresh,
                                  'abstentions':abstentions,'lifecycle_ns':service,'cost_complete':True,
                                  'process_cpu_including_oracle_ns':time.process_time_ns()-cpu,'steps':steps})
            cleanup_start=time.perf_counter_ns()
        results[name][-1]['lifecycle_ns']+=time.perf_counter_ns()-cleanup_start
        results[name][-1]['process_cpu_including_oracle_ns']=time.process_time_ns()-cpu
    return results


def develop(bundle,config=None):
    root=Path(bundle);config=dict(DEFAULTS if config is None else config)
    if (root/'freeze.json').exists():raise ValueError('development already frozen')
    manifest=json.loads((root/'manifest.json').read_bytes());data=(root/'development.json').read_bytes()
    if sha(data)!=manifest['development_sha256']:raise ValueError('development seal changed')
    results=run_fixtures(json.loads(data),BASELINES+('aki',),config)
    summaries={p:aggregate_attempts(rows) for p,rows in results.items()}
    eligible=[p for p in BASELINES if summaries[p]['fixture_pass_rate']==1 and summaries[p]['stale_attempts']==0]
    if not eligible:raise ValueError('no correct fresh baseline')
    winner=min(eligible,key=lambda p:(summaries[p]['total_lifecycle_ns'],p))
    report={'label':'synthetic host fixture plumbing; not agent evaluation','config':config,'selected_fixture_baseline':winner,'summaries':summaries,'rows':results}
    save_new(root/'development-results.json',report)
    save_new(root/'freeze.json',{'config':config,'baseline':winner,'code':code_hashes(),'manifest_sha256':sha((root/'manifest.json').read_bytes()),
                                  'development_results_sha256':sha((root/'development-results.json').read_bytes())})
    return report


def evaluate_holdout(bundle):
    root=Path(bundle)
    # Do not even read held-out bytes until code/config/selection seals validate.
    frozen=json.loads((root/'freeze.json').read_bytes())
    if frozen['code']!=code_hashes() or frozen['manifest_sha256']!=sha((root/'manifest.json').read_bytes()) or frozen['development_results_sha256']!=sha((root/'development-results.json').read_bytes()):
        raise ValueError('frozen experiment changed')
    development=json.loads((root/'development-results.json').read_bytes())
    if frozen['config']!=development['config'] or frozen['baseline']!=development['selected_fixture_baseline']:
        raise ValueError('configuration or baseline changed after development')
    manifest=json.loads((root/'manifest.json').read_bytes())
    save_new(root/'holdout-opened.json',{'freeze_sha256':sha((root/'freeze.json').read_bytes())})
    data=(root/'heldout.json').read_bytes()
    if sha(data)!=manifest['heldout_sha256']:raise ValueError('held-out seal changed')
    results=run_fixtures(json.loads(data),(frozen['baseline'],'aki'),frozen['config'])
    report={'label':'synthetic host fixtures, not real held-out agent tasks','real_agent_runs':0,'frozen_baseline':frozen['baseline'],
            'summaries':{p:aggregate_attempts(rows) for p,rows in results.items()},'rows':results}
    save_new(root/'heldout-results.json',report);return report
