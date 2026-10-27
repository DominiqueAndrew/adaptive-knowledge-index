from dataclasses import replace
import unittest
from pathlib import Path
import tempfile
from unittest.mock import Mock
from aki.platform_accounting import DomainProof, CgroupAccountingAdapter, UnsupportedAccounting, capacity_plan
from aki.setup_accounting import AccountingError
from aki.subtree_accounting import SubtreeSample as S


def proof():
    return DomainProof('linux', 'cgroup-v2', 'owned-domain', 2, 'a'*64,
                       True, True, True, True, True, True, True)


class PlatformAccountingTests(unittest.TestCase):
    def adapter(self, samples, *, seal=None, stop=None):
        timed=[replace(s,observed_ns=s.observed_ns*1_000_000) if isinstance(s,S) else s for s in samples]
        return CgroupAccountingAdapter(proof(), Mock(side_effect=timed),
            seal or Mock(return_value=True), stop or Mock(return_value=True), clock=lambda:20_000_000)

    def test_unsupported_platform_fails_before_reader_or_controls(self):
        for platform, backend in [('darwin','pid-polling'), ('linux','pid-polling'), ('windows','job-object')]:
            callback=Mock(side_effect=AssertionError('no OS calls permitted'))
            with self.assertRaises(UnsupportedAccounting):
                CgroupAccountingAdapter(replace(proof(),platform=platform,backend=backend),callback,callback,callback)
            callback.assert_not_called()

    def test_every_containment_obligation_is_required(self):
        for name in ('owned','cgroup2_mount','domain','atomic_child_enrollment','migration_denied',
                     'external_dispatch_denied','counter_retained_until_final_read'):
            with self.subTest(name=name), self.assertRaises(AccountingError):
                replace(proof(),**{name:False}).validate()
        with self.assertRaises(AccountingError):replace(proof(),capacity=0).validate()

    def test_scope_identity_change_or_enrolling_populated_scope_fails(self):
        for sample in (S('foreign',0,0,False), S('owned-domain',0,0,True)):
            with self.assertRaises(AccountingError):self.adapter([sample])

    def test_directory_adapter_integrates_reader_and_final_counter_on_original_files(self):
        from aki.subtree_accounting import read_cgroup_v2
        boot='12345678-1234-1234-1234-123456789abc'
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'cgroup.type').write_text('domain\n')
            (root/'cgroup.events').write_text('populated 0\n')
            (root/'cpu.stat').write_text('usage_usec 0\n')
            identity=read_cgroup_v2(root,boot,clock=lambda:0).identity
            clock=iter([0,10_000_000,20_000_000]).__next__
            a=CgroupAccountingAdapter.from_directory(replace(proof(),scope_identity=identity),root,boot,
                                                      lambda:True,lambda:True,clock=clock)
            # Fixture represents a child which consumed CPU and exited unseen.
            (root/'cpu.stat').write_text('usage_usec 57\n')
            a.close_dispatch_and_stop();r=a.finish()
            self.assertTrue(r['complete']);self.assertEqual(r['accounting']['observed_subtree_delta_ns'],57000)

    def test_short_lived_and_reparented_children_keep_cumulative_cpu(self):
        # No per-PID observations exist: child exits between samples, another is
        # reparented, and all accumulated CPU remains on the same kernel domain.
        a=self.adapter([S('owned-domain',0,10000,False),S('owned-domain',10,14000,True),
                        S('owned-domain',30,29000,False)])
        a.checkpoint();a.close_dispatch_and_stop();r=a.finish()
        self.assertTrue(r['complete']);self.assertTrue(r['may_delete_scope'])
        self.assertEqual(r['accounting']['observed_subtree_delta_ns'],19000)
        self.assertEqual(r['accounting']['conservative_cpu_ns'],21000)
        self.assertEqual(a.finish(),r)

    def test_parent_exit_with_live_descendants_is_pending_until_scope_empty(self):
        a=self.adapter([S('owned-domain',0,0,False),S('owned-domain',30,4000,True),S('owned-domain',40,9000,False)])
        a.close_dispatch_and_stop();r=a.finish()
        self.assertFalse(r['complete']);self.assertTrue(r['cleanup_pending']);self.assertFalse(r['may_delete_scope'])
        self.assertTrue(a.finish()['complete'])

    def test_vanished_scope_or_counter_read_fault_never_becomes_zero(self):
        for exc in (ProcessLookupError('vanished'),FileNotFoundError('removed'),PermissionError('unreadable')):
            a=self.adapter([S('owned-domain',0,0,False),exc,S('owned-domain',30,9000,False)])
            with self.assertRaises(AccountingError):a.checkpoint()
            op=Mock()
            with self.assertRaises(AccountingError):a.dispatch(op)
            op.assert_not_called();a.close_dispatch_and_stop();r=a.finish()
            self.assertFalse(r['complete']);self.assertIsNone(r['accounting'])

    def test_stop_errors_and_unacknowledged_controls_stay_failed_even_if_empty(self):
        for control in ('seal','stop'):
            for value in (False,ProcessLookupError('process vanished')):
                bad=Mock(side_effect=value) if isinstance(value,Exception) else Mock(return_value=value)
                a=self.adapter([S('owned-domain',0,0,False),S('owned-domain',30,9000,False)],**{control:bad})
                a.close_dispatch_and_stop();r=a.finish()
                self.assertFalse(r['complete']);self.assertEqual(r['errors'][0]['stage'],control)
                with self.assertRaises(AccountingError):a.close_dispatch_and_stop()
                bad.assert_called_once()

    def test_deleted_domain_during_shutdown_is_failure_not_quiescence(self):
        a=self.adapter([S('owned-domain',0,0,False),FileNotFoundError('deleted too early')])
        a.close_dispatch_and_stop();self.assertFalse(a.finish()['complete'])

    def test_dispatch_samples_both_sides_and_cannot_continue_after_failure(self):
        a=self.adapter([S('owned-domain',0,0,False),S('owned-domain',10,0,False),S('owned-domain',15,8000,False)])
        op=Mock(return_value='original fixture');self.assertEqual(a.dispatch(op),'original fixture');op.assert_called_once()
        a.close_dispatch_and_stop()
        with self.assertRaises(AccountingError):a.dispatch(op)

    def test_budget_quote_does_not_relabel_capacity_as_measurement(self):
        old=capacity_plan(12,60,30,budget_cpu_s=300)
        self.assertFalse(old['fits']);self.assertEqual(old['maximum_cpu_s'],1080)
        proposal=capacity_plan(12,240,60,budget_cpu_s=3600)
        self.assertTrue(proposal['fits']);self.assertEqual(proposal['termination_deadline_s'],300)
        self.assertTrue(proposal['requires_verified_owned_termination'])
        with self.assertRaises(AccountingError):capacity_plan(2.0,60,30,budget_cpu_s=300)
