# Research release history

## 0.2.0

- Fixed retained closure costs/GDS priorities becoming zero after selective
  refresh. Changed trees reset demand counts but retain validated costs.
- Added a shared same-content-tree no-op path for all policies. Earlier results
  that unnecessarily rebuilt unchanged trees retain explicit version caveats.
- Fixed reopened-policy budgets by discarding session-local derived rows in a
  charged transaction. Fresh-database phase-one runs were not affected.
- Batched eviction/admission under identical durable SQLite settings for every
  policy, with a common separate-write ablation.
- Added incremental syntax/file/search maintenance and active immutable-span
  membership. Imports still re-resolve against the current module universe.
- Fixed Unicode physical-line evidence and preserved exact line-ending bytes.
  Old extractor stores require refresh before serving.
- Added interleaved lifecycle experiments, commit-title-derived histories,
  a failed opt-in evidence gate, raw cost breakdowns, independent evidence checks,
  diagnostic reuse ceilings and reproducible figures.

Final code: `80085ac`; primary timing engine: `5bd8417`; gate code: `76316b7`.
Later documentation/analysis commits do not change those measurements.
The release passes 28 tests and 70 final-patch smoke query-condition checks.
Primary experiments separately check 53,550 rows / 97,020 operations. This is
a research artifact, not a claim of algorithmic priority, repair improvement
or production readiness.

## 0.1.0

Initial Python import-closure prototype, seven policies, synthetic/real-source
histories and pinned ARB retrieval-only comparisons. Negative findings and raw
runs remain available in `results/` and Git.
