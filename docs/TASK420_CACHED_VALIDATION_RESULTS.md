# Cached validation result — 2026-10-27

**Stopped before image import. No recorder fixture, compatibility check, benchmark
or model pilot ran in this attempt.** The default Docker engine had active
containers after native VM startup. The exclusive-runtime gate stopped work rather
than attribute their CPU use to AKI. The separate allowance is now closed; no retry
followed. The earlier recorder milestone remains a result of the earlier run only.

Execution code: `34e3767`. [Frozen protocol](TASK420_CACHED_VALIDATION_PROTOCOL.md).
[Safe numerical evidence](../results/runtime/task420-cached-validation.json).

| Gate | Actual outcome |
|---|---|
| Offline staging | Passed; 40 pinned files rehashed, zero downloads or registry requests. |
| Native VM / engine architecture | Startup and arm64 engine check passed. |
| Exclusive runtime | Failed: active containers detected. Their identities/owners were not retained. |
| Emulation-handler readback | Unreached because the collision gate preceded it; startup requested `--binfmt=false`. |
| Image import, guest creation | Unrun; no image or container created by this attempt. |
| Recorder / eight compatibility gates | Unrun, including CLI version and test collection. |
| Cleanup | Completed; attempt staging links removed, VM readback stopped, no pending cleanup. |
| Saved settings | Before/after hashes match for Colima profile, Lima profile, Docker config and SSH config. |
| CPU compliance | Driver reported complete, but independent retained-evidence audit rejects that conclusion. |

## Accounting and retained evidence

The driver recorded **93.688328312 conservative CPU-seconds**, **27.461661 seconds
active wall time**, zero download bytes and **2,791,274,917 bytes** peak disk
reservation against 300 CPU-seconds / 3 GiB limits. The CPU number is neither
certified complete nor attributable project-only cost: guest/VM counters included
unrelated containers, and the ledger combines overlapping counters and upper bounds.
The zero-download figure describes AKI's cache-only staging path; unrelated
containers' network traffic was not measured or attributed.

The append-only journal has 18 events: one baseline, 14 snapshots, two worker
counter errors and one final record. Both errors were ESRCH process-disappearance
races. One occurred during work with a previous sample, the other during cleanup
with no previous sample. The worker inventory handler suppressed them after the
PID disappeared, assuming their CPU would enter a parent's reaped-child counter.
The saved evidence does not establish that transfer. Therefore the driver's
`accounting_complete=true` is **not accepted as proof of compliance**. No corrected
total, unused allowance or actual CPU breach is inferred.

The follow-up patch removes that suppression. An unaccounted disappearing worker
now propagates an accounting failure and prevents a passing validation, while
bounded cleanup still runs. A focused original mock reproduces the rejected case.
**115 host tests pass** (114 before the live run). This stricter patch has not run
live. It makes uncertainty visible; it does not solve descendant-exit attribution
or establish that a future run will complete successfully.

The prior cache remains **844,838,767 bytes**, byte-identical including its original
manifest. Its 40 identities were checked before staging, within staging, and after
cleanup. The old budget hash remains
`7a065fe179dfea3cd327016b012270dd7f1235cc6901e87a1cbaf36c0f51bc2a`.
Both ledgers are closed. The large cleanup byte count represents removed hard-link
names in the new attempt; original cache data was not deleted or redownloaded.
Raw runtime logs and process evidence remain ignored and unpublished; the public
aggregate omits owner paths, configuration contents and process identifiers.

## Remaining blocker and decision

The exact blocked target is compatibility/recorder validation in the existing
**default Colima Docker engine**. It was known stopped before launch, but that did
not imply an empty/exclusive engine after startup. Starting the VM may have
auto-started existing containers; returning it to stopped also quiesced its guest.
No individual existing container was altered or deleted. Without retained identities
we cannot assign those containers to any other project or worker.

Further validation is **pending**, not retried or silently moved to another profile.
It first needs coordination for a demonstrably exclusive runtime and reliable
descendant-exit accounting. Do not stop/delete unknown containers, change their
restart policies or provision another VM under this closed allowance. No new
approval request is bundled with this report. The benchmark/model pilot stays
stopped, and no research efficacy or task-success result is claimed.
