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
