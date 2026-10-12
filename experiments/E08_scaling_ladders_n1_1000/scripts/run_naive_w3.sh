#!/bin/bash
# W3 naive ladder on the Pi: parts a->b->c->d in sequence, foreground, with the 5 s resource sampler.
# LAUNCH (only after pre-flight: get_throttled 0x0, 2.4 GHz under load, governor decided, :8080 free):
#   setsid nohup ~/powertest/run_naive_w3.sh > ~/powertest/naive_w3_run.log 2>&1 &
# PROGRESS: ~/powertest/naive_w3_run.log | naive_w3_continuity.log | naive_w3_scale.tsv | results/logs/pbench_run_*.log
set -u
export LD_LIBRARY_PATH=/home/pi/data/runtime-libs
ulimit -n 65536
cd /home/pi/data/repos/piparse-bench
LOG=$HOME/powertest/naive_w3_continuity.log
snap() { echo "$(date +%FT%T) $1 $(vcgencmd get_throttled) clock=$(vcgencmd measure_clock arm | cut -d= -f2) $(vcgencmd measure_temp) gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor) memavail_kB=$(awk '/MemAvailable/{print $2}' /proc/meminfo) max_current=$(od -An -tx1 /proc/device-tree/chosen/power/max_current | tr -d ' ')" >> "$LOG"; }
pkill -x main 2>/dev/null
"$HOME/powertest/naive_w3_sampler.sh" & SAMPLER=$!
snap PREFLIGHT
for p in a b c d; do
  snap "START $p"
  PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run "experiments/pi_naive_scaling_w3_$p.yaml"
  snap "END $p exit=$?"
done
snap DONE
kill "$SAMPLER" 2>/dev/null
