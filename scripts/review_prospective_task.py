#!/usr/bin/env python3
"""Inspect frozen development-task runtime metadata, never actions or gold labels.

Uses the existing bounded inert HTTP cache. Does not pull/build/run an image,
install dependencies, execute setup strings or inspect evaluation tasks.
"""
import argparse
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from replay_inputs import Budget, RemoteParquet


COLUMNS = [
    'instance_id', 'repo', 'base_commit', 'environment_setup_commit', 'version',
    'license_name', 'docker_image', 'image_name', 'install_config',
]
FILES = [
    'data/filtered-00000-of-00001.parquet',
    'data/test-00000-of-00002.parquet',
    'data/test-00001-of-00002.parquet',
]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--cohort', type=Path, required=True)
    p.add_argument('--instance', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    cohort = json.loads(args.cohort.read_text())
    eligible = [r for r in cohort['cohort']
                if r['instance_id'] == args.instance and r['split'] == 'development']
    if len(eligible) != 1:
        raise ValueError('Select exactly one frozen development task')
    task = eligible[0]
    budget = Budget(args.inputs)
    before = budget.state['downloaded_bytes']
    matches = []
    for name in FILES:
        url = ('https://huggingface.co/datasets/nebius/SWE-rebench/resolve/'
               + cohort['task_revision'] + '/' + name)
        parquet = pq.ParquetFile(RemoteParquet(budget, url))
        for group in range(parquet.num_row_groups):
            ids = parquet.read_row_group(group, columns=['instance_id']).column(0).to_pylist()
            positions = [i for i, value in enumerate(ids) if value == args.instance]
            if not positions:
                continue
            columns = [c for c in COLUMNS if c in parquet.schema_arrow.names]
            rows = parquet.read_row_group(group, columns=columns).to_pylist()
            for index in positions:
                row = rows[index]
                for key in ['repo', 'base_commit', 'environment_setup_commit']:
                    if row[key] != task[key]:
                        raise ValueError('Metadata disagrees with frozen cohort: ' + key)
                matches.append({'dataset_file': name, 'row_group': group,
                                'row_index': index, 'fields': row})
        budget.save()
    if not matches or any(r['fields'] != matches[0]['fields'] for r in matches):
        raise ValueError('Missing or conflicting task metadata')
    encoded = json.dumps(matches, sort_keys=True, separators=(',', ':')).encode()
    report = {
        'task_revision': cohort['task_revision'], 'instance_id': args.instance,
        'selected_columns': COLUMNS, 'matches': matches,
        'metadata_sha256': hashlib.sha256(encoded).hexdigest(),
        'new_download_bytes': budget.state['downloaded_bytes'] - before,
        'image_declared': bool(matches[0]['fields'].get('docker_image')
                               or matches[0]['fields'].get('image_name')),
        'commands_executed': False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in
                      ['instance_id', 'image_declared', 'new_download_bytes', 'metadata_sha256']}))


if __name__ == '__main__':
    main()
