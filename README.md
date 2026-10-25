# Adaptive Knowledge Index (AKI)

An experimental, dependency-free Python/SQLite physical-design layer for coding
retrieval. It observes requests and selectively materializes reusable import
closures under a byte budget. Source spans, hashes and revision-scoped evidence
remain authoritative.

**Current finding: a useful negative result.** Synthetic locality can make
materialization worthwhile, but the cost policy has not established an advantage
over the strongest simple baseline. Real ARB queries had zero relationship-cache
hits; the prototype retriever trails fresh official baselines and fails no-gold
abstention. This is a research artifact, with no established novelty or coding-agent
success claim. [Results and limitations](docs/RESULTS.md) · [design](docs/DESIGN.md)
· [prior art](docs/PRIOR_ART.md) · [research log](docs/RESEARCH_LOG.md).

## Run

Requires Python 3.11+ with SQLite FTS5. No package installation, model key,
embedding download, service, or GPU is needed.

```sh
python3 -m unittest discover -s tests -v
sh scripts/reproduce.sh my-run
```

The second command runs seven policies over five locality seeds and five
low-reuse seeds. Each run uses new SQLite databases and writes raw query timings,
correctness hashes, storage measurements, code hashes and summaries. It refuses
to overwrite output directories. OS filesystem caches are not flushed.

```python
from aki.source import read_python_tree
from aki.store import Store
from aki.policy import Policy
from pathlib import Path

store = Store("scratch.sqlite", scope="example-project")
store.refresh(read_python_tree(Path("/path/to/source")), "local source snapshot")
policy = Policy(store, "aki", budget=65_536)
files, costs = policy.query("package/core.py", "tests", store.revision, budget=4_096)
# Synchronize every edit before subsequent queries:
policy.refresh(read_python_tree(Path("/path/to/source")), "next snapshot", "selective")
store.close()
```

The library expects host-supplied immutable snapshots. It does not watch the
filesystem or support concurrent writers. A stale revision argument is rejected.
The byte budget covers materializations, not the authoritative source archive or
the whole process. See the [freshness contract](docs/DESIGN.md).

## What is compared

Disabled adaptation, static full materialization (unbounded reference), static
bounded materialization, closure LRU, rolling-frequency admission,
GreedyDual-Size-style retention, and AKI's measured-cost admission with hysteresis.
All use identical graph, ranking and token-packing semantics. Training/adaptation,
frozen future queries, genuinely unseen anchors, drift and mutation are separate
phases. The generated workloads are not real agent traces.

Immutable spans and import-edge evidence are stored in SQLite. Selective
invalidation checks changed graph boundaries, including new incoming edges from
previously unseen files. It retains only path sets proven unchanged under the
current extractor. Base parsing/index refresh is still conservative and complete.

## Reproduce the public-source experiments

Keep downloads adjacent to this repository. Source corpora retain their original
licenses and are not redistributed here. Inspect upstream code before executing
it. These commands use public downloads and existing `git` / `zstd` executables.

```sh
git clone https://github.com/eyuansu62/agent-retrieval-bench.git ../arb-upstream
git -C ../arb-upstream checkout 2c773139dd86003ec6defffa28bff1688c4af768
python3 scripts/prepare_arb.py --out ../arb-data
python3 -m aki.arb_eval --upstream ../arb-upstream --data ../arb-data --out results/my-arb

git clone https://github.com/pallets/click.git ../public-click
python3 -m aki.chronology --repo ../public-click --snapshots 8 --seeds 20,21,22 --count 120 --out results/my-click

git clone https://github.com/pytest-dev/pytest.git ../public-pytest
python3 -m aki.chronology --repo ../public-pytest --label pytest-dev/pytest --license MIT --ref 0f54d41bedf00505bb1ac2c724abf96ba6dcf48d --snapshots 6 --seeds 20,21,22 --count 80 --out results/my-pytest
```

ARB execution uses the official lexical, BM25, RepoMap and canonical BCY
functions from the pinned checkout. Scope is **101 trace2code positives and 82
no-gold samples**, not the entire 427-sample benchmark. No SWE-bench or GraphRAG
protocol has been run. The publication also contains an offline rescore of one
Oko ranking file, clearly distinguished from reproducing its paid reranker.

Historical experiment code is preserved in Git and each run records source
hashes; see the [run manifest](docs/RESULTS.md) before comparing versions.
Optional `scripts/analyze.py` renders figures using an already-installed
matplotlib. It is not required for the engine or experiments.

## License and attribution

Original project code is MIT licensed. The benchmark and repository histories
are attributed in [DATA_SOURCES.md](docs/DATA_SOURCES.md). Only original code,
numeric measurements, source hashes and public file rankings are published.
No source corpus, personal files, query/failure traces, credentials, or model
conversation is included.
