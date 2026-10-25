# One bounded setup option for task 420

**Proposal only, 2026-10-25.** This pass read public manifests, JSON package
metadata and build declarations. It did not fetch image layers or package
artifacts, restart the VM, install/build/run software, inspect held-out actions,
or make a model call. No alternate task was selected. The earlier absence of a
prebuilt *task* image remains true; this review identifies a feasible base from
which to assemble a declared development environment.

## Recommendation and verified facts

Keep `Backblaze__B2_Command_Line_Tool-420`. Use the Docker Official Images
`library/python:3.5.10-buster` native arm64 image at this immutable manifest:

```text
docker.io/library/python@sha256:fe70a4d5ac4049e60fddce443c417c637f63d90bf97f1a597e4ac13114771b43
```

[Docker Hub tag metadata](https://hub.docker.com/v2/repositories/library/python/tags/3.5.10-buster)
lists arm64/v8. The registry manifest and configuration JSON were independently
retrieved and matched their SHA-256 identities. The manifest lists **325,456,469
compressed layer bytes**. Its config declares Python 3.5.10 and pip 20.2.3, with
no entrypoint, exposed ports or volumes; default user is root and must be overridden.
Build history includes GCC. The corresponding
[historical Dockerfile](https://github.com/docker-library/python/blob/c85a8c6d27b6121ae196baae7d7e6353dc934991/3.5/buster/Dockerfile)
uses `buildpack-deps:buster`. Pull the finished immutable image; do not rerun that
old Dockerfile or contact retired Debian package mirrors. Verify Python/GCC versions
inside the isolated runtime before relying on the build metadata.

The [pinned task record](../results/runtime/task420-image-review.json) specifies
Python 3.5, GCC and Python dependencies. A metadata-selected candidate lock contains
**29 artifacts totaling 4,394,723 bytes**: 28 platform-independent Python wheels
and Arrow 0.12.0's 89,600-byte source archive. Source/build hashes and URLs are in
[the structured proposal](../results/runtime/task420-setup-proposal.json). The
chosen pytest 6.1.2 explicitly [supports Python 3.5](https://pypi.org/project/pytest/6.1.2/).
Arrow's [release setup declaration](https://github.com/arrow-py/arrow/blob/0.12.0/setup.py)
lists Python 3.5 and `python-dateutil` on Python 3. The proposed base already includes
the requested compiler, so no new apt/package-manager operation is proposed.

The task's runtime/setup/test requirements and available PyPI `Requires-Dist`
markers were checked against the candidate pins for CPython 3.5/Linux. No declared
conflict was found. Eight packages omit a machine-readable `Requires-Python` field;
legacy missing metadata is not compatibility proof. No resolver, installation,
imports, tests or agent attempt has run. These pins freeze a proposed instrumentation
environment, not the unknown historical environment used to produce a trajectory
or an official SWE-rebench score. Do not tune pins using task outcomes.

## Trust and isolation

The base comes from Docker's `library/python` namespace; package artifacts come
from the PyPI release records and `files.pythonhosted.org`. Hashes prevent silent
version drift but do not prove code safety. The old image has no modern attestation
verified here. Python 3.5 is [end-of-life](https://www.python.org/downloads/release/python-3510/),
so restrict it to this disposable, offline compatibility experiment.

Only a bounded host-side downloader may access the public registry or approved
PyPI artifact URLs. It must verify expected byte counts/hashes, count retries
against the transfer cap, and never execute downloaded files on macOS. Registry
access may use an anonymous short-lived bearer in memory; no login or persistent
credential is needed. Load the verified local image archive into the existing VM.

Review downloaded metadata/entrypoints before execution. Assemble a virtual
environment in a disposable container with `--network=none`, a numeric non-root
user, `--cap-drop=ALL`, `no-new-privileges`, default seccomp, a read-only root,
one CPU, 1 GiB RAM and 64 PIDs. Mount only the approved artifact directory read-only.
Install pinned artifacts offline, without dependency discovery/build isolation or
package-index access. Arrow's legacy setup is the sole external source build;
inspect its downloaded archive before executing it. Use bounded tmpfs for the
environment and scratch. Export only validated, bounded environment files to
task-local storage and hash the result; later tool containers mount it read-only.

For the pilot, copy the already-available public base source into bounded container
tmpfs. Run only reviewed setup/unit-test operations. No cloud-storage credentials,
network-dependent integration tests, owner-home mounts, Docker socket, unrelated
projects, privileged mode or host-writable bind mounts are allowed. Copy source
snapshots/deltas out through a checked, size-limited channel; do not extract arbitrary
container archives onto the host. Every source operation must pass through the
validated recorder adapter, with quiescent process boundaries and measured backend
CPU/wall time. Missing interception or metrics stops the attempt.

The complete runtime identity is the base manifest plus dependency/artifact hashes,
constructed environment tree hash, adapter version and public source revision.
Keep source base `15a60ad1c71b75366061e4f742ef52eb9dcc23e7` distinct from environment-
setup commit `ee2339bd21d21d6140936d58597957250a33fc26`. Do not silently execute the
latter's source as the task base. No historical solution, task outcome or held-out
action enters the model/policy. Model credentials stay outside task containers.

## Bounds, estimates and stop conditions

| Quantity | Evidence or proposed bound |
|---|---|
| Base plus candidate packages | **329,851,192 bytes / 314.57 MiB**, from manifests/metadata; artifact bodies not fetched |
| New transfer cap for this option | **512 MiB**, including metadata, retries and packages; within the existing phase-wide 2 GiB ceiling |
| New disk use | **1.5–2.5 GiB estimate**, **3 GiB stop ceiling**; expanded layer sizes are not known from compressed metadata |
| Environment/task/scratch tmpfs | **256 / 64 / 128 MiB** ceilings respectively |
| Setup CPU | **1–3 CPU-minute estimate**, **5 CPU-minute stop ceiling**; no native compilation is expected from the proposed Python set |
| Setup wall time | **2–8 minutes estimate** excluding slow transfer, **10-minute setup ceiling** |
| Pilot | Existing **12 operations**, **30 seconds per operation**, **10 minutes wall**; phase-wide **30 CPU-minute** ceiling remains |
| New monetary cost | **No paid API/compute purchase**; local resources and existing model subscription only |

Estimates are not measurements. The image's layer bodies might be unavailable even
though its manifest exists. Disk expansion, old dependency compatibility and the
adapter remain untested. Stop on unavailable/hash-mismatched artifacts, unexpected
dependencies, incompatible wheels/source, installation requiring a network or
extra package, resource-limit failures, or inability to enforce isolation/recording.
Do not add apt, switch architecture/task, weaken isolation or increase limits as
an automatic fallback. Verify imports, `pip check`, CLI entrypoints and one reviewed
unit-test collection before spending a model call. Setup failures remain reported
preflight failures, not agent task failures.

Delete only containers, temp volumes, exported environments and newly loaded image
objects created for this attempt, identified by recorded IDs/labels; never run a
global prune. Stop Colima afterward, preserve saved settings, keep reviewed local
captures under the recorder's retention policy, and publish only safe original
code, metadata/hashes and aggregate results. The CPU/disk/transfer allowance must
include cleanup and failed attempts. No new host package or security setting is needed.

## Consolidated approval scope

The smallest useful approval is for **one task-420 setup attempt** using the exact
native image and pinned candidate artifact list: restart the existing VM with
`--binfmt=false --save-config=false --activate=false --ssh-config=false`; fetch/load
only those artifacts within 512 MiB; inspect them; assemble/install the environment
offline inside the restricted disposable container; run the bounded compatibility
checks; and clean up. Conditional on those checks and fixture-tested recording,
continue the already planned one-task instrumentation pilot under its existing
limits and existing model access. No task substitution, paid service, additional
package, host install, permanent credential or security change is included.

No setup action is authorized merely by this document. If approved, the adapter
must still be implemented/reviewed/tested before real task actions. Keep the frozen
three-task cohort and acceptance criteria; this option does not promise a passing
setup or a successful repair. Because a plausible bounded native option exists,
other development tasks were not inspected or substituted during this pass.
