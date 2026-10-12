#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# E05 re-measure: the 5-arm head-to-head (NES naive / NES optimised / NES native->native / Flink / Spark) on the
# 10 stateless bid_strings queries + the 3 stateful queries, W23 on the Threadripper, records/s, 10 reps.
# Two layers: (A) the original Aug-14 5-arm runs (all five arms, incl. Flink + Spark) and (B) the Sep-02 one-code-state
# regeneration of the NES columns (the paper CSVs = B for NES + A for Flink/Spark). Usage: ./run.sh [--dry-run]
set -euo pipefail
PBENCH_DIR=${PBENCH_DIR:-$HOME/work/piparse-bench}
NES_BUILD_DIR=${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}
WORKER_PORT=${WORKER_PORT:-9099}
HERE=$(cd "$(dirname "$0")" && pwd); mkdir -p "$HERE/out"
if [[ "${1:-}" == "--dry-run" ]]; then run() { echo "+ $*"; }; else run() { echo "+ $*"; "$@"; }; fi
cat <<EOT
Estimated wall time (Threadripper PRO 5965WX, warm page cache):
  (A) nes_vs_flink_vs_spark_stateless_5arm  500 runs (5 arms x 10 q x 10 reps)   2 h 25 min  (paper run_group 20260814T000106-1b605eba, engine 66ab110f30)
  (A) nes_vs_flink_vs_spark_stateful_5arm   150 runs (5 arms x 3 q x 10 reps)    1 h 00 min  (20260814T023018-8d5faba3)
  (B) w23_native_native_regen               100 runs                                 7 min  (20260902T171734-780e8bea, b5d757c9f6 + overlay)
  (B) w23_simd_csvnative_regen              200 runs                                15 min  (20260902T180433-970509c0)
  (B) naive_corrected_regen_tip             100 runs (W1, interpreted + original codecs) 18 min (20260902T202750-35950c65)
  (B) stateful_serde_regen                   90 runs                              ~12 min  (3 run_groups 20260902T212534/213435/213621 — the _rest yamls are resume slices)
  (diag) w1_column_replication               90 runs                                19 min  (20260902T124928-25fb7252)
Data: bid_strings_3GB.{csv,nes}; ysb1k_with_varsized_3GB.{csv,nes}, person_840MB/auction_707MB(.nes), google-cluster-data-original_1G(.nes)
      under <build>/nes-systests/testdata/large/ (see ../../data/README.md). Flink/Spark arms: pyflink 2.1.3 + pyspark 3.5.9 in
      pbench's .venv (default interpreter) and the connector jars from flink-ext/build.sh + spark-ext/build.sh.
EOT
cd "$PBENCH_DIR"
run pkill -9 -x main || true
# (B) one-code-state NES regeneration — these are what the paper CSVs use for the NES columns
for exp in w23_native_native_regen w23_simd_csvnative_regen naive_corrected_regen_tip stateful_serde_regen; do
  run env PBENCH_KEEP_LOGS=1 uv run python bench.py run "experiments/$exp.yaml" --build-dir "$NES_BUILD_DIR" --worker-port "$WORKER_PORT"
done
# (A) the full 5-arm runs incl. Flink + Spark (long; the yamls say: launch --detach, Flink/Spark need the long timeouts)
for exp in nes_vs_flink_vs_spark_stateless_5arm nes_vs_flink_vs_spark_stateful_5arm; do
  run env PBENCH_KEEP_LOGS=1 PBENCH_FLINK_TIMEOUT=1800 PBENCH_SPARK_TIMEOUT=1800 uv run python bench.py run "experiments/$exp.yaml" \
      --build-dir "$NES_BUILD_DIR" --worker-port "$WORKER_PORT"
done
cat <<EOT

Done. Paper CSVs + figure from the new measurements (make_paper_csv.py / make_stateful_csv.py read ALL runs of the regen
experiments by name, so re-running (B) feeds them directly; the Flink/Spark medians are literals inside make_paper_csv.py
QUERIES and the Aug-14 CORRECTED per-rep raw CSV — update those from a new (A) run via:
  uv run python bench.py export nes_vs_flink_vs_spark_stateless_5arm ; uv run python bench.py export nes_vs_flink_vs_spark_stateful_5arm):
  python3 make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb
EOT
