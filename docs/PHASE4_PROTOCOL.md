# Phase four: bounded reconstruction feasibility

Registered 2026-10-25 before new cohort selection or action inspection. No paid
APIs, source/setup execution, container installation or third-party code execution.
Hard bounds: 2 GiB of new downloaded response bodies and 30 cumulative CPU-minutes.
All external bytes stay outside the public repository. Only original code,
aggregate/count/hash measurements and public metadata identifiers may be published.

## Outcome-blind cohort and held-out gate

Use pinned Nebius traces `35455389ab51bf5e2306bfd436ef72d0f98bf882` and task metadata
`89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`. Read only IDs/repository names and
base/environment commit/license metadata for selection. Do not read outcomes,
patches, problem statements or evaluation labels. Eligible repositories have four
or more distinct joinable tasks and MIT, Apache, BSD, ISC or MPL source license
metadata. Record upstream license text from downloaded archives as a separate
check; missing/unexpected licensing stops that repository without replacement.

Sort repositories by SHA256(`aki-phase4-repo:` + repository). Development uses the
first three eligible repositories already exposed by phase three; evaluation uses
the first three eligible repositories absent from the 101 exposed repositories.
For each, select four task IDs by SHA256(`aki-phase4-task:` + instance_id), then one
trajectory per task by SHA256(`aki-phase4-traj:` + trajectory_id). Never select by
outcome or observed reuse. Freeze all 24 IDs before loading their action values.
Do not inspect or replay the 12 evaluation trajectories unless development passes
the reconstruction gate below. Downloaded Parquet column chunks can contain other
rows; only selected development rows may be decoded into trajectory objects.

## Reconstruction and timing

Fetch pinned source archives, bounded at 64 MiB compressed / 256 MiB regular-file
content per snapshot. Never extract symlinks, write executable permissions, run
archive hooks, import repository modules or execute trace shell commands. Read
regular files as inert data. Hash the complete reconstructed source manifest.

Start at the declared base commit. Record whether a separate environment-setup
commit exists. A mismatch between returned source lines and the declared snapshot
is a reconstruction failure, not permission to search commits until one matches.
Permit only structured file views and independently implemented literal read-only
shell syntax. Opaque execution, unresolved paths, unsupported edits or ambiguous
parallel ordering stop the reconstructable prefix. Structured editor mutations
may be applied only with explicit before-text preconditions and unambiguous
success; otherwise stop. Report stop reasons and excluded work, never invent the
missing source state. Source identities are reconstructed, not logged identities.

For matched views, time locally implemented source read/decode/line selection
with monotonic wall and process CPU clocks, checking returned source lines against
recorded observations outside timers. Preserve order; reset at task boundaries.
These are local replay timings, not original agent service time or repair success.
Count snapshot acquisition/hash/parse costs separately and in complete lifecycle.
Compare disabled reuse, exact-result LRU (256 KiB), full-file/static preparation,
and simple on-demand file/interval reuse before any proposed adaptive candidate.
Use three fixed randomized interleavings, seeds 104, 105, 106; no OS cache flushing.

## Gates and stop rules

Development reconstruction passes only if at least 8/12 tasks provide at least
three matched read actions before a stop, and all included evidence matches the
pinned/reconstructed source. Report every mismatch, failed download and short
prefix; do not replace tasks. Failure stops evaluation and candidate work.
Only if this passes, freeze the implementation before inspecting held-out actions.
A new candidate further requires measured repeatable opportunity beyond the
strongest simple cache plausibly exceeding 20% of complete retrieval lifecycle
cost at identical evidence. No labels/future queries enter state; retrospective
free-cache analysis is explicitly diagnostic. Incomplete timings cannot pass.

If safe reconstruction fails, identify the exact missing resource (for example,
a source-tree manifest at tool boundaries or an original execution environment
export) and decide whether a narrower incremental-maintenance tool is the useful
current deliverable. No larger model is presumed to solve a provenance gap.
