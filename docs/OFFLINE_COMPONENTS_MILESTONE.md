# Offline readiness components — 2026-10-27

**137 host tests pass. No VM, profile, container, download, model call or real task
evaluation ran.** Both earlier live allowances remain closed and byte-unchanged.
This release supplies tested accounting/ownership primitives and evaluation
plumbing. It does not certify the previous CPU totals or a working Mac live adapter.

## Descendant-exit accounting

`aki/subtree_accounting.py` removes individual PID survival from the accounting
contract. Two explicit modes are available:

| Mode | What it charges | Required evidence |
|---|---|---|
| Durable subtree counter | Counter delta, rounding allowance and capacity bound since the last observation | Stable kernel scope/boot identity; cumulative usage includes exited descendants; no escape/reconfiguration. |
| Whole-lifetime capacity envelope | Physical CPU capacity × the whole interval, including unseen/exited descendants | Scope enrolled before dispatch and verified empty after dispatch is closed. |

The ledger rejects enrollment into a populated scope, unknown containment, counter
reset, identity reuse, clock regression and unconfirmed quiescence. A missing PID
or parent exit is never a finalization signal. Faults persist. The Linux cgroup-v2
reader reads one explicitly supplied owned domain, checks inode/boot identity,
rejects missing/symlinked/malformed counters, and observes populated state on both
sides of the CPU read. An exit transition requires another sample rather than
accepting an earlier CPU read as final. The reader is tested on original filesystem
fixtures; its Linux kernel contract has not been validated in a live guest here.

Proof obligations before live integration:

1. Enroll the empty scope before any charged dispatch; include setup/observer costs
   outside that scope in the outer ledger.
2. Verify ownership, stable identity, physical CPU capacity and that descendants
   cannot escape/reconfigure the accounting domain. Use physical capacity for a
   missing-interval bound, not a time-averaged CPU quota.
3. Preserve cumulative usage across child exits; no process-disappearance shortcut.
4. Close dispatch, observe the same scope empty, read its final counter, and only
   then delete it. Include cleanup and report-writing bounds.
5. Fail on missing or contradictory evidence. Never relabel a conservative bound
   as exact task CPU or subtract overlapping components without proof.

The Mac host still lacks an integrated durable descendant counter. The capacity
fallback is reliable as an upper bound under its containment contract but may be
too expensive: one 12-CPU envelope exhausts 300 CPU-seconds in 25 wall seconds, or
the 180-second work allowance in 15 seconds. The prior startup alone took 19.283
seconds. Thus repeating the same five-minute budget with that fallback is not a
credible way to finish validation. This limitation is explicit, not a reason to
weaken accounting. No production-wide reliability claim follows from mock tests.

## Runtime ownership and isolation

`aki/runtime_ownership.py` is a pure preflight/cleanup authorization model. It
requires a fresh `aki-...` profile, unique attempt identity, dedicated local socket
and only control/package mounts inside project scratch. It checks exact observed
ownership, architecture, CPU/memory, read-only mounts, disabled forwarding/emulation,
and complete container inventory. A preexisting profile, remote socket, extra
mount, changed owner or foreign container prevents cleanup authorization. Returned
plans are marked non-executable; no OS commands are issued by this module.

The old default-Colima entrypoint is now disabled before ledger creation or any
runtime command. Its historical implementation remains available for audit, but
the old invocation cannot accidentally start another shared-runtime attempt. A
test proves that neither budget nor subprocess access happens when it is invoked.

Existing-cache metadata confirms that the configured boot-image path and its
Colima cache parent are absent. No verified pristine boot image is available from
that inspected metadata. The mutable default VM disk is excluded; a digest alone
would not prove it clean. See [metadata audit](../results/runtime/boot-cache-metadata-audit.json).
This is not a whole-system image search. No evidence in retained AKI records
establishes whether ClauseWeave or Roblox depended on Colima; that remains unknown.

## Task-benefit harness and actual fixture run

`aki/task_benefit.py` evaluates matched current-source operations using the existing
Store/Policy implementations. Development compares disabled reuse, frequency, LRU,
GDS, bounded static and AKI. It selects the lowest observed lifecycle cost among
correct/fresh implemented caches, freezes that selection/configuration/code hashes,
then compares the selected cache, disabled reuse and AKI on a separate sealed file.
Every condition owns a fresh store and identical token/storage budgets. Within a
task, repeated operations and a source mutation exercise observed-only adaptation.
Evaluator oracles and future events never enter policy calls.

The seal prevents accidental pre-freeze reads, detects content/code/config changes
and permits only one holdout opening. It is not encryption or hostile-host access
control. The public fixtures deliberately share simple shapes: they test plumbing,
not generalization. Real held-out cohort actions remain unopened.

Reproduce the final original-fixture run:

```sh
python3 scripts/task_benefit_fixture.py --out scratch/new-task-benefit-fixture
python3 -m unittest discover -s tests -v
```

The final run contains three synthetic development cases × six policies and three
synthetic holdout cases × three policies, each with four steps: cold, repeat,
mutation and expected abstention. All 27 condition-attempts passed the fixture
oracles with no stale evidence. Frequency was selected among caches on development.
The held-out fixture lifecycle totals were **28.218 ms frequency**, **27.611 ms
disabled**, and **29.772 ms AKI**. Each condition had three expected abstentions.
These tiny one-run timings are harness checks, not evidence of an optimizer
advantage or inherent regression. Real task attempts are **zero**; resolved-task
metrics are **null**, not successful repairs.

[Final fixture inputs, freezes and raw outputs](../results/instrumentation/task-benefit-fixture-v2-20261027/)
are public original data. A first plumbing run selected disabled as the overall
fastest comparator. It is retained alongside its exact original source in
`research/offline-components/task_benefit_v1.py`. The final selector explicitly
retains both disabled reuse and the strongest observed implemented cache; this is
a harness correction, not policy tuning or selection of favorable real results.

Service timing includes temporary-store creation/deletion, index/refresh, query,
materialization and close costs. Synthetic data generation, independent oracles,
correctness checks and report serialization are outside that timer. Separately
reported process CPU includes those evaluator checks. There is no agent/model cost
to infer. The real-outcome aggregation interface requires verified executable-test
receipts; failed/cancelled attempts remain in denominators, stale evidence prevents
resolution, and missing costs/duplicate IDs cannot be scored. Its receipt verifier
and agent/runtime adapter are not implemented by this fixture runner. Exact
query-result caching and larger real-task comparisons remain future gates; no
claim is made that the implemented cache set exhausts all strong competitors.

## Minimal next validation proposal and stopping point

Keep the scope to **one original fixture in a fresh AKI-only runtime**, followed
by owned-scope teardown and independent counter reconciliation. No repository
setup, benchmark, model, default-runtime operation or unknown-container action.
Before requesting that live run, identify a pristine boot artifact with verified
primary-source provenance and exact size/digest; parameterize a reviewed dedicated
adapter; integrate actual containment/readback with these pure gates; and establish
a complete host-counter method or quote a sufficient explicit capacity-bound budget.

The previous no-download/300-CPU-second/3-GiB allowance authorizes none of that new
provisioning and remains closed. The new VM/disk/base acquisition would require
explicit bounded authorization; mounts and security must remain narrower, not
broader. Numeric provisioning limits cannot honestly be fixed while the clean
base and trustworthy host telemetry are missing. No further live permission is
requested yet. This release makes those proof obligations executable in fixtures
and leaves the concrete missing capabilities visible.
