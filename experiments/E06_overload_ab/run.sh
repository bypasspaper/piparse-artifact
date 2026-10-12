#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Re-measure the overload A/B on the Threadripper (E06). Port of piparse-bench results/run_tr_ovl.sh.
# 2026-10-05: stateless 200 runs + stateful 60 runs = 23 min (11:46 -> 12:09).
set -u
PBENCH_DIR=${PBENCH_DIR:-$HOME/work/piparse-bench}
NES_BUILD_DIR=${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}
WORKER_PORT=${WORKER_PORT:-9099}
HERE=$(cd "$(dirname "$0")" && pwd)
echo "Estimated wall time: ~25 min (TR). Ctrl-C within 5 s to abort."; sleep 5
cd "$PBENCH_DIR"
if pgrep -x main >/dev/null; then echo "ABORT: a NES worker (main) is already running on this host"; exit 2; fi
mkdir -p results/logs; LOG=results/logs/tr_ovl_continuity.log
snap() { echo "$(date +%FT%T) $1 gov=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor 2>/dev/null) load=$(cut -d' ' -f1-3 /proc/loadavg)" >> "$LOG"; }
snap PREFLIGHT
for f in nes_simd_overload_stateless nes_simd_overload_stateful; do
  snap "START $f"
  PBENCH_KEEP_LOGS=1 uv run python bench.py run "experiments/$f.yaml" --build-dir "$NES_BUILD_DIR" --worker-port "$WORKER_PORT"
  snap "END $f exit=$?"
done
snap DONE
echo "Then: python3 $HERE/make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb   # edit TR_RG in the script to the new run groups"
cat <<'NOTE'
Pi arm (yaml/experiments/pi_{stateless,stateful}_tier_ovl.yaml; pbench checkout on the Pi, W3+io1, governor performance,
pre-flight vcgencmd get_throttled == 0x0): run both yamls with the Pi's pbench wrapper the same way; export the rows with
the Pi dump job (E07/E08). The 2026-10-05 Pi A/B ran on the Aug-23 binary (pre overload-fix) and is INVALID as an
overload verdict; the valid Pi ctrl/ovl numbers are the build-e _nbi series in E07.
NOTE
