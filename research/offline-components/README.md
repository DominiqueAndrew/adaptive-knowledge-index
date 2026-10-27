# Original fixture harness history

`task_benefit_v1.py` is the exact original project source whose SHA-256 is recorded
in `results/instrumentation/task-benefit-fixture-20261027/freeze.json`. It is kept
to reproduce the first fixture plumbing run, not as a supported standalone script.
It used the fastest overall control as comparator; disabled reuse won. The current
harness retains disabled reuse separately and chooses the best observed implemented
cache for the paired comparison. Neither run used real tasks, models or held-out
cohort actions. The final v2 fixture run is explicitly synthetic and retains all
conditions, including AKI's higher observed tiny-run cost.
