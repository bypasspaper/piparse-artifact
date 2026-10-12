#!/usr/bin/env bash
# Profile one Fig-1 TEASER optimised query: launch warm InMemory window in background, attach nes-profile,
# record, dump full per-comm/per-symbol flat report, clean up.  usage: profile_opt_one.sh <q0|q2mod|ysb> [secs] [freq]
set -u
NAME="$1"; SECS="${2:-20}"; FREQ="${3:-4000}"; STAT="${4:-1}"; STATOPT=""; [ "$STAT" = "1" ] && STATOPT="--stat"
SCRATCH=/tmp/claude-1000/-home-user-work-nebulastream-public/f9057d9a-82ca-4860-8efc-985fed7b7954/scratchpad
REPO=/home/user/work/nebulastream-public
EXP="$SCRATCH/fig1_opt_prof_${NAME}.yaml"
OUT="$SCRATCH/optprof_${NAME}"
mkdir -p "$OUT"
cd ~/work/piparse-bench || exit 2
pkill -9 -x main 2>/dev/null; sleep 1
PBENCH_KEEP_LOGS=1 uv run python bench.py run --build-dir "$REPO/cmake-build-release" --worker-port 9099 "$EXP" > "$OUT/bench.log" 2>&1 &
BPID=$!
NES_PROFILE_OUTDIR="$OUT" "$REPO/.claude/skills/nes-profile/nes-profile.sh" --port 9099 --secs "$SECS" --freq "$FREQ" $STATOPT --out "$NAME" > "$OUT/profile_report.txt" 2>&1
RC=$?
if [ -f "$OUT/perf_${NAME}.data" ]; then
  perf report -i "$OUT/perf_${NAME}.data" --stdio -g none --percent-limit 0 --sort comm,dso,symbol 2>/dev/null > "$OUT/symbols_${NAME}.txt"
fi
# let the window finish on its own so bench.log gets the throughput line (bounded wait), then clean up
for i in $(seq 1 60); do kill -0 "$BPID" 2>/dev/null || break; sleep 5; done
kill "$BPID" 2>/dev/null; pkill -9 -x main 2>/dev/null; sleep 1
echo "=== RC=$RC  outputs in $OUT ==="
sed -n '1,70p' "$OUT/profile_report.txt"
echo "--- bench.log ---"; grep -iE 'throughput|Mrows|completed|FAILED|→' "$OUT/bench.log" | head
