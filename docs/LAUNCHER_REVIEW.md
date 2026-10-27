# Offline launcher review and explicit relation semantics — 2026-10-27

**Decision: reject another live Mac attempt at preflight.** A larger CPU
reservation does not establish complete helper containment or shutdown. The new
controller and its fault tests are reviewable, but an executable platform backend
is still missing. No new approval request is justified by these mock results.
The previous image proposal remains historical, not an approved execution plan.

180 host tests pass in 4.065 seconds. No image, VM, container, profile, guest
command, installation, model invocation or real benchmark ran. Installed-tool
help/man pages and pinned public source were inspected read-only. The existing
live ledgers remain closed and unchanged. No unknown runtime was inspected or
controlled, and no real held-out actions were opened.

## Concrete code and adversarial review

`aki/isolated_launcher.py` supplies the ordered controller for preflight, artifact
verification, runtime identity, guest confinement, an original fixture, guest
termination, VM termination, host/helper termination and attempt-only cleanup.
It emits typed **non-executable intents**; it contains no shell, network, subprocess
or guest-command execution shim. Live certification is always false until such a
trusted backend exists. Merely labeling a supplied receipt `live` cannot certify it.

The controller requires a fresh AKI identity and socket, runtime `none`, zero host
mounts/containers, 2 vCPUs and 2 GiB RAM. Artifact observations must match both
digests/size, charge transfer bytes, report actual expansion size under 3 GiB and
reserve compressed image + expanded base + 4-GiB writable root + 256-MiB logs.
Any additional copy must fit the same 8-GiB ceiling. Cumulative resource regressions,
exhaustion, duplicate dispatch and uncertain start retries are rejected.

Before guest work, the receipt contract requires enrollment before execution,
non-root/no capabilities/no-new-privileges, private network namespace without
routes, read-only source, noexec data, no host mounts/devices and denied cgroup
writes. Guest and host final receipts are separate. Both dispatchers must be
sealed, scopes retained for final counters, guest boot and VM identities stable,
and all helper execution accounted for. A stopped VM, missing PID/socket, exit 0
or stop acknowledgment alone is insufficient. Read errors, surviving/reparented
helpers, event loss, late spawns, changed identities and unknown counters fail.
Failure cleanup first requires fresh ownership readback; unrelated/default
resources are never cleanup targets.

The separate adversarial fixture suite tests the protocol from hand-authored
receipts and faults; it does not infer success from the controller's implementation.
A second review pass found and fixed three concrete defects: direct construction
of a default-profile lease bypassing the earlier proposer; an expansion flag
without observed size/full disk reservation; and nested receipt mutation after
acceptance. Tests cover each. Review was performed by the same implementation
agent in a separate pass, **not by an independent human or second agent**. A separate
reviewer may inspect this commit; no external independent review is claimed.

Mocks prove refusal and state transitions under their inputs. They cannot prove
that real OS observations are complete, authentic or available. The strict
capability gate requires an owned kernel domain covering **all host VM/helper
execution before every spawn**, with migration/external launch services excluded.
There is no connected backend supplying that on this Mac. An owned Linux cgroup
is an architectural option, not a currently connected or provisioned executor.

## Why the installed Mac path fails review

Local `limactl --version` reports 2.1.2; `limactl start --help` offers `--foreground`
and `--plain`. The matching pinned source is commit
`2d4314e945cda21ed777fe73a078619f23fc48df`.

- [Foreground startup](https://github.com/lima-vm/lima/blob/2d4314e945cda21ed777fe73a078619f23fc48df/pkg/instance/start.go)
  changes hostagent launch behavior; it is not a kernel descendant-containment
  domain or a lossless process event stream.
- [SSH options](https://github.com/lima-vm/lima/blob/2d4314e945cda21ed777fe73a078619f23fc48df/pkg/sshutil/sshutil.go)
  configure `ControlMaster=auto` and `ControlPersist=yes`.
  [Hostagent routines](https://github.com/lima-vm/lima/blob/2d4314e945cda21ed777fe73a078619f23fc48df/pkg/hostagent/hostagent.go)
  register separate SSH-master cleanup even around plain-mode operation.
- [User-network reconciliation](https://github.com/lima-vm/lima/blob/2d4314e945cda21ed777fe73a078619f23fc48df/pkg/networks/usernet/recoincile.go)
  can start a background helper. This identifies a possible lifecycle branch,
  not evidence that this helper ran in any earlier campaign.
- [VZ shutdown](https://github.com/lima-vm/lima/blob/2d4314e945cda21ed777fe73a078619f23fc48df/pkg/driver/vz/vz_driver_darwin.go)
  waits for VM stop state with a 30-second timeout and can return an error.
  That result does not establish the termination of every host helper.

An isolated project-only Lima home and foreground hostagent could reduce shared
state, but they do not supply the missing lifecycle witness. This review does not
establish that a reliable Mac backend is impossible; it establishes that the
currently available adapter does not prove it. No third-party code was executed.

## CPU reservation review

The earlier 60-CPU-minute figure is arithmetically correct for a 12-logical-CPU
machine over a **known completed** 300-second interval. It is not an enforced
aggregate CPU limit. If helpers outlive the interval, it cannot bound their later
cost. No observed process disappearance should silently complete that interval.

| Candidate | Work + cleanup window | Capacity bound | Review |
|---|---:|---:|---|
| Closed original CPU allowance | at most 25 seconds total | 300 CPU-seconds | Too little headroom; remains closed. |
| Shorter proposed window | 60 + 30 seconds | 1,080 CPU-seconds | Smaller conditional bound; not a proven enforcement mechanism. |
| Prior provisioning proposal | 240 + 60 seconds | 3,600 CPU-seconds | Larger conditional bound; same unresolved shutdown requirement. |

Reducing to 2 vCPUs does not bound host helpers. The locally installed Darwin
`getrlimit(2)` manual describes `RLIMIT_CPU` per process, and `RLIMIT_NPROC` per
user ID. A per-process limit is not an aggregate descendant budget; changing a
shared user's process limit would also be an inappropriate isolation substitute.
No limits or security settings were changed. Linux CPU bandwidth quotas likewise
do not by themselves certify end-to-end host lifecycle cost or bounded teardown.

Consequently **no narrower enforceable aggregate cap was verified**. The controller
reports `cpu_cap_enforced=false`; it refuses the installed Mac backend before
artifact acquisition. Asking for 60 CPU-minutes now would repeat an unresolved
technical gate under a larger allowance. A concrete approval proposal must wait
for a reviewed backend with genuine host-domain/quiescence evidence (or an
explicitly different execution environment and accounting contract). No resource
purchase, additional credential or security expansion is requested.

## Dynamic imports: explicit rejection, not guessed edges

The extractor now declares `python-static-imports-v1`. Query costs, refresh reports
and source-edge evidence expose that scope and `runtime_complete=false`.
`relation_semantics='runtime-complete'` raises `UnsupportedRelations` at Store,
Policy and exact-cache entry points **before cache lookup**. Unknown semantic
modes are rejected too. The default preserves the original static-import operation;
it never certifies complete runtime behavior, even on apparently simple files.

Diagnostic sites cover direct `__import__`, `importlib.import_module`, and common
import aliases. They are hints, not a complete detector. Aliasing a loader through
another variable, import hooks, generated code and arbitrary execution can remain
unrecognized. An empty diagnostic list is explicitly not a completeness certificate.
No dynamic expression is executed by the extractor and no speculative edge is
inserted. Extractor version v4 invalidates old materializations and persists the
diagnostics across reopen/no-op refresh.

Independent original fixtures record actual requested module names using closed
stub import functions; they load no external code/files. Those calls request a
dependency absent from the static graph, so the separate truth oracle disagrees
with an otherwise perfectly agreeing set of caches. Tests cover aliased forms,
unknown indirection, all seven policies, cache-hit rejection, diagnostic refresh,
and old-extractor invalidation. This closes the false-completeness API claim; it
does not add runtime dependency resolution or prove repair success.

```sh
python3 -m unittest discover -s tests -p 'test_isolated_launcher.py' -v
python3 -m unittest discover -s tests -p 'test_relation_semantics.py' -v
python3 -m unittest discover -s tests -v
python3 scripts/verify_release.py
```

The full suite exercises existing static retrieval/mutation comparisons after
the patch. Previous benchmark and tiny fixture timings remain tied to their
recorded commits; no new performance experiment, scientific holdout or agent task
result is claimed. The research conclusion remains useful incremental evidence
maintenance with adaptive task benefit unproved.
