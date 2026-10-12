#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# E08 — re-measure the many-source scaling ladders (N = 1 … 1000 concurrent sources/queries, 10-query stateless mix, csv -> json)
# ESTIMATED WALL TIME (Threadripper): smoke 5 min; NES+Flink step-20 ~17 h; Spark step-20 (64 MiB micro-batch source) ~19.5 h;
#   NES naive+native step-20 ~13.7 h; native fine 15 min; SIMD fine 18 min; naive+Flink+Spark low-N ~1.5 h  => ~52 h total.
# ESTIMATED WALL TIME (Raspberry Pi 5): NES optimised ladder ~2 h; Flink a-c ~15.5 h + N=1000 ~14 h; naive W3 a-d ~19 h; Spark + no-serde ladders ~1 day each.
set -euo pipefail
PBENCH_DIR=${PBENCH_DIR:-$HOME/work/piparse-bench}
NES_BUILD_DIR=${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}
cat <<EOF
# ======================= Threadripper (pbench at tag piparse-artifact-v1) =======================
cd $PBENCH_DIR
pkill -9 -x main || true; ss -ltnHp 'sport = :9099'            # worker comm is literally 'main'; port must be free
export PBENCH_FLINK_TIMEOUT=1800 PBENCH_SPARK_TIMEOUT=1800 PBENCH_KEEP_LOGS=1
RUN="uv run python bench.py run --build-dir $NES_BUILD_DIR --worker-port 9099"
\$RUN experiments/flink_spark_smoke_n1.yaml                                    # ALWAYS first: validates JVM + jars (Flink ~122 MB/s, Spark ~62 MB/s at N=1)
\$RUN --detach --log-file results/logs/step20.log      experiments/nes_vs_flink_vs_spark_scaling_step20.yaml           # NES(SIMD)+Flink, 51 pts x 1 rep (run_group 20260817T164347-3ec56b98)
\$RUN --detach --log-file results/logs/step20_spark.log experiments/nes_vs_flink_vs_spark_scaling_step20_spark_mb.yaml # Spark, real per-batch latency (20260820T144859-a82252ff)
\$RUN --detach --log-file results/logs/nn_step20.log   experiments/nes_naive_native_scaling_step20.yaml               # NES-Naive (W16) + NES-Native, 51 pts each (20260901T024303-4285bc04)
\$RUN experiments/nes_native_scaling_lowN_fine.yaml                            # N=1..100 step 1 (20260901T165004-628e9d01)
\$RUN experiments/nes_simd_scaling_lowN_fine.yaml                              # N=1..100 step 1 (20260901T171812-7a007e66)
\$RUN experiments/nes_naive_flink_spark_lowN_fine.yaml                         # 22-pt log grid 1..100, 3 arms (20260901T175023-5d971803)
#   Do NOT read the DuckDB while a run is open (single writer); build figures after the runs finish.
#   Historic July ladder behind expected/flink_vs_nes_latency_scaling (bid passthrough csv->csv, 1..1024 File sources):
#   experiments/latency_flink_passthrough_scaling.yaml + shredder_fragments_source_scaling.yaml (+ shredder_fragments_n1024_*.yaml for the certified N=1024 point).

# ======================= Raspberry Pi 5 (Pi checkout of pbench; yamls listed in README §Pi) =======================
# pre-flight: vcgencmd get_throttled == 0x0, 2.4 GHz under load, governor performance (naive/tiers) or ondemand (Flink), :8080 free
cd /home/pi/data/repos/piparse-bench; export LD_LIBRARY_PATH=/home/pi/data/runtime-libs; ulimit -n 65536
for p in a b c;   do PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run experiments/pi_scaling_file_\$p.yaml;    done   # NES optimised (Aug-23 binary, W3+io1)
for p in a b c;   do PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run --flink-python /home/pi/data/flink312/bin/python3 experiments/pi_flink_scaling_\$p.yaml; done
PBENCH_FLINK_TIMEOUT=150000 PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run --detach --flink-python /home/pi/data/flink312/bin/python3 experiments/pi_flink_scaling_c_n1000.yaml   # -Xmx8g, heartbeat 30 min
for p in a b c;   do PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run experiments/pi_spark_mb_\$p.yaml;        done   # Spark, 64 MiB micro-batch source
for p in a b c d; do PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run experiments/pi_naive_scaling_w3_\$p.yaml; done   # naive at W3 = scripts/run_naive_w3.sh (sampler + continuity log)
for p in a b c d; do PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run experiments/pi_noserde_scaling_\$p.yaml;  done   # native in/out (N=1000 at default_max_inflight_buffers=16)
PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run experiments/pi_naive_inflight_probe.yaml                               # the in-flight-window probe (scripts/run_inflight_probe.sh)
python3 ~/powertest/dump.py        # = scripts/pi_dump.py: DuckDB -> /home/pi/powertest/export/{nes,flink,spark,naive,naive_w3,native}_scaling.csv (+ raw jobs)

# ======================= figures =======================
python3 make_figure.py --check     # TR figures from ../../results/tr/piparse_bench.duckdb; Pi views from ../../results/pi/*.csv
EOF
