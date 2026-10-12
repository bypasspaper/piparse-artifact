#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Re-measure the ablation ladder (E01). Threadripper PRO 5965WX, bid_strings_3GB.csv, InMemory source.
# Wall time (measured 2026-08-24 / 2026-10-05, 3 reps each): suite r1-r4,r6,r6b 180 runs ~22 min; r7 30 runs ~4 min;
# r5 30 runs ~3 min (+ a rebuild of the fastpath-OFF binary, see below); eager_all 150 runs 19 min; lazy_nopass 90 runs 12 min.
set -euo pipefail
PBENCH_DIR=${PBENCH_DIR:-$HOME/work/piparse-bench}
NES_BUILD_DIR=${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}
WORKER_PORT=${WORKER_PORT:-9099}
HERE=$(cd "$(dirname "$0")" && pwd)
echo "Estimated wall time: ~60 min of measurement (+ one engine rebuild for r5). Press Ctrl-C within 5 s to abort."; sleep 5
cd "$PBENCH_DIR"
pgrep -x main >/dev/null && { echo "ABORT: a NES worker (main) is already running"; exit 2; }
run() { PBENCH_KEEP_LOGS=1 uv run python bench.py run "experiments/$1.yaml" --build-dir "$NES_BUILD_DIR" --worker-port "$WORKER_PORT"; }
# r1, r2, r3, r4, r6, r6b (W1 InMemory, FULL binary) and r7 (= matrix r_par: W23, ccx/pin off, NES_INMEM_REPEAT=20 -> true = reported x20)
run ablation_suite_json_inmem_seq_bidstr
run matrix/cell_csv_json_rparfix
# the two new rungs (same binary; eager_all needs the NES_EAGER_COPY_VARSIZED env, set inside the yaml)
run ablation_eager_all_bidstr
run ablation_lazy_nopass_bidstr
cat <<'NOTE'
r5 (+inline, general proxy inlining only) requires the FASTPATH-OFF binary so that the JSON output fast path lands at
r5->r6 and not inside r5 (ABLATION_LADDER_V7_HANDOVER.md §5):
  1. comment nes-plugins/OutputFormatters/JSONOutputFormatter/CMakeLists.txt line `nautilus_inline(json_output_formatter_plugin)`
  2. move `output_parse` from enable: to disable: in testing/configurations/InlineTagConfig.yaml
  3. RECONFIGURE (the tag config is read at configure time), rebuild nes-single-node-worker + nes-cli
  4. PBENCH_KEEP_LOGS=1 uv run python bench.py run experiments/ablation_r5_inmem_fpoff_bidstr.yaml --build-dir $NES_BUILD_DIR --worker-port $WORKER_PORT
  5. git checkout both files, reconfigure, rebuild (restores the canonical FULL binary)
Then assemble: the v7 CSVs were built by pbench scratchpad/assemble_v7.py (medians per variant x series, r7 x20);
the new rungs via:
  python3 decompose_eager_all.py  --run-group <eager_all run_group>
  python3 decompose_lazy_nopass.py --run-group <lazy_nopass run_group> --run-group-prev <eager_all run_group>
and splice the two v7-footing projection columns into data/ablation_ladder_v8_bidstr.csv; python3 make_figure.py
NOTE

# --- 2026-10-12 re-measurement of the two top rungs with lazy overloads ON (paper policy), ~15 min each -------------------
# r6_ctrl / r6b_ovl (W1, repeat 1) and r7_ctrl / r7_ovl (W23, NES_INMEM_REPEAT=20 -> true = reported x20); then splice:
#   python3 splice_overload_rerun.py            # -> data/ablation_ladder_v9_bidstr{,_mrows}.csv, out/ablation_overload_rerun_medians.csv
#   python3 make_figure.py                      # -> out/ablation_ladder_v9.{png,svg} (v9 is picked automatically when present)
pkill -9 -x main; PBENCH_KEEP_LOGS=1 uv run --project "$PBENCH_DIR" python "$PBENCH_DIR/bench.py" run "$PBENCH_DIR/experiments/ablation_r6_overload_rerun_bidstr.yaml" --build-dir "$NES_BUILD_DIR" --worker-port 9099
pkill -9 -x main; PBENCH_KEEP_LOGS=1 uv run --project "$PBENCH_DIR" python "$PBENCH_DIR/bench.py" run "$PBENCH_DIR/experiments/ablation_r7_overload_rerun_bidstr.yaml" --build-dir "$NES_BUILD_DIR" --worker-port 9099
