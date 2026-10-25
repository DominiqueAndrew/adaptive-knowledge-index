# Phase four: safe replay stops before a credible adaptive-index experiment

**Decision: focus the current deliverable on incremental source/evidence
maintenance. Keep adaptive selection experimental.** The bounded replay cannot
safely reconstruct enough of these agent workloads to test a higher-cost reusable
operation. We did not substitute invented state, run repository code on the host,
or use the held-out cohort to rescue the result.

## Registered cohort and executed scope

Protocol commit `313c382` precedes selection. Cohort commit `ce59006` freezes 24
task IDs from six repositories using only metadata: repository, task/trajectory
IDs, revisions and license. It joins the pinned CC-BY-4.0 Nebius releases from
[phase three](PHASE3_RESULTS.md); 385 repositories met the registered eligibility
rule, and no conflicting task metadata was found. Selection uses four distinct
tasks per repository and one outcome-blind trajectory per task.

| Split | Repositories | Tasks | Action inspection |
|---|---|---:|---|
| Development | Backblaze/B2_Command_Line_Tool; certbot/certbot; miurahr/aqtinstall | 12 | Performed |
| Held out | numba/numba; planetlabs/planet-client-python; sanic-org/sanic | 12 | Not performed |

Development repositories were already exposed in phase three; held-out repositories
were absent from that sample. No outcome, patch or task-solution field selected
the cohort. All 12 development source archives downloaded successfully. Their
upstream root licenses matched the expected MIT/Apache family. No task was replaced.
Parquet column chunks include unselected rows, but no held-out action row was
selected, decoded into a Python trajectory, inspected or replayed.

All archives were read as inert data. No trace shell command, setup script,
repository import, test suite, binary or container ran. Regular files were written
without executable permissions; links were recorded without following them.
Archive paths, duplicate entries, sizes and links have safety tests. Source inputs
and raw actions remain outside this public project. Published records contain
counts, identifiers, source metadata, timings and hashes only.

## Measured result and gate

The final replay matched **21 source views** exactly to the observed numbered-line
maps, with **zero mismatches**. Each of the 12 tasks yields only one or two such
views before an opaque execution. No task reaches the registered three-read
minimum, so **0/12 qualify; the required minimum was 8/12**.

The stopping operations are three Python setup-script executions, eight Python
pytest-module executions and one other Python execution. These can run arbitrary
project code and alter state; their command text is not a filesystem change log.
We did not assume they were harmless or execute them to guess what happened.
Ten of twelve tasks also declare an environment-setup commit distinct from the
base commit. The matching early views establish only those observed prefixes,
not equivalence of the whole initial or later execution environment.

Local read/hash/decode/view selection took **9.795 ms wall / 2.505 ms process CPU
in total** across the 21 matched views. Complete reconstruction-function time,
including observation checks and bookkeeping, was 20.590 ms. Source archive
acquisition separately took 5.243 s and unpacking/hashing took 1.948 s across the
12 snapshots. These are one-pass measurements on the same shared Mac as phase
two, after downloads warmed filesystem caches. They are not original agent tool
latencies, an end-to-end agent cost, or stable latency estimates. No p50/p95,
break-even or speedup inference is justified by these short selected prefixes.
Skipped shell reads and all later work have no reconstructed service timing.

Every timed read records a source-file hash, reconstructed source-tree hash,
view-signature hash, observed/predicted evidence hashes and CPU/wall times.
There are zero repeated valid view signatures in these prefixes. This says
nothing about reuse later in the full attempts; the prefixes are dominated by
initial inspection before setup/tests. The tree identity includes regular-file
hashes and unfollowed-link target hashes. It is a reconstructed content identity,
not a source-tree hash logged by the original agent environment.

Because the reconstruction gate failed, held-out replay, three-seed interleaved
policy comparisons, static/file-cache comparisons and candidate implementation
were **not run**. No adaptive-benefit or task-success conclusion is drawn from
unexecuted comparisons. Original phase-two and phase-three negative results remain.

## Reconstruction corrections and provenance

The first pass assumed `/testbed` and stopped at all twelve initial paths. The
actual environment uses `/workspace/<repo>__<version>`. We resolved the mapping
from the same pinned task version metadata; IDs, thresholds and outcomes did not
change. `initial_root_diagnostic.json` preserves that initial parser failure.
Three later stops were literal read-only `find` pipelines, so the parser gained
narrow predicate/pipeline handling with regression coverage. All three eventually
reached project-code execution too; the scientific gate decision did not depend
on rejecting a harmless read. No arbitrary shell evaluation was added.

View semantics were checked against [OpenHands 0.54.0](https://github.com/OpenHands/OpenHands/tree/0.54.0)
and its pinned [openhands-aci 0.3.1 implementation](https://github.com/OpenHands/openhands-aci/tree/0.3.1).
Our original implementation supports only UTF-8 text and explicitly handled line
ranges/clipping. Unsupported encodings, roots, links, responses or mutations stop
the prefix. Source mutations require explicit preconditions and observed success;
none occurred before the twelve stopping boundaries in this cohort.

The source archive acquisition times precede the final duplicate/path validation
hardening. All twelve actual manifests were independently checked against those
final conditions; no unsafe/duplicate/reserved path was found. Final view timing
code hashes are pinned in `summary.json`. No core Store or Policy behavior changed.

## Resources, safety and smallest missing input

The experiment budget accounts for **1,091,501,594 bytes (1.017 GiB)**, including
a conservative 2 MiB allowance for connector-based primary-source review. Measured
script download bodies are 1,089,404,442 bytes. Measured script CPU is 38.123 s;
with a conservative 60 s allowance for independent validation, accounted CPU is
98.123 s. Both remain below 2 GiB / 1,800 s. Download response bodies, cache hits
and cumulative CPU are tracked; Parquet reads and archive reads enforce caps.
The downloaded source snapshots contain 29,114,630 regular-file bytes across
5,674 archive entries. No paid API, purchase, installation or credential was used.

The smallest next useful resource is a **provider export of the source-directory
snapshot or verified delta immediately after the first opaque execution for each
of these twelve frozen development attempts**, plus its actual source-tree hash
and tool start/end times. Later opaque operations would need equivalent boundaries
before extending replay. This reuses existing attempts rather than requesting
new model generations. Base commits alone are insufficient. An isolated reviewed
execution environment is an alternative, but none was installed or assumed safe.
This is an unavailable-evidence blocker, not a denied action or pending approval.

## Research decision across all four phases

The useful result already demonstrated is the shared incremental-maintenance
mechanism: phase two measured 69.1%, 80.4% and 65.2% mean paired lifecycle reductions
on Click, pytest and held-out Flask histories versus the full-refresh control.
These are maintenance results on declared snapshot/task-derived sequences, not
novel adaptation or agent repair results. The strongest simple cache matched AKI
on the useful synthetic condition, and closures occupied too little real-source
service time to support more admission tuning. Actual trace auditing found little
observed reuse under conservative boundaries; this replay found a concrete state
provenance gap before a meaningful cost experiment could begin.

Therefore ship/document the narrower **incremental, revision-scoped source and
evidence index** as the current research artifact. Preserve immutable provenance,
explicit snapshot synchronization, safe fallback and measured update costs.
Do not promote the optimizer as an established advance, promise automatic live
filesystem freshness, or claim better coding-agent outcomes. Further adaptive
research should resume only when instrumented state/timing evidence identifies a
repeatable cost that strong simple caches cannot already remove.

## Reproduce and inspect

Attribution for the CC-BY-4.0 data: Nebius, Trofimova and colleagues (2025),
*OpenHands Trajectories with Qwen3-Coder-480B-A35B-Instruct*. Source corpora retain
their upstream licenses. This is neither an official SWE-bench protocol run nor
prospective agent evaluation.

```sh
python3 scripts/prepare_replay_cohort.py --inputs ../replay-inputs --exposed ../trace-inputs/nebius/sample.jsonl --output results/my-phase4/cohort.json
python3 scripts/fetch_replay_development.py --inputs ../replay-inputs --cohort results/my-phase4/cohort.json
python3 scripts/resolve_replay_roots.py --inputs ../replay-inputs --cohort results/my-phase4/cohort.json
python3 scripts/reconstruct_development.py --inputs ../replay-inputs --cohort results/my-phase4/cohort.json --output results/my-phase4
python3 -m unittest discover -s tests -v
python3 scripts/verify_replay_results.py
python3 scripts/verify_release.py
```

Use a fresh external input directory for a new download-budget ledger. Reusing one
uses its cached ranges and continues its existing budget. Existing PyArrow is
needed for the downloader only. Certificate verification remains enabled. The
final suite passes **42 tests**; independent checks reconcile all twelve task
records, twenty-one evidence comparisons, the frozen cohort and resource caps.
Historical release manifests require their corresponding historical checkout.
