#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# E12 — re-measure the thread-structure study (DPP | gang k=4 | chunker k=4 | thread-per-query | rr) under the engine's
# admission rule (<=64 buffers per query, <=1000 in flight), identical / cost-skewed / bursty queries, both machines.
# ESTIMATED WALL TIME: Threadripper ~1 h 45 min (rr 6 min + heavy 29 min + burst 29 min + main window 23 min + quote chunker 5 min);
#                      Raspberry Pi 5 ~2 h 20 min (main+rr 30 min + quote 6 min + heavy ~45 min + burst ~45 min), driven over ssh.
# The isolated rig (no engine, no pbench): nes-input-formatters/tests/Benchmark/FormatterLatencyBenchmark.cpp at engine tag
# piparse-artifact-v1 (rig/FormatterLatencyBenchmark_with_rr_skew_2026-09-22.cpp is the snapshot that produced the data;
# same code, re-formatted when committed).
set -euo pipefail
NES_REPO=${NES_REPO:-$HOME/work/nebulastream-public}
NES_BUILD_DIR=${NES_BUILD_DIR:-$NES_REPO/cmake-build-release}
cat <<EOF
# ---- 1. build the rig (host release build, see ../../env/tr/) ----
cmake --build $NES_BUILD_DIR --target formatter-latency-benchmark

# ---- 2. data: 512 MiB numeric quote-free CSV, 5 x UINT64 per row (creationTS,key,v1,v2,v3; the rig names them f0..f4) ----
python3 $NES_REPO/scripts/benchmarking/gen_formatter_csv.py \\
        $NES_REPO/nes-systests/testdata/large/formatter/bench_5xUINT64_512m.csv --target-mb 512
#   (deterministic generator, defaults --keys 64 --rows-per-ms 50; ~14.3 M rows; the rig gates every row on tuples/row == 1.0000)
#   The Pi needs the same file under /home/pi/data/repos/nebulastream/nes-systests/testdata/large/formatter/.

# ---- 3. sweeps (rig/run_fig.sh; edit REPO/BIN/DATA/FNATTR for TR and R/PI for the Pi at the top of the script) ----
#   Threadripper: governor performance, taskset 0-23 (SMT siblings excluded), W=24 pinned pooled workers.
#   Pi: ondemand holds 2.4 GHz under load; pre-flight vcgencmd get_throttled == 0x0; run inside nes-development:local-piparse, --cpuset-cpus 0-3.
cd rig
MACHINE=tr ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4" DW=64 CAP=1000 TAG=ws        ./run_fig.sh   # main window 4 arms (2026-09-10)  -> sweep_tr_ws_D64_C1000.csv
MACHINE=tr ARMS="chunker 4" CUT=quote                   DW=64 CAP=1000 TAG=ws        ./run_fig.sh   # + quote-aware chunker (appends)
MACHINE=tr ARMS="rr 1"                                  DW=64 CAP=1000 TAG=ws_rr     ./run_fig.sh   # rr rows (2026-09-23)             -> sweep_tr_ws_rr_D64_C1000.csv
MACHINE=tr ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 HEAVY=0.1,4 TAG=ws_heavy ./run_fig.sh   # cost skew  -> sweep_tr_ws_heavy_D64_C1000.csv
MACHINE=tr ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 BURST=20,20 TAG=ws_burst ./run_fig.sh  # bursts     -> sweep_tr_ws_burst_D64_C1000.csv
MACHINE=pi ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 TAG=ws2  ./run_fig.sh   # Pi main window incl. rr          -> sweep_pi_ws2_D64_C1000.csv
MACHINE=pi CUT=quote ARMS="chunker 4"                        DW=64 CAP=1000 TAG=ws2  ./run_fig.sh   # + quote-aware chunker (appends)
MACHINE=pi ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 HEAVY=0.1,4 TAG=ws2_heavy ./run_fig.sh
MACHINE=pi ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 BURST=20,20 TAG=ws2_burst ./run_fig.sh
#   (exactly rig/tr_chain_2026-09-23.sh + rig/pi_chain_2026-09-23.sh; the *chain2* scripts are the burst re-runs after the seed/timer fix)
#   Each run_fig.sh invocation writes/appends <TAG>.csv next to the script and per-arm consoles + run_<machine>.meta under logs/.

# ---- 4. figures ----
cd ..; python3 make_figure.py --check      # -> out/core_story_ws2.{png,pdf}, out/skew_story.{png,pdf}
EOF
