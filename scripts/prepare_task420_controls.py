#!/usr/bin/env python3
"""Prepare original controls/locks and a reviewable plan; never execute the plan.

No Docker, network, package install, model connection or benchmark operation is
performed. A separate, approved live integration must supply actual CPU/ownership
events to SetupWatchdog and CpuLedger; the plan cannot certify those itself.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aki.setup_plan import container_command, render_locks


def prepare(output, attempt):
    output = output.resolve()
    if output == ROOT or not output.is_relative_to(ROOT):
        raise ValueError('prepare inside a dedicated project output directory')
    proposal = json.loads((ROOT/'results/runtime/task420-setup-proposal.json').read_text())
    spec = importlib.util.spec_from_file_location('aki_guest_control', ROOT/'runtime/task420/control.py')
    control = importlib.util.module_from_spec(spec); spec.loader.exec_module(control)
    # Local manifest ID is learned from verified import; no guessed config ID.
    placeholder = 'sha256:'+'0'*64
    create = container_command(attempt, placeholder, output, ROOT, control.clean_environment())
    locks = render_locks(proposal)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    directory = output/'control'; directory.mkdir(mode=0o755)
    for name, contents in locks.items(): (directory/name).write_text(contents)
    (directory/'control.py').write_bytes((ROOT/'runtime/task420/control.py').read_bytes())
    (directory/'idle.py').write_bytes((ROOT/'research/task420-attempt1/control/idle.py').read_bytes())
    plan = {
        'status': 'prepared only; not authorized or live-validated', 'live_execution_enabled': False,
        'attempt_identity': attempt, 'task': 'Backblaze__B2_Command_Line_Tool-420',
        'registry_image': proposal['image'],
        'create_argv_template': create,
        'local_image_placeholder': placeholder,
        'image_rule': 'Replace placeholder only with verified imported local manifest; match exact exported original config and layer hashes.',
        'guest_preflight_argv': [control.PYTHON, '-I', '-B', '/control/control.py', 'preflight'],
        'source_transfer_argv': [control.PYTHON, '-I', '-B', '/control/control.py', 'populate'],
        'setup_steps': control.setup_steps(), 'guest_environment': control.clean_environment(),
        'environment_verification': 'Merge explicit guest_environment with Env from the digest-verified public image config using expected_container_environment; reject all other actual container variables.',
        'supervision': {'total_wall_seconds': 600, 'teardown_reserved_seconds': 90,
                        'cpu_ceiling_seconds': 300, 'cleanup_cpu_reserved_seconds': 120,
                        'transfer_bytes': 512*1024**2, 'disk_bytes': 3*1024**3,
                        'required_cpu_components': ['supervisor', 'workers', 'runtime_host', 'guest'],
                        'unknown_accounting': 'Stop work, attempt bounded owned-resource cleanup, report incomplete.'},
        'sequence': ['validate_frozen_inputs', 'start_outer_supervisor', 'stage_verified_artifacts',
                     'start_native_vm_and_register_owned_pids', 'load_image_once', 'verify_original_config_and_layers',
                     'create_one_confined_container', 'verify_actual_container_configuration',
                     'guest_preflight', 'source_transfer', 'offline_setup_steps',
                     'owned_recorder_fixture', 'bounded_teardown', 'finalize_all_cpu_components'],
        'checks_before_any_agent': ['All ownership and CPU accounting finalized within bounds.',
                                  'No metadata-only or mocked test substitutes for live recorder validation.',
                                  'No agent/model dispatch is implemented or enabled by this plan.'],
        'control_sha256': {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(directory.iterdir())},
    }
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n')
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--attempt-id', required=True, help='32 lowercase hex characters; never reused for another attempt')
    args = parser.parse_args()
    result = prepare(args.output, args.attempt_id)
    print(json.dumps({'status': result['status'], 'steps': len(result['setup_steps']), 'live_execution_enabled': False}))
