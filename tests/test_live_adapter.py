"""Original host fixtures for the live bridge; no VM, network or model calls."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import ssl
import errno
import zipfile
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import task420_live_worker as worker
import run_task420_attempt as supervisor
from aki.setup_tls import verified_context
from aki.setup_accounting import AccountingError


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

CONTROL=module('fixture_control',ROOT/'runtime/task420/control.py')
with mock.patch.dict(sys.modules,{'control':CONTROL}):BACKEND=module('fixture_backend',ROOT/'runtime/task420/backend.py')


class LiveBridgeTests(unittest.TestCase):
    def test_known_exited_process_has_bounded_tail_only_during_cleanup(self):
        old={'identity':'fixture','cpu_ns':10,'reaped_children_cpu_ns':0,'observed_ns':100,'unobserved_ns':0}
        error=AccountingError('fixture ESRCH');error.errno=errno.ESRCH
        with mock.patch.object(supervisor,'darwin_process_cpu',side_effect=error):
            result=supervisor.owned_sample(1,old,cleanup=True,capacity=4,now=120)
            self.assertEqual(result['cpu_ns'],10);self.assertEqual(result['unobserved_ns'],80)
            for previous,cleanup in [(old,False),(None,True)]:
                with self.assertRaises(AccountingError):supervisor.owned_sample(1,previous,cleanup=cleanup,capacity=4,now=120)
            error.errno=errno.EPERM
            with self.assertRaises(AccountingError):supervisor.owned_sample(1,old,cleanup=True,capacity=4,now=120)

    def test_only_pinned_unused_windows_launcher_data_is_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'pip-20.2.3-py2.py3-none-any.whl'
            with zipfile.ZipFile(p,'w') as z:z.writestr('pip/_vendor/distlib/t32.exe',b'MZfixture')
            self.assertEqual(len(worker.review_wheel(p)['inert_launcher_data']),1)
            with zipfile.ZipFile(p,'w') as z:z.writestr('unreviewed.exe',b'MZfixture')
            with self.assertRaises(RuntimeError):worker.review_wheel(p)
            with zipfile.ZipFile(p,'w') as z:z.writestr('native.so',b'fixture')
            with self.assertRaises(RuntimeError):worker.review_wheel(p)

    def test_local_tls_preflight_loads_existing_roots_without_network(self):
        with mock.patch('urllib.request.urlopen',side_effect=AssertionError('network not allowed')):
            context,proof=verified_context()
        self.assertGreater(proof['loaded_ca_count'],0)
        self.assertTrue(context.check_hostname);self.assertEqual(context.verify_mode,ssl.CERT_REQUIRED)

    def test_tls_preflight_rejects_empty_or_disabled_verification(self):
        empty=mock.Mock();empty.cert_store_stats.return_value={'x509_ca':0}
        with mock.patch('ssl.create_default_context',return_value=empty):
            with self.assertRaises(RuntimeError):verified_context()
        disabled=mock.Mock();disabled.cert_store_stats.return_value={'x509_ca':10};disabled.check_hostname=False
        with mock.patch('ssl.create_default_context',return_value=disabled):
            with self.assertRaises(RuntimeError):verified_context()

    def test_guest_syntax_and_scoped_read_edit(self):
        ast.parse((ROOT/'runtime/task420/backend.py').read_text(),feature_version=(3,5))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'example.py').write_text('VALUE = 1\n')
            self.assertEqual(BACKEND.dispatch({'op':'read','path':'example.py'},d,True)['text'],'VALUE = 1\n')
            BACKEND.dispatch({'op':'edit','path':'example.py','old':'1','new':'2'},d,True)
            self.assertEqual((p/'example.py').read_text(),'VALUE = 2\n')
            with self.assertRaises(ValueError):BACKEND.dispatch({'op':'edit','path':'example.py','old':'missing','new':'3'},d,True)
            with self.assertRaises(ValueError):BACKEND.dispatch({'op':'shell','command':'anything'},d,True)
            for name in ['../private','/private','.secret','a/../b']:
                with self.assertRaises(ValueError):BACKEND.source_path(d,name)
            (p/'link').symlink_to(p/'example.py')
            with self.assertRaises(ValueError):BACKEND.source_path(d,'link')

    def test_guest_snapshot_rejects_link_and_read_limit(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/'example.py').write_text('one\ntwo\n')
            self.assertEqual(BACKEND.snapshot(d)[0]['path'],'example.py')
            with self.assertRaises(ValueError):BACKEND.dispatch({'op':'read','path':'example.py','start':1,'end':300},d,True)
            (p/'link').symlink_to(p/'example.py')
            with self.assertRaises(ValueError):BACKEND.snapshot(d)

    def test_worker_streaming_bounds_are_real_host_subprocess_fixtures(self):
        self.assertEqual(worker.run([sys.executable,'-I','-c','import sys; print(sys.stdin.read())'],data=b'fixture').strip(),b'fixture')
        with self.assertRaisesRegex(RuntimeError,'output cap'):worker.run([sys.executable,'-I','-c','print("x"*10000)'],limit=100)
        with self.assertRaisesRegex(RuntimeError,'timeout'):worker.run([sys.executable,'-I','-c','import time; time.sleep(5)'],timeout=.05)
        with self.assertRaisesRegex(RuntimeError,'startup provisioning'):
            worker.run([sys.executable,'-I','-c','print("downloading",flush=True); import time; time.sleep(5)'],reject_pattern=b'downloading')

    def test_mirror_and_recorder_bridge_with_synthetic_guest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);guest=root/'guest';guest.mkdir()
            def backend(root,request,fixture=False):
                if request['op']=='initialize':
                    (guest/'example.py').write_text('VALUE = 1\n');result=BACKEND.snapshot(str(guest))
                elif request['op']=='execute':result={'exit_code':0,'output':'FIXTURE_OK'}
                else:result=BACKEND.dispatch(request,str(guest),True)
                return {'result':result,'wall_ns':10,'cpu_ns':5}
            with mock.patch.object(worker,'backend',side_effect=backend):worker.fixture(root)
            result=json.loads((root/'fixture-result.json').read_text())
            self.assertEqual(len(result['observations']),4)
            self.assertEqual((root/'fixture-mirror/example.py').read_text(),'VALUE = 2\n')
            self.assertTrue(result['verification'])

    @unittest.skipUnless(sys.platform=='darwin','Mac owned-process inventory')
    def test_sampler_reads_only_child_inventory_of_current_process(self):
        import os,subprocess
        p=subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(2)'])
        try:self.assertIn(p.pid,supervisor.children(os.getpid()))
        finally:p.terminate();p.wait()


if __name__=='__main__':unittest.main()
