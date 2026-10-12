#!/bin/bash
# The _nbi retake chain on the inlining binary (build e), WITHOUT the throughput gate (the fix is verified by IR + checksum A/B).
export LD_LIBRARY_PATH=/home/pi/data/runtime-libs; ulimit -n 65536
C=$HOME/powertest/tiers_nbi_continuity.log
snap() { echo "$(date +%FT%T) $1 $(vcgencmd get_throttled) clock=$(vcgencmd measure_clock arm | cut -d= -f2) $(vcgencmd measure_temp) gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor) memavail_kB=$(grep MemAvailable /proc/meminfo | awk "{print \$2}")" >> "$C"; }
cd /home/pi/data/repos/piparse-bench; pkill -x main 2>/dev/null
snap "CHAIN nbi START (build e, gate skipped)"
for e in pi_stateless_tier_nbi pi_stateful_tier_nbi pi_native_stateless_nbi pi_native_stateful_nbi pi_naive_stateless_w3_nbi pi_naive_stateful_w3_nbi; do
  snap "START $e"
  PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run "experiments/$e.yaml" >> $HOME/powertest/tiers_nbi_run.log 2>&1
  snap "END $e exit=$?"
done
snap DONE
