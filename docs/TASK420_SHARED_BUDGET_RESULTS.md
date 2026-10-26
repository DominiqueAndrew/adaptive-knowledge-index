# First live recorder milestone; pilot still blocked

The shared-budget continuation reached a useful narrow result: **the recorder
worked across four actual isolated guest operations**, with eight source boundaries
and independently verified journal/delta/output identities. This was an original
synthetic fixture, not an agent task or an AKI efficacy evaluation.

The native arm64 VM, digest-verified Python 3.5.10 image, offline non-root container
and all writable `noexec` mounts passed their checks. Pinned bootstrap/dependency
installation, imports, project metadata and both dependency checks passed. No
network or private mount was exposed to the task container.

## Runs and shared costs

Two setup runs consumed the same durable allowance; no budget was reset.

| Run | Execution commit | Outcome | Active wall | CPU ledger charge |
|---|---|---|---:|---:|
| 1 | `31284cf` | Artifact review stopped before VM startup | 21.771 s | 8.364 s |
| 2 | `e3ff05a` | Live fixture passed; CLI check stopped; shutdown accounting incomplete | 61.029 s | 158.123 s |
| Total | | Campaign closed; no pilot | **82.800 s** | **166.487 s** |

Transfer charged **329,892,894 bytes (314.61 MiB)** against 512 MiB. The second run
rehashed and reused the first run's image/package artifacts. Peak additional-disk
reservation was **2,791,110,143 bytes (2.60 GiB)** against 3 GiB. Reservations are
not actual disk consumption. CPU charges are conservative, overlap host/guest
counters and include capacity bounds; they are not additive physical CPU cost.
**Complete compliance with the 300 CPU-second cap is not certified**, because two
process-counter failures during teardown marked accounting incomplete. The final
counter aggregate was finalized, but that does not erase those missing observations.
The closed guard prevented another setup retry or any pilot/model call.

The first review failure concerned Windows launcher `.exe` files bundled inside
the exact pinned pip/setuptools pure-Python wheels. Their identities and package
roles were reviewed as inert data; a narrow allowlist accepts those members while
rejecting unknown executables and native libraries. They were never executed.
No architecture, `noexec`, TLS or confinement control was relaxed.

## Actual fixture measurements

| Original operation | Recorded service interval | Guest operation body |
|---|---:|---:|
| Read | 275.423 ms | 0.072 ms |
| Edit | 270.828 ms | 0.132 ms |
| Execute assertion | 349.344 ms | 72.148 ms |
| Read | 270.990 ms | 0.084 ms |
| Total | **1,166.584 ms** | **72.436 ms** |

The recorded service interval excludes the preliminary guest snapshot and is not
full end-to-end time. This was established in the [offline audit](TASK420_OFFLINE_AUDIT.md);
the original numeric measurements are unchanged.

Guest operation-body CPU totaled **50.255 ms**. The difference between that interval and
body timings includes Docker dispatch and post-source-snapshot transfer. Recorder-local
snapshot/journal/finalization wall overhead totaled approximately **4.02 ms**.
The journal has ten valid events, four complete operations and eight source
snapshots. Four observations are not a latency distribution or retrieval benchmark.
These measurements show why observer, transport and operation costs must remain
separate in the future evaluation.

## Why the pilot did not run

The frozen CLI check called `main()` with `--help` and expected exit code zero.
Static inspection after failure shows that the pinned CLI intentionally exits 1
even for its valid help command. Its `version` command returns zero without an
external service request. The follow-up control now uses that command. Test
collection was not reached in the live run; no successful compatibility gate or
agent repair result is claimed.

Two `ESRCH` process-counter errors occurred during cleanup. The old guard correctly
refused to classify accounting as complete. A follow-up host-tested sampler retains
the last observation plus a CPU-capacity bound for an already registered process
that exits during teardown. Unknown processes, live-work failures and permission
errors still fail. Teardown now explicitly marks its stopping state. This fix has
not been live-validated and does not reclassify the historical run as complete.

## Cleanup, validation and decision

Both run cleanups completed: the owned container and loaded image were removed,
the VM is confirmed stopped and saved configuration hashes are unchanged. No
runtime resource or credential remains active. The verified offline artifact cache
is deliberately retained inside ignored project storage: **844,838,767 bytes**.
It supports audit/reuse without spending the download allowance again; it is not
published. Private captures and runtime logs also remain local.

Host tests: **99** before run 1, **100** before run 2, **101** after the follow-up
fixes. The live fixture capture was independently verified again afterward. Numeric
provenance and all operation timings are in
[`task420-shared-budget.json`](../results/runtime/task420-shared-budget.json).

The milestone is working isolated instrumentation and dependency compatibility
through six gates. The research decision is unchanged: incremental evidence/source
maintenance is the useful current tool; adaptive selection remains unproven.
The next justified experiment is live validation of shutdown accounting and the
final compatibility gates, then the same single task-420 pilot. The present
campaign remains closed because its full CPU use cannot be certified. Any next
runtime execution needs an explicitly measurable allowance; no paid API, host
installation, new credential, alternative task or held-out exposure is required.
