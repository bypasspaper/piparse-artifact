#!/usr/bin/env bash
# Motivation figure sweep (FIGURE_SPEC.md). MACHINE=tr (this box) | pi (over ssh, inside the Pi's dev container).
set -uo pipefail
MACHINE=${MACHINE:?tr|pi}
OUT=$(cd "$(dirname "$0")" && pwd)
STREAMS=${STREAMS:-1,2,4,8,16,32,64,128,256,512}                # user 2026-09-09: up to 512 queries
PI_STREAMS=${PI_STREAMS:-1,2,4,8,16,32,64,128,256,512}   # 16 GiB: ~4.5 MB JIT per compiled query stage
LOWN=${LOWN:-1,2,4,8,16,32}          # spin=50 also run here (design-best envelope below the knee)
REPS=${REPS:-3}; WARMUP=${WARMUP:-1}; WINDOW=${WINDOW:-5}
DW=${DW:-1}                          # buffers in flight per query (1 = one at a time; 64 = engine per-source cap)
CAP=${CAP:-0}                        # global admission cap on buffers in flight (engine: 1000); 0 = none
CUT=${CUT:-scan}                     # chunker cut method: scan (default) | quote | index | memchr (CSV arm label chunker_<cut>)
WS=${WS:-2048}                       # NES_LAT_WS_MIB: data working set floor (MiB) at every N -> streaming regime everywhere (TR trough fix 2026-09-10)
ARMS=${ARMS:-"dpp 1|gprivate 1|gprivate 4|chunker 4"}
HEAVY=${HEAVY:-}                     # NES_LAT_HEAVY=<fraction>,<mult>: per-query cost skew (2026-09-22; applied to every arm alike)
BURST=${BURST:-}                     # NES_LAT_BURST=<active_ms>,<idle_ms>: bursty streams (2026-09-22; applied to every arm alike)
GENS=${GENS:-$([ "$DW" -ge 32 ] && echo 32 || echo 8)}   # control-block reuse distance = 72*32 = 2304 buffers at D=64 (queue lag seen: ~600 under interference)
COMMON="NES_LAT_D=$DW NES_LAT_CAP=$CAP NES_LAT_CUT=$CUT NES_LAT_WS_MIB=$WS NES_LAT_RING=16 NES_LAT_GENS=$GENS NES_LAT_FMT_KIB=32 NES_LAT_REPS=$REPS NES_LAT_WARMUP_S=$WARMUP NES_LAT_WINDOW_S=$WINDOW${HEAVY:+ NES_LAT_HEAVY=$HEAVY}${BURST:+ NES_LAT_BURST=$BURST}"
ARGS="128 5 f1 FNATTR FastUINT64"
mkdir -p "$OUT/logs"
if [ "$MACHINE" = tr ]; then
  REPO=/home/user/work/nebulastream-public
  BIN=$REPO/cmake-build-release/nes-input-formatters/tests/Benchmark/formatter-latency-benchmark
  DATA=$REPO/nes-systests/testdata/large/formatter/bench_5xUINT64_512m.csv
  FNATTR=$REPO/testing/configurations/invokeModeConfGlobalFnAttr.yaml
  CSV=$OUT/sweep_tr${TAG:+_$TAG}${DW:+_D$DW}${CAP:+_C$CAP}.csv; W=${W:-24}; CPUS=0-23     # pooled designs get EVERY core (no producer thread in the closed loop)
  runbin() { taskset -c $CPUS env "$@"; }
else
  PI='pi@PI-LINK-LOCAL-ADDRESS'
  R=/home/pi/data/repos/nebulastream
  BIN=$R/cmake-build-release-piparse/nes-input-formatters/tests/Benchmark/formatter-latency-benchmark
  DATA=$R/nes-systests/testdata/large/formatter/bench_5xUINT64_512m.csv
  FNATTR=$R/testing/configurations/invokeModeConfGlobalFnAttr.yaml
  CSV=$R/latency_fig_pi${TAG:+_$TAG}${DW:+_D$DW}${CAP:+_C$CAP}.csv; W=${W:-4}; CPUS=0-3; STREAMS=$PI_STREAMS
  # everything after the env assignments is the benchmark command; run it inside the container on the Pi
  runbin() { ssh -o BatchMode=yes "$PI" "docker run --rm --cpuset-cpus $CPUS -v $R:$R -w $R nebulastream/nes-development:local-piparse env $*"; }
fi
echo "sweep($MACHINE${TAG:+/$TAG}) started $(date -Is) streams=$STREAMS reps=$REPS window=$WINDOW W=$W D=$DW cap=$CAP heavy=${HEAVY:-off} burst=${BURST:-off} arms=$ARMS" | tee -a "$OUT/logs/run_${MACHINE}.meta"
# Pi: the firmware throttles the ARM clock under a weak supply while cpufreq keeps reporting 2.4 GHz (2026-09-09..22 ran at
# 1.0 GHz unnoticed) -- record the throttle flag + measured clock before and after every arm, in the log AND the meta file
pistate() { [ "$MACHINE" = pi ] || return 0; local s; s=$(ssh -o BatchMode=yes "$PI" 'echo "throttled=$(vcgencmd get_throttled | cut -d= -f2) arm=$(( $(vcgencmd measure_clock arm | cut -d= -f2) / 1000000 ))MHz temp=$(vcgencmd measure_temp | cut -d= -f2) gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"' 2>&1); echo "pi-state $1: $s"; echo "$(date -Is) $1 $s" >> "$OUT/logs/run_${MACHINE}.meta"; }
run() { # arm k spin streams
  local arm=$1 k=$2 spin=$3 streams=$4
  echo "=== $MACHINE arm=$arm k=$k spin=$spin N=$streams $(date -Is)"
  pistate "before $arm k=$k spin=$spin"
  runbin NES_LAT_ARM=$arm NES_LAT_K=$k NES_LAT_SPIN_US=$spin NES_LAT_STREAMS=$streams NES_LAT_WORKERS=$W $COMMON NES_LAT_OUT=$CSV \
    "$BIN" "$DATA" 128 5 f1 "$FNATTR" FastUINT64 2>&1 | grep -v DIAG_ | tee "$OUT/logs/${MACHINE}${TAG:+_$TAG}_${arm}$([ "$CUT" != scan ] && echo "_$CUT")_k${k}_spin${spin}.txt"
  pistate "after $arm k=$k spin=$spin"
}
IFS="|" read -ra ARMLIST <<< "$ARMS"
for spec in "${ARMLIST[@]}"; do
  set -- $spec
  run $1 $2 0 "$STREAMS"
  run $1 $2 50 "$LOWN"
done
if [ "$MACHINE" = pi ]; then rsync -a -e 'ssh -o BatchMode=yes' "pi@[PI-LINK-LOCAL-ADDRESS]:$CSV" "$OUT/sweep_pi${TAG:+_$TAG}${DW:+_D$DW}${CAP:+_C$CAP}.csv"; fi
echo "sweep($MACHINE) finished $(date -Is)" | tee -a "$OUT/logs/run_${MACHINE}.meta"
