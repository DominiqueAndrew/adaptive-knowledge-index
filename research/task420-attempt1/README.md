# Historical task-420 setup controls

These original programs preserve the first bounded setup attempt. **They are not
a supported agent adapter or a ready-to-run retry command.** The attempt stopped
at its first compatibility check, before dependency installation or task execution.
See `docs/TASK420_ATTEMPT1.md` and `results/runtime/task420-attempt1.json`.

`stage.py` was originally `scripts/pilot420_stage.py`. `setup_driver.py` was
`scripts/pilot420_setup.py`; the archived driver is its final state after Docker
29 identity-representation checks. Initial selector failures are recorded in the
report, not claimed to be reproduced by that final driver. `continue.py` retains
the original import path and assumptions about the existing attempt. The three
`control/` programs are the exact original helper sources used inside the container.
They include the failed virtual-environment setup, not a silently fixed version.

Staging performs real downloads; the driver loads/starts a container. Running any
of them requires a separately authorized bounded attempt. Do not reset counters,
reuse a partial workspace, weaken isolation, or treat these archives as approval.
Fetched image/package bodies and private runtime logs are excluded from Git.
