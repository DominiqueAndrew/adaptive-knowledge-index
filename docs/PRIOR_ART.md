# Prior art and evaluation constraints

Source audit, 2026-10-25. These are literature observations, not replicated
measurements. AKI's broad idea is not new. Its proposed distinction is a
commit-aware physical-design layer for cross-file evidence paths, evaluated
against strong fresh caches with full lifecycle accounting. Novelty is unproven.

| Work | Established overlap | Consequence for this project |
|---|---|---|
| [Agentic Context Cracking](https://arxiv.org/html/2608.31082v2) | Query-guided speculative evidence structures, structured lookup, raw-source fallback and amortization; static-corpus setting | Closest architectural precedent. Generic adaptive structuring is not a contribution. Its related-question warm-up is target-conditioned; use independently generated future workloads here. |
| [GAM-RAG](https://proceedings.mlr.press/v306/wang26cq.html), [full text](https://arxiv.org/html/2603.01783v1) | Experience-dependent retrieval weights on an entity/sentence/passage graph | The reported 61% reduction concerns warmed query time in 2Wiki scenarios, not established end-to-end cost on changing code. |
| [A-Mem](https://arxiv.org/abs/2502.12110), [system](https://github.com/agiresearch/A-mem), [evaluation](https://github.com/WujiangXu/AgenticMemory) | Adaptive notes, links and memory evolution | Conversational-memory scores are not code-index lifecycle evidence. |
| [Amber](https://aclanthology.org/2025.findings-acl.418/) | Adaptive retrieval, stopping and memory updates in open-domain QA | Adjacent control strategy, not an equivalent code physical-design baseline. |
| [ReMindRAG](https://arxiv.org/abs/2510.13193), [code](https://github.com/kilgrims/ReMindRAG) | Traversal experience in graph-edge embeddings | Additional experience-reuse comparator for a later model-assisted experiment. |
| [Database Cracking](https://ir.cwi.nl/pub/12236), [adaptive indexing hybrids](https://www.vldb.org/pvldb/vol4/p586-idreos.pdf) | Query-driven physical organization and convergence | Include initialization and per-query overhead from the first query. |
| [DynaMat](https://pages.aueb.gr/users/kotidis/Publications/Sigmod99/99DynaMat.pdf) | Joint fragment selection and maintenance under space/time constraints | Maintenance-aware materialization is established database work. |
| [DBA Bandits](https://arxiv.org/abs/2010.09208), [HMAB](https://www.vldb.org/pvldb/vol16/p216-perera.pdf) | Observed index benefit and interacting index/view selection | A generic online optimizer is insufficient for novelty. |
| [GreedyDual-Size](https://www.usenix.org/conference/usits-97/cost-aware-www-proxy-caching-algorithms), [TinyLFU](https://arxiv.org/abs/1512.00727) | Cost/size/recency retention and lightweight admission | Include GDS-style and window-frequency baselines, not only LRU. Our small implementations are labeled adaptations, not exact reference packages. |
| [Semantic caching](https://arxiv.org/abs/2508.07675), [FreshCache](https://arxiv.org/abs/2607.04281) | Online reuse/mismatch costs and freshness | Avoid blanket claims of new cost-aware or freshness-aware caching. |
| [LocAgent](https://arxiv.org/abs/2503.09089) | Parsed heterogeneous code graph and multihop localization | Keep extraction and traversal semantics identical across storage policies. |

## ARB source audit

[ARB](https://github.com/eyuansu62/agent-retrieval-bench) has 345 positive
samples (106 code2test, 80 comment2context, 101 trace2code, 58 edit2ripple) and
82 no-gold samples (50 natural, 32 counterfactual). Use all_files without keep
lists. Corpus metadata and evaluator are MIT; source snapshots retain upstream
licenses ([license notes](https://github.com/eyuansu62/agent-retrieval-bench/blob/main/DATA_LICENSE.md)).
We distribute download instructions, hashes and numeric/ranking outputs, not
corpus text or public failure traces. Evaluator pin: `2c773139dd86003ec6defffa28bff1688c4af768`.

The README records October 22 fixes to RepoMap determinism and closed-tool
prefix scoring. Old published RepoMap scores cannot serve as a fresh baseline.
Canonical BCY uses a regex tokenizer and greedy ranked-file packing with a
partial final file. Legacy character-counted gold_coverage is not BCY. A gold
file exposed by one token does not imply sufficient evidence or successful repair.

[Community results](https://github.com/eyuansu62/agent-retrieval-bench/blob/main/docs/community_results.md)
include a stronger Oko 0.9.1 reference (Jev reranker), with saved rankings at
`bartlomein/oko@9a8094edef23f0c3cb6d31ea511aa6597f430dfd`. The published MRR
range is 0.4009–0.4063 and BCY@8k 0.5275–0.5365 on all 345 positives. Those
are author-reported, not our results. The nominal held-out half was seen in
later regression checks. No selective evaluation was reported. CodeNib's
reported graph-expansion regression is a warning against assuming graph edges
improve ranking.

## Falsifiable program

1. Validate official scoring and pin inputs; run lexical, BM25 and current RepoMap.
2. Match retrieval semantics, freshness and byte budgets across cache policies.
3. Measure startup, optimization, materialization, eviction, refresh and storage;
   report cold, warm, future queries, zero-reuse and drift separately.
4. Exercise changed/deleted/moved files, new incoming dependencies, and branch
   changes. Never equate absence from a cached positive footprint with safety.
5. Keep benchmark gold outside the policy API. Split tuning from held-out tests
   and disclose generated rather than real chronological workload sequences.
6. Require improvement against the strongest matched baseline. An illustrative
   next-stage practical target is 20% lower lifecycle cost at identical output;
   this is a project goal, not a result or literature-backed threshold.
7. Only after a measured retrieval-layer win, run a bounded, fixed-model repair
   experiment. No SWE-bench, GraphRAG or agent-success claims without their actual
   protocols. More expensive models are not a remedy for an unproven optimizer.

Future broader retrieval validation could inspect [SWE-Explore](https://arxiv.org/abs/2606.07297)
and [CORE-Bench for agentic code retrieval](https://arxiv.org/abs/2606.11864).
Neither has been run here.
