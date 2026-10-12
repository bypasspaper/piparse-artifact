#!/usr/bin/env bash
# Whole-lifetime profile of the optimised YSB single-pass window: perf record from port-bind until the run ends,
# then restrict the report to the busy DataSrc/WorkerThread window (window_report.sh). usage: profile_opt_ysb_full.sh [freq]
set -u
NAME="$1"; FREQ="${2:-8000}"
SC=/tmp/claude-1000/-home-user-work-nebulastream-public/f9057d9a-82ca-4860-8efc-985fed7b7954/scratchpad
REPO=/home/user/work/nebulastream-public
OUT="$SC/optprof_${NAME}"; mkdir -p "$OUT"
cd ~/work/piparse-bench || exit 2
pkill -9 -x main 2>/dev/null; sleep 1
PBENCH_KEEP_LOGS=1 uv run python bench.py run --build-dir "$REPO/cmake-build-release" --worker-port 9099 "$SC/fig1_opt_prof_${NAME}.yaml" > "$OUT/bench.log" 2>&1 &
BPID=$!
PID=""
for i in $(seq 1 120); do PID=$(ss -ltnHp 'sport = :9099' 2>/dev/null | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2); [ -n "$PID" ] && break; sleep 0.5; done
[ -z "$PID" ] && { echo "no worker on :9099"; kill $BPID; exit 3; }
echo "worker pid=$PID; recording whole lifetime @ ${FREQ}Hz"
perf record -F "$FREQ" -o "$OUT/perf_${NAME}.data" -p "$PID" -- sleep 400 2>"$OUT/perf_record.err" &
PPID_=$!
for i in $(seq 1 90); do kill -0 "$BPID" 2>/dev/null || break; sleep 5; done
sleep 2; kill -INT "$PPID_" 2>/dev/null; wait "$PPID_" 2>/dev/null
kill "$BPID" 2>/dev/null; pkill -9 -x main 2>/dev/null; sleep 1
echo "--- bench.log ---"; grep -v DIAG_ "$OUT/bench.log" | grep -iE 'throughput|Mrows|completed|FAILED|died' | head -5
echo "--- windowed report ---"; "$SC/window_report.sh" "$OUT/perf_${NAME}.data" "$OUT/symbols_${NAME}.txt" 200
