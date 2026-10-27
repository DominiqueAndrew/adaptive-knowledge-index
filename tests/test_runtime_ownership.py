import copy
import unittest
from unittest import mock
import sys
from pathlib import Path
from aki.runtime_ownership import propose_lease,verify_runtime,cleanup_plan,OwnershipError
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import run_task420_attempt as legacy


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.args={'profile':'aki-fixture','attempt':'a'*32,'endpoint':'unix:///fixture/aki-fixture/docker.sock','attempt_root':'/fixture/project/scratch/run','workspace':'/fixture/project','existing_profiles':['default','unrelated']}
        self.lease=propose_lease(**self.args)
        self.actual={'profile':'aki-fixture','attempt':'a'*32,'owner':'adaptive-knowledge-index','endpoint':self.args['endpoint'],
                     'arch':'aarch64','cpus':2,'memory_bytes':2*1024**3,'readonly_mounts':list(self.lease.readonly_mounts),'writable_mounts':[],
                     'ssh_agent':False,'rosetta':False,'binfmt_handlers':[],'public_address':False,'port_forwarder':'none','template':False,'kubernetes':False,'containers':[]}

    def test_preexisting_profile_or_private_mount_is_rejected(self):
        for changes in [{'profile':'default'},{'existing_profiles':['aki-fixture']},{'attempt_root':'/private'},{'endpoint':'tcp://localhost:2375'}]:
            with self.assertRaises(OwnershipError):propose_lease(**(self.args|changes))

    def test_exact_empty_owned_runtime_passes(self):self.assertTrue(verify_runtime(self.lease,self.actual))

    def test_legacy_default_adapter_cannot_reopen_a_live_attempt(self):
        with mock.patch.object(sys,'argv',['driver','--execute-approved-single-attempt','--validation-only','--campaign','unused']),mock.patch.object(legacy,'SharedBudget',side_effect=AssertionError('ledger touched')),mock.patch.object(legacy.subprocess,'run',side_effect=AssertionError('runtime touched')):
            with self.assertRaisesRegex(SystemExit,'Live adapter disabled'):legacy.main()

    def test_identity_security_and_foreign_container_block_cleanup(self):
        for change in [{'attempt':'b'*32},{'readonly_mounts':['/private']},{'writable_mounts':['/fixture']},{'ssh_agent':True},{'port_forwarder':'ssh'},
                       {'containers':[{'id':'c'*64,'attempt':'foreign'}]}]:
            with self.assertRaises(OwnershipError):cleanup_plan(self.lease,self.actual|change,created_container_ids=frozenset())

    def test_cleanup_only_accepts_created_ids_and_exact_owner(self):
        actual=copy.deepcopy(self.actual);actual['containers']=[{'id':'c'*64,'attempt':'a'*32}]
        with self.assertRaises(OwnershipError):cleanup_plan(self.lease,actual,created_container_ids=set())
        p=cleanup_plan(self.lease,actual,created_container_ids={'c'*64})
        self.assertFalse(p['may_stop_default_profile']);self.assertFalse(p['executable'])
