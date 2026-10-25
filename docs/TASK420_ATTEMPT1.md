# Task 420: first bounded setup attempt

**Outcome: compatibility gate failed; no prospective agent pilot ran.** This is
a harness failure, not a retrieval/repair result or proof that Python 3.5 package
dependencies are incompatible. The [structured record](../results/runtime/task420-attempt1.json)
and [historical original controls](../research/task420-attempt1/README.md) preserve
the result. No second compatibility attempt was made.

## What actually happened

Staged the approved arm64 image and 29 dependency artifacts with exact sizes and
SHA-256 checks. Compressed layers were additionally checked against the original
uncompressed layer hashes before import. Native-only Colima started in 17.971 s,
with the three saved host configurations unchanged.

Docker 29's image store assigned a converted manifest identity. Two initial
client-side selectors incorrectly assumed the old configuration-ID representation
and full legacy config fields. Read-only inspection showed unchanged layers;
the original configuration blob was then recovered from a local export and its
exact hash verified. No image was downloaded or loaded a second time. Preserve
both the registry manifest and converted local manifest in provenance.

One non-root container was created with network disabled, all capabilities dropped,
no-new-privileges, read-only root, one CPU, 1 GiB memory/no additional swap, 64 PIDs,
and bounded environment/workspace/scratch tmpfs. Only the approved package and
original control directories were mounted read-only; no private directory or
Docker socket was mounted. Docker's archive source-copy path failed before writing
anything. After verifying the same container's workspace was empty and writable,
a bounded non-root JSON helper copied 82 public base files into its tmpfs.

The first compatibility command was:

```text
/usr/local/bin/python3 -m venv --copies /env
```

It failed with permission denied. Read-only diagnosis found a copied Python file
with mode 0755 and `/env` mounted `noexec`. The virtual-environment bootstrap must
execute that copied interpreter, which the mount prevents. Docker supplied this
flag even though the proposed mount options did not spell it out. No pip install,
repository setup, test collection, task tests, model call or pilot operation followed.
The recorder/backend integration therefore remains unvalidated for real tasks.

## Actual usage and limits

| Measure | Recorded value | Limit / interpretation |
|---|---:|---|
| Transferred artifact/metadata payload | 329,867,946 bytes (314.59 MiB) | 512 MiB; no second fetch |
| Expanded image layers | 840,434,688 bytes | Within 1 GiB staging allocation |
| Conservatively accounted disk at import | 2,015,178,255 bytes (1.88 GiB) | 3 GiB; includes an allowance for compressed image content |
| Staging host CPU / wall | 4.885 s / 21.797 s | Measured, not a model estimate |
| Host setup CPU including allowance | 55.846 s | Includes a conservative 50 s allowance for earlier orchestration |
| Guest busy CPU since boot at failed check | 65.330 s | Includes guest boot/daemon work, not only this container |
| Guest busy CPU before cleanup | 67.490 s | Shutdown CPU after VM termination was not measured |
| Elapsed staging-to-compatibility failure | 541.897 s | Below 600 s proposal setup-wall ceiling |
| Elapsed staging-to-runtime shutdown | 618.473 s | **18.473 s beyond** that ceiling during diagnosis/cleanup |
| Compatibility / pilot attempts | 1 / 0 | Stop after first failed compatibility check |

The accounted CPU at failure is about 121.2 s against the 300 s allowance, but it
is not a complete measured final lifecycle CPU figure: some host work uses an
allowance and guest shutdown was not sampled. Transfer counts describe consumed
HTTP payload bytes, not TLS/header/network-interface traffic. Disk is conservative
accounting rather than a continuous filesystem high-water measurement. Do not
report these as fully instrumented agent costs or claim every timing limit passed.

The setup-wall cleanup overrun is a real harness deficiency. A future attempt needs
a reserved teardown interval and one outer watchdog spanning transfer, setup,
diagnosis and cleanup; the check must not live only inside the setup loop.

## Cleanup and next engineering step

Removed the single named container and newly imported image successfully. Deleted
844,838,739 bytes of task-local staged image/package files. Colima is confirmed
stopped. Saved Colima, SSH and Docker configuration hashes still match their
pre-start values. No global image/volume prune or unrelated project change occurred.
Raw runtime logs remain private; only original controls and sanitized measurements
are published. Held-out actions and the frozen cohort are unchanged.

Added a small mount preflight check and four stdlib regression tests **after** this
attempt. They reject a copied interpreter on `noexec`, distinguish path prefixes,
handle nested mounts and fail closed when mount coverage is missing. They do not
reproduce a successful isolated setup or certify the live adapter.

A conservative future implementation can keep all writable tmpfs non-executable:
invoke the already verified base interpreter and install pinned Python libraries
into a data-only target directory, with explicit import paths and fixed CLI module
dispatch. This is an unexecuted design adjustment, not a tested fix. Validate the
mount/transport/CPU-accounting controls on owned fixtures before another bounded
runtime attempt; do not make the entire writable workspace executable. The one
authorized attempt is closed, so no retry, installation or model run followed
the failed gate.
