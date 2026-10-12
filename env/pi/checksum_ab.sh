#!/bin/bash
# Checksum A/B: inline binary (build e, nautilus 0001-0005) vs build d (no inlining) on the 10 stateless queries.
export LD_LIBRARY_PATH=/home/pi/data/runtime-libs; ulimit -n 65536
set -uo pipefail
B=/home/pi/data/repos/nebulastream/cmake-build-release-piparse/nes-single-node-worker
cd /home/pi/data/repos/piparse-bench
pkill -x main 2>/dev/null
cp -p $B/nes-single-node-worker $B/nes-single-node-worker.builde
echo "=== arm A: inline (build e)"; /home/pi/data/pbench run experiments/pi_stateless_checksum_inl.yaml > ~/powertest/checksum_inl.log 2>&1; grep -E "\] |checksum\]|Done:" ~/powertest/checksum_inl.log | sed "s/\[warm_read\].*//" | cut -c1-100
cp -p $B/nes-single-node-worker.buildd $B/nes-single-node-worker
echo "=== arm B: no inlining (build d)"; /home/pi/data/pbench run experiments/pi_stateless_checksum_noinl.yaml > ~/powertest/checksum_noinl.log 2>&1; grep -E "\] |checksum\]|Done:" ~/powertest/checksum_noinl.log | sed "s/\[warm_read\].*//" | cut -c1-100
cp -p $B/nes-single-node-worker.builde $B/nes-single-node-worker
echo "=== restored:"; ls -la --time-style=long-iso $B/nes-single-node-worker | awk "{print \$5, \$6, \$7}"; cmp $B/nes-single-node-worker $B/nes-single-node-worker.builde && echo "worker == build e"
echo "=== DIFF (checksum lines):"; diff <(grep -o "checksum\].*" ~/powertest/checksum_inl.log) <(grep -o "checksum\].*" ~/powertest/checksum_noinl.log) && echo "CHECKSUMS IDENTICAL"
