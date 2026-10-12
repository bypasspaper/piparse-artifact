#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# E03 re-measure: figW (worker sweep on 12 KB / ~3-span rows, LF vs LOCKING shredder) + its q_ex twin, figS/figL (span
# sweep at 4 and 8 KiB raw buffers), the latency probe, and the ISOLATED formatter-scaling-benchmark arms.
# Usage: ./run.sh [--dry-run]     env: PBENCH_DIR, NES_BUILD_DIR (release build, host or dev-container), ENGINE_DIR, WORKER_PORT
set -euo pipefail
PBENCH_DIR=${PBENCH_DIR:-$HOME/work/piparse-bench}
NES_BUILD_DIR=${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}
ENGINE_DIR=${ENGINE_DIR:-$(dirname "$NES_BUILD_DIR")}
WORKER_PORT=${WORKER_PORT:-9099}
HERE=$(cd "$(dirname "$0")" && pwd); mkdir -p "$HERE/out"
if [[ "${1:-}" == "--dry-run" ]]; then run() { echo "+ $*"; }; else run() { echo "+ $*"; "$@"; }; fi
cat <<EOT
Estimated wall time on the paper machine (Threadripper PRO 5965WX, 24 physical cores, warm page cache, binary = tag piparse-artifact-v1):
  data generation (9 x 500 MiB CSVs)                        ~1 min
  e2e  shredder_worker_probe      192 runs, 6 reps, W1..24    13 min   (paper run_group 20260831T173338-1b014b79)
  e2e  shredder_worker_probe_qex  192 runs                    13 min   (20261005T170750-d5bb1e82)
  e2e  shredder_span_sweep        168 runs, 7 rows x 2 bufs   14 min   (20260831T135736-941d625d)
  e2e  shredder_latency_probe      12 runs                     1 min   (20260831T142959-dab6103c)
  isolated worker probe (reps 15, 8 thread counts, 2 modes)  ~10 min
  isolated span sweep   (reps 15, 7 rows x 2 bufs x 3 W)     ~25 min
EOT

# ---- 1. data: spanning rows (gitignored; written into the engine tree and symlinked into the build tree) ----
FMT=$ENGINE_DIR/nes-systests/testdata/large/formatter
run mkdir -p "$FMT" "$NES_BUILD_DIR/nes-systests/testdata/large/formatter"
for n in 4 12 16 40 80 160 320 640; do
  [[ -f "$FMT/bigstr_id_${n}k_500m.csv" ]] || run bash -c "python3 '$HERE/gen_bigstr_id.py' $((n*1000)) > '$FMT/bigstr_id_${n}k_500m.csv'"
done
# q_ex twin: the first 43,546 bid_strings rows with url padded to 12,000 chars (needs bid_strings_3GB.csv, see ../../data/README.md)
[[ -f "$FMT/bidstr_url12k_500m.csv" ]] || run python3 "$HERE/gen_bidstr_url12k.py" \
  "$NES_BUILD_DIR/nes-systests/testdata/large/nexmark/bid_strings_3GB.csv" "$FMT/bidstr_url12k_500m.csv" 12000
for f in "$FMT"/bigstr_id_*_500m.csv "$FMT"/bidstr_url12k_500m.csv; do run ln -sfn "$f" "$NES_BUILD_DIR/nes-systests/testdata/large/formatter/"; done

# ---- 2. e2e arms (pbench worker-cli, InMemory prefill, Monitoring sink). pkill first: a stray worker contaminates the run ----
cd "$PBENCH_DIR"
run pkill -9 -x main || true
for exp in shredder_worker_probe shredder_worker_probe_qex shredder_span_sweep shredder_latency_probe; do
  run env PBENCH_KEEP_LOGS=1 uv run python bench.py run "experiments/$exp.yaml" --build-dir "$NES_BUILD_DIR" --worker-port "$WORKER_PORT"
done

# ---- 3. isolated arm: formatter-scaling-benchmark (EXCLUDE_FROM_ALL target; arg list in FormatterScalingBenchmark.cpp header) ----
# arg13 = 2 : 2-field (id UINT64, s VARSIZED) row projected to id = the shredder-isolated SELECT id (same work as the e2e query)
run cmake --build "$NES_BUILD_DIR" --target formatter-scaling-benchmark
BIN=$NES_BUILD_DIR/nes-input-formatters/tests/Benchmark/formatter-scaling-benchmark
cd "$ENGINE_DIR"   # the harness resolves the data path relative to the engine root
run bash -c "'$BIN' nes-systests/testdata/large/formatter/bigstr_id_12k_500m.csv 4 0 15 1,2,4,8,12,16,20,24 leanprod 1 - - both - SIMDCSV 2 | tee '$HERE/out/isolated_worker_probe_12k_leanprod.log'"
run bash -c "for buf in 4 8; do for tag in 4k 16k 40k 80k 160k 320k 640k; do echo \"########## BUF \${buf}k SPAN \${tag} ##########\"; \
  '$BIN' nes-systests/testdata/large/formatter/bigstr_id_\${tag}_500m.csv \$buf 0 15 8,16,24 leannoemit 1 - - both - SIMDCSV 2; done; done | tee '$HERE/out/isolated_span_sweep_4k8k.log'"

cat <<EOT

Done. To draw the figures from the NEW measurements:
  python3 parse_isolated.py out/isolated_span_sweep_4k8k.log out/isolated_tidy.csv      # new isolated span sweep
  cp out/isolated_worker_probe_12k_leanprod.log data/logs/                               # make_worker_figure.py reads data/logs/
  python3 make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb                   # e2e arms = latest run_group per experiment
  python3 make_qex_span_figure.py <new shredder_worker_probe_qex run_group> out --db $PBENCH_DIR/results/piparse_bench.duckdb
EOT
