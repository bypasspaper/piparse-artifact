#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Re-measure the par-rung W-sweep probe (E02): 4 arms x W-sweep x 3 reps = 72 runs, measured 18 min on 2026-10-06
# (Threadripper, idle box; smoke variant 4 runs < 1 min).
set -euo pipefail
PBENCH_DIR=${PBENCH_DIR:-$HOME/work/piparse-bench}
NES_BUILD_DIR=${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}
WORKER_PORT=${WORKER_PORT:-9099}
HERE=$(cd "$(dirname "$0")" && pwd)
echo "Estimated wall time: ~18 min (smoke: <1 min with --smoke). Ctrl-C within 5 s to abort."; sleep 5
cd "$PBENCH_DIR"
pgrep -x main >/dev/null && { echo "ABORT: a NES worker (main) is already running"; exit 2; }
EXP=wsweep_q14_vs_q0_parrung; [ "${1:-}" = "--smoke" ] && EXP=${EXP}_smoke
PBENCH_KEEP_LOGS=1 uv run python bench.py run "experiments/$EXP.yaml" --build-dir "$NES_BUILD_DIR" --worker-port "$WORKER_PORT"
echo "Now: python3 $HERE/extract.py --db $PBENCH_DIR/results/piparse_bench.duckdb --run-group <new run_group> --out $HERE/out/wsweep_q14_vs_q0.csv"
echo "     python3 $HERE/make_figure.py --csv $HERE/out/wsweep_q14_vs_q0.csv"
