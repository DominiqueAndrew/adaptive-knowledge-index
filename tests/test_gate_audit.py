"""Original local fixtures/mocks only; no runtime, network or model calls."""
import base64
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).parent))
from test_live_adapter import BACKEND, worker, supervisor
from aki.recorder import Recorder, CaptureError, verify
from aki.setup_accounting import AccountingError
from aki.setup_watchdog import SetupWatchdog, Command


def row(data):
    return {'path':'example.py','data':base64.b64encode(data).decode(),'sha256':hashlib.sha256(data).hexdigest(),'mode':0o644}


class RemainingGateAuditTests(unittest.TestCase):
    def test_validation_only_plan_has_no_pilot_or_model_phase(self):
        self.assertEqual([p for p,t in supervisor.work_phases(True)],['stage','start','import','setup'])
        self.assertEqual(supervisor.work_phases(False)[-1][0],'pilot')

    def test_pid_reuse_and_clock_regression_are_rejected(self):
        previous={'identity':'old','cpu_ns':2,'observed_ns':100}
        with mock.patch.object(supervisor,'darwin_process_cpu',return_value={'identity':'new','cpu_ns':3}):
            with self.assertRaises(AccountingError):supervisor.owned_sample(7,previous,cleanup=True,capacity=4,now=120)
            with self.assertRaises(AccountingError):supervisor.owned_sample(7,previous,cleanup=True,capacity=4,now=99)

    def test_faults_retain_component_clock_and_previous_counter(self):
        error=AccountingError('synthetic missing counter');error.counter_component='workers';error.counter_context={'pid':7,'previous':{'cpu_ns':4}}
        def missing():raise error
        runner=SetupWatchdog(cpu_snapshot=missing,total_s=1,teardown_reserve_s=.5)
        result=runner.run([Command('must-not-launch',(sys.executable,'-c','raise Exception()'))],[])
        self.assertFalse(result['accounting_complete'])
        detail=result['accounting_fault_details'][0]
        self.assertEqual(detail['component'],'workers');self.assertEqual(detail['phase'],'work')
        self.assertEqual(detail['context']['previous']['cpu_ns'],4)

    def test_accounting_journal_retains_prior_snapshot(self):
        with tempfile.TemporaryDirectory() as d:
            accounting=object.__new__(supervisor.Accounting);accounting.root=Path(d)
            accounting._record('baseline',{'capacity':4});accounting._record('snapshot',{'cpu':10})
            rows=[json.loads(s) for s in (Path(d)/'accounting-evidence.jsonl').read_text().splitlines()]
            self.assertEqual([r['kind'] for r in rows],['baseline','snapshot'])

    def test_container_quiescence_rejects_live_survivors(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            for pid in [1,9,12]:(p/str(pid)).mkdir()
            (p/'12/stat').write_text('12 (original fixture) S 1 2 3')
            with self.assertRaises(ValueError):BACKEND.assert_quiescent(d,current_pid=9)
            (p/'12/stat').write_text('12 (original fixture) Z 1 2 3')
            BACKEND.assert_quiescent(d,current_pid=9)

    def test_execute_always_terminates_owned_process_group(self):
        for timeout in (False,True):
            process=mock.Mock(pid=7654321)
            process.wait.side_effect=[subprocess.TimeoutExpired('original-fixture',25),0] if timeout else [0]
            process.poll.return_value=None if timeout else 0
            with mock.patch.object(BACKEND.subprocess,'Popen',return_value=process) as launch, mock.patch.object(BACKEND.os,'killpg') as kill:
                if timeout:
                    with self.assertRaises(ValueError):BACKEND.execute('/fixture',True)
                else:BACKEND.execute('/fixture',True)
                self.assertTrue(launch.call_args.kwargs['start_new_session'])
                kill.assert_called_once_with(process.pid,signal.SIGKILL)

    def recorder(self,root):
        source=root/'source';source.mkdir();(source/'example.py').write_bytes(b'VALUE = 1\n')
        rec=Recorder(root=source,scopes=['example.py'],output=root/'capture',allow_collection=True,
                     source_kind='synthetic_fixture',store_source_blobs=True,store_tool_requests=True)
        return source,rec

    def test_failed_mutation_still_records_actual_post_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,rec=self.recorder(root);state=[b'VALUE = 1\n']
            def backend(root,action,fixture):
                if action['op']=='snapshot':return {'result':[row(state[0])]}
                state[0]=b'VALUE = 2\n';raise RuntimeError('original fixture failure after write')
            with mock.patch.object(worker,'backend',side_effect=backend):
                try:
                    with self.assertRaises(RuntimeError):worker.record_operation(root,source,rec,{'op':'edit'},fixture=True)
                finally:rec.close()
            self.assertEqual((source/'example.py').read_bytes(),state[0])
            self.assertTrue(verify(root/'capture')['integrity_verified'])
            end=[json.loads(s) for s in (root/'capture/events.jsonl').read_text().splitlines() if json.loads(s)['event']=='end'][0]
            self.assertEqual(end['status'],'error');self.assertTrue(end['after']['changed'])

    def test_missing_guest_post_snapshot_invalidates_capture(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source,rec=self.recorder(root);calls=[0]
            def backend(root,action,fixture):
                if action['op']=='snapshot':
                    calls[0]+=1
                    if calls[0]>1:raise RuntimeError('post snapshot missing')
                    return {'result':[row(b'VALUE = 1\n')]}
                return {'result':'read','wall_ns':1,'cpu_ns':1}
            with mock.patch.object(worker,'backend',side_effect=backend):
                try:
                    with self.assertRaises(RuntimeError):worker.record_operation(root,source,rec,{'op':'read'},fixture=True)
                finally:rec.close()
            with self.assertRaises(CaptureError):verify(root/'capture')

    def test_gate_rejects_truthy_but_failed_verification(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'compatibility.json').write_text(json.dumps({'passed':True,'completed':[{}]*8}))
            (root/'fixture-result.json').write_text(json.dumps({'verification':{'integrity_verified':False,'complete_operations':4}}))
            with self.assertRaises(RuntimeError):worker.assert_live_gates(root)


if __name__=='__main__':unittest.main()
