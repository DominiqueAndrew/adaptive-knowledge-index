"""Adversarial protocol review. All actors/receipts are original host fixtures."""
import ast
import copy
from dataclasses import replace
from pathlib import Path
import unittest
from aki.isolated_launcher import IsolatedLauncher, Limits, LaunchError, host_backend_readiness
from aki.runtime_ownership import RuntimeLease

ATTEMPT='a'*32
PIN={'sha256':'a'*64,'sha512':'b'*128,'size':1234}
LEASE=RuntimeLease('aki-fixture',ATTEMPT,'unix:///fixture/aki-fixture/control.sock',(),runtime='none')
RUNTIME={'profile':'aki-fixture','attempt':ATTEMPT,'owner':'adaptive-knowledge-index','endpoint':LEASE.endpoint,'runtime':'none',
         'arch':'aarch64','cpus':2,'memory_bytes':2*1024**3,'readonly_mounts':[],'writable_mounts':[],
         'ssh_agent':False,'rosetta':False,'binfmt_handlers':[],'public_address':False,'port_forwarder':'none',
         'template':False,'kubernetes':False,'containers':[]}


def receipts(kind='fixture'):
    values={
        'preflight':{'fresh_namespace':True,'global_configuration_unchanged':True,'kernel_domain_enrolled_before_spawn':True,
                     'migration_denied':True,'external_dispatch_denied':True,'counter_retained_until_final':True,
                     'platform':'linux','backend':'owned-cgroup-v2','coverage':'all_vm_and_helper_execution',
                     'external_services':False,'host_scope':'fixture-boot:host-domain','host_logical_cpus':12},
        'artifact':PIN|{'expanded_size_checked':True,'maximum_expanded_bytes':3*1024**3,'no_extra_artifacts':True,
                        'expanded_bytes':1024**3,'disk_reservation_bytes':1234+5*1024**3+256*1024**2},
        'runtime':{'runtime':copy.deepcopy(RUNTIME),'all_helpers_in_host_scope':True,'runtime_config_read_back':True,
                   'vm_identity':'owned-vm-generation','boot_identity':'owned-guest-boot'},
        'guest':{'enrolled_before_exec':True,'nonroot':True,'no_new_privileges':True,'capabilities_empty':True,
                 'network_namespace_private':True,'network_routes':[],'host_mounts':[],'source_readonly':True,
                 'data_noexec':True,'cgroup_write_denied':True,'devices_denied':True,
                 'guest_scope':'owned-guest-boot:domain','boot_identity':'owned-guest-boot'},
        'fixture':{'only_original_fixture':True,'model_calls':0,'benchmark_operations':0,'heldout_reads':0,'complete_recorder_boundaries':True},
        'guest_final':{'dispatch_sealed':True,'stop_acknowledged':True,'populated':False,'counter_final_before_removal':True,
                       'read_error':False,'guest_scope':'owned-guest-boot:domain','boot_identity':'owned-guest-boot','cpu_ns':50000},
        'vm_stop':{'stop_acknowledged':True,'terminal_state_observed':True,'state':'stopped','vm_identity':'owned-vm-generation'},
        'host_final':{'dispatch_sealed':True,'populated':False,'all_registered_helpers_terminal':True,
                      'counter_final_before_removal':True,'event_loss':False,'read_error':False,'late_spawns':0,
                      'host_scope':'fixture-boot:host-domain','baseline_cpu_ns':10000,'cpu_ns':90000},
        'cleanup':{'only_attempt_resources':True,'runtime_removed':True,'temporary_credentials_removed':True,
                   'original_cache_unchanged':True,'global_configuration_unchanged':True,'private_mounts_used':False},
    }
    return {k:v|{'attempt':ATTEMPT,'evidence_kind':kind} for k,v in values.items()}


def through(controller,stop_before=None,rows=None):
    rows=rows or receipts(controller.kind)
    for stage in controller.STAGES:
        if stage==stop_before:return
        controller.resources(elapsed_ns=(controller.stage+1)*1_000_000_000,download_bytes=1234,disk_bytes=10_000)
        controller.intent(stage);controller.observe(stage,rows[stage])


class LauncherFaultTests(unittest.TestCase):
    def make(self,**kwargs):return IsolatedLauncher(LEASE,PIN,**kwargs)

    def test_complete_original_trace_is_contract_only_never_a_live_certificate(self):
        for kind in ('fixture','live'):
            c=self.make(evidence_kind=kind);through(c)
            report=c.report();self.assertTrue(report['contract_passed'])
            self.assertFalse(report['live_certified']);self.assertFalse(report['lifecycle_cpu_certified'])
            self.assertFalse(report['complete_vm_and_helper_evidence']);self.assertTrue(report['modeled_finalization_contract_passed'])
            self.assertFalse(report['executable_entrypoint_available']);self.assertFalse(report['cpu_cap_enforced'])
            self.assertEqual(report['whole_machine_cpu_window_bound_ns'],108_000_000_000)
            self.assertTrue(all(i['executable'] is False for i in c.intents))

    def test_installed_darwin_foreground_mode_is_rejected_before_acquisition(self):
        c=self.make();r=receipts()['preflight']|{'platform':'darwin','backend':'lima-foreground'}
        c.intent('preflight')
        with self.assertRaisesRegex(LaunchError,'no complete kernel'):c.observe('preflight',r)
        with self.assertRaises(LaunchError):c.intent('artifact')
        self.assertEqual(c.failure_cleanup_intent()['action'],'no_runtime_action')
        self.assertFalse(c.start_requested)

    def test_every_security_and_finalization_boolean_is_required(self):
        for stage,receipt in receipts().items():
            for key,value in receipt.items():
                if type(value) is not bool:continue
                with self.subTest(stage=stage,key=key):
                    c=self.make();through(c,stage);c.intent(stage)
                    with self.assertRaises(LaunchError):c.observe(stage,receipt|{key:not value})
                    self.assertFalse(c.report()['contract_passed'])

    def test_missing_receipt_fields_cannot_be_inferred_from_success_exit(self):
        for stage,key in [('preflight','host_scope'),('artifact','sha256'),('runtime','boot_identity'),
                          ('guest','guest_scope'),('guest_final','cpu_ns'),('vm_stop','vm_identity'),('host_final','cpu_ns')]:
            c=self.make();through(c,stage);r=receipts()[stage];del r[key];r['exit_code']=0;c.intent(stage)
            with self.assertRaises(LaunchError):c.observe(stage,r)

    def test_orphan_reparented_helper_and_event_loss_fail_even_after_vm_stop(self):
        # This independent final host gate rejects a stopped VM with a child still
        # alive, unknown exits, event loss, late forks, replaced identity or ESRCH.
        faults=[{'populated':True},{'all_registered_helpers_terminal':False},{'event_loss':True},
                {'late_spawns':1},{'host_scope':'reused-domain'},{'read_error':True},
                {'cpu_ns':None},{'cpu_ns':9999},{'baseline_cpu_ns':-1}]
        for fault in faults:
            c=self.make();through(c,'host_final');c.intent('host_final')
            with self.assertRaises(LaunchError):c.observe('host_final',receipts()['host_final']|fault)
            with self.assertRaises(LaunchError):c.intent('cleanup')
            self.assertFalse(c.report()['complete_vm_and_helper_evidence'])

    def test_guest_namespace_and_noexec_cannot_be_weakened(self):
        for fault in ({'network_routes':['default']},{'host_mounts':['/private']},
                      {'data_noexec':False},{'nonroot':False},{'boot_identity':'other-boot'}):
            c=self.make();through(c,'guest');c.intent('guest')
            with self.assertRaises(LaunchError):c.observe('guest',receipts()['guest']|fault)

    def test_foreign_resource_cannot_be_adopted_or_stopped_after_start_error(self):
        c=self.make();through(c,'runtime');c.intent('runtime')
        with self.assertRaises(LaunchError):c.observe('runtime',receipts()['runtime']|{'runtime':RUNTIME|{'attempt':'b'*32}})
        self.assertEqual(c.failure_cleanup_intent()['action'],'read_ownership_only')
        self.assertEqual(c.failure_cleanup_intent(RUNTIME|{'attempt':'b'*32})['action'],'no_runtime_action')
        owned=c.failure_cleanup_intent(RUNTIME)
        self.assertEqual(owned['action'],'request_owned_teardown');self.assertFalse(owned['may_stop_default'])
        self.assertFalse(owned['may_delete_unverified_state'])

    def test_uncertain_start_is_never_automatically_retried(self):
        c=self.make();through(c,'runtime');c.intent('runtime')
        with self.assertRaisesRegex(LaunchError,'uncertain'):c.intent('runtime')
        self.assertEqual(c.failure_cleanup_intent()['action'],'read_ownership_only')
        self.assertEqual(sum(i['stage']=='runtime' for i in c.intents),1)

    def test_budget_regression_and_exhaustion_fail_without_reset(self):
        for observation in ({'elapsed_ns':-1,'download_bytes':0,'disk_bytes':0},
            {'elapsed_ns':301*10**9,'download_bytes':0,'disk_bytes':0},
            {'elapsed_ns':1,'download_bytes':257*1024**2,'disk_bytes':0},
            {'elapsed_ns':1,'download_bytes':0,'disk_bytes':9*1024**3}):
            c=self.make()
            with self.assertRaises(LaunchError):c.resources(**observation)
            self.assertFalse(c.report()['contract_passed'])
        c=self.make();c.resources(elapsed_ns=2,download_bytes=100,disk_bytes=0)
        with self.assertRaises(LaunchError):c.resources(elapsed_ns=3,download_bytes=99,disk_bytes=0)

    def test_work_deadline_keeps_teardown_reserve_and_requires_final_receipts(self):
        c=self.make();through(c,'guest')
        c.resources(elapsed_ns=240*10**9,download_bytes=1234,disk_bytes=10000)
        with self.assertRaisesRegex(LaunchError,'deadline'):c.intent('guest')
        self.assertEqual(c.failure_cleanup_intent(RUNTIME)['action'],'request_owned_teardown')
        self.assertFalse(c.report()['lifecycle_cpu_certified'])

    def test_capacity_reservation_is_not_misrepresented_as_enforcement(self):
        with self.assertRaises(LaunchError):self.make(limits=replace(Limits(),cpu_reservation_s=300))
        smaller=Limits(work_wall_s=60,teardown_wall_s=30,cpu_reservation_s=1080)
        c=self.make(limits=smaller);self.assertFalse(c.report()['cpu_cap_enforced'])
        self.assertFalse(host_backend_readiness('linux','owned-cgroup-v2',coverage='only_guest',external_services=False)['ready'])
        self.assertFalse(host_backend_readiness('linux','owned-cgroup-v2',coverage='all_vm_and_helper_execution',external_services=True)['ready'])

    def test_no_executable_os_download_or_guest_command_backend_is_hidden_in_controller(self):
        p=Path(__file__).parents[1]/'aki'/'isolated_launcher.py';tree=ast.parse(p.read_text())
        imports={n.module for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
        imports|={a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names}
        self.assertFalse(imports & {'subprocess','os','socket','urllib','requests','ctypes'})
        calls={n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
        self.assertFalse(calls & {'exec','eval','open','compile','__import__'})

    def test_recorded_receipts_cannot_change_after_acceptance(self):
        c=self.make();r=receipts()['preflight'];intent=c.intent('preflight');intent['stage']='altered'
        c.observe('preflight',r);self.assertEqual(c.intents[0]['stage'],'preflight')
        r['host_scope']='tampered';self.assertEqual(c.receipts['preflight']['host_scope'],'fixture-boot:host-domain')

    def test_review_rejects_default_profile_even_if_lease_constructor_is_bypassed(self):
        for lease in (replace(LEASE,profile='default'),replace(LEASE,endpoint='unix:///other/control.sock'),
                      replace(LEASE,cpus=4),replace(LEASE,runtime='docker')):
            with self.assertRaises(LaunchError):IsolatedLauncher(lease,PIN)

    def test_review_requires_actual_expansion_size_and_full_disk_reservation(self):
        for fault in ({'expanded_bytes':None},{'expanded_bytes':4*1024**3},{'disk_reservation_bytes':1234}):
            c=self.make();through(c,'artifact');c.intent('artifact')
            with self.assertRaises(LaunchError):c.observe('artifact',receipts()['artifact']|fault)

    def test_review_preserves_nested_runtime_evidence_against_later_mutation(self):
        c=self.make();through(c,'runtime');r=receipts()['runtime'];c.intent('runtime');c.observe('runtime',r)
        r['runtime']['writable_mounts'].append('/private')
        self.assertEqual(c.receipts['runtime']['runtime']['writable_mounts'],[])
