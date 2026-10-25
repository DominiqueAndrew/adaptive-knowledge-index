# Data sources and pins

| Input | Source and revision | Terms / publication handling |
|---|---|---|
| Original synthetic graph generator | `aki.benchmark.synthetic`, 500 source modules, 125 tests, one package initializer | Original MIT project code; no external source corpus |
| ARB evaluator | [eyuansu62/agent-retrieval-bench](https://github.com/eyuansu62/agent-retrieval-bench) at `2c773139dd86003ec6defffa28bff1688c4af768` | MIT; executed from separate checkout, not vendored |
| ARB data | [Hugging Face](https://huggingface.co/datasets/eyuansu71/agent_retrieval_bench) at `5901e1ee3aff048290db72edf9c63bc498b79ea3` | Metadata MIT, source files retain upstream licenses; corpora and query text not published |
| Click source history | [pallets/click](https://github.com/pallets/click), eight first-parent revisions ending `2247b35ea1c47c727d7a06e51fa280e12a863ff6` | BSD-3-Clause, verified LICENSE.txt; original source not vendored |
| pytest source history | [pytest-dev/pytest](https://github.com/pytest-dev/pytest), six first-parent revisions ending `0f54d41bedf00505bb1ac2c724abf96ba6dcf48d` | MIT, verified LICENSE; original source not vendored |
| Phase-two Click / pytest tasks | Thirty first-parent commit titles per repository ending at the same pins above; retrieval runs on each task commit's parent | Same licenses; title text is not redistributed; hashes and commit IDs are recorded |
| Phase-two Flask holdout | [pallets/flask](https://github.com/pallets/flask/tree/d086db856be187255b8ec61ef409357393020f32), thirty first-parent task events ending `d086db856be187255b8ec61ef409357393020f32` | BSD-3-Clause verified at the pin; original source not vendored |
| Oko saved rankings | [bartlomein/oko](https://github.com/bartlomein/oko/tree/9a8094edef23f0c3cb6d31ea511aa6597f430dfd/benchmarks/published/0.9.1/agent-retrieval-bench/details), `oko-0.9.1-run1_details.jsonl` | Offline numeric rescore; third-party raw file not vendored; no Jev API called |

ARB bundles downloaded and SHA-256 verified:

```
19b252e8cfff42107fedc74005dbb6972f2970af33651ce0c1571546819e41c4  agent_retrieval_bench_v2_trace2code.tar.zst
bb358d6b65b7ef6aa36b417240cab4f2d51a8d69e699e573cf324ab339a5c1d8  agent_retrieval_bench_v2_abstention.tar.zst
c5a7f218fe1c1aead870acef2d8939da1884e0e4d30cec78f23cef41f05420cf  oko-0.9.1-run1_details.jsonl
387cdfb25835b176ba27707d43dc31cae6b31514231923af237ad04deef19c0b  agent_retrieval_bench_v2_code2test.tar.zst
```

The two ARB archives total 210,831,967 compressed bytes. Local extracted inputs
are about 1.6 GiB. The union of used corpora is 168 snapshots with 116,299 file
records (counts include near-duplicate files across commits). The prototype's
Python parser rejected 5,949 file records, often because released file chunks
are truncated. FTS still searches those files. Counts are in
`results/arb-v1/snapshot_costs.json`.

The dataset's initial download used its observed `main` and was verified against
the recorded revision's LFS checksums; the reproduction script uses the immutable
revision URL directly. No benchmark code or downloaded repository code was
installed or executed as application code. Only the inspected ARB ranking/scoring
modules are imported.

Phase two adds the 443,641,745-byte code2test archive. Only the preregistered
29 positives in `fastapi/fastapi`, `huggingface/transformers`, `mockito/mockito`,
`spring-projects/spring-boot` and `vuejs/core` enter the held-out evaluation.
They span 28 distinct snapshots, 18 Python positives and 11 other-language
positives. Their sample and corpus-manifest checksums are recorded in
`results/phase2/selective-heldout/provenance.json`. The full archive remains
outside this code repository; outputs contain numeric scores, ranks and evidence
hashes, never source text. The exposed development positives split 27 Python /
74 other-language samples. No untouched natural-negative subset was available.

To reproduce the Oko rescore, download the pinned file above and run:

```sh
python3 scripts/rescore_oko.py --upstream ../arb-upstream --data ../arb-data --rankings ../arb-data/oko-0.9.1-run1_details.jsonl --out results/my-oko-rescore.json
```

Citation: Bowen Qin and Yi Xie, *Agent Retrieval Bench: Evaluating Repository
Context Retrieval for Coding Agents*, 2026,
[arXiv:2607.24882](https://arxiv.org/abs/2607.24882).
