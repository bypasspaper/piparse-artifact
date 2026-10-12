#!/usr/bin/env bash
# E10 re-measure recipe. Estimated wall time (Threadripper 5965WX): float sweep ~1 h 50 min (300 runs; the naive
# stringstream tail at REPEAT=20 is the cost), int sweep ~32 min (300 runs, naive at REPEAT=3), mixed sweep ~65 min
# (480 runs), mixed naive ~17 min (120 runs). Smokes: serde_micro_smoke (K=4, 15 runs, ~3 min), serde_micro_mixed_smoke (8 runs).
# Needs: worker with the TOFLOAT64/TOINT64 plugins (engine tag piparse-artifact-v1), datasets
# <build>/nes-systests/testdata/large/serde_micro/{floatk,intk}{1..20}.{csv,nes} (8.7 GB):
#   python3 scripts/generators/gen_serde_micro.py base && python3 scripts/generators/gen_serde_micro.py slice {1..20}
#   python3 scripts/generators/gen_serde_micro_int.py base && python3 scripts/generators/gen_serde_micro_int.py slice {1..20}
#   (edit DATA= / C2B= at the top of both generators to your build tree; C2B = nes-systests/testdata/small/csv_to_binary.py)
set -euo pipefail
PBENCH_DIR=${PBENCH_DIR:-$HOME/work/piparse-bench}
NES_BUILD_DIR=${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}
PORT=${WORKER_PORT:-9099}
cd "$PBENCH_DIR"
pkill -9 -x main 2>/dev/null || true; sleep 1
if ss -ltnHp "sport = :$PORT" | grep -q .; then echo "port $PORT busy (ghost worker?) -- abort"; exit 1; fi
run() { PBENCH_KEEP_LOGS=1 uv run python bench.py run "experiments/$1.yaml" --build-dir "$NES_BUILD_DIR" --worker-port "$PORT"; }
for e in ${@:-serde_micro_smoke}; do run "$e"; done     # full set: serde_micro_full serde_micro_int_full serde_micro_mixed_full serde_micro_mixed_naive
echo "then: python3 make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb"
