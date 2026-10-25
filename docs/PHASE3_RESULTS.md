# Phase three: executed-agent traces do not yet justify a new candidate

The registered opportunity gate remains unmet. A bounded sample of real executed
OpenHands trajectories shows little exactly repeated retrieval or reusable numbered
file output under conservative mutation boundaries. We did not implement another
AKI candidate, tune closure admission, or claim that bytes imply time saved.

## Provenance and scope

The protocol was committed as `af80b41` before sampled action values were read.
[Nebius SWE-rebench-OpenHands-Trajectories](https://huggingface.co/datasets/nebius/SWE-rebench-openhands-trajectories/tree/35455389ab51bf5e2306bfd436ef72d0f98bf882)
is pinned to `35455389ab51bf5e2306bfd436ef72d0f98bf882`, licensed
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
Attribution: Maria Trofimova, Anton Shevtsov, Ibragim Badertdinov, Konstantin Pyaev,
Simon Karasik and Alexander Golubev, Nebius (2025), *OpenHands Trajectories with
Qwen3-Coder-480B-A35B-Instruct*. The dataset card identifies OpenHands 0.54.0 and
Qwen3-Coder-480B-A35B-Instruct with actual environment observations. This is an
audit of released executions, not our own model or SWE-bench run.

We selected the lowest 128 hashes of a fixed salt plus trajectory ID from row
group 0 (4,096 rows) of a 67,074-row Parquet file. There are 101 repositories in
the sample. This is a convenience sample of one row group; it does not support
population estimates across all coding agents. All sampled rows are now development
data. No outcome, gold patch, model patch column, or test label selected the cohort
or entered the audit. We retained only tool calls and tool responses locally;
assistant reasoning and system/user prompts were discarded. The original schema
was inspected before action values, and a 150 MiB transfer cap was registered.
119,811,131 bytes were transferred; the local projected sample is 25,239,452 bytes.
Range hashes, row indices, versions and sample hash are in `source_manifest.json`.
Raw trajectories, source text, commands and responses are **not redistributed**.

## Measurements

The sample contains 8,613 calls: 3,594 editor calls (2,213 views, 1,381 writes),
4,424 shell calls, 358 think calls, 126 task-tracker calls and 111 finish calls.
The syntactic read screen accepts 1,207 shell calls; 3,217 remain opaque. No trace
command was executed. The screen rejects expansions, redirections, interpreters,
arbitrary sed programs and unknown commands. It is not a proof of shell purity.

There are 1,784 views with unambiguous numbered-line output, 427 without it
(including directories, errors and empty views), and two missing responses.
The parser excludes partial lines with OpenHands clipping metadata; 42 view
responses contain a clipping marker. The measured denominator is 107,284 numbered
line instances / 3,764,066 UTF-8 content bytes, excluding line numbers and wrappers.

| File-view diagnostic | Every shell clears state | Literal read screen retains state |
|---|---:|---:|
| Exact same-key, same-output repetitions | 0 | 2 |
| 256 KiB exact-result LRU repetitions | 0 | 2 |
| Repeated numbered-line bytes | 50,503 | 93,580 |
| Fraction of numbered-line bytes | 1.34% | 2.49% |
| Overlap bytes beyond exact view keys | 50,503 | 91,503 |
| Views with some overlap beyond exact keys | 166 | 238 |
| Views whose observed numbered lines were all seen | 16 | 45 |
| Maximum result-LRU payload bytes | 57,177 | 65,564 |

The line cache is unlimited and compares observed line hashes after the fact.
“Observed lines all seen” does not establish complete requested-range coverage,
EOF knowledge, or a safely answerable tool call. It is not an achievable cost
upper bound. LRU budgets count only response payload bytes, not Python metadata.
Neither condition has result-cache pressure at 256 KiB. A cost policy cannot be
justified by evictions that this sample does not exhibit.

A separate exact-command audit covers the 1,156 literal read commands that set an
explicit absolute working directory with `cd PATH && ...`. The other 51 syntactic
reads are excluded because ambient cwd is not supplied. There are 1,064 lexical
search calls among these. Unlimited exact caching and a separate 256 KiB LRU both
find **one** same-key, same-output repeat (201 bytes); it is a lexical search.
The eligible shell outputs total 1,251,165 bytes (1,193,908 lexical). The LRU peaks
at 39,688 payload bytes. Opaque execution and any editor write clear this shell
cache. This does not analyze semantic query equivalence or reuse inside the search
engine; near-duplicate searches could behave differently.

All repeat counts are within a trajectory. Repeated attempts at the same issue are
not treated as chronological independent tasks or warmed using later attempts.
No new held-out efficacy comparison was performed because the advancement gate
requires cost evidence that this release does not supply.

## Freshness and measurement limits

Editor writes invalidate the affected file for view accounting; opaque shell
calls invalidate all views. Shell-result accounting invalidates globally on every
write. Histories reset for each trajectory. The strict condition clears on every
shell call. The permissive condition is only a syntactic sensitivity analysis:
aliases, symlinks, background activity and shell state are not reconstructed.
No equality mismatches remain after excluding clipping metadata; that is observed
consistency, **not verified source freshness**. The initial parser treated four
strict-condition and ten permissive-condition clipped-line differences as source
changes. Investigation identified appended tool metadata, the parser was fixed,
and a regression test now rejects incomplete clipped lines. No policy threshold
was fitted to these values.

The Parquet message schema contains roles, content, names and call IDs/arguments;
it has no explicit action start/end/CPU times or before/after source-tree hashes.
Timeout arguments specify a limit, not elapsed time. Test durations appearing in
observations are not retrieval service timings. Byte fractions cannot be converted
to wall-time, API cost, token savings, p50/p95, break-even, or task success.

[Separate SWE-rebench task metadata](https://huggingface.co/datasets/nebius/SWE-rebench/tree/89cdfbab4ab1bd8f5a658bb212d1b63624f4f881)
(CC-BY-4.0, pinned `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`) does expose base commits
and environment setup commits. Initial revisions are therefore available in
principle by joining IDs; they are not inherently unavailable. They do not by
themselves establish intermediate working trees after opaque shell commands.
We did not execute dataset setup/install commands or run unreviewed containers.

## Decision and bounded next evidence requirement

The 20% lifecycle-advantage gate cannot pass on count/byte evidence, and the
observed reuse is insufficient reason to add expensive extraction or packaging.
There is no positive adaptive-indexing claim here. The useful phase-two incremental
maintenance result remains separate and unchanged.

The specific missing artifact is an instrumented retrieval log with monotonic
start/end and CPU times, source-tree identity before each action, returned-evidence
hashes, and complete mutation boundaries. A provider export would avoid model
spending. A bounded first study would use 24 outcome-blind tasks across six
repositories (12 tasks/three repositories development; 12/three held out), fixed
model/scaffold, and include unsuccessful attempts. First replay only audited
read actions on matching snapshots, cap source downloads at 2 GiB and replay at
30 CPU-minutes, and compare disabled reuse, static/incremental source loading,
exact LRU, interval memoization and only then any justified AKI candidate.
No paid API budget is requested until that opportunity survives. Full repair
success would require an additional executable fixed-budget evaluation.

This is an evidence limitation, not a denied operation or a pending approval.
Existing resources completed the independent trace audit; no purchase or new
credential was required. Freshness and task quality remain unmeasured on this
trace release, and no claim of SWE-bench, GraphRAG, or agent repair performance
is made.

## Reproduce and verify

The downloader requires already-installed PyArrow (the core AKI library remains
stdlib-only). Review the script, then use an output directory outside this repo.
On this Mac the system certificate bundle was selected through
`SSL_CERT_FILE=/etc/ssl/cert.pem`; TLS verification was never disabled.

```sh
python3 scripts/fetch_trace_sample.py --output ../trace-inputs/nebius
python3 scripts/audit_agent_traces.py --input ../trace-inputs/nebius/sample.jsonl --output results/my-trace-audit
python3 -m unittest discover -s tests -v
python3 scripts/verify_trace_results.py
python3 scripts/verify_release.py
```

35 tests pass. The independent aggregate verifier reconciles 384 per-trajectory
count records with summaries and checks budgets and count bounds. The latest
release manifest fingerprints code, documentation and metrics. The historical
phase-two manifest is unchanged; verify it from checkout `7c2ac5a`, not against
later documentation edits. Primary phase-two timings retain their original engine
revision `5bd8417`; this phase changes no core Store or Policy behavior.
