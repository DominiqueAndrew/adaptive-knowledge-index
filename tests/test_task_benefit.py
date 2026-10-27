import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from aki.task_benefit import develop,evaluate_holdout,aggregate_attempts,run_fixtures,DEFAULTS
from aki.policy import Policy
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
from task_benefit_fixture import prepare,cases


class TaskBenefitTests(unittest.TestCase):
    def test_heldout_not_opened_during_development_or_before_freeze(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'fixture';prepare(root);original=Path.read_bytes
            def read(p):
                if p.name=='heldout.json':raise AssertionError('future input read')
                return original(p)
            with mock.patch.object(Path,'read_bytes',read):
                with self.assertRaises(FileNotFoundError):evaluate_holdout(root)
                develop(root)
            report=evaluate_holdout(root)
            self.assertEqual(report['real_agent_runs'],0)
            self.assertNotEqual(report['frozen_baseline'],'disabled')
            self.assertIn('disabled',report['summaries'])
            self.assertTrue(all(s['fixture_pass_rate']==1 for s in report['summaries'].values()))
            self.assertTrue(all(s['resolved_tasks'] is None for s in report['summaries'].values()))
            with self.assertRaises(FileExistsError):evaluate_holdout(root)

    def test_changed_seal_or_frozen_configuration_prevents_evaluation(self):
        for target in ('heldout.json','freeze.json'):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d)/'fixture';prepare(root);develop(root)
                p=root/target
                if target=='heldout.json':p.write_bytes(p.read_bytes()+b' ')
                else:
                    v=json.loads(p.read_bytes());v['config']['token_budget']=1;p.write_text(json.dumps(v))
                with self.assertRaises(ValueError):evaluate_holdout(root)

    def test_policy_receives_current_operations_not_oracle_or_future_events(self):
        seen=[]
        class Spy(Policy):
            def query(self,*args,**kwargs):
                self.assert_no_gold=not kwargs;seen.append(args)
                return super().query(*args,**kwargs)
        rows=run_fixtures(cases('original-')[:1],('frequency','aki'),DEFAULTS,policy_factory=Spy)
        self.assertEqual(len(seen),8)
        self.assertTrue(all(len(args)==5 and isinstance(args[0],str) for args in seen))
        for result in rows.values():
            self.assertTrue(result[0]['fresh']);self.assertTrue(result[0]['correct'])
            self.assertNotEqual(result[0]['steps'][0]['revision'],result[0]['steps'][2]['revision'])

    def test_real_metric_requires_tests_and_counts_failed_cancelled_attempts(self):
        base={'kind':'executable_task','task_id':'x','status':'completed','correct':True,'fresh':True,'lifecycle_ns':10,'cost_complete':True,'abstentions':0}
        with self.assertRaises(ValueError):aggregate_attempts([base])
        receipt={'verified':True,'protocol_sha256':'a'*64,'output_sha256':'b'*64,'tests_collected':1,'exit_code':0}
        rows=[base|{'test_receipt':receipt},base|{'task_id':'failure','status':'failed'},base|{'task_id':'cancel','status':'cancelled'}]
        v=aggregate_attempts(rows);self.assertEqual(v['resolved_rate'],1/3);self.assertEqual(v['cost_per_resolved_task_ns'],30)
        rows[0]['fresh']=False;self.assertEqual(aggregate_attempts(rows)['resolved_tasks'],0)

    def test_missing_cost_and_duplicate_attempts_cannot_be_scored(self):
        row={'kind':'synthetic_fixture','task_id':'x','correct':True,'fresh':True,'lifecycle_ns':1,'cost_complete':True,'abstentions':0}
        with self.assertRaises(ValueError):aggregate_attempts([row,row])
        with self.assertRaises(ValueError):aggregate_attempts([row|{'cost_complete':False}])
