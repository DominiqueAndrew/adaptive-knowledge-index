# Targeted Codex/Colima readiness check

This follow-up narrows the capability gap; it is not a prospective agent evaluation.
No existing Codex session was resumed or inspected, no benchmark source/setup/test
code executed, and no credential or paid API account was created.

## Model side: existing authenticated transport works

The Codex executable is bundled with the installed ChatGPT application rather than
on the shell PATH:

```sh
"/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex" --version
"/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex" login status
```

Observed version: `0.163.0-alpha.10.2`. The status check reports an existing ChatGPT
login rather than API-key authentication. Only authentication-mode booleans were
reported; tokens/account details were not printed or copied.

One bounded, ephemeral connectivity probe used a constant project-owned prompt,
a JSON schema requesting `{"ready":true}`, and the recorder on an original fixture.
The CLI completed with exit code 0 and the expected JSON. Its emitted item list
contained only `agent_message`, with no tool-call events. Reported usage was
15,889 input tokens / 15 output tokens / zero reasoning-output tokens. The CLI's
fixed context is substantial even for a tiny request; do not repeat connectivity
probes or treat this as a cost-efficient per-action agent loop without measuring it.

Relevant invocation controls were:

```sh
CODEX_CLI="/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
"$CODEX_CLI" exec --ephemeral --ignore-user-config --sandbox read-only \
  --skip-git-repo-check --json --color never \
  --disable apps --disable shell_tool --disable unified_exec \
  --disable multi_agent --disable memories --disable hooks \
  --disable skill_search --disable skill_mcp_dependency_install \
  --disable shell_snapshot --disable in_app_browser \
  --cd /path/to/original-fixture --output-schema /path/to/schema.json -
```

The fixed probe was supplied on stdin. No dangerous sandbox/approval bypass flag
or session-resume option was used. Existing auth was reused; invocation overrides
did not persist new model/tool settings. The matched recording verified one complete
operation, two source boundaries and four journal events. Captures, schema and
model output stayed local under ignored scratch storage and are not published.
This verifies the model transport on a trusted fixture; it does not validate a
complete adapter against adversarial repository content or implement a repair agent.

## Runtime side: stopped Colima, not Docker Desktop

The installed Docker CLI's active context is `colima`. Its existing default profile
reports `Stopped`, uses the Docker runtime and has an existing VM disk. No Docker
Desktop or OrbStack app bundle was found in the standard Applications locations.
Therefore there is no installed Docker GUI app to open for this task.

Colima's help supports the following resume command while leaving saved host
configuration, context selection and generated SSH configuration unchanged:

```sh
colima start --save-config=false --activate=false --ssh-config=false
docker --context colima version
```

**At this original checkpoint, this command was prepared, not executed.** A later
bounded attempt and confirmed shutdown are recorded in
[the resume check](COLIMA_RESUME_CHECK.md). Starting this VM invokes its configured
guest provisioning, including system/group/mount and filesystem-resize operations.
That is broader than the permission to launch an ordinary installed app without
settings changes. No package download/install commands were found by the narrow
configuration check, but this was not a proof that all runtime startup dependencies
are already satisfied. Do not silently authorize installation or permission prompts.

The original next step was to start this existing Colima profile, or explicitly
authorize its normal guest boot/provisioning under the command above. The resume
check supersedes that status and records the narrower remaining boundary. Stop if startup
requires a download, installation, new permission or configuration change. A new
Docker Desktop installation or new model API credential is not the requested step.
A read-only process-list attempt was sandbox-blocked; installed-bundle inspection
provided the required CLI information instead, without retrying that operation.

## Smallest safe next pilot

The first frozen task is `Backblaze__B2_Command_Line_Tool-420`; its public base
snapshot and cohort metadata are already available from phase four. Keep the
[prospective protocol](PROSPECTIVE_CAPTURE_PROTOCOL.md) unchanged and the held-out
actions unopened.

After the existing runtime is reachable:

1. Inspect/review the exact task image and adapter before running repository code;
   pin the image digest. A running daemon alone does not establish safe isolation.
2. Give the task container only its public source, bounded temporary storage and
   the capture interface. Do not mount owner home directories, model credentials,
   Docker socket or unrelated projects into untrusted task execution.
3. Use the existing ChatGPT-authenticated CLI as the planner only through a reviewed
   adapter with validated action dispatch. Preserve approvals/sandboxing; never
   infer that the trusted connectivity probe makes arbitrary host tools safe.
4. Route every source read/edit/setup/test through the recorder and isolated backend.
   Backend CPU/wall times and synchronized source state must be available. Enforce
   the frozen 12-operation/30-seconds-per-operation/10-minute-task ceilings.
5. Verify every recorded boundary and source delta before considering the next task.
   Missing coverage, unsupported operations or source instability stop the pilot.

Model access is now verified using existing authorized resources. A full prospective
run is still unexecuted: runtime resume/provisioning and a reviewed live tool-dispatch
integration remain. No new spending is requested, and no adaptive benefit is claimed.
