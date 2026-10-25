# Corrected live attempt: stopped at TLS preflight

One authorized attempt ran at frozen commit `238d6b5`. Its first request to the
public Docker registry authentication endpoint failed certificate verification.
No artifact response body was downloaded. No VM start, container/image creation,
dependency installation, live recorder fixture, task operation or model call
occurred. This is a setup failure, not an agent-task failure or AKI result.

The supervisor stopped work, ran its bounded cleanup phases, finalized accounting
and exited. There are no pending created resources. The existing VM was stopped
at the initial precondition and no startup command was issued. Saved configuration
hashes remained unchanged. The failed attempt was not retried.

## Actual measurements

| Measure | Observed result |
|---|---:|
| Total wall time including preparation | 1.178685 s |
| Supervised work and cleanup | 0.566712 s |
| Observed CPU component sum | 0.845956 CPU-s |
| Conservative CPU accounting | 1.851191 CPU-s |
| Artifact response bodies downloaded | 0 bytes |
| Artifact bodies removed during cleanup | 0 bytes |
| Peak disk reservation | 872,445,257 bytes |
| Model calls / pilot operations | 0 / 0 |

Disk reservation is capacity set aside, not actual disk consumption. TLS handshake
transport bytes were not instrumented and are not claimed zero. The conservative
CPU total includes a one-CPU-second report-writing allowance and 0.005235 CPU-s
of unsampled bounds. The frozen driver put the report-writing allowance in its
`measured_ns` field; the public report explicitly separates it, and the follow-up
patch correctly classifies that allowance as a bound. Host/guest CPU components
may overlap and must not be interpreted as additive physical CPU cost.

Raw numeric command measurements, identities and limitations are in
[`task420-attempt2.json`](../results/runtime/task420-attempt2.json). Private logs,
source captures, prompts and authentication data are excluded from publication.

## Diagnosis and subsequent code fix

A read-only local comparison found that this installed Python 3.11.5/OpenSSL
configuration loads **zero CA certificates**, in both normal and isolated mode.
Therefore isolated mode alone did not cause the failure. This should have been
caught by a trust-store preflight in the driver before starting an attempt.

The already-installed `certifi` 2025.01.31 bundle loads **150 CA certificates**.
The follow-up `aki/setup_tls.py` now checks trust availability locally before
allocating an attempt. It uses the default verified context when populated, or
the existing certifi bundle when the default store is empty. It checks
`CERT_REQUIRED`, hostname verification and nonzero CA count, then fingerprints the
chosen bundle. All download requests, including the task-metadata HEAD request,
receive that explicit context. It installs nothing, persists no credential,
changes no OS security setting, and never uses an unverified context. If actual
TLS validation still fails, it stops; there is no automatic fallback or retry.

The frozen driver passed **93 host tests** before execution. The follow-up patch
passes **95 host tests**, including local trust loading and rejection of empty or
verification-disabled contexts. These checks make no network request. They do not
prove the registry connection, native setup or recorder fixture now succeeds.

## Remaining gate

The single attempt is closed. The exact pending action is a **new verified TLS
request to the public Docker registry**, followed only on success by one bounded
fixture-first attempt using the same pinned artifacts, task and restrictions.
It needs renewed live authorization, not a host installation, paid service, new
credential or certificate-verification bypass. No automatic approval rejection
occurred; the runtime correctly rejected an unverifiable TLS chain.

Keep the registered 512 MiB transfer / 3 GiB disk ceilings, all `noexec` mounts,
native-only startup flags, offline non-root container and ownership-scoped cleanup.
The driver imposes the stricter common 600-second/300-CPU-second envelope described
in [the frozen protocol](TASK420_LIVE_ATTEMPT2_PROTOCOL.md). Live recorder and
compatibility gates remain unpassed; the conditional pilot has not started.
