#!/usr/bin/env bash
# Fig1 TEASER v2 chain (2026-09-28): naive + optimised(overload ON) profiles for q0 / q2og / ysb, clean throughput, Flink q2og.
SC=/tmp/claude-1000/-home-user-work-nebulastream-public/f9057d9a-82ca-4860-8efc-985fed7b7954/scratchpad
cd ~/work/piparse-bench || exit 2
stamp() { echo "##### $1 $(date '+%H:%M:%S')"; }
ysb_retry() { local name=$1; for i in 1 2 3 4; do stamp "profile $name attempt $i"; $SC/profile_ysb_full.sh $name 8000 2>&1 | grep -v DIAG_ | grep -E 'throughput|FAILED|died|busy window|wrote|no busy' | cut -c1-140; if grep -q 'throughput=' $SC/optprof_$name/bench.log 2>/dev/null && [ -s $SC/optprof_$name/symbols_$name.txt ]; then echo "SUCCESS $name attempt $i"; return 0; fi; done; echo "GAVE UP $name"; return 1; }
pkill -9 -x main 2>/dev/null; sleep 1
for n in naive_q0 naive_q2og; do stamp "profile $n"; $SC/profile_opt_one.sh $n 20 4000 0 2>&1 | grep -v DIAG_ | grep -E 'RC=|per-thread split|throughput|FAILED|died' | head -5; done
ysb_retry naive_ysb
for n in q0 q2og; do stamp "profile $n (overload ON)"; $SC/profile_opt_one.sh $n 20 4000 0 2>&1 | grep -v DIAG_ | grep -E 'RC=|per-thread split|throughput|FAILED|died' | head -5; done
ysb_retry ysb
stamp "NES clean throughput"; pkill -9 -x main 2>/dev/null; sleep 1
PBENCH_KEEP_LOGS=1 uv run python bench.py run experiments/fig1_teaser_thru.yaml --build-dir ~/work/nebulastream-public/cmake-build-release --worker-port 9099 2>&1 | grep -v DIAG_ | grep -E '^\s+\[|→|FAILED|Done|WARNING'
stamp "Flink q2og profile"; pkill -9 -x main 2>/dev/null
$SC/profile_flink_one.sh q2og 2>&1 | grep -E 'JVM pid|RC=|throughput|FAILED|Done' | head -6
stamp "Flink q2og clean throughput"
uv run python bench.py run experiments/fig1_flink_thru_q2og.yaml --build-dir ~/work/nebulastream-public/cmake-build-release 2>&1 | grep -E '^\s+\[|→|FAILED|Done' | head -8
stamp "ALL DONE"
