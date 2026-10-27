# Offline runtime/root-cause audit — 2026-10-27

No VM/container was started, stopped or created during this audit. No download,
installation, model call, benchmark or held-out action inspection occurred. Inputs
were retained AKI evidence, selected current profile metadata, installed Colima
0.10.3 documentation/help and original deterministic host tests. Both prior
allowances remain closed. This report supersedes no raw measurement.

## Counter failure: established cause

At execution commit `34e3767`, `_workers()` read aggregate reaped-child usage, then
enumerated descendants and read individual counters. If a counter failed, its
exception handler tested PID existence. `ProcessLookupError` caused `continue`.
That silently accepted a missing CPU observation on an assumption: the process's
CPU would eventually appear in an observed parent's reaped-child total. Neither
parent/reaping identity nor that accounting transfer was saved. A descendant can
exit between enumeration and sampling; disappearance alone proves no such transfer.

The retained journal contains two such events:

| Event | Phase | Previous sample | Missing interval information |
|---|---|---|---|
| First worker ESRCH | Work/startup | Present | Last sample preceded failure by 24.010225 ms. |
| Second worker ESRCH | Cleanup | Absent | No observed counter or process start identity. |

The journal can identify these faults; it cannot reconstruct their missing usage.
A later finalized ledger does not repair the evidence gap. The reported
93.688328312 CPU-second charge remains uncertified. It also includes unrelated
container CPU in the guest total. We do not subtract that cost or infer spare budget.

Commit `352625a` removed the silent-disappearance branch. Five additional
deterministic original fault tests now cover known/unknown ESRCH, permission
failure, explicit known-process teardown bounds, blocked work dispatch, cleanup
continuation, final-snapshot failure, persistence of earlier faults despite a good
final sample, and ledger closure preventing a retry. **5/5 focused tests and
120/120 host tests pass**. No new live validation occurred. Failing closed is
established by these tests; complete attribution of rapidly exiting descendants
is still not solved. A future collector must retain parent/start/reap identities
or an explicit conservative bound, never infer a zero-cost disappearance.

The reproducible host mock `python3 scripts/reproduce_worker_exit_fault.py` extracts
only the original project's `_workers` method from `34e3767` and the current file.
With the same missing, previously unobserved worker, the old method returns zero
after recording an error; the current method raises. The [saved output](../results/runtime/worker-exit-fault-reproduction.json)
is a deterministic fault reproduction, not a new CPU measurement.

## Why cleanup did not imply an empty engine

Earlier cleanup was intentionally limited to AKI-owned containers/images. The
first attempt records removal of `aki-task420-attempt1`; the later successful
fixture attempt records owner-checked removal of its created container and tag.
Other attempts never created containers. Those records do not establish that the
shared default engine had no other persistent containers. Stopping a VM is not an
inventory or ownership check for its next startup.

On the cached validation, native engine inspection passed and `docker ps -q`
returned nonempty output before AKI image import. That proves at least one active
container was outside this attempt. The output/identities, labels, creation times,
restart policies and Docker events were not retained. The profile currently
matches its pre-run hash, uses Docker, and has Kubernetes disabled with no explicit
provision-list entries. None of that identifies the active containers.

Two explanations remain consistent with the record: preexisting containers
started with the engine, or another worker started containers during that window.
We cannot assign them to the user, ClauseWeave, Roblox or another project, and
cannot establish that they were leftovers from AKI. No hidden sessions, private
traces, other-project source trees or guest disk contents were inspected to guess
an attribution. Exact ownership requires a later, separately permitted inventory
while its owner has the engine running, not another VM start for this audit.

## Impact: known and unknown

The VM was stopped before the attempt. AKI started it, detected the collision,
then its cleanup stopped the entire default VM. Thus guest services/containers
running during that window were quiesced by VM shutdown. No individual unknown
container was deleted, reconfigured or explicitly stopped, but that does **not**
mean unrelated work was unaffected. We did not record whether another worker
relied on those services, was interrupted, retried or lost unsaved work. Those
impacts are unknown. Returning to the prior stopped state does not prove no
concurrent impact. Four selected saved configuration hashes still match.

The design error was treating ownership of a VM startup as exclusive ownership
of its persistent runtime. An active-container gate detects contamination only
after shared services may have started. Cleanup must never rely on that assumption
again. The existing default profile is unsuitable for an unattended AKI retry.

## Concrete exclusive-runtime option, not authorized execution

Use a **new AKI-only Colima profile and Docker context**, never `default`,
`axiom-simulation` or `rhetorix-lms`. Require a fresh profile identity, explicit
project ownership marker, independent lock and initially empty engine inventory.
Every lifecycle and accounting command must be parameterized by that identity;
remove hard-coded default context/profile/PID paths before execution. Stop/delete
only the owned profile after validating its ownership marker. If an unknown
container appears even there, stop dispatch and seek its owner; do not treat it as
permission for broad engine cleanup.

Installed Colima help confirms support for named profiles, `--disk-image`, explicit
mounts (including disabling defaults), `--template=false`, `--port-forwarder none`,
`--ssh-agent=false`, `--vz-rosetta=false`, `--binfmt=false`, `--kubernetes=false`,
`--activate=false`, `--save-config=false` and `--ssh-config=false`. A proposed new
profile would use two CPUs/two GiB RAM to reduce contention. CPU capacity must be
read back and fed into the collector, replacing its current fixed four-CPU guest
assumption. Mount only the new attempt's control and package directories read-only
into the VM; transfer public sources/image bytes through bounded streams. Do not
mount the project root, old logs/captures, home folder, credentials or other work.
Retain all existing guest noexec/non-root/network-none/capability/resource limits.
Disable templates, SSH-agent forwarding, public addressing and port forwarding.
Read back effective mounts/network/context before any repository code runs.

This changes resource ownership, not permission to weaken confinement. It avoids
starting/stopping the default runtime and grants the guest fewer host paths. It
does add a separate VM disk and needs explicit provisioning/cleanup authorization.
It is **not ready for live approval**: the boot-image path recorded by the current
Lima profile is absent. The retained Python container layers are not a bootable
Colima base. No other verified pristine boot image has been identified. Copying
the existing mutable default VM disk could copy private state and auto-start
containers and is excluded. No broad filesystem hunt or disk mounting was done.

Before any permission request, obtain a pristine base's exact primary-source URL,
digest, compressed size and expanded disk needs through permitted metadata review;
check whether a clean copy is available. Quote a bounded download/disk allowance
only then. Also complete profile parameterization, explicit runtime ownership and
descendant-exit accounting fixtures. The former five-CPU-minute/3-GiB/no-download
approval does not authorize this new provisioning. Do not manufacture a new budget,
change unknown restart policies or try another existing profile. No new approval
is requested by this report.
