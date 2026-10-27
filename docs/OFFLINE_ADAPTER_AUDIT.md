# Accounting contract and adversarial cache audit — 2026-10-27

**159 host tests pass. No VM, container, profile, binary download, installation,
benchmark or model invocation ran.** The two live campaigns remain closed with
unchanged ledger hashes. This release implements a testable platform adapter and
stronger evaluation checks; it does not certify a working Mac runtime.

## What changed and what the tests establish

`aki/platform_accounting.py` integrates the existing subtree ledger and cgroup-v2
reader with explicit enrollment, dispatch, seal, owned-stop and final-read states.
Unsupported platforms/backends fail before any callback. Darwin PID polling is
explicitly unsupported for complete descendant accounting. The adapter requires a
bound scope identity and a preflight receipt establishing ownership, domain type,
atomic enrollment before child execution, denied migration/external dispatch and
retention of the counter until its final read. These inputs must come from a
reviewed launcher; supplying booleans or a receipt hash does not discover or prove
the underlying OS facts. There is no such live launcher wired on this Mac yet.

Original host mocks/filesystem fixtures exercise vanished children, short-lived
work between samples, reparenting without cgroup migration, a surviving descendant
after parent exit, missing/reset/replaced domains, read failures and failed stop
or seal acknowledgments. Faults remain failures even if a later sample is empty.
Live descendants yield a pending result, not zero cost. Scope deletion is allowed
only after closed dispatch and a successful final empty-domain read. No cleanup
is executed by this adapter. Its successful receipt covers the domain, not the
host, VM, transport or observer. The reader now checks identity again after the
last event read. These tests simulate the kernel contract; they do not validate it
against a running Linux kernel or establish a universal termination deadline.

The [kernel's cgroup-v2 documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html)
specifies inherited membership on fork, hierarchical CPU statistics and recursive
populated state. Process reparenting is distinct from migration between cgroups.
Its `cgroup.kill` interface handles concurrent forks but is not a promise that all
work terminates within a chosen deadline. A trusted, bounded supervisor must keep
the domain and final counter available. Guest accounting cannot substitute for
Mac startup/shutdown accounting.

The ownership preflight now supports `runtime=none` with **zero host mounts and
zero container state**. It still rejects preexisting/default profiles, unrelated
ownership and foreign resources. Malformed inventory IDs fail explicitly. These
are observation-validation functions, not an OS authority or profile launcher.
The old shared-runtime driver remains disabled.

## Evaluation defects challenged

The previous fixture oracle used the implementation parser. Agreement with a fresh
rebuild could therefore hide a shared extraction error. The evaluator now accepts
complete hand-authored answer/path/edge expectations, kept outside policy inputs.
`aki/evidence_audit.py` checks those edges and current span bytes/hashes without
calling the parser. Missing relationships are correctness failures; an empty
answer does not automatically become a stale-evidence failure.

Eight adversarial tests exercise all seven matched policies through new incoming
edges outside the old footprint, unresolved imports becoming resolvable, added
package initializers, same-content file moves, deletion, restored branches, shifted
import evidence and content growth that changes token packing. Tests explicitly
reject old revision requests. Injected wrong answers, extra stale edges, stale span
text and stale file hashes are detected. A dynamic-import fixture deliberately
fails the independent relationship expectation while all implementations return
the same empty closure. Static AST import extraction is still incomplete for
runtime Python behavior; these tests do not repair that limitation.

Added `exact_lru`, a durable exact-result comparator keyed by scope, extractor,
tree revision, root, operation, text and token budget. It uses the same incremental
base Store, SQLite FULL durability, batched admission/eviction and logical-byte cap.
Any changed tree invalidates its packed results; a no-op tree preserves them. This
is a conservative versioned cache, not semantic caching or selective result repair.
Key bytes count against capacity. Restart clears entries whose admission state was
not adopted, matching the existing session policy. Tests cover key separation,
current packing, eviction, restart and byte accounting. No admission thresholds
were tuned, and no real held-out actions were opened.

## Recorded fixture rerun and limits

The affected sealed harness was run once with all seven development conditions:

```sh
python3 scripts/task_benefit_fixture.py --out results/instrumentation/task-benefit-fixture-v3-20261027
python3 -m unittest discover -s tests -v
python3 scripts/verify_release.py
```

[Original fixture inputs and raw outputs](../results/instrumentation/task-benefit-fixture-v3-20261027/)
contain 21 development and nine holdout condition-attempts, 120 query operations,
all correct/fresh under their declared fixture expectations. Frequency was again
the fastest observed simple development cache: 32.061 ms total, versus 38.240 ms
for exact-result LRU. Disabled was 28.738 ms; AKI was 30.243 ms. The selected-cache
holdout totals were 32.181 ms frequency, 29.383 ms disabled and 27.904 ms AKI.
All three had three expected abstentions. Real task attempts are zero; resolved
metrics are null. The fixture selection and every raw run are retained, including
the earlier v1/v2 results and their old code revisions.

These small public synthetic cases share simple shapes. Changes in the ordering
of millisecond totals across runs illustrate why they are plumbing checks, not
evidence of an adaptive win. The new adversarial cases are correctness tests, not
a fresh held-out scientific dataset. Exact-result caching is now included, but
the baseline set is not exhaustive: no W-TinyLFU, semantic cache, language-server
index or real repair agent is claimed. The earlier negative lifecycle findings
remain the research conclusion. A useful next agent candidate still requires
prospective operation costs and demonstrable opportunity beyond strong caches.

## Concrete provisioning scope, not current authorization

The smallest useful next live check is **one original accounting fixture in a
fresh native `runtime=none` Colima VM**, with no Docker engine, legacy Python,
benchmark repository, model or existing OCI-cache import. This tests the missing
Linux counter/containment contract before attempting task 420 again. It does not
establish the compatibility of task 420 or its recorder/container adapter.

Verified public metadata is saved in
[isolated-image-proposal.json](../results/runtime/isolated-image-proposal.json):

- Installed Colima 0.10.3 source commit `00f6c297e92a82c04a4ab507db0a61435650d7e8`
  [pins the arm64 `none` image and SHA-512](https://github.com/abiosoft/colima/blob/00f6c297e92a82c04a4ab507db0a61435650d7e8/embedded/images/images.txt).
- [Official colima-core v0.10.4 asset metadata](https://api.github.com/repos/abiosoft/colima-core/releases/tags/v0.10.4)
  gives asset 437242088, `ubuntu-24.04-minimal-cloudimg-arm64-none.raw.gz`,
  **209,768,031 bytes (200.05 MiB)** and SHA-256
  `1acf2b1740a27120ebdce156106d286a2b21dbce67defa33e64594ef2b29ca5d`.
  The release is not marked immutable; verify both pinned digests and exact size.
- [The image build source](https://github.com/abiosoft/colima-core/blob/078088ada3cce8835b8c42710ab44d17a935b195/scripts/image.sh)
  provisions Ubuntu with Python-related dependencies. Its upstream Ubuntu URL and
  package repositories are mutable, so this is release provenance, not a hermetic
  build attestation. The binary has not been downloaded, scanned or boot-verified
  here. Packaged emulation binaries must never be activated; native-only handlers
  still need readback. Do not run its privileged image-build scripts.

Proposed **new**, cumulative caps (none granted or spent):

| Resource | Cap and basis |
|---|---|
| Download | 256 MiB; one 200.05-MiB pinned compressed image, no package/tool downloads. |
| Additional allocated disk | 8 GiB; stream expansion capped at 3 GiB before any boot, one at-most-4-GiB writable root, compressed image and 256-MiB metadata/log reserve. No runtime data disk. Expanded size is unknown, so exceeding the expansion gate stops setup. Extra copies would need to fit this same cap. |
| VM | One fresh AKI-only profile, native arm64/VZ, 2 vCPUs, 2 GiB RAM, no mounts, templates, Docker, Kubernetes, emulation, host-agent forwarding, public address or automatic port forwarding. No default profile/context/config changes. |
| Wall time | At most 240 seconds from acquisition start through work, then 60 seconds reserved for owned teardown/accounting. Slow transfer/startup stops progression. |
| CPU bound | **3,600 CPU-seconds (60 CPU-minutes)**, a conservative 12-logical-CPU × 300-second whole-machine capacity reservation. This is not predicted or measured CPU usage, and guest CPU is not added again. |
| Work | Only original short-lived/reparented-child accounting fixtures and matching recorder hashes, non-root in a private guest network namespace with no network route, read-only source/noexec data. No arbitrary trace commands or third-party project code. |
| Cleanup | Only that attempt's profile, domain, processes and new files after ownership readback. Preserve the old cache, records, unrelated profiles and default runtime. |

The old five-CPU-minute cap buys at most 25 wall seconds under this safe capacity
method; the earlier 19.283-second startup left insufficient validation/teardown
headroom. `capacity_plan(12,240,60,budget_cpu_s=3600)` tests the new reservation.
It charges all machine CPU conservatively and subtracts no unrelated worker cost.
This is intentionally much larger than expected fixture work; it avoids pretending
that missing descendant samples are measurements. The image/disk limits and time
limits are abort ceilings, not predictions that provisioning will succeed.

**Remaining prerequisite:** a reviewed exclusive live launcher must produce actual
mount/cgroup/identity receipts, enroll before forks, deny scope escape, close the
only dispatcher and prove final owned-runtime shutdown. Linux scope counters alone
do not prove that every Mac VM/helper process has ended. A whole-machine capacity
bound covers hidden work during the observation interval, but cannot certify
future CPU after an unproven shutdown. An OS hang or stop failure must therefore
remain an uncertified failed run, with no new work dispatched and no claim that
the cap held. The current adapter intentionally cannot manufacture that proof.

The proposal requires new approval for the clean image, fresh profile/guest-only
control setup, larger disk and capacity reservation after launcher review. It is
not an executable retry command or an invitation to reuse a closed allowance. If
complete Mac shutdown evidence cannot be obtained, the supported alternative is
an explicitly authorized Linux executor with a trusted cgroup lifecycle supervisor;
that capability is not currently connected. No purchases or credentials are
requested. ClauseWeave/Roblox dependence on the previously stopped shared service
remains unknown from permitted AKI records; this audit adds no evidence of impact.
