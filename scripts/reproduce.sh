#!/bin/sh
# From the project root. Existing directories are never overwritten.
set -eu
RUN_NAME=${1:-reproduction}
python3 -m unittest discover -s tests -v
python3 -m aki.benchmark --nodes 500 --seeds 50,51,52,53,54 --count 160 --invalidation selective --out "results/$RUN_NAME-synthetic"
python3 -m aki.benchmark --nodes 500 --seeds 40,41,42,43,44 --count 100 --scenario low_reuse --invalidation selective --out "results/$RUN_NAME-low-reuse"
# Public data/history are optional and obtained separately; see README.
