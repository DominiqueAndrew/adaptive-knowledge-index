import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from aki.setup_accounting import AccountingError
from aki.subtree_accounting import SubtreeSample as S,SubtreeLedger,read_cgroup_v2

BOOT='12345678-1234-1234-1234-123456789abc'


class SubtreeTests(unittest.TestCase):
    def ledger(self,**kw):return SubtreeLedger(S('fixture',0,100,False),4,containment_verified=True,quantum_ns=1,**kw)

    def test_kernel_subtree_total_keeps_exited_descendant_cost(self):
        a=self.ledger(durable_counter=True);a.observe(S('fixture',10,109,True))
        # Descendants disappear, but the scope counter retains all their CPU.
        a.seal_dispatch(11);r=a.finalize(S('fixture',20,145,False))
        self.assertEqual(r['observed_subtree_delta_ns'],45);self.assertEqual(r['conservative_cpu_ns'],47)

    def test_unobserved_descendants_are_covered_by_whole_lifetime_envelope(self):
        a=self.ledger(durable_counter=False);a.observe(S('fixture',10,100,True))
        self.assertEqual(a.upper_bound(20)['conservative_cpu_ns'],80)
        a.seal_dispatch(21);self.assertEqual(a.finalize(S('fixture',30,100,False))['conservative_cpu_ns'],120)

    def test_parent_exit_or_missing_scope_is_not_quiescence(self):
        for populated,sealed in [(False,False),(True,True)]:
            a=self.ledger(durable_counter=True)
            if sealed:a.seal_dispatch(1)
            with self.assertRaises(AccountingError):a.finalize(S('fixture',10,110,populated))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(AccountingError):read_cgroup_v2(Path(d)/'deleted',BOOT)

    def test_identity_counter_and_clock_faults_stay_failed(self):
        for bad in [S('reused',10,110,False),S('fixture',10,99,False),S('fixture',-1,110,False)]:
            a=self.ledger(durable_counter=True)
            with self.assertRaises(AccountingError):a.observe(bad)
            with self.assertRaises(AccountingError):a.upper_bound(20)

    def test_unknown_containment_rejected_and_stale_interval_charged(self):
        with self.assertRaises(AccountingError):SubtreeLedger(S('x',0,0,False),1,durable_counter=True,containment_verified=False)
        with self.assertRaises(AccountingError):SubtreeLedger(S('x',0,0,True),1,durable_counter=True,containment_verified=True)
        a=self.ledger(durable_counter=True);a.observe(S('fixture',10,110,True))
        self.assertEqual(a.upper_bound(20)['conservative_cpu_ns'],10+40+2)

    def test_reader_validates_kernel_file_fixture_and_does_not_infer_missing_zero(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'cgroup.type').write_text('domain\n');(root/'cpu.stat').write_text('usage_usec 37\nuser_usec 20\n')
            (root/'cgroup.events').write_text('populated 0\nfrozen 0\n')
            s=read_cgroup_v2(root,BOOT,clock=lambda:100);self.assertEqual(s.usage_ns,37000);self.assertFalse(s.populated)
            (root/'cpu.stat').unlink()
            with self.assertRaises(AccountingError):read_cgroup_v2(root,BOOT)
            (root/'cpu.stat').symlink_to(root/'cgroup.events')
            with self.assertRaises(AccountingError):read_cgroup_v2(root,BOOT)

    def test_exit_between_counter_and_event_read_requires_another_sample(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);values={'cgroup.type':['domain'],'cgroup.events':['populated 1','populated 0'],'cpu.stat':['usage_usec 10']}
            def opened(path,*args,**kwargs):return io.StringIO(values[path.name].pop(0))
            with mock.patch.object(Path,'open',opened):s=read_cgroup_v2(root,BOOT,clock=lambda:100)
            self.assertTrue(s.populated)

    def test_scope_replacement_during_last_event_read_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);values={'cgroup.type':['domain'],'cgroup.events':['populated 0','populated 0'],'cpu.stat':['usage_usec 10']}
            original=Path.stat;calls=0
            def stat(path,*args,**kwargs):
                nonlocal calls
                result=original(path,*args,**kwargs)
                # Only stat(), not is_symlink()'s lstat(), observes replacement.
                if path==root and kwargs.get('follow_symlinks',True):
                    calls+=1
                    if calls==3:return mock.Mock(st_dev=result.st_dev,st_ino=result.st_ino+1)
                return result
            def opened(path,*args,**kwargs):return io.StringIO(values[path.name].pop(0))
            with mock.patch.object(Path,'open',opened),mock.patch.object(Path,'stat',stat):
                with self.assertRaisesRegex(AccountingError,'replaced'):read_cgroup_v2(root,BOOT,clock=lambda:100)
