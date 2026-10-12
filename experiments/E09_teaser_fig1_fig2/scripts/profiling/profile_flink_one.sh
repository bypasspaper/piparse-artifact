#!/usr/bin/env bash
# Profile one Fig1-on-Flink query: run the pbench flink arm with async-profiler loaded into the
# pyflink gateway JVM (JVM_ARGS is honoured by pyflink_gateway_server.py), cpu event @4 kHz,
# per-thread collapsed stacks with kernel/inlined annotations, for the WHOLE job. Also dumps
# jstack (tid->thread-name map) + per-thread CPU (top -H) once the pipeline threads are up.
set -u
NAME="$1"
SCRATCH=/tmp/claude-1000/-home-user-work-nebulastream-public/f9057d9a-82ca-4860-8efc-985fed7b7954/scratchpad
REPO=/home/user/work/nebulastream-public
AP=/home/user/.local/share/JetBrains/Toolbox/apps/clion/lib/async-profiler/amd64/libasyncProfiler.so
EXP=~/work/piparse-bench/experiments/fig1_flink_prof_${NAME}.yaml
OUT="$SCRATCH/flink_prof_${NAME}"
mkdir -p "$OUT"
cd ~/work/piparse-bench || exit 2

export JVM_ARGS="-XX:+UnlockDiagnosticVMOptions -XX:+DebugNonSafepoints -agentpath:$AP=start,event=cpu,interval=250us,threads,ann,collapsed,file=$OUT/prof_%p.collapsed"
T0=$(date +%s)
PBENCH_KEEP_LOGS=1 uv run python bench.py run --build-dir "$REPO/cmake-build-release" "$EXP" > "$OUT/bench.log" 2>&1 &
BPID=$!

# Find the gateway JVM started after T0 (PythonGatewayServer in cmdline).
JPID=""
for i in $(seq 1 120); do
  for p in $(pgrep -x java); do
    if tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -q PythonGatewayServer; then
      st=$(stat -c %Y /proc/$p 2>/dev/null || echo 0)
      [ "$st" -ge "$T0" ] && JPID=$p
    fi
  done
  [ -n "$JPID" ] && break
  sleep 1
done
echo "JVM pid: ${JPID:-NOT FOUND}" | tee "$OUT/jvm.txt"

# Wait for the pipeline threads, let the JIT settle, then snapshot thread names + per-thread CPU.
if [ -n "$JPID" ]; then
  for i in $(seq 1 180); do
    if jstack "$JPID" 2>/dev/null | grep -q "Source Data Fetcher"; then break; fi
    sleep 1
  done
  sleep 20
  jstack "$JPID" > "$OUT/jstack.txt" 2>&1
  top -H -b -n 1 -p "$JPID" > "$OUT/top_threads.txt" 2>&1
  ps -L -o tid,pcpu,comm -p "$JPID" > "$OUT/ps_threads.txt" 2>&1
fi

wait "$BPID"; RC=$?
echo "=== RC=$RC  outputs in $OUT ==="
ls -la "$OUT"
grep -iE 'throughput|Mrows|completed|failed|Done' "$OUT/bench.log" | tail -5
