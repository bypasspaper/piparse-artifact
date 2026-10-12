#!/usr/bin/env bash
# E09 re-measure recipe. Estimated wall time (Threadripper 5965WX, idle, performance governor):
#   Fig2 predicate sweep  : NES ~50 min (300 runs) + Flink ~13 min (30 runs)           -> fig2_pred_{nes,flink}.yaml
#   Fig2 full projection  : NES ~85 min (400 runs)                                      -> fig2_fieldsweep_v2.yaml
#   Fig2 one-field proj.  : NES ~38 min (200 runs) + Flink ~12 min                      -> fig2_proj1_{nes,flink}.yaml
#   Fig1 v2 profile chain : ~40 min (6 perf profiles + throughput + Flink q2og profile) -> scripts/profiling/run_teaser2.sh
# Needs: worker + nes-cli built in $NES_BUILD_DIR (engine tag piparse-artifact-v1), pbench at tag piparse-artifact-v1,
# datasets nf{1..10}.csv / nm{1..10}.csv (+ _x10 twins for Flink) under <build>/nes-systests/testdata/large/multicol/
# (see ../../data/README.md), bid_1GB/bid_6GB + ysb datasets for Fig1, PyFlink 2.1.3 + JDK 11 for the Flink arms,
# perf + async-profiler for the Fig1 profiles.
set -euo pipefail
PBENCH_DIR=${PBENCH_DIR:-$HOME/work/piparse-bench}
NES_BUILD_DIR=${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}
PORT=${WORKER_PORT:-9099}
cd "$PBENCH_DIR"
pkill -9 -x main 2>/dev/null || true; sleep 1
if ss -ltnHp "sport = :$PORT" | grep -q .; then echo "port $PORT busy (ghost worker?) -- abort"; exit 1; fi
run() { PBENCH_KEEP_LOGS=1 uv run python bench.py run "$@" --build-dir "$NES_BUILD_DIR" --worker-port "$PORT"; }
case "${1:-pred}" in
  pred)  run experiments/fig2_pred_nes.yaml;   uv run python bench.py run experiments/fig2_pred_flink.yaml --build-dir "$NES_BUILD_DIR" ;;
  pass)  run experiments/fig2_fieldsweep_v2.yaml ;;
  proj1) run experiments/fig2_proj1_nes.yaml;  uv run python bench.py run experiments/fig2_proj1_flink.yaml --build-dir "$NES_BUILD_DIR" ;;
  fig1)  echo "Fig1 v2 chain: edit SC= in scripts/profiling/run_teaser2.sh to point at scripts/profiling, then run it"; exit 2 ;;
  *) echo "usage: $0 {pred|pass|proj1|fig1}"; exit 2 ;;
esac
echo "then: python3 make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb"
