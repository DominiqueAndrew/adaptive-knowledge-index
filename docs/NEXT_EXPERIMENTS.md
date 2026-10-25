# Next experiments and resource decisions

Do not spend on embeddings or repair-model calls merely because the current
admission policy failed. First establish that real agent accesses contain enough
repeatable, still-valid expensive work for the candidate family to matter.

1. Replay actual ordered retrieval actions, preserving task/commit boundaries,
   and measure the free/unlimited reuse bound before designing new candidates.
   The present commit-title workload is not an observed agent trace. Prefer
   cohorts with several chronological tasks per repository; one isolated static
   query per snapshot cannot test cross-task adaptation well.
2. If closures remain below the practical savings threshold, compare a different
   operator family (for example, repeated cross-file symbol/caller resolution)
   against a common fast base and strong caches. Register its semantics and
   stop criterion before measuring a held-out sequence. Do not manufacture
   favorable target-derived warm-ups or tune another closure policy on test data.
3. Revisit selective retrieval using evidence beyond path/symbol presence.
   The registered gate failed. Reserve new natural-negative repositories before
   calibration; the existing 82 negatives are all exposed. A no-answer decision
   is a separate quality problem from a safe materialization miss/fallback.
4. Only after a cost/quality opportunity survives these checks, define a paired
   executable repair study with fixed model, scaffold, task split and budget.
   Count all failed attempts and validate with actual tests. No such experiment
   has been run here, and no paid resource budget is currently requested.

## Availability checks, not benchmark results

The official [SWE-Explore repository](https://github.com/Qiushao-E/SWE-Explore-Bench)
publishes exploration/scoring code under MIT and describes read-action-derived
line-region labels. Its [dataset card](https://huggingface.co/datasets/SWE-Explore-Bench/SWE-Explore-Bench)
lists **CC-BY-NC-ND-4.0**, and exposes read-step metadata as well as ground truth.
Do not assume the code's MIT license also covers the dataset or redistribute
transformed trajectory data as MIT. Before replay, pin versions, inspect the
actual available action schema and upstream source licenses, and keep evaluation
labels out of policy inputs. Successful-trajectory selection would be a sampling
limitation. This audit did not download or run that benchmark.

The official [CORE-Bench dataset card](https://huggingface.co/datasets/zhangfw123/CORE-Bench)
lists **CC-BY-NC-SA-4.0**. It is another possible retrieval-quality evaluation,
not automatically a chronological access log. Its public viewer reported a
schema cast error during this inspection; that does not establish inaccessible
download files. No CORE-Bench experiment or result is claimed.

Current CPU/disk resources are sufficient for this milestone. The remaining
scientific gap is a measured reusable-work opportunity and task-quality evidence,
not evidence that purchasing a larger model will help. Any later paid request
should specify task count, fixed conditions, token limits, maximum cost, and the
decision it will resolve before requesting authorization.
