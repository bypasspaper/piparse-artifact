#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# E07 — re-measure the Raspberry Pi 5 per-query tiers (optimised ctrl/ovl, native, naive W3) on build e.
# ESTIMATED WALL TIME: ~1 h 45 min on the Pi (Pi-clock 08:06 -> 09:47 on 2026-10-06 for the 6-tier _nbi chain, 442 runs);
#                      + ~45 min if you also re-take the naive W3 tiers under their original names (130 runs).
# Everything below runs ON THE PI (pi-box). Nothing here runs on the Threadripper except the export pull.
set -euo pipefail
PI_PBENCH=${PI_PBENCH:-/home/pi/data/repos/piparse-bench}     # Pi checkout of piparse-bench (tag piparse-artifact-v1)
PI_PBENCH_BIN=${PI_PBENCH_BIN:-/home/pi/data/pbench}           # wrapper: .venv/bin/python bench.py
cat <<EOF
# ---- Pi-side pre-flight (every run; the governor resets to ondemand on reboot) ----
sudo cpupower frequency-set -g performance          # or accept ondemand (holds 2.4 GHz under load)
vcgencmd get_throttled                              # MUST print throttled=0x0 (27 W PSU, max_current 5000 mA)
vcgencmd measure_clock arm                          # ~2400 MHz under 4-core load
pkill -x main || true; ss -ltnp | grep -q 8080 && echo "port 8080 busy" && exit 1

# ---- Pi-side: the per-query tiers on build e (worker built with NES_INLINE_ON_ARM=ON in the nautilus-0005 image,
#      see ../../env/pi/) -- exactly scripts/chain_nbi_only.sh ----
cd $PI_PBENCH; export LD_LIBRARY_PATH=/home/pi/data/runtime-libs; ulimit -n 65536
for e in pi_stateless_tier_nbi pi_stateful_tier_nbi pi_native_stateless_nbi pi_native_stateful_nbi \\
         pi_naive_stateless_w3_nbi pi_naive_stateful_w3_nbi; do
  PBENCH_KEEP_LOGS=1 $PI_PBENCH_BIN run experiments/\$e.yaml
done
#   The *_nbi yamls are verbatim copies of pi_stateless_tier / pi_stateful_tier (optimised: ctrl + ovl series, 7 reps),
#   pi_native_{stateless,stateful} (SystemNative in, NATIVE out) and pi_naive_{stateless,stateful}_w3 (yaml/ here) with
#   the experiment name suffixed; they exist only in the Pi checkout. The ctrl/ovl series definition is yaml/pi_*_tier_ovl.yaml.

# ---- Pi-side: export the raw run rows (DuckDB -> CSV), then pull them to the artifact (scripts/export_pi_tiers_build_e.sh) ----
#   produces results/pi/pi_tiers_{aug,nb,nbi}_raw.csv + pi_inline_verify_raw.csv

# ---- anywhere: rebuild the tidy medians + tables from the exports ----
python3 make_figure.py      # -> out/pi_tiers_build_e.csv, out/pi_tiers_build_e_tables.md (must equal data/ + expected/)
EOF
