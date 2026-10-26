# Closed-campaign audit — 2026-10-26

The campaign remains closed. This audit used retained evidence, static source
inspection and original local fixtures/mocks only. No VM, container, download,
installation, benchmark execution or model call occurred. No cache or budget was
deleted, reset or reopened. The earlier four-operation live recorder fixture is
valid instrumentation evidence; there is still no agent pilot or adaptive result.

## CPU: what the record supports

The two runs recorded a combined conservative charge of **166.486912557 seconds**.
This mixes observed counters with capacity bounds; it is not a measurement of
physical CPU consumption and is not certified complete. Two teardown reads failed
with `explicit process CPU unavailable: 3` (ESRCH). Their process identities,
component names and monotonic failure timestamps were not retained. The previous
progress file was overwritten, so those facts cannot be recovered afterward.

The second run's total supervised duration minus its work-command durations leaves
at most **6.352176 seconds** for cleanup and unattributed overhead. Assuming all
earlier coverage was complete, both gaps were confined to that interval and the
same 12-CPU host capacity applied:

| Conditional reconciliation | Conservative total |
|---|---:|
| One affected host-counter component at full capacity throughout cleanup | 242.713025 s |
| Both possible host components at full capacity throughout cleanup | 318.939137 s |

These are sensitivity bounds under stated assumptions, not observed totals or
proof of a breach. The record cannot identify which scenario applies; the latter
exceeds the 300-second limit. Therefore compliance cannot be certified and no
unused CPU allowance can be inferred. The original incomplete status is retained.

The repaired supervisor preserves a bounded, local append-only counter journal,
baseline capacities and VM disk allocation, per-process observations, component
and timestamp information for faults, and final counters. It rejects PID reuse,
clock regression and unexplained runtime-host counter loss after VM stop. Its
known-process ESRCH tail remains an explicit capacity bound, not a zero-cost read.
These repairs have local tests; shutdown accounting still requires live validation.

## Download and retained disk reconciliation

All **40 cache files** were rehashed against the pinned inventory; there are no
extra files or symlinks in that cache.

| Retained cache content | Bytes |
|---|---:|
| Nine expanded image layer tar files | 840,434,688 |
| 29 pinned package artifacts | 4,394,723 |
| Image config and local Docker-save manifest | 9,356 |
| **Total** | **844,838,767 (805.70 MiB)** |

The charged download is **329,892,894 bytes (314.61 MiB)**: 325,456,469 compressed
layer bytes, 4,394,723 package bytes, 33,510 metadata response-body bytes and an
8,192-byte header allowance. The larger retained cache is explained by expanding
the compressed image layers; it is not evidence of uncharged artifact downloads.

At audit time the whole campaign contained 95 unique regular files, **844,957,468
logical bytes** and **846,905,344 allocated file bytes**, with no symlinks. The
118,701 logical bytes outside the cache are local controls, logs and capture
metadata. Allocation is an APFS point-in-time observation and excludes directory
metadata, snapshots/shared extents and historical VM growth. The recorded peak
**2,791,110,143-byte reservation** included image/tmpfs/capture allowances; it was
not a measurement of allocated peak disk. The historical VM allocation baseline
was not saved, so exact historical VM growth cannot be reconstructed.

The cache consists exclusively of verified public artifacts and generated public
image metadata. Local captures/logs outside it can contain owner filesystem paths
and public task text; they remain ignored and unpublished. Only original project
code, documentation and safe numerical aggregates are published. The cache and
closed budget are preserved; the budget hash is in the aggregate audit artifact.

## Exact compatibility issue and remaining gates

Static inspection of pinned
[`b2/console_tool.py`](https://github.com/Backblaze/B2_Command_Line_Tool/blob/15a60ad1c71b75366061e4f742ef52eb9dcc23e7/b2/console_tool.py)
shows `Help.run` at line 534 returns 1, while `Version.run` at line 1040 returns 0.
The source SHA-256 is
`51a977052cf9de6053569ce774f1cecf76e6718e5066d948b010abd2e52e8f4d`.
The failed gate called `main()` with `--help` and incorrectly required zero. The
existing correction calls `version`; no source execution was needed to establish
the mismatch. That corrected gate has not run live.

| Gate | Evidence and remaining limitation |
|---|---|
| Artifact identity and native image | Pinned hashes verified again offline; prior live image verification passed. |
| TLS and confinement | Prior setup used verified TLS, offline non-root/noexec confinement and no private mounts/socket. No settings were weakened. |
| Original recorder fixture | Prior live four-operation capture independently verifies. New failure-boundary and child-quiescence checks are local/mock tested only. |
| Dependencies/imports/metadata | Six prior live setup steps passed; no new compatibility claim. |
| CLI version and unit collection | Static version fix is locally checked; both final live gates remain pending. |
| CPU accounting and teardown | Cleanup previously completed but accounting did not. New provenance and strict fault handling need live validation. |
| Agent dispatch | Requires eight completed compatibility gates and independently verified fixture integrity. No pilot/model call occurred. Output caps and gate rejection have host checks. |

The audit also corrected source capture after failed tool mutations: post-source
is now collected even on errors; unavailable post-source invalidates the capture.
Guest execution tears down its process group and rejects surviving non-zombie
processes at source boundaries. These checks use original fixtures/mocks, not
third-party benchmark execution, and still need Linux runtime validation.

Historical fixture `service_wall_ns` started **after** the preliminary guest
snapshot. The reported 1.166584-second sum is preserved but is not full service
time. Future service measurements include the pre-snapshot and explicitly label
their scope. No missing historical timing was synthesized.

## Validation and next decision

`python3 -m unittest discover -s tests -p test_gate_audit.py -v`: **9 passed**.
`python3 -m unittest discover -s tests -v`: **110 passed**, 2.627 seconds.
These are host tests, including mocked runtime checks, not a live compatibility run.
The aggregate [audit evidence](../results/runtime/task420-offline-audit.json) can
be reproduced against retained local inputs with `scripts/audit_retained_task420.py`;
the script hashes artifacts and parses source AST without importing benchmark code.

Retain task 420 for a narrowly scoped validation: six compatibility gates and the
live fixture already passed. The evidence does not justify changing tasks to seek
an easier outcome. No further optimizer work is supported by this result.

If a future live check is approved, the smallest useful scope is **cached fixture,
remaining compatibility gates and shutdown accounting only**, with no agent/model
phase. The added `--validation-only` plan excludes pilot dispatch. Proposed limits
are one explicitly new allowance of 300 CPU-seconds including teardown, 600 seconds
active wall time, and 3 GiB additional disk. Existing verified cache must be reused;
zero image/package-body downloads are needed. The current stage still requests
registry metadata, so either an explicitly capped metadata allowance (proposed
64 KiB) or a reviewed offline-staging change is necessary. A future driver must
enforce that small network cap before execution; it is not implemented by the
validation-only flag. Preparing that separate ledger/cache reuse must not reopen
or alter the closed campaign. Native-only startup, unchanged saved configuration,
offline non-root/noexec execution, no private mounts/socket and attempt-only cleanup
remain required. This paragraph is a scope proposal, not authorization or a runnable
instruction to reset the old budget. Agent evaluation would remain a separate gate.
