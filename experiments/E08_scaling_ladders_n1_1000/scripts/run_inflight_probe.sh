#!/bin/bash
set -u
export LD_LIBRARY_PATH=/home/pi/data/runtime-libs
ulimit -n 65536
cd /home/pi/data/repos/piparse-bench
LOG=$HOME/powertest/inflight_probe_continuity.log
snap() { echo "$(date +%FT%T) $1 $(vcgencmd get_throttled) clock=$(vcgencmd measure_clock arm | cut -d= -f2) $(vcgencmd measure_temp) gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)" >> "$LOG"; }
pkill -x main 2>/dev/null
snap START
PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run experiments/pi_naive_inflight_probe.yaml
snap "DONE exit=$?"
