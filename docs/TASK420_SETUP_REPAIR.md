# Task 420 setup repair: host-verified, live validation pending

The first live attempt is closed. This change repairs its control code and tests
failure handling with original host fixtures and mocked runtime metadata. It does
not repeat the attempt or establish Python 3.5 dependency compatibility, recorder
operation in a container, agent task success, or an adaptive-index improvement.
The [original failed attempt](TASK420_ATTEMPT1.md), including its 18.473-second
cleanup overrun and incomplete final CPU measurement, remains unchanged.

## Specific repairs

`runtime/task420/control.py` uses `/usr/local/bin/python3` from the immutable base
image for every command. `/env` stores separate bootstrap and dependency libraries;
no copied interpreter or installed console wrapper is executed there. All writable
mounts, including `/env`, `/workspace` and `/tmp`, retain `noexec,nosuid,nodev`.
This permits the approved interpreter to read Python modules as data; it is not a
claim that `noexec` prevents interpreted code from running. Third-party module
execution remains an explicitly approved, isolated live step.

The plan installs three pinned bootstrap tools and 26 pinned runtime dependencies
offline with artifact hashes, no dependency resolution or index access, separate
targets and disabled bytecode/cache output. Project metadata goes to `/env`.
The actual B2 CLI `main()` is called for its help check: the frozen source lacks a
`__main__` dispatch, so `python -m b2.console_tool --help` was not a reliable check.
Python 3.5 syntax is tested; this host test is not a Python 3.5 runtime test.

`aki/setup_watchdog.py` supervises a single command sequence from its first work
step through teardown. A wall-clock watchdog operates independently of pipe I/O;
nonblocking stdin/stdout and bounded output prevent a stuck input transfer or
output flood from bypassing checks. Default work cutoff is 510 seconds of a
600-second total, reserving 90 seconds for teardown and final accounting. Cleanup
continues after individual failures and missing telemetry, within the remaining
wall time; unsuccessful cleanup is reported as pending. This is not an OS-level
hard real-time guarantee. A command killed during Docker cleanup cannot itself
prove the underlying resource stopped; fresh confirmation is still required.

`aki/setup_accounting.py` requires supervisor, worker, runtime-host and guest CPU
components with stable identities. Missing counters, counter resets and unconfirmed
termination cannot produce a successful result. Unobserved intervals, including
shutdown tails, are conservatively charged at registered CPU capacity. Work stops
with 120 CPU-seconds reserved inside the 300 CPU-second ceiling. Guest CLK_TCK must
be measured. The macOS sampler reads only an explicitly supplied PID; its test
reads the test process itself. Host VM and guest counters may overlap, so their
sum is a conservative bound, not an additive physical CPU measurement. Download
bytes accumulate across retries; disk capacity is reserved before writes.

`aki/setup_plan.py` validates the original pinned image config and uncompressed
layer identities without assuming a Docker 29 local manifest ID equals its config
digest. Container validation checks exact resource limits, ownership, isolation,
mounts and environment. Expected environment includes defaults from the verified
public image config plus explicit overrides; unexpected client proxy variables
still fail validation without logging their values. Source transfer validates the
entire bounded inventory, hashes and paths before writing to an empty directory.
Cleanup requires both the registered created ID and the attempt label.

## Reproduce the host checks

From the repository root, using Python 3.11+:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/verify_release.py
python3 -S scripts/prepare_task420_controls.py \
  --output scratch/my-reviewed-controls \
  --attempt-id 0123456789abcdef0123456789abcdef
```

The last command creates only local original control files, hash locks and
`plan.json`; it refuses to overwrite an existing directory. Choose a fresh identity
for each actual attempt. It does not contact Docker, start a VM, download or install
anything, execute repository code, or call a model. The plan has
`live_execution_enabled: false` and a visibly invalid all-zero image placeholder,
which must be replaced only after a verified image import.

The full suite passes **88 tests**, including **28 new repair tests**. New tests
cover source/artifact fixture validation, mocked image/configuration checks,
accounting gaps/resets/shutdown bounds, a real sample of the test process's CPU,
and real original host subprocesses that block input, flood output, fail cleanup
or hang. Watchdog tests use explicitly labeled mock CPU totals; those totals are
not live resource measurements. Numeric validation provenance is in
`results/runtime/task420-setup-repair.json`.

## Remaining integration and precise future approval scope

These are tested control components and a reviewable disabled plan, not an enabled
end-to-end Docker/agent driver. Before any new live attempt, the adapter must wire
every staging/startup/import/setup/cleanup operation through the supervisor, retain
all owned runtime process identities, supply prompt in-memory CPU snapshots from
bounded collectors, and finalize all components after confirmed shutdown. The
complete source-transfer/import/recorder path remains unvalidated in the guest.
Pure-Python dependency importability on `noexec` and the reviewed Arrow source
build must be checked there; no compatibility success is assumed. A failed mount
or import check must stop, never relax security flags or trigger a silent retry.

The smallest useful next permission is **one fixture-first live validation**, not
an unlimited retry or an agent evaluation claim:

- Reacquire only the previously pinned native image and 29 approved artifacts,
  with cumulative transfer at most 512 MiB and additional disk at most 3 GiB.
  The previous attempt's local downloaded artifacts were removed.
- Start the existing native Colima profile with `--binfmt=false`,
  `--save-config=false`, `--activate=false`, `--ssh-config=false`; do not alter saved
  settings, install host tools, add credentials or spend money.
- Include staging, startup, compatibility checks, an original recorder fixture
  and confirmed teardown in the 300 CPU-second and 600 wall-second setup budget,
  reserving 90 wall seconds and 120 CPU seconds for teardown. Stop work earlier if
  accounting becomes incomplete or the remaining bound cannot cover teardown.
- Use one offline, non-root, read-only-root container with one CPU, 1 GiB memory,
  no swap, 64 PIDs, dropped capabilities and no-new-privileges. Retain all `noexec`
  mounts. Mount only this attempt's public artifacts/original controls read-only;
  expose no private directory, credentials or Docker control socket in the guest.
- Validate actual container metadata, guest restrictions and recorder boundaries
  before any task/model dispatch. Remove only resources proven created by this
  attempt and verify configuration hashes. Report any pending cleanup explicitly.

An eventual task-420 agent pilot would additionally need the reviewed adapter and
separate gated dispatch, capped at the previously proposed 12 operations/10 minutes,
using existing authorized model access and the unchanged development task. No
model dispatch is implemented or enabled by this setup plan. Held-out actions
remain unopened. No new live approval is requested or exercised by this release.
