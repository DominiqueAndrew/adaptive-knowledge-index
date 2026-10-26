import json
from pathlib import Path
import tempfile
import unittest
from aki.setup_budget import SharedBudget


class SharedBudgetTests(unittest.TestCase):
    def test_retry_preserves_cpu_and_transfer(self):
        with tempfile.TemporaryDirectory() as d:
            b=SharedBudget(d);self.assertEqual(b.begin('first'),300*10**9)
            (Path(d)/'transfer.json').write_text(json.dumps({'download_bytes':330_000_000}))
            b.finish('first',{'accounting_complete':True,'cleanup_pending':[],'peak_conservative_cpu_ns':40*10**9,
                'status':'work_stopped','elapsed_s':25})
            b.close();b=SharedBudget(d)
            try:
                self.assertEqual(b.state['download_bytes'],330_000_000)
                self.assertEqual(b.begin('second'),260*10**9)
                self.assertEqual(b.state['active_wall_s'],25)
            finally:b.close()

    def test_pending_run_cannot_be_reset(self):
        with tempfile.TemporaryDirectory() as d:
            b=SharedBudget(d);b.begin('first');b.close();b=SharedBudget(d)
            try:
                with self.assertRaises(RuntimeError):b.begin('second')
            finally:b.close()

    def test_missing_accounting_closes_campaign(self):
        with tempfile.TemporaryDirectory() as d:
            b=SharedBudget(d);b.begin('first')
            b.finish('first',{'accounting_complete':False,'status':'accounting_incomplete','elapsed_s':1})
            try:
                with self.assertRaises(RuntimeError):b.begin('second')
            finally:b.close()

    def test_cpu_reserve_and_single_pilot_gate(self):
        with tempfile.TemporaryDirectory() as d:
            b=SharedBudget(d)
            try:
                b.state['cpu_charged_ns']=180*10**9
                with self.assertRaises(RuntimeError):b.begin('over-budget')
                b.state['cpu_charged_ns']=0
                (Path(d)/'pilot-started.json').write_text('{}')
                with self.assertRaises(RuntimeError):b.begin('second-pilot')
            finally:b.close()
