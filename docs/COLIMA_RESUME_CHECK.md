# Colima resume check — 2026-10-25

This is runtime-readiness evidence, not a benchmark or prospective agent run.
The frozen first task remains `Backblaze__B2_Command_Line_Tool-420`. No task
container, repository setup/test code, new agent attempt or held-out action ran.

This historical checkpoint is superseded by the successful
[native-only startup and image review](NATIVE_PILOT_PREFLIGHT.md). The original
attempt below is preserved; native startup permission is no longer the blocker.

## Observed outcome

The existing Colima 0.10.3 installation (commit
`00f6c297e92a82c04a4ab507db0a61435650d7e8`) was started once with:

```sh
colima start --save-config=false --activate=false --ssh-config=false
```

A bounded local guard watched startup output and interrupted on download,
installation or new-permission indications. The existing VM reached its ready
message, then emitted `installing: 386 OK` and `installing: amd64 OK`. The guard
interrupted startup after 13.888 seconds (process exit -2). These success messages
had already been emitted: the guard did not prevent those guest operations.
No download or new-permission prompt appears in the captured startup log. That
log is not an exhaustive network/system audit.

Colima initially reported a broken profile after the interrupted command, but a
separate read-only readiness check reached Docker Engine 29.5.2 on linux/arm64.
The VM was then deliberately shut down with `colima stop`, which completed with
exit 0. A subsequent profile check confirmed `Stopped`. The startup was not retried.
This leaves no benchmark container running.

Hashes of saved Colima, SSH and Docker configuration were equal before and after
the guarded startup. The VM's normal boot/disk/system activity is not claimed to
have been rolled back. Raw runtime logs, configuration fingerprints and local
paths remain in ignored private scratch storage; none are published.

## What the installation messages mean

The [source at the installed Colima commit](https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/core/core.go)
checks for an existing guest `binfmt` executable, then calls it with `--install`
for 386 and the foreign architecture. The
[matching VM startup code](https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/environment/vm/lima/lima.go)
invokes that function when binfmt is enabled. This supports interpreting the two
messages as guest emulation-handler registration, rather than evidence of a new
package download. It does not establish every guest side effect from this log.

Installed help also documents `--binfmt=false` as a way to disable foreign-
architecture emulation for a start. That alternative was inspected, not executed;
using it would require a native arm64-compatible task runtime. Do not assume the
frozen task's published image supports that architecture or change its environment
silently.

## Remaining boundary

The explicit stop-on-installation boundary was honored by interrupting and then
stopping the VM, rather than silently exempting this `--install` operation. Before
another startup, resolve whether boot-time registration using the existing guest
binary is permitted, or use an explicitly accepted native-only startup. This is
not a request for a new credential, paid API, package installation or purchase.

After runtime readiness, the task image still needs digest/architecture/size and
isolation review, and the live adapter still needs validated action dispatch and
backend CPU/wall accounting. The existing tool-disabled Codex connectivity probe
does not replace those checks. Keep the [frozen prospective protocol](PROSPECTIVE_CAPTURE_PROTOCOL.md),
resource ceilings and held-out partition unchanged. There is no pilot evidence
beyond runtime readiness, and no adaptive-benefit result from this follow-up.
