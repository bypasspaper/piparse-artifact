#!/bin/bash
# After build e (nautilus 0001-0005 image): run the inlining verification probe, gate, then launch the full _nbi chain.
export LD_LIBRARY_PATH=/home/pi/data/runtime-libs; ulimit -n 65536
L=$HOME/powertest/build_2026-10-06e.log; C=$HOME/powertest/tiers_nbi_continuity.log
snap() { echo "$(date +%FT%T) $1 $(vcgencmd get_throttled) clock=$(vcgencmd measure_clock arm | cut -d= -f2) $(vcgencmd measure_temp) gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor) memavail_kB=$(awk '/MemAvailable/{print $2}' /proc/meminfo)" >> "$C"; }
until grep -qE 'NES_BUILD_DONE|NES_BUILD_FAILED|ninja: build stopped' "$L" 2>/dev/null; do sleep 30; done
grep -q NES_BUILD_DONE "$L" || { snap "BUILD FAILED -> stop"; exit 2; }
cd /home/pi/data/repos/piparse-bench; pkill -x main 2>/dev/null
snap "START verify"
PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run experiments/pi_inline_verify.yaml > $HOME/powertest/verify_run.log 2>&1
snap "END verify exit=$?"
python3 - "$HOME/powertest/verify_run.log" >> "$C" <<'PY'
import re, sys, statistics
res = {}; k = None
for line in open(sys.argv[1]):
    m = re.search(r"\] (\S+)/(\S+) x=\d+ rep=", line)
    if m: k = (m.group(1), m.group(2)); continue
    m = re.search(r"→ ([0-9.]+) MB/s", line)
    if m and k: res.setdefault(k, []).append(float(m.group(1)))
med = {k: statistics.median(v) for k, v in res.items()}
q0 = med.get(("q0", "ctrl"), 0); q2c = med.get(("q2_og", "ctrl"), 0); q2o = med.get(("q2_og", "ovl"), 0)
gain = q0 / 1329.2 if q0 else 0; ovl = q2o / q2c if q2c else 0
print(f"VERIFY q0 ctrl {q0:.1f} MB/s (no-inline binary 1329.2 -> x{gain:.2f}); q2_og ctrl {q2c:.1f} ovl {q2o:.1f} (ovl/ctrl {ovl:.2f}); q0 ovl {med.get(('q0','ovl'),0):.1f}")
ok = gain >= 1.10 and q2c > 0
print("VERIFY GATE", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
PY
if [ $? -ne 0 ]; then snap "GATE FAILED -> chain not launched"; exit 3; fi
snap "GATE PASSED -> launching _nbi chain"
for e in pi_stateless_tier_nbi pi_stateful_tier_nbi pi_native_stateless_nbi pi_native_stateful_nbi pi_naive_stateless_w3_nbi pi_naive_stateful_w3_nbi; do
  snap "START $e"
  PBENCH_KEEP_LOGS=1 /home/pi/data/pbench run "experiments/$e.yaml" >> $HOME/powertest/tiers_nbi_run.log 2>&1
  snap "END $e exit=$?"
done
snap DONE
