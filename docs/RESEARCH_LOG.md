# Research log

## 2026-10-25: protocol before implementation

Question: can an online cost policy improve total measured retrieval cost over
strong same-operator caching under bounded storage, distribution changes, and
repository mutations? A negative result is acceptable. No agent success claim.

Environment: isolated new project; Python 3.11.5, SQLite 3.42.0 with FTS5,
Apple Mac14,10 arm64, 12 logical CPUs, 32 GiB RAM, macOS Darwin 25.6.0.
No paid inference, embeddings, or third-party installation.

Plan fixed before pilot: canonical immutable hashed source spans; deterministic
Python AST import/symbol extraction; SQLite forward/reverse import closure;
per-anchor physical materializations shared by dependency/ripple/test queries.
The base and all policies must produce identical ranked results. Record all
foreground and maintenance work, ingestion, optimizer, writes, invalidation,
and storage. Full-repository refresh is conservative and synchronous initially.

Comparators: disabled, static full (unbounded reference), static bounded
(deterministic path order), on-demand LRU, decayed frequency, cost-based AKI.
All adaptive policies get identical byte budgets and observed queries only.
Train/adapt then freeze for unseen evaluation; separately measure online drift
and mutation. Multiple seeds; order shuffled by seed. Cold means new database
and empty application cache, NOT a flushed OS disk cache. Quality: parity with
independent BFS, deterministic token-budget packing, and later real gold scores.

Synthetic workloads will be explicitly identified. Public repository workload
sequences are generated, not captured agent traces. No private source indexing.

ARB verified at upstream commit 2c773139dd86003ec6defffa28bff1688c4af768
(MIT evaluator), README warns 2026-10-22 fixes invalidate naive comparisons to
older RepoMap figures. Download size and corpus licenses must be checked.
Data is kept outside this publication repository. Only hashes/metrics emitted.

Novelty is unproven. Agentic Context Cracking (arXiv:2608.31082v2) already
describes workload-driven grounded structure, fallback and amortization.
Investigate commit-aware invalidation, budgeted cross-file index selection,
and honest lifecycle accounting rather than claiming adaptive reuse is new.

## Pilot and development (same day)

`python3 -m unittest discover -s tests -v` initially passed 10 tests.
`python3 -m aki.benchmark --nodes 180 --seeds 0,1 --count 80 --out results/pilot-v1`
ran 4,800 exact-output checks. AKI was effectively tied with simpler policies.
Per-file SQLite lookups during context packing dominated useful cached work.
The initial pilot predates the first Git commit; its raw measurements and source
hashes are preserved, but the exact initial source checkout is not recoverable
from Git. Treat it as an exploratory diagnostic, not the reproduction target.

A shared token-count dictionary removed those repeated reads for every policy.
Added measured GDS-style caching, bounded recent-demand bookkeeping, selective
graph-boundary invalidation and actual import-span evidence. Synthetic-v2 used
seeds 10–14, 28,000 exact-output checks; AKI improved over disabled adaptation,
but the frequency baseline was close. This is not evidence of novel superiority.
Those exploratory raw data also predate the first complete commit and are
included for transparency, not as a fully pinned reproduction target.

The first committed implementation is `f325d4c`; source-span grounding and
mutation/property checks are in `78b7920`; pinned acquisition/rescoring commands
are in `927d03c`. Source hashes in each provenance file identify the actual code
even when a measurement started immediately before its commit existed.

## ARB static retrieval gate

Executed 101 trace2code positives and all 82 no-gold cases with official
all_files candidates and no keep list. Parsed 168 distinct base snapshots,
116,299 file records. Fresh official lexical, BM25 and deterministic RepoMap
rankings were produced through the pinned evaluator. Canonical BCY used its
regex tokenization and partial-file-prefix packing. Legacy character metrics
were not substituted. The official baseline methods also happened to run on
one no-gold sample sharing a positive snapshot; that singleton is not a
meaningful selective comparison. Only the four prototype methods cover all
82 negatives.

The graph prototype returned identical ranks under disabled/LRU/AKI storage.
There were 145 relationship requests and zero cache hits in that initial
version. The graph retriever's BCY@8k was 0.2162 versus 0.3795 Lexical and
0.5066 RepoMap. All 82 no-gold cases returned results, a complete abstention
failure. This falsifies a retrieval-quality advantage in this setting and
provides no demonstrated reuse benefit. No labels were used to tune the method.

Downloaded one Oko 0.9.1 ranking file at its pinned commit and verified its
published SHA-256. Offline rescoring of the same 101 trace2code samples gave
MRR 0.7383 and BCY@8k 0.8152. Ranking generation, paid API cost and runtime were
not reproduced. Its development-exposure caveat remains relevant.

## Fairness review and confirmatory protocol correction

An independent code/data inspection found that the phase named `unseen_roots`
could include anchors sampled as noise during adaptation. Query strings were
new, but the stronger anchor claim was not guaranteed. Preserved all earlier
results (`final-synthetic`) and corrected the generator to reserve a disjoint
anchor partition. Added a test for partition disjointness and unique query
strings. Commit `3569710` records that correction. Confirmatory locality seeds
50–54 were selected next, without using their scores; the final directory is
`final-synthetic-v2`. The zero-reuse control is unchanged and retains seeds
40–44. Do not present the earlier mislabeled phase as true unseen-anchor evidence.

Added caching of empty closures as a stronger demand-cache baseline. ARB's
published initial run is pinned to its recorded source hashes; its zero-hit
observation should not be generalized to all possible negative-result caches.

## Real history experiments

Click: eight first-parent revisions ending at
`2247b35ea1c47c727d7a06e51fa280e12a863ff6`, selected mechanically. Three seeds,
120 generated queries per revision, all seven policies and both global/selective
invalidation modes. 40,320 queries matched a freshly recomputed BFS oracle.
Only four transitions changed the Python source tree; unchanged-source commits
were retained in the chronology rather than discarded for a favorable result.
The simple disabled baseline was fastest on average; selective maintenance
helped full prebuilding substantially but did not make it the best policy.

Added pytest as a second, larger MIT-licensed history rather than extrapolating
from Click. Six first-parent revisions ending at
`0f54d41bedf00505bb1ac2c724abf96ba6dcf48d`, three seeds and 80 generated queries
per revision, with the same conditions. Source snapshots are passed in order;
policies never access future commits or gold labels. The harness preloads
snapshots solely for repeatable evaluation. Git source acquisition and oracle
work are outside measured service lifecycle cost, disclosed in the report.

No inference API calls, package installation, paid compute or purchased data.
No existing personal project is part of these input sources.

## Phase two diagnosis and preregistration

`f2de1ca` records the hypotheses and stop criteria in `PHASE2_PROTOCOL.md` before
implementation. `results/phase2/diagnosis.json` measures the old history runs:
initialization/refresh accounts for 95.98% of Click and 97.82% of pytest service
cost. Even eliminating every traversal for free could save only 2.49% / 1.51%.
This is an impossible optimistic bound, not an achieved caching improvement.
The original synthetic 6.5% AKI/frequency lifecycle difference was observed,
not causal: identical ingestion code was 52.75 ms slower in AKI's run order,
while its query work was 6.63 ms faster. New experiments interleave conditions.

The original ARB zero-hit result has narrow scope: only 27/101 positives are
Python (26 Click, one pytest), and the extractor supports Python. Among 145
explicit-path relationship requests, only 38 anchors are Python, 133 closures
are empty, and no exact anchor repeats within a snapshot. Two requests encounter
a previously queried nonempty subpath. This cannot establish absence of reuse
in actual coding-agent workloads. Original ARB timing has unequal populations
(183 prototype versus 102 upstream queries) and incompletely charged cloned
store setup; only its quality comparison is retained.

Reproduced the retained-cost defect before fixing it: a validated expensive
closure kept hitting after a changed-tree selective refresh, but its measured
base cost and estimated benefit became zero. Reproduced the restart defect:
with a 250-byte budget, reopening followed by two admissions reported 232 bytes
while SQLite held 464. Fresh-database phase-one benchmarks were not affected by
that restart bug. Same-tree transitions also rebuilt the base and reset state
(3/7 Click and 3/5 pytest transitions), confounding the original global/selective
prebuilding comparison. All old results are preserved with these qualifications.

`76316b7` fixes those defects for every policy, batches durable replacements,
adds syntax-cache/incremental base maintenance, and freezes the paired harness
and optional selective gate. New module additions still re-resolve imports in
unchanged files. `9929b57` additionally fixes Python physical line accounting:
embedded Unicode U+2028 inside a string must not shift AST import evidence.
The new extractor version forces revalidation of older stores. The complete
suite now passes 26 tests. The phase-two lifecycle engine is pinned by each
run's code hashes and commit; later analysis/documentation changes do not alter
retrieval or admission rules.

The new gate was scored once without subsequent rule tuning. On all 183 exposed
development samples it fails the registered criterion: natural no-gold abstention
remains 0/50, counterfactual abstention becomes 4/32, and positive Recall@20 falls
from 0.69637 to 0.51650. The official lexical output matches all 101 prior positive
top-20 rankings, MRR, recall and canonical BCY exactly. On the 29 previously
unexposed code2test positives in five preselected repositories, the same gate
allows every query and changes no rankings (MRR 0.11113, Recall@20 0.30460,
BCY@8k 0.18966). There is no new natural-negative holdout. The gate remains
experimental/opt-in; these results do not support selective retrieval quality.

The pinned code2test archive has SHA-256
`387cdfb25835b176ba27707d43dc31cae6b31514231923af237ad04deef19c0b`.
Python's default certificate configuration initially failed; the successful
retry used the Mac's existing `/etc/ssl/cert.pem` with TLS verification enabled.
No tools were installed and no certificates or credentials were created.
Flask was pinned to `d086db856be187255b8ec61ef409357393020f32` before its task
titles were inspected; its BSD-3-Clause license was checked from that revision.
Thirty actual commit-title tasks per repository are routed on parent snapshots.
These are deterministic task-derived accesses, not observed agent trajectories.

The serial lifecycle command sequence is reproduced by
`scripts/reproduce_phase2.sh`; source downloads are separate prerequisites.
Raw query answer hashes, refresh cost breakdowns, acquisition time and storage
are retained. Every policy receives the same no-op path, incremental/full base
choice, invalidation mode and durable-write ablation. No policy sees future
queries or evaluator labels. Synthetic seeds 70–72 are separately labeled.

## Phase two measured milestone

All primary runs completed on the frozen `5bd8417` engine. Disabled-policy
complete lifecycle means (full / incremental) are Click 8.497 / 2.621 s,
pytest 28.322 / 5.530 s and held-out Flask 5.143 / 1.787 s. Mean paired reductions
are 69.14%, 80.39% and 65.25%; every repetition exceeds the registered 40% goal.
This is shared base maintenance, not an AKI admission-policy advantage.

AKI and frequency remain essentially tied on synthetic locality (748.61 versus
749.49 ms mean), missing the 20% goal. No real-source sequence meets that goal.
The retained Flask AKI cold-refresh outlier is 920.34 ms before the first query;
frequency and disabled are 156.17 and 149.78 ms. Its cause is unknown and must
not be described as causal admission overhead. All raw repetitions remain.

Independent accounting/hash checks pass 53,550 primary query-condition records
and 97,020 operations. An unlimited, free, exactly validated demand-cache audit
finds valid-repeat ceilings of only 0.232%, 0.339% and 0.323% of full service
cost on Click/pytest/Flask. Reuse exists (97/180, 103/180 and 67/144 requests),
but these closures are cheap. Synthetic locality's corresponding ceiling is
39.81%; low reuse is zero. This triggers the registered stop rule for further
closure-admission search on these real-source workloads.

Final release checks added old-extractor serving guards and byte-exact source
loading in `80085ac`. All 28 tests pass. A separate final-patch smoke run checks
70 task-condition rows / 420 operators across all 35 conditions. Primary timings
retain their earlier code version rather than being relabeled. A final-code
source audit verifies 90 snapshots, 68,833 active span instances and 120,915
evidence links against actual current text, with zero mismatches or parse errors.
Counts include unchanged instances across snapshots. This verifies implemented
source/graph semantics, not task evidence sufficiency or agent repair success.

Results, per-refresh costs, latency/break-even records, storage, provenance and
figures are in `results/phase2`; interpretation is in `PHASE2_RESULTS.md`.
No paid resource is needed for this milestone. `NEXT_EXPERIMENTS.md` records the
next scientific decision and source/license availability checks, without
claiming new benchmarks were run or that a larger model would solve the gap.

## Phase three — actual executed-agent access audit

Registered `PHASE3_PROTOCOL.md` in `af80b41` before action inspection. Downloaded a
bounded, pinned CC-BY-4.0 Nebius OpenHands sample: 128 outcome-blind trajectories,
101 repositories, 8,613 tool calls. No raw trace/source/query text is published.
The view audit finds 1.34–2.49% observed numbered-line byte overlap under strict
and literal-read boundary conditions; exact view repeats are 0/2. Among 1,156
explicit-cwd literal shell reads, exact caching finds one equal-output repeat.
Simple LRU matches unlimited exact caching; neither faces payload budget pressure.
Clipped tool notices initially looked like changed source lines; corrected the
parser and added a test before final accounting. This was a data-format defect,
not evidence of stale AKI serving.

No action timings or per-action tree hashes exist in the trace schema. Base
commits are available separately, but arbitrary intermediate shell effects remain
unreconstructed. The registered lifecycle gate cannot pass on bytes/counts.
No new candidate was implemented, no model call/purchase made, and no official
repair benchmark claim is made. `PHASE3_RESULTS.md` records the bounded missing
instrumented-log requirement, source attribution and reproducible audit commands.
The existing incremental-maintenance finding and all earlier negatives remain.

## Phase four — bounded source reconstruction reaches a real blocker

Registered protocol `313c382`; froze 24 metadata-selected tasks across six
repositories in `ce59006`. Acquired all twelve development source snapshots and
only selected development action objects. Corrected a `/testbed` assumption using
pinned task-version metadata for `/workspace/<repo>__<version>`. Expanded only a
safe literal-find grammar; no command execution was introduced.

Twenty-one views match source evidence; zero mismatches. All tasks stop after
one or two matched reads at Python setup/test/module execution, so 0/12 meet the
registered three-read minimum (8/12 required). Held-out actions remain uninspected.
No policy benchmark or new candidate was run after that failed gate. Final local
view read/hash/decode/selection totals are 9.795 ms wall and 2.505 ms CPU, explicitly
not original agent service times or full lifecycle savings.

Budgeted downloads are 1.017 GiB; measured script CPU 38.123 s, with conservative
review/validation allowances still well within the 2 GiB/30 CPU-minute cap.
No third-party setup/test/source code ran. The missing input is post-opaque-action
source snapshots or verified deltas with actual tree identities and tool timings.
Current deliverable decision: incremental source/evidence maintenance, retaining
AKI admission as experimental and all prior negative results. See
`PHASE4_RESULTS.md` for exact limits, provenance, tests and the smallest next input.

## Instrumentation release — missing evidence made actionable

Added the opt-in POSIX `aki.recorder` and a small reviewed-adapter bridge. It records
explicitly enrolled source snapshots/deltas, monotonic observer times, separately
reported executor metrics, and request/output hashes. Optional source/request
retention stays private and local. No hidden session, unrelated project, private
repository, model credential, remote capture endpoint or background watcher is
accessed. Whole-repository/environment freshness is not inferred from a scoped
snapshot. Failed or incomplete boundaries fail validation.

Demonstrated only on original project-owned fixtures: five complete operations,
ten boundaries, twelve events, exact-byte source versions and add/delete deltas.
This is instrumentation validation, not agent evaluation. Captures remain ignored
under scratch; publication contains only code, documentation and tests. The
prospective protocol reuses the frozen 24-task cohort and defines a three-task
pilot with explicit budgets and stop criteria before held-out inspection.

The Docker CLI exists, but a bounded read-only version check found its daemon
unreachable/not running. No daemon or container was started. No reviewed live
agent adapter/model transport is configured here. Those are the concrete remaining
capabilities needed for a prospective run; no purchase is requested. The useful
current deliverable remains incremental source/evidence maintenance, with adaptive
selection unresolved.

## Targeted runtime/model feasibility follow-up

Found the app-bundled Codex CLI despite its absence from PATH; existing ChatGPT
authentication is active. One tool-disabled ephemeral fixture probe succeeded,
with only an agent-message event and a verified recording (one operation/two
boundaries). Reported model usage was 15,889 input and 15 output tokens; no repeat
probe or paid API setup was performed. No existing sessions were read or resumed.

Docker targets an existing stopped Colima profile, not an installed Docker Desktop
app. Its VM startup has guest provisioning/system/disk operations, so the narrower
ordinary-app-launch permission was not expanded to that boot. Recorded the exact
resume command, remaining reviewed-isolation/adapter checks, and the first frozen
one-task pilot in `CODEX_CLI_READINESS.md`. No benchmark code ran; held-out actions
remain unopened. Generated captures stay local; only documentation is published.

## Guarded runtime resume follow-up

Started the existing Colima profile once with save-config/context/SSH-config
changes disabled. Its VM booted, then printed successful 386/amd64 installation
messages; the startup guard interrupted at 13.888 seconds. Matching installed
Colima source identifies an existing guest binfmt invocation for emulation-handler
registration, not a package downloader. The messages had already been emitted;
the guard is not claimed to have prevented those guest operations.

Read-only Docker readiness succeeded (Engine 29.5.2, linux/arm64). Stopped the VM
and verified its profile is Stopped. Saved configuration hashes were equal across
startup. No benchmark image or code ran, no further model probe was made, and
held-out actions remain uninspected. The installation boundary requires resolution
before another startup; native-only `--binfmt=false` is documented but untried.
Image review and live adapter validation remain. See `COLIMA_RESUME_CHECK.md`.

## Native startup and task-image gate

Native-only Colima start completed in 19.264 seconds with binfmt disabled and no
download/install/permission indication. Docker 29.5.2 answered on linux/arm64;
no qemu/Rosetta handler files were present. Saved configuration hashes remained
equal through shutdown, and the VM is confirmed Stopped.

Reviewed pinned task 420 runtime metadata, transferring 511,343 additional bytes.
Both image fields are null. The declared environment needs Python 3.5, GCC and
pip-installed dependencies. No reviewed compatible image is currently available;
unrelated cached project images were not reused. Added a bounded metadata-review
command restricted to frozen development tasks, with no action/gold/outcome reads
and no execution of setup strings. See `NATIVE_PILOT_PREFLIGHT.md` and numeric
records under `results/runtime/`.

Image construction/installation was not silently added to the no-install scope.
The live adapter bridge still needs a validated isolated backend; no agent attempt
was launched. Existing model access works; the remaining input is a reviewed
native task image or a permitted bounded isolated build, then adapter validation.
Held-out actions and the frozen cohort are unchanged. No adaptive result added.

## First bounded task-420 setup attempt — failed compatibility gate

Verified and staged 329,867,946 bytes, including the pinned native image and 29
package artifacts. Resolved Docker 29's converted manifest representation by
matching the exact original config blob and all uncompressed layer hashes, without
another import. One confined non-root/offline container received 82 public files.
Its first compatibility command failed: `/env` was `noexec`, preventing execution
of the copied virtual-environment interpreter. No dependency installation, task
test, model call, recorder pilot or held-out action followed.

Removed the owned container/image and 844,838,739 local artifact bytes; VM stopped
and saved settings unchanged. Staging used 4.885 measured CPU-seconds. Accounted
setup CPU at failure was about 121.2 s including a 50 s host allowance; final
shutdown CPU is not fully measured. Failure occurred at 541.897 elapsed seconds;
runtime shutdown finished at 618.473 s, an 18.473 s cleanup overrun against the
proposal's setup-wall ceiling. This must remain visible in reports.

Preserved the original failed controls and added a deterministic mount preflight
guard with four regression tests. No isolated-runtime fix or second compatibility
attempt was executed. See `TASK420_ATTEMPT1.md`; adaptive efficacy remains unresolved.

## Closed-attempt control repair — no live execution

Replaced the proposed copied virtual environment with base-interpreter dispatch
and separate bootstrap/runtime library data while preserving all `noexec` mounts.
Static review found a second silent-check problem: the frozen B2 console module
does not dispatch `main` under `python -m`; the repaired help check calls it
explicitly. Added an outer command watchdog reserving teardown inside the total
deadline, complete CPU-component validation with conservative unsampled tails,
and byte/disk ledgers. Mock checks cover Docker manifest conversion, inherited
public image environment, confinement, and ownership-scoped cleanup.

The host suite passes 88 tests, including 28 new tests. Actual original host
subprocess fixtures exercise blocked pipes, output caps and cleanup failures;
runtime/configuration/CPU scenarios otherwise use mocks. A local preparation-only
command generated a disabled plan and hash locks. No VM/container was restarted,
artifact downloaded/installed, benchmark code executed or model called. No held-out
actions were accessed. Historical controls and failed-run evidence remain intact.

The Docker/recorder integration is not live-validated or enabled. The next precise
permission scope and preconditions are documented in `TASK420_SETUP_REPAIR.md`:
one bounded fixture-first attempt, original limits, all security flags retained,
no task dispatch until runtime and recorder checks pass. This closes the code and
host-test work; adaptive efficacy and prospective agent evaluation remain unresolved.

## Authorized corrected attempt — initial TLS failure, no live fixture reached

Froze the integrated driver and bounded three-turn planner protocol in `238d6b5`
after 93 host tests. The one authorized attempt failed immediately at the public
registry token request with certificate verification failure. No artifact body,
VM start, dependency execution, recorder fixture, task operation or model call
followed. Bounded cleanup completed with finalized accounting and unchanged saved
configuration hashes. Total preparation/work/cleanup wall was 1.178685 seconds;
observed CPU components sum to 0.845956 seconds, conservative total 1.851191 seconds.

Local read-only diagnosis found zero default Python CA roots in both ordinary and
isolated mode. Existing certifi loads 150 roots. Added a verified-context preflight,
explicit context propagation to registry/artifact/task-metadata requests and two
tests. Also separated the driver's one-CPU-second report-writing allowance from
observed CPU fields; the original raw record remains unmodified and the public
numeric report discloses the old labeling. Final suite: 95 tests passed. No new
network request or execution retry occurred after failure. See `TASK420_ATTEMPT2.md`.

The precise remaining gate is renewed authorization for the verified registry
preflight and conditional bounded fixture-first attempt. It requires no host
installation, new credential or security-setting change. Adaptive benefit,
live recorder feasibility and prospective agent outcomes remain unresolved.

## Shared-budget continuation — first live recorder evidence

Used one durable 512 MiB / 3 GiB / 300 CPU-second campaign across two setup runs,
with verified artifact reuse and no pilot retry. Run 1 (`31284cf`, 99 host tests)
stopped while reviewing bundled Windows launcher data. A narrow review of the
pinned pip/setuptools wheel members resolved that check without executing the
launchers or weakening TLS, architecture or mount constraints.

Run 2 (`e3ff05a`, 100 tests) started the native isolated runtime, verified a live
four-operation original fixture, and passed six dependency/setup checks. Four
complete operations, eight source snapshots and ten journal events independently
verified. Recorded fixture service intervals summed to 1.166584 s versus 0.072436 s guest operation
bodies. This is instrumentation evidence, not an agent/retrieval result.

The CLI help check stopped on exit 1; static inspection confirms the legacy CLI
uses that status for help. Two ESRCH counter errors during shutdown left accounting
incomplete, and the shared guard closed the campaign. No model call, pilot or
held-out inspection occurred. Cumulative transfer 329,892,894 bytes, active wall
82.799640 s, registered conservative CPU charge 166.486913 s. The CPU total cannot
be certified complete. Containers/image removed, VM stopped, saved settings unchanged;
844,838,767 bytes of verified offline artifacts retained locally for audit/reuse.

Changed the next compatibility check to `version` and added a host-tested bounded
tail for known processes exiting during teardown. Final suite: 101 tests. These
patches were not run live and do not change the incomplete historical status.
See `TASK420_SHARED_BUDGET_RESULTS.md`; adaptive efficacy remains unresolved.

## 2026-10-26 — closed-campaign offline audit

No live operation, download, benchmark execution or model call. Rehashed the exact
40-file cache: 844,838,767 bytes, with compressed image expansion explaining its
difference from 329,892,894 charged download bytes. Whole-campaign logical files
total 844,957,468 bytes; retain local captures/logs and artifacts unpublished.
The budget hash and closed state are unchanged.

The missing teardown counter identities/timestamps prevent certification of the
166.486913-second charge. Conditional reconciliation gives 242.713025 seconds for
one affected host component or 318.939137 for both, assuming full prior coverage
and gaps only during cleanup. Neither is an observed total or proof of breach.
Preserve the incomplete accounting finding rather than infer spare allowance.

Static inspection confirms legacy Help.run returns 1 and Version.run returns 0.
Remaining live gates are corrected CLI/version, unit collection, new source-boundary
controls and shutdown accounting. Added append-only counter evidence, strict runtime
fault handling, failure-safe post-source capture, guest child cleanup/quiescence,
bounded planner output and verified gates. A validation-only plan excludes models.
Nine focused fixture/mock tests pass; full suite 110 passes in 2.627 seconds.

The historical service interval omitted the preliminary guest snapshot; wording
is corrected and raw measurements retained. Future measurements include that work.
Retain task 420 for a future explicitly authorized compatibility/accounting-only
check; no new task selection or optimizer work. See `TASK420_OFFLINE_AUDIT.md` for
the evidence, limitations and narrow future scope. The current campaign is closed.

## 2026-10-27 — cached validation stopped before image import

Separate authorization and a fresh allowance: no downloads, no models, 300 CPU-s,
600 active wall seconds, 3 GiB additional disk. Frozen execution commit `34e3767`,
114 host tests. Added cache-only staging, independent zero-transfer ledger and
runtime exclusivity gate; reverified all 40 cached files without modifying the old
cache, manifest or budget. Used the same native-only non-persistent startup flags.

One attempt: staging passed, native engine started, then active containers triggered
the contamination guard. No image import, guest creation, recorder fixture, package
setup, compatibility step, benchmark or model call ran. No runtime retry. Cleanup
returned the VM to stopped and removed only new staging paths. Four saved config
hashes match; old cache and budget hashes remain unchanged. Existing container
identities were not retained, so their ownership is unknown. VM startup/shutdown
may have started/quiesced auto-start containers; none was individually modified.

Driver charged 93.688328312 conservative CPU-s and 27.461661 active wall seconds;
peak disk reservation 2,791,274,917 bytes. AKI staging transferred zero bytes;
unrelated containers' traffic was not measured. Both ledgers are closed.

The new journal exposed two suppressed worker ESRCH errors, one with no prior
sample. Despite driver accounting_complete=true, reaped-child coverage was not
proved; independent audit rejects CPU completeness and project-only attribution.
Removed the suppression and added a failing-before/fixed-after mock. Final suite:
115 passes, 2.562 s. Patch is host-tested only, with no new live attempt.

Decision: do not retry until runtime exclusivity and reliable descendant-exit
accounting are established. Preserve the failed evidence and pending compatibility
gates. See `TASK420_CACHED_VALIDATION_RESULTS.md`; adaptive claims remain unchanged.

## 2026-10-27 — offline counter/ownership root-cause audit

No VM/container lifecycle command, download, benchmark or model call. Read only
retained AKI evidence, selected profile metadata and installed Colima help. Earlier
cleanup removed owned containers; it never established an empty shared engine.
The cached run retained no active-container IDs/policies, so their owners and
auto-start versus concurrent-creation origin are unknown. Stopping default Colima
quiesced its guest services; unrelated-worker interruption/data impact is unknown.
Neither “everything was untouched” nor attribution to another project is justified.

Deterministically replayed original `_workers` from `34e3767`: an unobserved worker
ESRCH is logged then accepted as zero when its PID disappears. Current code raises.
Added five original tests spanning missing/known counters, explicit teardown bound,
work dispatch, cleanup, final snapshot and ledger closure. Focused 5/5; suite 120
passes in 2.556 seconds. No missing live usage was reconstructed or budget reopened.

Designed a separate owned AKI profile/context with two CPUs/two GiB RAM, no shared
default-runtime lifecycle and only attempt control/package read-only mounts. The
configured pristine boot-cache path is missing; existing mutable VM disk cloning
is excluded because it could copy private state/containers. A clean pinned base,
bounded provisioning quote and complete descendant-exit evidence remain prerequisites;
this is not a ready live retry or a new approval request.

Added task-benefit design: no closure-admission tuning after the measured <0.34%
opportunity ceiling; require genuine prospective costly/reusable work, matched
strong caches and actual paired executable-task outcomes under full lifecycle
accounting. The 12-task held-out cohort is not enough by itself for a broad quality
noninferiority claim. No held-out actions were opened. See root-cause audit and
TASK_BENEFIT_EXPERIMENT.md for the decision rules and limits.

## 2026-10-27 — offline readiness components and sealed fixture harness

Implemented exit-independent accounting primitives: an owned durable subtree
counter with stable identity/rounding/stale-interval bounds, plus whole-lifetime
physical-capacity fallback. Finalization needs closed dispatch and an observed
empty scope; missing PIDs and parent exits are not proof. Cgroup reader uses
two-sided populated checks and rejects malformed/replaced/missing domains. Original
filesystem/mocked tests only; no kernel/VM runtime claim. The Mac integration is
still missing. A 12-CPU full-capacity envelope would spend the 180 CPU-s work
allowance in 15 wall seconds, shorter than the prior 19.283-second startup, so
another identical-budget attempt is not justified with that fallback.

Implemented pure dedicated-profile ownership/isolation and cleanup gates. They
reject preexisting/default profiles, extra host mounts, identity changes and
foreign containers. Disabled the legacy default-runtime driver before any live
command or ledger creation. Its historical code remains for audit. The configured
pristine boot cache and parent directory are absent; no other verified boot
artifact is inferred. Mutable VM disks are excluded. ClauseWeave/Roblox dependency
on Colima remains unknown from the permitted records.

Implemented a sealed fixture evaluation harness with development-only baseline
selection, matching budgets, fresh independent stores and frozen code/config.
Held-out input cannot be read by its evaluator before freezing; seals detect
changes and prevent repeated opening. This is accidental-leakage prevention, not
encryption. Actual frozen research holdout actions remain uninspected. Task-success
aggregation requires executable-test receipts, includes failures/cancellations,
rejects stale evidence/missing cost and emits no real success value for fixtures.

Ran original synthetic fixtures only. Final run: 18 development and nine holdout
condition-attempts (four steps each), all correct/fresh. Frequency was the lowest
observed development cache; keep disabled as a separate control. Holdout fixture
totals: frequency 28.218 ms, disabled 27.611 ms, AKI 29.772 ms. These tiny single-run
timings establish harness function, not efficacy. The first plumbing run that chose
disabled overall is retained with its exact source hash; no negative evidence was
discarded. Real task attempts/model calls are zero and resolved-task metrics null.

Final suite: 137 host tests pass in 3.337 seconds. Both live budget files retain
their prior hashes and closed states. No VM/profile/container/download/security
change or private-session inspection occurred. See OFFLINE_COMPONENTS_MILESTONE.md
for proof obligations and the unresolved boot/host-accounting prerequisites.

## 2026-10-27 — platform adapter and independent freshness challenge

Implemented an injected Linux-cgroup platform adapter connecting enrollment,
dispatch, seal, owned-stop and final read to the subtree ledger. Unsupported
platforms (including Darwin PID polling), incomplete containment, vanished scopes,
read/stop failures and unacknowledged controls fail closed. A surviving descendant
keeps cleanup pending. The reader verifies identity after its final event read.
These are original filesystem/mocked tests; no Linux kernel or Mac live launcher
has been certified. Guest-domain accounting does not cover the host lifecycle.

Added durable exact-result LRU with complete revision/query/budget keys and the
same Store durability/logical-byte cap. The fixture harness now accepts independent
hand-authored expectations. Adversarial checks span all seven matched policies,
including added boundary edges, newly resolvable imports, package initializers,
moves/deletions/branch restoration, current token packing and stale evidence
injection. A dynamic import is intentionally exposed as an extraction gap; empty
but incomplete answers are not mislabeled as stale source.

Final focused suite: 159 tests, 3.553 seconds. A single affected sealed harness run
(v3) records 30 synthetic condition-attempts/120 operations, all fixture-correct and
fresh. Frequency selected among simple development caches; heldout totals are
32.181 ms frequency, 29.383 ms disabled and 27.904 ms AKI. Earlier reversed ordering
and all prior raw results remain. No efficacy inference from these tiny plumbing
timings, no real task success, no new threshold tuning or real heldout reads.

Read-only official release/source metadata identifies a smaller arm64 runtime=none
image: 209,768,031 bytes, pinned SHA-256/SHA-512. The release is not immutable and
the build is not hermetically attested; no binary was acquired. Proposed separate
validation scope: one original fixture, zero host mounts/Docker/model/benchmark,
256 MiB download, 8 GiB added disk with preboot expansion gate, 2-vCPU/2-GiB VM,
240-second work plus 60-second cleanup, 3,600 CPU-second whole-machine conservative
reservation. This requires new approval and actual exclusive-launcher receipts;
an unproven shutdown still makes lifecycle CPU uncertified. The old 300-CPU-second
allowances remain closed and unchanged. No VM/container/profile action, installation,
artifact download, hidden-session read or other-project inspection occurred.
See OFFLINE_ADAPTER_AUDIT.md and its metadata/provenance record.
