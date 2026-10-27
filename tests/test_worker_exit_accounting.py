"""Deterministic original fault fixtures; no VM, network or benchmark execution."""
import errno
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import run_task420_attempt as supervisor
from aki.setup_accounting import AccountingError,CpuLedger
from aki.setup_budget import SharedBudget
from aki.setup_watchdog import SetupWatchdog,Command


def complete():
    return {'conservative_cpu_ns':40,'finalized':True,
            'components':{name:{'measured_ns':10,'unobserved_upper_bound_ns':0,'active':False}
                          for name in CpuLedger.REQUIRED}}


class WorkerExitAccountingTests(unittest.TestCase):
    def accounting(self,cleanup,previous):
        a=object.__new__(supervisor.Accounting);a.host_capacity=12;a.worker_max=0
        a.runner=mock.Mock(phase='cleanup' if cleanup else 'work')
        a.worker_samples={7:previous} if previous else {}
        return a

    def test_missing_worker_samples_fail_despite_disappearance(self):
        prior={'identity':'7:original','cpu_ns':10,'reaped_children_cpu_ns':3,'observed_ns':100}
        for cleanup,previous,code in [(False,prior,errno.ESRCH),(True,None,errno.ESRCH),
                                      (False,None,errno.ESRCH),(True,prior,errno.EPERM)]:
            with self.subTest(cleanup=cleanup,known=bool(previous),errno=code):
                a=self.accounting(cleanup,previous);error=AccountingError('original missing counter');error.errno=code
                usage=mock.Mock(ru_utime=0,ru_stime=0)
                with mock.patch.object(supervisor,'children',return_value=[7]),mock.patch.object(supervisor,'darwin_process_cpu',side_effect=error),mock.patch.object(supervisor.time,'monotonic_ns',return_value=120),mock.patch.object(supervisor.resource,'getrusage',return_value=usage),mock.patch.object(a,'_record') as record,mock.patch.object(supervisor.os,'kill',side_effect=ProcessLookupError) as disappearance:
                    with self.assertRaises(AccountingError):a._workers()
                    disappearance.assert_not_called()  # A missing PID is never a zero-CPU proof.
                    self.assertEqual(record.call_args.args[1]['context']['errno'],code)
                    self.assertEqual(a.worker_max,0)

    def test_known_teardown_tail_is_explicit_positive_bound(self):
        prior={'identity':'7:original','cpu_ns':10,'reaped_children_cpu_ns':3,'observed_ns':100}
        a=self.accounting(True,prior);error=AccountingError('original exited counter');error.errno=errno.ESRCH
        with mock.patch.object(supervisor,'children',side_effect=[[7],[]]),mock.patch.object(supervisor,'darwin_process_cpu',side_effect=error),mock.patch.object(supervisor.time,'monotonic_ns',return_value=120),mock.patch.object(supervisor.resource,'getrusage',return_value=mock.Mock(ru_utime=0,ru_stime=0)):
            self.assertEqual(a._workers(),10+3+20*12)
            self.assertEqual(a.worker_samples[7]['observed_ns'],100)
            self.assertEqual(a.worker_samples[7]['bound_reason'],'known_process_exited_ESRCH')

    def run_fault(self,phase):
        launched=[];state={'fault_delivered':False}
        runner=None
        def snapshot():
            if runner.phase==phase and not state['fault_delivered']:
                state['fault_delivered']=True
                error=AccountingError('original unaccounted worker');error.counter_component='workers'
                error.counter_context={'pid':7,'previous':None,'errno':errno.ESRCH}
                raise error
            return complete()
        runner=SetupWatchdog(cpu_snapshot=snapshot,total_s=10,teardown_reserve_s=5,clock=lambda:100)
        def command(c):
            runner._check();launched.append(c.name)
            return {'name':c.name,'exit':0,'wall_s':0,'fixture_only':True}
        with mock.patch.object(runner,'_run_command',side_effect=command):
            result=runner.run([Command('work',('never-executed',))],[Command('cleanup',('never-executed',))])
        return result,launched

    def test_work_fault_blocks_dispatch_and_survives_good_final_snapshot(self):
        result,launched=self.run_fault('work')
        self.assertEqual(launched,['cleanup'])
        self.assertTrue(result['cpu']['finalized'])
        self.assertFalse(result['accounting_complete'])
        self.assertEqual(result['status'],'accounting_incomplete')
        self.assertEqual(result['accounting_fault_details'][0]['component'],'workers')

    def test_cleanup_fault_preserves_cleanup_but_invalidates_result_and_budget(self):
        result,launched=self.run_fault('cleanup')
        self.assertEqual(launched,['work','cleanup'])
        self.assertFalse(result['accounting_complete'])
        self.assertFalse(result['cleanup_pending'])
        with tempfile.TemporaryDirectory() as d:
            b=SharedBudget(d,download_limit=0);b.begin('original-fixture');b.finish('original-fixture',result);b.close()
            self.assertTrue(json.loads((Path(d)/'budget.json').read_text())['closed'])
            b=SharedBudget(d)
            try:
                with self.assertRaises(RuntimeError):b.begin('must-not-retry')
            finally:b.close()

    def test_final_snapshot_failure_cannot_report_complete(self):
        runner=SetupWatchdog(cpu_snapshot=lambda:complete(),total_s=10,teardown_reserve_s=5,clock=lambda:100)
        with mock.patch.object(runner,'_snapshot',side_effect=AccountingError('original final counter missing')):
            result=runner.run([],[])
        self.assertFalse(result['accounting_complete'])
        self.assertEqual(result['status'],'accounting_incomplete')


if __name__=='__main__':unittest.main()
