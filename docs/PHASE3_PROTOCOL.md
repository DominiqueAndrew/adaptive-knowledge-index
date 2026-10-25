# Phase three: executed-agent trace opportunity audit

Registered 2026-10-25, before reading sampled action values. This is a diagnostic
of actual executed agent accesses, not SWE-bench evaluation or a repair result.
No new AKI candidate or admission tuning is authorized by these measurements alone.

## Source and fixed sample

Use Nebius SWE-rebench-OpenHands-Trajectories, revision
`35455389ab51bf5e2306bfd436ef72d0f98bf882`, CC-BY-4.0. The official dataset card
identifies OpenHands v0.54.0 with Qwen3-Coder-480B-A35B-Instruct and both successful
and unsuccessful attempts. Select 128 rows from Parquet row group 0 by the lowest
SHA256 of `aki-phase3-2026-10-25:` plus trajectory ID. This is a bounded convenience
sample, not a representative random sample of all repositories. Do not select by
outcome, read outcome columns, use gold patches, or generate target warmups.
No policy is tuned on this sample; no final evaluation claim will be made.

Keep downloaded actions/observations outside the public project. Publish scripts,
aggregate metrics, hashes and opaque identifiers only, with source attribution.
Never execute commands found in trajectories. Inspect structured tool calls as data.
Download only required Parquet columns, with a hard 150 MiB transfer cap.

## Questions and estimands

1. How many calls are structured file views, literal shell searches/reads, writes,
   or opaque operations? How often can views reuse the same file/range or line
   subranges after conservative mutation boundaries?
2. Does an unlimited exact-result cache leave additional overlapping file-view
   work? Compare simple 256 KiB result LRU and unlimited interval memoization;
   the latter is an optimistic diagnostic, not an AKI algorithm or achievable
   speedup. Report call counts, returned bytes and numbered-line overlap. Bytes
   are not tokenizer tokens, latency, dollars or a repair-quality score.
3. Are per-action timings, base revisions and source-state transitions available
   to estimate lifecycle savings without inventing costs? Do not infer CPU cost
   from transcript length, tool timeout settings or LLM deliberation.

Use original within-trajectory order and reset caches at trajectory boundaries.
An editor mutation invalidates that file; opaque shell or other execution clears
all cached evidence. Parse only a narrow literal read-only shell grammar; shell
variables, substitutions, redirections, unknown commands and ambiguous state are
opaque. Directory listing completeness is not a file-view cache candidate.
For exact keys, compare later observations with previous observations and report
mismatches; never treat observed reuse as verified repository correctness.

## Falsifiable decision

Advance to a candidate implementation only if measured avoidable service time
beyond the strongest simple matched cache can plausibly exceed 20% of complete
retrieval lifecycle cost, with identical returned evidence and safe source-state
validation. Include source loading, parsing, routing, materialization, invalidation,
packing and all foreground/background work. A count/byte-only opportunity cannot
pass this gate. If required timing or source state is missing, report that specific
measurement gap and a bounded collection/replay plan instead of claiming speedup.

The selected sample is exploratory development data from this point onward.
Any subsequent implementation needs a fresh repository-disjoint, outcome-blind
cohort, fixed budgets, frozen code and quality/freshness checks before evaluation.
