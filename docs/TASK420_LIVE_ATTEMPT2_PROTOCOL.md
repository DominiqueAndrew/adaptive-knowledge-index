# Corrected single live attempt: frozen execution protocol

Recorded before this attempt starts. The previous attempt remains closed and its
failure unchanged. This run uses the same task, image manifest, 29 artifact pins,
source commit and resource/security bounds in `TASK420_SETUP_PROPOSAL.md`, with
the noexec/accounting repairs in `TASK420_SETUP_REPAIR.md`.

The new bridge is explicit opt-in: `python3 -I scripts/run_task420_attempt.py
--execute-approved-single-attempt`. This command performs real external actions
and requires the separate live authorization. It creates a unique ignored scratch
directory and does not reuse a partial attempt. Host tests do not invoke it.

Sequence: verified staging; native VM startup; one image import and raw-config /
layer verification; exact container configuration checks; original live recorder
fixture; public source transfer and offline compatibility checks; conditional
task-420 instrumentation pilot; ownership-scoped cleanup and confirmed shutdown.
No stage is retried automatically. The outer supervisor remains active throughout.

The whole attempt uses a deliberately stricter common **600 wall-second / 300
CPU-second** envelope, including any pilot and teardown. Work stops by 510 seconds
or 180 conservatively accounted CPU seconds, reserving 90 wall seconds and 120 CPU
seconds for cleanup. Downloads are at most 512 MiB, including official problem-text
metadata; disk reservations are at most 3 GiB. Host/VM/guest CPU counters overlap,
so their sum is a conservative bound, not additive physical cost. Startup and
unsampled tails receive capacity bounds. The guest counter covers all four existing
VM CPUs; the task container is limited to one. No saved VM settings change.

Only the already frozen development task's `instance_id`, `repo`, `base_commit`
and `problem_statement` are selected from the pinned SWE-rebench dataset. Existing
inert range-cache blocks may be reused. No historical trajectory, solution patch,
test patch, outcome or held-out action is supplied to the planner. Metadata-row
projection is not a benchmark execution or gold-label use.

Fixture gate: four original operations (read, edit, execute an assertion, read),
complete pre/post source mirrors, valid recorder chain/deltas/output hashes and
actual guest operation CPU/wall observations. The fixture executes before package
installation. Compatibility then requires all eight declared steps, including
dependency checks, the actual B2 entrypoint and test collection. Failure stops
progression and triggers teardown.

If gates pass, a tool-disabled, ephemeral existing ChatGPT-authenticated Codex CLI
acts as the planner: fixed `gpt-6-astra`, low reasoning, at most three calls of
45 seconds each, at most four actions per reply and twelve dispatched source
operations total. No API key is accepted. The host adapter allows only bounded
reads, single-match literal edits and the reviewed offline pytest-collection
command. No arbitrary shell, network or model tool dispatch is allowed. Planner
tools, apps, hooks, memories and web search are disabled. Unexpected tool events
or incomplete usage reporting stop the pilot. Model use and all operation costs
are recorded; successful collection is not a repaired-task success.

All public-source evidence stays in private local capture storage. Reported backend
timings cover guest operation bodies; full host service time also includes Docker
dispatch and snapshot transfer, and the lifecycle CPU ledger includes process
startup. Keep these scopes distinct. The pilot coverage criterion remains at least
three source reads and one execution/mutation boundary with verified recording.
Failure is reported, not replaced with synthetic reads or another task.

Publish only original code, safe numeric measurements, hashes and conclusions.
No captures, problem text, model prompts/replies, tokens, owner paths or private
runtime logs enter the public repository. Passing this pilot would establish
instrumentation feasibility only, not AKI benefit, novelty, or repair efficacy.
