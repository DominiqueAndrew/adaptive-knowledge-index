# Design and safety contract

AKI is a small physical-design experiment. A Python AST parser creates local
import edges and symbol locations. SQLite recursive CTEs traverse the graph.
All policies share that extractor, traversal, ranking and context packing.
Materializations store sorted reachable file paths per `(anchor, direction)`;
they store neither query strings nor answers. Reverse closures serve both
ripple and test projections. This is deliberately a narrow candidate family.

Source spans are immutable UTF-8 text records with SHA-256, project scope,
content-tree revision, path, line boundaries and provenance. Each import edge
points to a source span and extractor version. `Store.edge_evidence` resolves
current evidence; a relation's presence is not proof of downstream task correctness.
The local source loader rejects invalid UTF-8 rather than hashing a silently
replaced string. It is bounded to Python files of at most 1 MB and skips hidden
paths and symlinks. Canonicality applies to the supplied text snapshot; it is
not a promise that every repository byte was indexed.
The AST extractor is static and incomplete: dynamic imports, runtime dispatch,
external modules, configuration dependencies, and other languages are not modeled.
Package initializers and syntactically present conditional imports are included.
Import reachability is a possible dependency relation, not proven execution flow.

## Freshness contract

Clients submit complete immutable snapshots through `refresh` and must query
the returned content-tree revision. A different scope or stale revision is
rejected. The package is single-owner; it is not a concurrent database service
or a filesystem watcher. A host must synchronize repository edits before
queries. Passing a previous snapshot as if it were current cannot be detected
without host integration. No universal live-filesystem freshness claim is made.

Global mode drops every materialization. Selective mode computes old/new edge
symmetric differences after reparsing the new snapshot. A forward closure is
invalidated if any changed outgoing-edge source is in its old closure plus
anchor. A reverse closure is invalidated if any changed incoming-edge target
is in that footprint. Deleted footprint files invalidate either direction.
This catches new edges from previously unseen nodes: a positive-only list of
previously read source files would miss those negative dependencies.

If no boundary changes, the reachable path set is invariant and can be retained
under the new revision. Content and token counts are always refreshed, including
when the relationship set survives. Validation, retained-row writes, parsing,
source refresh, invalidation and rewarming are charged. Base indexing is still
fully rebuilt; selective *base* indexing is future work. Immutable historical
spans accumulate; there is no garbage collector in this prototype.

## Admission and accounting

- `disabled`: evaluate each recursive CTE.
- `static_full`: prebuild every anchor/direction. Explicitly unbounded reference.
- `static_bounded`: deterministic path-order prebuild under the same byte budget.
  Its complete candidate enumeration is measured and may be wasteful.
- `lru`: admit on demand and evict the least recently accessed closure. It is a
  stronger reusable-structure cache than exact-query memoization.
- `frequency`: two-use admission, a rolling 128-request frequency window and
  frequency-based victim selection. Inspired by admission caches, not a claimed
  exact implementation of W-TinyLFU.
- `gds`: GreedyDual-Size-style measured traversal cost divided by size with an
  aging clock, demand admission and priority refresh on access.
- `aki`: expected demand in a 64-request horizon multiplied by measured saved
  traversal cost, with a build-cost prior updated from actual writes, a 1.25
  hysteresis factor, and observed invalidation risk on refresh. Admission must
  exceed the aggregate lost benefit of all victims plus construction cost.

No label, future query, test success, or future repository change enters the
policy. First-lookup/build priors are fixed heuristic constants, not calibrated
ground truth. The estimator is neither an optimal optimizer nor a bandit. It
may be wrong under drift. Distinct anchor/direction candidates do not share
physical storage; the measured marginal comparison includes victim opportunity
cost but does not solve general overlapping-subgraph selection.

Byte budgets constrain serialized materialization payload plus key/revision
and a fixed row allowance. SQLite allocated/live page bytes are reported
separately. This is not a hard whole-process RAM or disk quota: the canonical
base, historical spans, Python policy bookkeeping and SQLite overhead are
additional. No background workers or embeddings exist. Costs are measured wall
nanoseconds, not artificial API-price equivalents. Actual inference/API cost is zero.

Benchmarks exclude evaluation-oracle computation, workload generation and raw
measurement serialization from the measured retrieval service cost. Those are
not hidden policy work. New databases define cold runs; OS caches are not
flushed. Timing is sensitive to machine load and interpreter overhead. Paired
seed summaries and raw events make these limits inspectable.

## Evaluation separation

Generated-workload packing uses a documented regex token proxy and whole-file
greedy skip-if-too-large behavior. It is only an exact-semantics test. ARB uses
the upstream canonical tokenizer, file renderer, partial-prefix rule and
4k/8k/16k/32k budgets. These are separate metrics and are never equated.

Synthetic adaptation precedes frozen held-out query strings. New queries may
share anchors by design; unseen-anchor and drift phases are separate. Parameter
development used pilot seeds 0–1 and exploratory seeds 10–14; primary final
confirmatory seeds are 50–54, with low-reuse controls 40–44. An earlier run with
seeds 30–34 is preserved but superseded after fixing anchor-partition leakage.
Source graphs are not independent
repositories. Click's eight actual ancestral revisions run in chronological
order but queries are generated, not reconstructed human/agent tasks. ARB is
static real-task evaluation with no gold tuning; it is not a longitudinal trace.
