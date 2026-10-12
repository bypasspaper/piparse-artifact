#!/usr/bin/env bash
# E11 re-measure recipe. Estimated wall time (Threadripper 5965WX): the 16 cells r_base+r_comp (W1, BlockingFile) ran
# 4 h 07 min for all 3 rungs on 2026-08-04/05 (1440 runs); the corrected r_par re-run (W23, InMemory, ccx/pin OFF) took
# 1 h 13 min (480 runs, 16 x cell_*_rparfix.yaml). W-sweep: ~6 min (32 runs). Per cell: ~15 min (r_base+r_comp) + ~5 min (r_par).
# Needs: engine tag piparse-artifact-v1 built with ENABLE_LARGE_TESTS=ON (bid_strings_3GB.csv + the json/hl7/xml twins
# under <build>/nes-systests/testdata/large/nexmark/, see ../../data/README.md: hl7 via yaml/gates/hl7/convert_csv_to_hl7.sh,
# xml via yaml/gates/xml/convert_csv_to_xml.py; checksum gates in yaml/gates/ MUST pass first: anchor 31300000,269477267979).
set -euo pipefail
PBENCH_DIR=${PBENCH_DIR:-$HOME/work/piparse-bench}
NES_BUILD_DIR=${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}
PORT=${WORKER_PORT:-9099}
cd "$PBENCH_DIR"
pkill -9 -x main 2>/dev/null || true; sleep 1
if ss -ltnHp "sport = :$PORT" | grep -q .; then echo "port $PORT busy (ghost worker?) -- abort"; exit 1; fi
run() { PBENCH_KEEP_LOGS=1 uv run python bench.py run "$1" --build-dir "$NES_BUILD_DIR" --worker-port "$PORT"; }
case "${1:-cell}" in
  cell)   # one cell, e.g. ./run.sh cell csv json  -> r_base + r_comp from cell_csv_json.yaml, r_par from cell_csv_json_rparfix.yaml
          in=${2:-csv}; out=${3:-json}; run experiments/matrix/cell_${in}_${out}.yaml; run experiments/matrix/cell_${in}_${out}_rparfix.yaml ;;
  all)    for i in csv json hl7 xml; do for o in csv json hl7 xml; do run experiments/matrix/cell_${i}_${o}.yaml; run experiments/matrix/cell_${i}_${o}_rparfix.yaml; done; done ;;
  wsweep) run experiments/wsweep_output_plateau.yaml ;;
  *) echo "usage: $0 {cell <in> <out>|all|wsweep}"; exit 2 ;;
esac
echo "then export per-run rows (see expected/ARCHIVE_README_matrix_2026-08-05.md: experiment=cell_<in>_<out>[_rparfix], series=r_base|r_comp|r_par)"
echo "and: python3 make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb"
