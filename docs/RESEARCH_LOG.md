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
