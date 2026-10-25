# Frozen prospective instrumentation feasibility protocol

This is a proposed future run, registered before any prospective agent execution.
No model, Docker container, repository setup or third-party test runs are part of
the current instrumentation demonstration. Only project-owned synthetic fixtures
have exercised the recorder.

Reuse the 24-task/six-repository cohort frozen in `ce59006`, in
`results/phase4/cohort.json`. Do not select replacement tasks based on ease, reuse,
success or capture quality. Development and held-out repositories remain disjoint.
Existing historical trajectories are context for availability only; do not feed
their solutions, edits, outputs or task outcomes to a new agent or policy.

## Initial pilot and resource ceiling

The first task in frozen order from each development repository is:

- `Backblaze__B2_Command_Line_Tool-420`
- `certbot__certbot-5687`
- `miurahr__aqtinstall-364`

Run one new attempt each with a fixed model/scaffold/configuration recorded before
launch. Select model, adapter version, source scopes, runtime image digest and
supported read/edit/execute tools before collecting any live actions. This is an
instrumentation feasibility pilot, not an optimizer efficacy test. No optional
warm-up generated from target tasks, future query access or gold-label feedback.

Cap the three-task pilot at 12 tool operations per task, 30 seconds per operation,
10 minutes wall per task, 30 cumulative CPU-minutes and 2 GiB new downloads.
Capture caps are additionally enforced by the recorder. Reserve at most 1 GiB
combined capture storage for the three tasks (each session has 256 MiB retained
source/requests plus 64 MiB journal). Estimate: fewer than 40 MiB clean source for
these tasks based on the earlier 12-snapshot 29.1 MB measurement; image size and
model usage are unknown and must be bounded before launch. An image exceeding the
download allowance is a stop, not permission to pull it anyway. No API spending
or new credential is authorized by this protocol. Use only a separately approved
existing model connection, or stop and specify its exact access/cost requirement.

## Capture acceptance gate

Before moving beyond the three-task pilot, require all three attempts to provide:

1. At least three real source reads and one complete execution/mutation boundary.
2. A trace of every dispatched source operation, including failure/cancellation;
   no missing wrapper calls, silent dropped events or concurrent writers.
3. Verified source deltas/retained blobs and actual request bytes in private local
   storage, with observed output hashes, so source reads can be reconstructed.
4. Nonmissing backend wall/CPU measurements and separate observer/capture overhead.
5. Declared scope coverage for every evidence file and operation, a pinned runtime
   context, and no unresolved source instability or cap overflow.

The first failure stops progression. Report every attempt and stop reason,
including unsuccessful tasks. Do not infer success from tool feedback or judge
answers with retrieval hashes. Only executable task tests in the reviewed runtime
can establish repair outcomes, and this pilot is not powered to compare them.

If the pilot passes, run the remaining nine development tasks without changing
cohort membership. Freeze the adapter, source profile and measurement code before
opening the twelve held-out tasks. If development motivates a schema change,
repeat the affected development checks and preserve the version distinction.
No held-out action has been inspected in the current release.

## Research decision after valid data

First measure still-valid repeated work and a clearly labeled free/unlimited
reuse diagnostic. Compare disabled reuse, static/incremental maintenance, exact
LRU and simple interval/file memoization at the same evidence, source-access,
storage and token budgets. Preserve cold/warm and changed-source boundaries.
Use three paired interleavings (seeds 104, 105, 106) for deterministic retrieval
replay; model stochasticity is a separate factor requiring explicit paired runs.
Count initial loading, parsing, selection, materialization, invalidation, storage,
validation, background work and actual inference usage. Report recording overhead
separately and include it if the proposed deployed system requires that observer.

Do not add an adaptive candidate unless measured reusable opportunity beyond the
strongest simple cache can plausibly exceed the existing 20% lifecycle target at
identical evidence quality/freshness. A missing measurement is not zero cost.
The current useful deliverable remains incremental source/evidence maintenance;
the recorder makes a later falsifiable experiment possible, not successful.
