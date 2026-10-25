# Opt-in source-boundary recorder

`aki.recorder` provides the missing observation mechanism; it does not implement
an agent, launch repository code, watch a filesystem, discover sessions, or upload
anything. It was demonstrated only on original project-owned synthetic fixtures.
No prospective agent evaluation is claimed.

## Run the original fixture demonstration

Requires Python 3.11+ on a POSIX host (tested on the connected Mac). No package,
credential, Docker image or model connection is needed.

```sh
python3 -S -m unittest discover -s tests -v
python3 scripts/recorder_demo.py --output scratch/my-recorder-demo
python3 scripts/verify_recording.py scratch/my-recorder-demo/capture
```

The output directory must be new. The demo creates its own source files and
records two reads, one edit, one creation and one deletion. It verifies five
complete operations, ten source boundaries and twelve journal events. These are
instrumentation tests, not agent tasks or retrieval-quality results. Generated
captures remain ignored under `scratch/`; no capture data is published.

## API and adapter contract

Enrollment requires all of: an explicit root, explicit relative file/directory
scopes, a new output directory outside that root, source-kind declaration and
`allow_collection=True`. Public runs also require an explicit `owner/repository`
identity. The caller attests that this is a clean public checkout; the library does
not query GitHub or infer visibility from local files. Absolute host paths are not
written to the journal.

Wrap the actual tool dispatch, including setup/tests/edits, rather than reading a
transcript afterward:

```python
from pathlib import Path
from aki.recorder import Recorder, canonical

recorder = Recorder(
    root=Path("/workspace/public-task"),
    scopes=["src", "tests", "pyproject.toml"],
    output=Path("/capture/task-run"),
    source_kind="public_repository",
    repository="OWNER/REPOSITORY",  # explicit reviewed public source
    declared_revision=BASE_COMMIT_SHA,
    allow_collection=True,
    store_source_blobs=True,        # separate opt-in: private local source copies
    store_tool_requests=True,       # separate opt-in: actual tool arguments
)
try:
    with recorder.operation("source_execute", canonical(tool_request)) as event:
        result = isolated_backend.execute(tool_request)
        event.output(canonical({"stdout": result.stdout,
                                "stderr": result.stderr,
                                "exit_code": result.exit_code}))
        event.executor_metrics(wall_ns=result.wall_ns, cpu_ns=result.cpu_ns)
finally:
    recorder_overhead = recorder.close()
```

`isolated_backend` is an integration point, **not a provided or implicitly trusted
executor**. An adapter must route every source operation through the wrapper,
serialize calls, wait for child/background writers to stop, and expose the exact
source filesystem used by the tool. A copy that is not synchronized with the
executor is not authoritative. Record backend times from its own measurements;
missing executor CPU/wall values remain JSON `null`, never zero. Model prompts,
responses and account sessions are outside this recorder's collection interface.

The bridge `scripts/record_agent_run.py` imports an adapter module only after the
explicit `--allow-reviewed-adapter` flag. That module must expose
`run(recorder, config)`, implement the existing agent loop/tool dispatch, and enforce
its own model/tool/time budget. The bridge is not a new agent framework and does
not supply a model transport or read credentials. Do not run an unfamiliar adapter
on the owner's host.

## Recorded schema: `aki-observation-v1`

The UTF-8 JSONL journal has a session header, paired `begin`/`end` records and a
session end. Every record links to the previous record's SHA-256. This checks
integrity and truncation; it is not an authenticated signature or proof of agent
correctness.

| Record/field | Meaning |
|---|---|
| session | Explicit repository/kind, declared revision, hashed scope names, retention flags and hard caps |
| begin | Operation ID/type, request hash/byte count and current source snapshot |
| snapshot | `scoped_tree_sha256`, file/byte counts, changed path-ID entries and deletions |
| file entry | Exact-byte SHA-256, byte count and executable bit; path ID is SHA-256 of the relative path |
| end | Status, exception type only, output hash/byte count, after-snapshot and timing fields |
| observer timing | Monotonic start/end, elapsed wall and recorder-process CPU for the wrapped block |
| executor timing | Adapter-provided backend wall/CPU nanoseconds, or `null` when unavailable |
| session end | Started operation count and overhead counters before the final journal event |

Snapshots include additions/deletions within enrolled directories. File identity
uses original bytes, including line endings. With source retention enabled,
content-addressed immutable blobs and a private path map permit reconstruction of
changed files. Tool-request retention separately preserves the exact request
bytes. Output bodies are never retained by this recorder; their exact hashes
allow comparison with independently reconstructed tool output. Without opt-in
source/request retention, a hash-only recording alone cannot replay changed files
or recover query text. This distinction is intentional.

A source-tree hash identifies only the **enrolled namespace**, not the whole Git
repository, dependency installation or execution environment. `scope_complete`
means all paths in that declared profile were inspected. It does not prove semantic
completeness. The prospective adapter must reject evidence reads/writes outside
that profile, and separately pin the runtime image/dependency state. A new file
outside enrolled paths is not observed. Broaden enrollment explicitly before a
new run if the task needs it; do not silently extend a frozen evaluation profile.

Capture uses anchored directory descriptors and `O_NOFOLLOW`, rejects symlinks,
special files, hidden/sensitive-looking paths, oversized files and changed
inventories. Metadata is checked before/after reading. These are stability checks,
not an atomic filesystem snapshot: writers must be quiescent. Unobserved changes
between wrapped operations abort capture. Failed boundaries, nested/concurrent
operations, missing successful-output hashes and incomplete/crashed logs fail
verification. Capture errors must not be converted into a successful empty tree.

Observer CPU is not remote/container/child CPU. Observer wall includes adapter
transport and bookkeeping within the wrapped block. Snapshot and journal CPU/wall
costs are tracked separately; `close()` returns counters including its final
journal write and finalization work. The session-end record's counters explicitly
precede that record. Measure total session wall/CPU outside the recorder too, as
the demo/bridge does. Do not omit capture overhead from deployed lifecycle claims,
or mistake recording overhead for underlying retrieval cost.

## Privacy and storage boundaries

Default retention is hashes/counts only: no raw query, command, output, source
text, absolute path or exception message in the journal. Hashes are pseudonymous,
not anonymization; low-entropy content may be guessed. There is no comprehensive
secret scanner. A source-kind declaration does not prove a checkout is public.

Source blobs, tool requests and the private path map can contain sensitive text
if the operator enrolls inappropriate inputs. Those features require explicit
opt-in, remain local, and must never be published automatically. Review a clean
public checkout before enrollment; do not use private repositories, hidden Codex
sessions, unrelated chats, home directories or credentials as inputs. Logs use
mode 0700 directories / 0600 files. The recorder performs no network operations.

Limits per session: 2 MiB per file/request, 64 MiB per snapshot, 10,000 files,
256 MiB combined retained source/request bytes, 64 MiB journal, and 200 operations.
The prospective pilot sets tighter tool/time limits. A cap causes failure rather
than silent sampling. The private path map adds a small bounded metadata file.

## Exact prospective entry point and present blockers

After a reviewed isolated executor and adapter exist, create a run config in that
executor. These are explicit configuration values, not discovery commands:

```sh
cat > /capture/run-config.json <<'JSON'
{
  "root": "/workspace/public-task",
  "scopes": ["src", "tests", "pyproject.toml"],
  "output": "/capture/task-run",
  "source_kind": "public_repository",
  "repository": "OWNER/REPOSITORY",
  "declared_revision": "REPLACE_WITH_PINNED_40_HEX_COMMIT",
  "allow_collection": true,
  "store_source_blobs": true,
  "store_tool_requests": true
}
JSON
python3 /aki/scripts/record_agent_run.py \
  --config /capture/run-config.json \
  --adapter reviewed_agent_adapter \
  --allow-reviewed-adapter
python3 /aki/scripts/verify_recording.py /capture/task-run
```

Replace the repository/revision and **reviewed source scopes** with the chosen
frozen task's actual layout. The commit placeholder intentionally fails validation.
The adapter must already exist on the isolated executor's Python path; no package
is installed by these commands. Its config may carry its own reviewed model/scaffold
settings, but the recorder does not dump that config or fetch any credential.

Run third-party setup/tests only in a reviewed image pinned by digest, with no
owner-home, credential or unrelated-project mounts. Use an isolated task source
mount, separate capture storage, resource limits, a writable temporary directory
and restricted network access. The logger must have a synchronized view of source;
the adapter must wait for writers/children before after-snapshots. A host-side
planner may use an already-approved model connection, while repository execution
remains isolated. Record image digest, model/scaffold version, tokenizer and actual
model usage in the frozen experiment manifest without logging prompts or secrets.

**Current capability check:** Python and Docker CLI are installed. A bounded
read-only `docker version` check returned daemon-not-running-or-unreachable;
no container or daemon was started. This project has no reviewed live agent
adapter/model transport configured. The current Codex tools do not expose a
per-tool interception hook for this recorder; hidden sessions were not accessed.
Thus fixture capture can run now, but an actual prospective agent evaluation is
not ready using the currently verified capabilities. The missing pieces are a
reachable reviewed isolated task executor and an explicit tool-dispatch adapter
for an approved existing model/scaffold connection. No new paid resource is
presumed necessary or authorized.

The [frozen prospective protocol](PROSPECTIVE_CAPTURE_PROTOCOL.md) specifies the
cohort, pilot, stop conditions and resource estimates. No adaptive-indexing or
agent-success claim follows from this instrumentation release.

The recorder cannot redact an adapter's own console/provider logs. Disable prompt
logging or keep those logs private under the approved experiment's controls.
Only the recorder's explicitly documented artifacts have its retention rules.
The default library/test suite remains stdlib-only; recorder capture is POSIX-only.
