#!/usr/bin/env python3
"""Bounded pinned data read; never executes dataset code or trajectory commands.

Requires an already-installed pyarrow. Stores restricted research inputs outside
this repository. No outcome/patch columns or assistant reasoning are selected.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request

DATASET = 'nebius/SWE-rebench-openhands-trajectories'
REVISION = '35455389ab51bf5e2306bfd436ef72d0f98bf882'
URL = f'https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/trajectories.parquet'
SIZE = 2079503354
CAP = 150 * 1024**2
SELECTION = 'aki-phase3-2026-10-25:'


def project_messages(trajectory):
    """Keep only audit-relevant calls/responses, without reasoning or edit text."""
    messages = []
    for message in trajectory:
        if message['role'] == 'assistant' and message.get('tool_calls'):
            calls = []
            for call in message['tool_calls']:
                function = call['function']; name = function['name']
                arguments = json.loads(function['arguments'])
                allowed = ('command','path','view_range') if name == 'str_replace_editor' else ('command','is_input','timeout') if name == 'execute_bash' else ()
                arguments = {k: arguments[k] for k in allowed if k in arguments}
                calls.append({**call, 'function': {'name': name, 'arguments': json.dumps(arguments)}})
            messages.append({'role': 'assistant', 'tool_calls': calls})
        elif message['role'] == 'tool':
            projected = {key: message.get(key) for key in ('role','name','tool_call_id','content')}
            if message.get('name') not in ('str_replace_editor','execute_bash'):
                projected['content'] = ''
            messages.append(projected)
    return messages


class RangeFile(io.RawIOBase):
    def __init__(self):
        self.pos = 0
        self.total = 0
        self.ranges = []

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else SIZE + offset
        if not 0 <= self.pos <= SIZE:
            raise ValueError('seek outside pinned file')
        return self.pos

    def read(self, count=-1):
        count = SIZE - self.pos if count < 0 else min(count, SIZE - self.pos)
        if count == 0: return b''
        if self.total + count > CAP:
            raise ValueError('150 MiB transfer cap exceeded')
        start, end = self.pos, self.pos + count - 1
        req = urllib.request.Request(URL + f'?range={start}-{end}',
                                     headers={'Range': f'bytes={start}-{end}'})
        with urllib.request.urlopen(req, timeout=60) as response:
            if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{SIZE}':
                raise ValueError('server did not honor exact pinned byte range')
            payload = response.read(count + 1)
        if len(payload) != count: raise ValueError('unexpected byte count')
        self.pos += count
        self.total += count
        self.ranges.append({'start': start, 'end': end, 'sha256': hashlib.sha256(payload).hexdigest()})
        return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    if args.output.resolve().is_relative_to(project):
        raise ValueError('research inputs must be outside the public project')
    import pyarrow
    import pyarrow.parquet as pq
    source = RangeFile()
    parquet = pq.ParquetFile(source)
    ids = parquet.read_row_group(0, columns=['trajectory_id']).column(0).to_pylist()
    selected = set(sorted(range(len(ids)), key=lambda i: hashlib.sha256((SELECTION + ids[i]).encode()).hexdigest())[:128])
    # Reading selected column chunks is much smaller than the 2 GB complete file.
    table = parquet.read_row_group(0, columns=['trajectory_id', 'instance_id', 'repo', 'trajectory'])
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / 'sample.jsonl'
    with path.open('w') as stream:
        for index in sorted(selected):
            row = table.slice(index, 1).to_pylist()[0]
            row['trajectory'] = project_messages(row['trajectory'])
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    manifest = {'dataset': DATASET, 'revision': REVISION, 'license': 'CC-BY-4.0',
                'parquet_bytes': SIZE, 'parquet_rows': parquet.metadata.num_rows,
                'row_group': 0, 'row_group_rows': len(ids), 'selected_rows': len(selected),
                'selection': 'lowest SHA256(' + SELECTION + ' + trajectory_id)',
                'selected_indices': sorted(selected), 'transfer_bytes': source.total,
                'ranges': source.ranges, 'pyarrow': pyarrow.__version__,
                'sample_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'sample_bytes': path.stat().st_size,
                'excluded': ['outcome columns', 'model patch column', 'assistant reasoning and think arguments',
                             'editor new/old text arguments', 'system/user prompts']}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({k: manifest[k] for k in ('selected_rows', 'transfer_bytes', 'sample_bytes', 'sample_sha256')}))


if __name__ == '__main__': main()
