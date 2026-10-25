#!/bin/sh
# Local CPU-only runs. Prepare public checkouts/bundles using docs first.
set -eu
prefix=${1:?Pass a new output prefix, e.g. results/reproduction}
python3 -m unittest discover -s tests -v
python3 -m aki.paired --label synthetic-locality --seeds 70,71,72 --budget 65536 --write-ablation --out "${prefix}-synthetic"
python3 -m aki.paired --label synthetic-low-reuse --seeds 70,71,72 --scenario low_reuse --count 100 --budget 65536 --out "${prefix}-low-reuse"
python3 -m aki.paired --repo ../public-click --label pallets/click --license BSD-3-Clause --ref 2247b35ea1c47c727d7a06e51fa280e12a863ff6 --tasks 30 --seeds 70,71,72 --write-ablation --out "${prefix}-click"
python3 -m aki.paired --repo ../public-pytest --label pytest-dev/pytest --license MIT --ref 0f54d41bedf00505bb1ac2c724abf96ba6dcf48d --tasks 30 --seeds 70,71,72 --write-ablation --out "${prefix}-pytest"
python3 -m aki.paired --repo ../public-flask --label pallets/flask --license BSD-3-Clause --ref d086db856be187255b8ec61ef409357393020f32 --tasks 30 --seeds 70,71,72 --write-ablation --out "${prefix}-flask"
python3 scripts/analyze_phase2.py "${prefix}-synthetic" "${prefix}-low-reuse" "${prefix}-click" "${prefix}-pytest" "${prefix}-flask" --out "${prefix}-analysis.json"
python3 -m aki.selective_eval --upstream ../arb-upstream --data ../arb-data --split development --out "${prefix}-selective-development"
python3 -m aki.selective_eval --upstream ../arb-upstream --data ../arb-code2test --split heldout --out "${prefix}-selective-heldout"
