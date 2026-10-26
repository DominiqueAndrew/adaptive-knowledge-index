# Shared-budget continuation, October 26

This continuation retains task 420, its source/runtime/artifact pins, TLS validation,
native-only nonpersistent startup, offline non-root confinement, all `noexec` mounts,
fixture/compatibility gates and the frozen planner/action schema. Held-out actions
remain unopened. No host installation, emulation, paid API or new credential is used.

Recoverable setup retries now share **one** 512 MiB transfer allowance, 3 GiB peak
additional-disk allowance and 300 CPU-second allowance. A durable campaign ledger
records completed attempts and refuses concurrent, pending/unaccounted or closed
campaigns. CPU already charged is subtracted before the next supervisor starts.
All observed work and teardown costs count; incomplete accounting blocks further
work. The common 120 CPU-second teardown reserve remains conservative. Active run
wall time also shares a stricter 600-second envelope, excluding offline code review.

The pinned expanded image and package bodies remain inside this campaign's isolated
artifact cache across recoverable setup failures; they are rehashed before reuse.
No partial guest environment is reused. Download reservations are persisted before
each response read, so an interrupted read cannot silently reset transfer costs.
Readonly package mounts contain only verified files from that cache. Image import,
containers and VM startup/shutdown remain attempt-scoped. Final cleanup removes the
campaign's cached artifacts, not unrelated runtime images or projects.

There is at most **one pilot**, capped at twelve source operations and ten minutes,
and only after the live fixture/recorder and all compatibility gates pass. A durable
pilot-start marker blocks a second pilot even if the first fails. The existing
stricter common CPU/wall envelope may stop it earlier. A stopped setup is not an
agent failure; passing instrumentation is not a repair-success or AKI-efficacy result.

Explicit execution uses the same campaign path for every recoverable retry:

```sh
python3 -I scripts/run_task420_attempt.py --execute-approved-single-attempt \
  --campaign scratch/task420-shared-20261026
```

This performs live actions and requires the separately established authorization.
Budget or permission boundaries stop work; errors do not authorize weaker TLS,
mounts, isolation, more resources or a different task. Publish only original code,
safe numeric measurements and hashes, keeping captures and private runtime logs local.
