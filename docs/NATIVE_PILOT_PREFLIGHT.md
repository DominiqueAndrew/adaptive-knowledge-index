# Native runtime and task 420 preflight

Date: 2026-10-25. This is a readiness review, not an agent attempt or benchmark.
The task remains `Backblaze__B2_Command_Line_Tool-420`; no replacement was selected.

## Runtime result

One native-only start completed successfully in 19.264 seconds:

```sh
colima start --save-config=false --activate=false --ssh-config=false --binfmt=false
```

The guard saw no download, installation or new-permission indication. Docker
Engine 29.5.2 answered on linux/arm64. A read-only guest check found no qemu or
Rosetta binfmt handler files. Saved Colima, SSH and Docker configuration hashes
matched before startup, after startup and after shutdown. These checks are not
an exhaustive audit of all guest activity.

After the image review below stopped progression, `colima stop` completed with
exit 0 and a subsequent profile check confirmed `Stopped`. No benchmark container
was created. The [numeric readiness record](../results/runtime/native-readiness.json)
contains no host paths, credentials, configuration contents or runtime log bodies.

## Frozen task image review

The [metadata record](../results/runtime/task420-image-review.json) was read from
`nebius/SWE-rebench` revision `89cdfbab4ab1bd8f5a658bb212d1b63624f4f881`,
file `data/test-00000-of-00002.parquet`. Its base and environment-setup commits
match the frozen cohort:

- Source base: `15a60ad1c71b75366061e4f742ef52eb9dcc23e7`.
- Environment setup: `ee2339bd21d21d6140936d58597957250a33fc26`.
- `docker_image`: null; `image_name`: null.
- Python: 3.5; pre-install: package-index update and GCC installation.
- Setup: requirements file, nose/pytest and editable package installation.

These are **unexecuted setup instructions**, not an environment we reproduced.
The public base `setup.py` and requirements were inspected as text only. They
declare additional runtime dependencies, so a bare Python executable would not
establish the intended task environment. No compatible, reviewed task image was
available from the pinned metadata or the local image inventory. Unrelated
project images were not opened, reused, modified or published.

This absence is narrower than a claim that no suitable image exists anywhere.
The [dataset maintainer explains](https://huggingface.co/datasets/nebius/SWE-rebench/discussions/10)
that only part of this corpus has prebuilt images. The separate leaderboard's
image-availability statement does not supply an image for this frozen task.
Without an image identity we cannot truthfully pin its digest, validate native
arm64 support, audit its entrypoint or bound its download size.

The first metadata inspection transferred 511,343 bytes using the existing
bounded public-input cache. It loaded no patch, test-patch, action or outcome
columns. A task problem statement was retained locally but was not sent to a model.
The published reviewer excludes that text too and selects only runtime metadata:

```sh
SSL_CERT_FILE=/etc/ssl/cert.pem python3 scripts/review_prospective_task.py \
  --inputs ../replay-inputs --cohort results/phase4/cohort.json \
  --instance Backblaze__B2_Command_Line_Tool-420 \
  --output scratch/task420-image-review.json
```

It rejects tasks outside the frozen development partition, validates commit
identity, and uses the existing byte/CPU budget. It never executes setup strings
or invokes Docker. The reported extra transfer count depends on the local cache.

## Adapter review and next capability

`scripts/record_agent_run.py` remains an explicitly opted-in bridge to a reviewed
adapter. It is not a complete agent/backend: it does not itself implement image
isolation, operation limits, process quiescence, backend CPU accounting or model
dispatch. The recorder and tool-disabled Codex probe cannot substitute for these.
No live adapter was certified or agent attempt launched after the image gate failed.

The exact missing input is a reviewed **native arm64 task environment**, pinned by
digest, with the specified Python/dependencies and no task solution embedded.
Alternatively, a bounded isolated image build would need permission for its
reviewed downloads/package installation; the current no-install boundary was not
expanded to do this. Its recipe, architecture support and size must be established
before execution. Retain the existing 2 GiB download and 30 CPU-minute ceilings;
image size/build time are unmeasured, not assumed to fit. No paid API, new model
credential, host package installation or task substitution is needed or requested.

Once that input exists, implement and fixture-test the smallest validated dispatch
adapter, then freeze it before the first real action. Keep the 12-operation,
30-second-operation and 10-minute-task limits. The three-task acceptance gate,
held-out partition and [prospective protocol](PROSPECTIVE_CAPTURE_PROTOCOL.md)
remain unchanged. Actual prospective agent attempts: **zero**. No new evidence of
adaptive indexing efficacy or repair success was obtained in this preflight.
