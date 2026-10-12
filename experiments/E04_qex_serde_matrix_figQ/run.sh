#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# E04 re-measure: figQ = q_ex 1..23-worker sweep over the full serde matrix (native->native, native->JSON, csv->JSON,
# csv->native) + the LOCKING-shredder companion; figI = the superseded q2_mod 4-arm ideal sweep.
# Usage: ./run.sh [--dry-run]     env: PBENCH_DIR, NES_BUILD_DIR, WORKER_PORT
set -euo pipefail
PBENCH_DIR=${PBENCH_DIR:-$HOME/work/piparse-bench}
NES_BUILD_DIR=${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}
WORKER_PORT=${WORKER_PORT:-9099}
HERE=$(cd "$(dirname "$0")" && pwd); mkdir -p "$HERE/out"
if [[ "${1:-}" == "--dry-run" ]]; then run() { echo "+ $*"; }; else run() { echo "+ $*"; "$@"; }; fi
cat <<EOT
Estimated wall time (Threadripper PRO 5965WX, warm page cache, binary = tag piparse-artifact-v1):
  qex_serde_matrix_scaling      192 runs (4 arms x 8 W x 6 reps)   14 min   (paper run_group 20260902T220312-52fa4604)
  qex_locking_scaling            48 runs (1 arm  x 8 W x 6 reps)    4 min   (20260903T084122-767c3984)
  shredder_ideal_scaling_q2mod  160 runs (4 arms x 8 W x 5 reps)   13 min   (20260902T102956-283f8cf0, figI)
  first-time staging of the repeat-8 MmapFile inputs (26.8 GB csv + 25.6 GB nes) adds several minutes and needs ~55 GB free disk.
Data: bid_strings_3GB.csv and its packed twin bid_strings_3GB.nes under <build>/nes-systests/testdata/large/nexmark/ (see ../../data/README.md).
EOT
cd "$PBENCH_DIR"
run pkill -9 -x main || true
# the yamls recommend a detached launch (long-running); --detach writes results/logs/pbench_run_<ts>.log
for exp in shredder_ideal_smoke_q2mod shredder_ideal_scaling_q2mod qex_serde_matrix_scaling qex_locking_scaling; do
  run env PBENCH_KEEP_LOGS=1 uv run python bench.py run "experiments/$exp.yaml" --build-dir "$NES_BUILD_DIR" --worker-port "$WORKER_PORT"
done
cat <<EOT

Done. Figures from the new measurements (the scripts read the LATEST run_group of each experiment):
  python3 make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb
EOT
