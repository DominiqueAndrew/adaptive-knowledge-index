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
