# Phase 2: preregistered diagnosis-driven revision

2026-10-25 UTC. Written before phase-two implementation/evaluation. Phase-one
results remain published. They exposed implementation defects and a weak
candidate/workload match, not a universal failure of adaptive indexing.

## Observations motivating the next hypothesis

Measured disabled-policy refresh/initialization shares are 95.98% (Click) and
97.82% (pytest). Even an impossible free cache of **all** traversal work could
save at most 2.49% and 1.51% of those old service totals. This is an optimistic
diagnostic upper bound, not an achievable cache result. Synthetic traversal
work instead accounts for 56.04% of total cost. Further tuning of closure
admission on the old real-history setup cannot meet a 20% service-cost goal.

ARB's 183 exposed queries produce 145 exact-path requests: only 38 anchors are
Python, 133 closures are empty, zero roots repeat within a snapshot, and only
two requests encounter a previously queried nonempty subpath. Its 101 positive
samples include only 27 Python samples (26 Click, one pytest), versus 74 Go/Rust
samples. These statistics describe this adapter/setup, not real agent reuse.

Reproduced defects: retained closure hits lose measured base costs after
selective refresh; identical source snapshots rebuild and reset policy state;
reopened policy state ignores persisted cache storage. Separately committed
evictions and builds make demand-cache writes expensive. Phase-one startup
outliers and unequal ARB timing scopes prevent causal algorithm/runtime claims.

## Frozen hypotheses and criteria

**H2a — common incremental base maintenance.** Reusing unchanged parsed source
and updating only changed file/search records will reduce complete service cost
by at least 40% relative to a full-refresh base **with the same no-op fast path**
on a new chronological real-task-derived workload, with identical paths,
source hashes and freshness decisions. All policies receive this optimization.
An improvement here is an engineering result, not a novel admission-policy win.

**H2b — admission after fixing the implementation.** Preserve validated retained
cost estimates, preserve all state on identical snapshots, enforce restart
budgets, and batch eviction/build in one durable transaction. Keep window=128,
horizon=64, hysteresis=1.25 and existing admission priors fixed. Compare disabled,
closure LRU, frequency, GDS, AKI and static references. Claim an AKI benefit only
if full cost is at least 20% below the strongest matched simple policy and every
output matches. If the measured free-traversal upper bound still cannot meet
that goal, stop policy search on this candidate family and report the limit.

**H2c — selective retrieval as an explicit evidence gate.** Add an opt-in,
gold-blind rule: retrieve only when the query explicitly mentions an existing
path (or unique basename), or an unambiguous declared symbol not in the pinned
upstream RepoMap generic-symbol set. Otherwise return `insufficient_evidence`,
not a claim that the repository provably contains no useful context. Support
all languages represented by the released symbol metadata. No score threshold
will be fit to gold labels. Freeze the rule before evaluating it; no post-score
threshold tuning. Compare the identical ranker with and without the gate.

Development-only success criterion: improve correct abstention on the 50 already
exposed natural no-gold examples to at least 20%, while losing no more than five
absolute percentage points of positive Recall@20 on the already exposed 101
positives. This is an exploratory criterion, not a formal noninferiority test.
If it fails, keep the gate explicitly experimental/opt-in rather than replacing
the default retriever. Do not tune another rule to repair that score.

## Data separation

- Exposed development: existing phase-one synthetic data, Click/pytest histories,
  ARB trace2code and no-gold subsets. All are disclosed as already exposed.
- New development workload: chronological historical Click and pytest commit
  titles on each commit's parent source snapshot. Anchor selection uses only
  title text and current source, never changed-file gold, future commits or the
  final target query. One task event per real commit; do not invent repeated
  warm-up questions. Include non-code commits as workload events.
- New history evaluation: `pallets/flask`, up to 30 first-parent task events from
  a pinned public revision selected before reading task titles. Do not inspect
  this history until code and parameters are frozen.
- New retrieval evaluation: ARB `v2_code2test`, restricted to the preselected
  previously unexposed repositories `fastapi/fastapi`,
  `huggingface/transformers`, `mockito/mockito`, `spring-projects/spring-boot`,
  and `vuejs/core` (published inventory suggests 29 positives). No code2test
  queries/labels have been opened. Grouped repository selection prevents
  cross-task reuse of the same exposed PR/issue as a purported held-out case.
- There is no untouched natural no-gold set available in the downloaded ARB
  release: all 82 negatives were already evaluated. Report that limitation.
  Deterministic wrong-repository controls may accompany new positives but must
  be labeled constructed controls, never a new natural-no-gold benchmark.

Historic commit titles are real task signals; the deterministic request
generation is **task-derived**, not an observed agent trace. Changed-file lists
may be used only after ranking as an explicitly incomplete diagnostic target,
never as anchors, warm-up, filtering/admission feedback or a success label.

## Accounting and checks

Use three paired repetitions with condition order shuffled/interleaved at each
task and refresh. Record acquisition, snapshot hashing, parse/resolve,
invalidation, storage update, policy initialization, query, optimizer and cache
write costs. Include construction/maintenance; no asynchronous/free work.
Store answer hashes and each refresh report. Correctness checks run outside
timed service cost. Corpus reading is separately measured and charged equally
where shared. Do not compare timing populations with different sample counts.

Keep the same logical byte budget for all matched policies; full static remains
an explicitly unbounded reference. Report allocated database bytes, cold and
warm phases, p50/p95, churn, and the free-traversal opportunity bound. A batched
durable-write ablation must be applied to all policies, not only AKI.

Regression tests must cover retained-cost priorities, no-op state preservation,
reopened-cache budget accounting, module additions resolving previously missing
imports, file moves/deletions, changed source-span evidence, and equivalence of
full/incremental refresh under mutations. Re-run affected comparisons on the
final patch. Preserve old results and make code-version distinctions explicit.

No paid inference, package installation, persistent credentials or community
posting. Existing CPU resources suffice. Source acquisition requires only public
licensed data. Run targeted diagnostics and avoid redundant benchmark reruns.
