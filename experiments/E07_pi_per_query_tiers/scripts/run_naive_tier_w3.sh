#!/bin/bash
# Pi naive PER-QUERY tiers at W3: stateless (10 queries x 10 reps) then stateful (3 x 10), foreground, sampler on.
# LAUNCH: setsid nohup ~/powertest/run_naive_tier_w3.sh > ~/powertest/naive_tier_w3_run.log 2>&1 < /dev/null &
set -u
export LD_LIBRARY_PATH=/home/pi/data/runtime-libs
ulimit -n 65536
cd /home/pi/data/repos/piparse-bench
LOG=$HOME/powertest/naive_tier_w3_continuity.log
snap() { echo "$(date +%FT%T) $1 $(vcgencmd get_throttled) clock=$(vcgencmd measure_clock arm | cut -d= -f2) $(vcgencmd measure_temp) gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor) memavail_kB=$(awk '/MemAvailable/{print $2}' /proc/meminfo) max_current=$(od -An -tx1 /proc/device-tree/chosen/power/max_current | tr -d ' ')" >> "$LOG"; }
pkill -x main 2>/dev/null
sed "s#OUT=/home/pi/powertest/naive_w3_scale.tsv#OUT=/home/pi/powertest/naive_tier_w3_scale.tsv#" "$HOME/powertest/naive_w3_sampler.sh" > "$HOME/powertest/naive_tier_w3_sampler.sh"; chmod +x "$HOME/powertest/naive_tier_w3_sampler.sh"
"$HOME/powertest/naive_tier_w3_sampler.sh" & SAMPLER=$!
snap PREFLIGHT
for t in stateless stateful; do
  snap "START $t"
  PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run "experiments/pi_naive_${t}_w3.yaml"
  snap "END $t exit=$?"
done
snap DONE
kill "$SAMPLER" 2>/dev/null
