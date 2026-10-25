"""Host-owned fixtures/mocks only: no Docker, downloads, installs or benchmark code."""
import ast
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

from aki.setup_accounting import AccountingError, ByteLedger, CpuLedger, darwin_process_cpu, guest_cpu_snapshot
from aki.setup_plan import PlanError, container_command, expected_container_environment, owned_container_removal, render_locks, verify_container, verify_loaded_image
from aki.setup_watchdog import Command, SetupStopped, SetupWatchdog

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('aki_test_guest', ROOT/'runtime/task420/control.py')
GUEST = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(GUEST)
ATTEMPT = 'a'*32
IMAGE = 'sha256:'+'b'*64


def original_file(name='src/example.py', data=b'value = 1\n'):
    return {'path': name, 'data': base64.b64encode(data).decode(),
            'sha256': hashlib.sha256(data).hexdigest(), 'mode': 0o644}


def good_inspect():
    return {'Id': 'c'*64, 'Image': IMAGE,
            'Config': {'User': '65534:65534', 'Labels': {'org.aki.attempt': ATTEMPT}, 'Env': ['HOME=/tmp']},
            'HostConfig': {'Privileged': False, 'ReadonlyRootfs': True, 'NetworkMode': 'none',
                           'CapAdd': None, 'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges:true'],
                           'NanoCpus': 10**9, 'Memory': 1024**3, 'MemorySwap': 1024**3, 'PidsLimit': 64,
                           'Tmpfs': {name: 'rw,nosuid,nodev,noexec,size='+size+',uid=65534,gid=65534'
                                     for name, size in [('/env', '256m'), ('/workspace', '64m'), ('/tmp', '128m')]}},
            'Mounts': [{'Destination': '/'+name, 'Source': '/fixture/attempt/'+name, 'RW': False, 'Type': 'bind'}
                       for name in ('control', 'packages')]}


class GuestPlanTests(unittest.TestCase):
    def test_control_is_python35_syntax_and_never_calls_data_interpreter(self):
        ast.parse((ROOT/'runtime/task420/control.py').read_text(), feature_version=(3, 5))
        for name, argv in GUEST.setup_steps():
            self.assertEqual(argv[:4], ['/usr/local/bin/python3', '-I', '-B', '-c'])
            self.assertNotIn('venv', argv)
            self.assertFalse(any('/env/bin/' in arg for arg in argv))
        self.assertIn('from b2.console_tool import main; main()', dict(GUEST.setup_steps())['cli_help'][4])
        self.assertIn('--egg-base', dict(GUEST.setup_steps())['project_metadata'][4])

    def test_bootstrap_and_runtime_install_are_separate_offline_hash_locked_targets(self):
        steps = dict(GUEST.setup_steps())
        for name, target in [('bootstrap', GUEST.BOOT), ('dependencies', GUEST.SITE)]:
            args = steps[name]
            for flag in ['--no-index', '--no-deps', '--no-cache-dir', '--require-hashes', '--no-compile']:
                self.assertIn(flag, args)
            self.assertEqual(args[args.index('--target')+1], target)
        self.assertNotIn('/workspace', steps['bootstrap'][4])
        self.assertNotIn('/workspace', steps['dependencies'][4])

    def test_environment_does_not_inherit_host_secret_or_pip_configuration(self):
        with mock.patch.dict(os.environ, {'PRIVATE_TEST_TOKEN': 'fixture-only', 'PIP_INDEX_URL': 'https://invalid.example'}):
            env = GUEST.clean_environment()
        self.assertNotIn('PRIVATE_TEST_TOKEN', env); self.assertNotIn('PIP_INDEX_URL', env)
        self.assertEqual(env['PIP_CONFIG_FILE'], '/dev/null')
        self.assertEqual(env['B2_ACCOUNT_INFO'], '/tmp/aki-empty-account.sqlite')

    def test_mount_check_accepts_noexec_data_but_rejects_executable_workspace(self):
        lines = ['overlay / overlay ro 0 0'] + ['tmpfs '+p+' tmpfs rw,nosuid,nodev,noexec 0 0'
                                               for p in ['/env', '/workspace', '/tmp']]
        self.assertTrue(GUEST.check_mounts(lines, 65534, (3, 5, 10)))
        for altered in [lines[:-1], [s.replace('noexec', 'exec') for s in lines], lines+['tmpfs /usr/local tmpfs noexec 0 0']]:
            with self.assertRaises(ValueError): GUEST.check_mounts(altered, 65534, (3, 5, 10))
        with self.assertRaises(ValueError): GUEST.check_mounts(lines, 0, (3, 5, 10))
        with self.assertRaises(ValueError): GUEST.check_mounts(lines, 65534, (3, 11, 0))

    def test_source_transfer_validates_all_rows_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = original_file('../escape.py')
            with self.assertRaises(ValueError): GUEST.populate(directory, [original_file(), bad])
            self.assertEqual(list(Path(directory).iterdir()), [])
            self.assertEqual(GUEST.populate(directory, [original_file()])['files'], 1)
            self.assertEqual((Path(directory)/'src/example.py').read_bytes(), b'value = 1\n')
            with self.assertRaises(ValueError): GUEST.populate(directory, [original_file()])

    def test_source_transfer_rejects_ambiguous_names_hashes_and_modes(self):
        cases = [[original_file(), original_file('SRC/EXAMPLE.py')],
                 [original_file('a'), original_file('a/b')], [original_file('.secret')],
                 [dict(original_file(), data='???')], [dict(original_file(), sha256='0'*64)],
                 [dict(original_file(), mode=0o4755)]]
        for rows in cases:
            with self.subTest(rows=rows):
                with self.assertRaises((ValueError, TypeError)): GUEST.validate_source(rows)

    def test_artifact_fixture_checks_size_hash_symlinks_and_extras(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'original.txt').write_bytes(b'fixture')
            records = [{'filename': 'original.txt', 'size': 7, 'sha256': hashlib.sha256(b'fixture').hexdigest()}]
            self.assertTrue(GUEST.verify_artifacts(directory, records))
            (root/'extra').write_bytes(b'not approved')
            with self.assertRaises(ValueError): GUEST.verify_artifacts(directory, records)
            (root/'extra').unlink(); (root/'original.txt').unlink(); (root/'original.txt').symlink_to('missing')
            with self.assertRaises(ValueError): GUEST.verify_artifacts(directory, records)


class PlanValidationTests(unittest.TestCase):
    def test_published_candidate_renders_three_bootstrap_and_26_runtime_pins(self):
        proposal = json.loads((ROOT/'results/runtime/task420-setup-proposal.json').read_text())
        locks = render_locks(proposal)
        self.assertEqual(len(locks['bootstrap.lock'].splitlines()), 3)
        self.assertEqual(len(locks['runtime.lock'].splitlines()), 26)
        proposal['candidate_dependencies']['packages'][0]['version'] = 'x\nmalicious'
        with self.assertRaises(PlanError): render_locks(proposal)

    def test_import_identity_accepts_converted_manifest_only_with_exact_blob_and_layers(self):
        config = json.dumps({'architecture': 'arm64', 'os': 'linux', 'rootfs': {'diff_ids': ['sha256:a']}}).encode()
        digest = 'sha256:'+hashlib.sha256(config).hexdigest()
        info = {'Architecture': 'arm64', 'Os': 'linux', 'Id': IMAGE, 'RootFS': {'Layers': ['sha256:a']}}
        self.assertEqual(verify_loaded_image(config, digest, config, info)['local_manifest'], IMAGE)
        with self.assertRaises(PlanError): verify_loaded_image(config, digest, config+b' ', info)
        info['RootFS']['Layers'] = ['sha256:changed']
        with self.assertRaises(PlanError): verify_loaded_image(config, digest, config, info)

    def test_container_plan_keeps_every_writable_mount_noexec(self):
        args = container_command(ATTEMPT, IMAGE, '/fixture/attempt', '/fixture', GUEST.clean_environment())
        mounts = [args[i+1] for i, arg in enumerate(args) if arg == '--tmpfs']
        self.assertEqual(len(mounts), 3)
        self.assertTrue(all(',noexec,' in value for value in mounts))
        self.assertNotIn('--privileged', args)
        with self.assertRaises(PlanError): container_command(ATTEMPT, IMAGE, '/private', '/fixture', {})

    def test_image_environment_is_merged_only_from_verified_public_config(self):
        blob = json.dumps({'config': {'Env': ['PYTHON_VERSION=3.5.10', 'HOME=/root']}}).encode()
        digest = 'sha256:'+hashlib.sha256(blob).hexdigest()
        env = expected_container_environment(blob, digest, {'HOME': '/tmp'})
        self.assertEqual(env, {'PYTHON_VERSION': '3.5.10', 'HOME': '/tmp'})
        with self.assertRaises(PlanError): expected_container_environment(blob+b' ', digest, {})
        info = good_inspect(); info['Config']['Env'].append('PYTHON_VERSION=3.5.10')
        self.assertTrue(verify_container(info, ATTEMPT, IMAGE, '/fixture/attempt', env))
        info['Config']['Env'].append('HTTP_PROXY=fixture-only')
        with self.assertRaises(PlanError): verify_container(info, ATTEMPT, IMAGE, '/fixture/attempt', env)

    def test_confinement_rejects_security_and_private_environment_changes(self):
        info = good_inspect()
        self.assertTrue(verify_container(info, ATTEMPT, IMAGE, '/fixture/attempt', {'HOME': '/tmp'}))
        changes = [('Privileged', True), ('NetworkMode', 'host'), ('ReadonlyRootfs', False),
                   ('SecurityOpt', ['no-new-privileges:true', 'seccomp=unconfined']),
                   ('MemorySwap', 2*1024**3), ('Devices', [{}]), ('PidMode', 'host')]
        for key, value in changes:
            changed = copy.deepcopy(info); changed['HostConfig'][key] = value
            with self.subTest(key=key):
                with self.assertRaises(PlanError): verify_container(changed, ATTEMPT, IMAGE, '/fixture/attempt', {'HOME': '/tmp'})
        changed = copy.deepcopy(info); changed['Config']['Env'].append('HTTP_PROXY=fixture-only')
        with self.assertRaises(PlanError): verify_container(changed, ATTEMPT, IMAGE, '/fixture/attempt', {'HOME': '/tmp'})
        changed = copy.deepcopy(info); changed['Mounts'][0]['RW'] = True
        with self.assertRaises(PlanError): verify_container(changed, ATTEMPT, IMAGE, '/fixture/attempt', {'HOME': '/tmp'})

    def test_tmpfs_normalization_and_conflicting_options(self):
        info = good_inspect(); info['HostConfig']['Tmpfs']['/env'] = info['HostConfig']['Tmpfs']['/env'].replace('256m', '268435456')
        self.assertTrue(verify_container(info, ATTEMPT, IMAGE, '/fixture/attempt', {'HOME': '/tmp'}))
        for suffix in [',exec', ',uid=0', ',size=1g']:
            altered = copy.deepcopy(info); altered['HostConfig']['Tmpfs']['/env'] += suffix
            with self.assertRaises(PlanError): verify_container(altered, ATTEMPT, IMAGE, '/fixture/attempt', {'HOME': '/tmp'})

    def test_cleanup_requires_created_id_and_matching_owner(self):
        info = good_inspect()
        self.assertEqual(owned_container_removal(info, ATTEMPT, {info['Id']})[-1], info['Id'])
        with self.assertRaises(PlanError): owned_container_removal(info, ATTEMPT, set())
        with self.assertRaises(PlanError): owned_container_removal(info, 'd'*32, {info['Id']})


class AccountingTests(unittest.TestCase):
    def ledger(self):
        result = CpuLedger()
        for name in result.REQUIRED:
            result.register(name, name, 4 if name == 'guest' else 1, 0, 0, active=True)
        return result

    def test_missing_counters_are_not_free_cpu(self):
        with self.assertRaises(AccountingError): CpuLedger().snapshot(0)

    def test_unsampled_tail_counts_toward_cpu_and_is_finalized_with_bound(self):
        ledger = self.ledger(); ledger.update('guest', 'guest', 10, 20)
        self.assertEqual(ledger.snapshot(30)['components']['guest']['unobserved_upper_bound_ns'], 40)
        for name in ledger.REQUIRED: ledger.finalize(name, 40, confirmed=True)
        final = ledger.snapshot(100)
        self.assertTrue(final['finalized'])
        self.assertEqual(final['components']['guest']['unobserved_upper_bound_ns'], 80)

    def test_identity_reset_negative_time_or_unconfirmed_shutdown_fails(self):
        ledger = self.ledger(); ledger.update('guest', 'guest', 10, 20)
        for args in [('guest', 'rebooted', 11, 21), ('guest', 'guest', 9, 21), ('guest', 'guest', 11, 19)]:
            with self.assertRaises(AccountingError): ledger.update(*args)
        with self.assertRaises(AccountingError): ledger.finalize('guest', 30, confirmed=False)

    def test_guest_hz_is_observed_and_guest_time_not_double_counted(self):
        text = 'cpu 10 2 3 99 88 4 5 6 1000 2000\n'
        record = guest_cpu_snapshot(text, 250, '12345678-1234-1234-1234-123456789abc')
        self.assertEqual(record['cpu_ns'], 30*10**9//250)
        with self.assertRaises(AccountingError): guest_cpu_snapshot(text, None, record['identity'])

    def test_transfer_retries_and_disk_reservations_do_not_reset(self):
        ledger = ByteLedger(10, 20); ledger.receive(6)
        with self.assertRaises(AccountingError): ledger.receive(5)
        ledger.allocate(15); ledger.release(5); ledger.allocate(10)
        self.assertEqual(ledger.disk_peak, 20)
        with self.assertRaises(AccountingError): ledger.allocate(1)
        with self.assertRaises(AccountingError): ledger.release(21)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS-owned-process sampler fixture')
    def test_mac_sampler_reads_only_this_owned_process(self):
        before = darwin_process_cpu(os.getpid()); start = time.process_time()
        while time.process_time()-start < 0.01: pass
        after = darwin_process_cpu(os.getpid())
        self.assertEqual(before['identity'], after['identity'])
        self.assertGreater(after['cpu_ns'], before['cpu_ns'])


class WatchdogFixtureTests(unittest.TestCase):
    @staticmethod
    def metrics(value=0, finalized=True):
        return {'conservative_cpu_ns': value, 'finalized': finalized, 'fixture_only': True,
                'components': {name: {'measured_ns': value if name == 'supervisor' else 0,
                                      'unobserved_upper_bound_ns': 0,
                                      'active': name == 'supervisor' and not finalized}
                               for name in CpuLedger.REQUIRED}}

    def command(self, code, name='owned-fixture', **kwargs):
        return Command(name, (sys.executable, '-S', '-c', code), **kwargs)

    def test_blocked_input_is_interrupted_and_cleanup_has_reserved_time(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory)/'cleaned'
            cleanup = self.command('from pathlib import Path; Path('+repr(str(marker))+').write_text("done")', 'cleanup')
            runner = SetupWatchdog(cpu_snapshot=self.metrics, total_s=1, teardown_reserve_s=0.6)
            result = runner.run([self.command('import time; time.sleep(60)', input_bytes=b'x'*1024**2)], [cleanup])
            self.assertTrue(marker.exists()); self.assertEqual(result['status'], 'work_stopped')
            self.assertLess(result['elapsed_s'], 1)
            with self.assertRaises(SetupStopped): runner.run([], [])

    def test_hung_cleanup_is_bounded_and_reported_pending(self):
        runner = SetupWatchdog(cpu_snapshot=self.metrics, total_s=0.6, teardown_reserve_s=0.4)
        result = runner.run([], [self.command('import time; time.sleep(60)', 'hung-cleanup')])
        self.assertTrue(result['cleanup_pending']); self.assertEqual(result['status'], 'cleanup_pending')
        self.assertLess(result['elapsed_s'], 0.8)

    def test_output_flood_stops_work_and_still_cleans(self):
        runner = SetupWatchdog(cpu_snapshot=self.metrics, total_s=1, teardown_reserve_s=0.5, output_limit=100)
        result = runner.run([self.command('print("x"*10000)')], [self.command('pass', 'cleanup')])
        self.assertIn('output cap', result['reason']); self.assertEqual(len(result['cleanup']), 1)

    def test_missing_cpu_stops_work_without_suppressing_safety_cleanup(self):
        def missing(): raise AccountingError('missing runtime counter')
        runner = SetupWatchdog(cpu_snapshot=missing, total_s=1, teardown_reserve_s=0.5)
        result = runner.run([self.command('raise AssertionError("must not run")')], [self.command('pass', 'cleanup')])
        self.assertEqual(result['work'], []); self.assertEqual(len(result['cleanup']), 1)
        self.assertFalse(result['accounting_complete']); self.assertEqual(result['status'], 'accounting_incomplete')

    def test_cpu_reserve_stops_work_before_hard_cpu_ceiling(self):
        sample = lambda: self.metrics(190)
        runner = SetupWatchdog(cpu_snapshot=sample, total_s=1, teardown_reserve_s=0.5,
                               cpu_limit_ns=300, cleanup_cpu_reserve_ns=120)
        result = runner.run([self.command('raise AssertionError("must not run")')], [self.command('pass', 'cleanup')])
        self.assertEqual(result['work'], []); self.assertEqual(len(result['cleanup']), 1)
        self.assertFalse(result['cpu_ceiling_exceeded'])

    def test_unfinalized_cpu_prevents_success_claim(self):
        sample = lambda: self.metrics(finalized=False)
        result = SetupWatchdog(cpu_snapshot=sample, total_s=1, teardown_reserve_s=0.5).run([], [])
        self.assertEqual(result['status'], 'accounting_incomplete')

    def test_inconsistent_or_missing_final_cpu_cannot_claim_completion(self):
        for broken in [{'conservative_cpu_ns': 0, 'finalized': True},
                       dict(self.metrics(), conservative_cpu_ns=-1),
                       dict(self.metrics(), conservative_cpu_ns=100)]:
            result = SetupWatchdog(cpu_snapshot=lambda: broken, total_s=1, teardown_reserve_s=0.5).run([], [])
            self.assertEqual(result['status'], 'accounting_incomplete')

    def test_cleanup_failure_is_recorded_and_does_not_skip_next_owned_cleanup(self):
        runner = SetupWatchdog(cpu_snapshot=self.metrics, total_s=1, teardown_reserve_s=0.5)
        result = runner.run([], [self.command('raise SystemExit(4)', 'first'), self.command('pass', 'second')])
        self.assertEqual([r['name'] for r in result['cleanup']], ['second'])
        self.assertEqual(result['cleanup_pending'][0]['name'], 'first')
        self.assertEqual(result['command_records'][0]['exit'], 4)


if __name__ == '__main__':
    unittest.main()
