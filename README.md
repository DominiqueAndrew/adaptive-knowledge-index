# Adaptive Knowledge Index (AKI)

An experimental, dependency-free Python/SQLite physical-design layer for coding
retrieval. It observes requests and selectively materializes reusable import
closures under a byte budget. Source spans, hashes and revision-scoped evidence
remain authoritative.

**Current finding: a useful negative result.** Synthetic locality can make
materialization worthwhile, but the cost policy has not established an advantage
over the strongest simple baseline. The original ARB adapter had zero relationship-cache
hits in a weakly matched workload (only 27/101 positives are Python); the prototype retriever trails fresh official baselines and fails no-gold
abstention. This is a research artifact, with no established novelty or coding-agent
success claim. Phase two fixes measured state/freshness defects, tests incremental
source maintenance on real historical tasks, and retains the failed selective
retrieval experiment. [Phase-two results](docs/PHASE2_RESULTS.md) ·
[Original results and limitations](docs/RESULTS.md) · [design](docs/DESIGN.md)
· [prior art](docs/PRIOR_ART.md) · [research log](docs/RESEARCH_LOG.md).

**Phase three uses actual executed-agent traces.** An outcome-blind, pinned
sample of 128 OpenHands trajectories contains 2,213 file views. Observed line
overlap is only 1.34–2.49% of numbered-line bytes under two conservative boundary
rules; exact view and literal-search repeats are rare. These are byte/count
diagnostics, not latency or task-success results. Missing per-action timings and
source-tree states prevent a lifecycle claim. The evidence does not justify a new
candidate implementation. [Trace audit, limits and next data requirement](docs/PHASE3_RESULTS.md).

**Bounded replay also stops at an evidence gap.** The frozen 24-task/six-repository
study reconstructed 21 source views in its 12 development tasks, all matching the
pinned source. Every task then reached project-code execution before enough reads
to pass the registered coverage gate; held-out actions remain uninspected. The
current useful deliverable is incremental source/evidence maintenance. Adaptive
selection remains experimental. [Replay findings and research decision](docs/PHASE4_RESULTS.md).

Version 0.3 adds an [opt-in local recorder](docs/INSTRUMENTATION.md) for scoped
source hashes/deltas, tool-boundary timings and output hashes. Source/request bytes
require separate opt-in; nothing is discovered or uploaded automatically. Its demo
uses only project-owned fixtures. The [prospective protocol](docs/PROSPECTIVE_CAPTURE_PROTOCOL.md)
preserves the frozen cohort; live agent evaluation still needs a reviewed isolated
executor and an explicit adapter to an approved model/scaffold connection.

The first isolated task-420 setup failed at a `noexec` compatibility gate and was
cleaned up. [Repaired controls and host checks](docs/TASK420_SETUP_REPAIR.md) preserve
that restriction, reserve teardown time and reject incomplete CPU accounting.
Their disabled setup plan still needs an approved live validation; no prospective
agent result is claimed.

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
current extractor. Complete source snapshots are hashed; unchanged syntax and
file/search rows are reused, while all imports are resolved against the current
module universe. This catches newly added modules and incoming dependencies.
Identical snapshots preserve policy state. A new Policy discards old derived
cache rows, so persisted storage cannot silently escape its byte budget.

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

Phase two adds 30 commit-title tasks each from Click, pytest and a previously
unused Flask history, with three interleaved timing repetitions, full source
acquisition costs, all seven policies and matched write ablations. It also scores
an unchanged opt-in evidence gate on 29 previously unused code2test positives.
These are retrieval/history experiments, not agent repair-success measurements.
See [the preregistered protocol](docs/PHASE2_PROTOCOL.md) and run
`sh scripts/reproduce_phase2.sh results/my-phase2` after preparing its pinned
public data. [Next experiments](docs/NEXT_EXPERIMENTS.md) explain why more
resource spending is not yet justified.

## License and attribution

Original project code is MIT licensed. The benchmark and repository histories
are attributed in [DATA_SOURCES.md](docs/DATA_SOURCES.md). Only original code,
numeric measurements, source hashes and public file rankings are published.
No source corpus, personal files, query/failure traces, credentials, or model
conversation is included.

[CLI/runtime readiness follow-up](docs/CODEX_CLI_READINESS.md): the bundled Codex
CLI works with existing ChatGPT authentication. A [native-only Colima start](docs/NATIVE_PILOT_PREFLIGHT.md)
subsequently reached Docker readiness without installation messages. Task 420
declares no runtime image and needs Python 3.5 plus installed dependencies; a
reviewed compatible image and live tool-dispatch adapter remain. The VM is stopped,
and no prospective agent attempt has run.

The [first bounded setup attempt](docs/TASK420_ATTEMPT1.md) subsequently verified
the pinned artifacts but failed virtual-environment bootstrap on a `noexec` mount.
Its container/image/artifacts were removed. The pilot remains unattempted; resource
measurements, accounting limits and a cleanup timing overrun are reported explicitly.
