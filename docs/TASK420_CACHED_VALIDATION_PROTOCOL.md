# Frozen cached validation — 2026-10-27

This is compatibility/instrumentation validation, not a benchmark or agent pilot.
The previously closed campaign and its retained cache remain unchanged. A separate,
single-attempt allowance permits at most 300 conservative CPU-seconds including
shutdown, 600 seconds active wall time and 3 GiB additional disk. No downloads,
registry requests or model calls are allowed. No host installations, emulation,
private-folder mounts, Docker socket in the guest, credentials or saved-setting
changes are authorized. Only this attempt's runtime resources may be cleaned up.

Preflight: the default four-CPU native Colima VM is stopped; host has 12 logical
CPUs, 32 GiB RAM and about 46 GiB available disk. Observed load averages were
4.13/5.01/5.41 and memory-pressure reporting showed 87% system-wide free percentage
with zero swap I/O. These are point-in-time observations, not a reservation of
capacity. Process-list/one sysctl query was sandbox-restricted; no elevation was
used to obtain another task's process details. Owned-process counters and the
dedicated VM's counters determine charges; unrelated host CPU is not treated as
project work. Any active container discovered immediately after startup stops
validation to avoid contaminating guest accounting. Other projects are untouched.

The exact 40-file cache is reverified against pinned package/config/layer hashes
before execution and again within the charged staging phase. New attempt paths
hard-link the existing immutable bytes; the new image manifest is a separate file.
The old cache manifest, task data and budget are not rewritten. Staging requests
neither registry metadata nor task text. The fresh ledger has a zero-byte transfer
limit; both network staging and pilot dispatch reject validation-only attempts.

Frozen sequence:

1. Reverify cached artifacts under the supervisor.
2. Start the existing VM with `--binfmt=false --save-config=false --activate=false
   --ssh-config=false`; reject unexpected provisioning and emulation handlers.
3. Load and verify the exact arm64 image, create the existing offline non-root
   container with read-only root, noexec tmpfs, bounded memory/PIDs and one CPU.
4. Validate the four-operation original recorder fixture before dependencies.
5. Run eight fixed compatibility steps: bootstrap, dependencies, dependency check,
   imports, project metadata, project dependency check, CLI version and unit-test
   collection. Collection is not a test-suite result or repair-success evaluation.
6. Remove only owned container/image/staging links; stop the VM, compare saved
   config hashes, finalize the append-only CPU evidence and close the new allowance.

Abort work at 180 conservative CPU-seconds to reserve 120 for cleanup. Accounting
failure always stops work and invalidates compliance; cleanup still attempts to
quiesce owned execution. Totals include observer/supervisor/worker, VM host and
guest costs with explicit conservative gaps/overlap. They are not additive physical
CPU measurements. Preserve all failures and distinguish completed, failed and
unreached gates. No retries or pilot are implied by this one validation command:

```sh
python3 scripts/run_task420_attempt.py --execute-approved-single-attempt \
  --validation-only --cache-only-from scratch/task420-shared-20261026 \
  --campaign scratch/task420-cached-validation-20261027
```

Host validation before live dispatch: 114 tests passed, including four new original
cache fixtures proving zero-fetch staging, unchanged old bytes, strict integrity
failure, independent ledger creation and disabled model/network phases. The live
result must be reported separately. Failure of a gate does not authorize widening
the environment, changing dependencies, resetting the ledger or starting a model.
