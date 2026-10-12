#!/bin/bash
# Pi worker rebuild from the Threadripper source state (2026-10-06, nautilus 0001-0005 image, pass plugin refreshed: CCACHE_RECACHE). Log: ~/powertest/build_2026-10-06e.log
set -uxo pipefail
REPO=/home/pi/data/repos/nebulastream
BUILD=cmake-build-release-piparse
IMAGE=nebulastream/nes-development:local-piparse-inl
run() {
  docker run --rm --workdir "$REPO" -v "$REPO:$REPO" \
    -v /home/pi/data/ccache:/ccache -e CCACHE_DIR=/ccache -e CCACHE_RECACHE=1 \
    -v /home/pi/data/cargo/home:/cargo-home -e CARGO_HOME=/cargo-home -e CARGO_NET_OFFLINE=true \
    "$IMAGE" "$@"
}
date +%FT%T
run cmake -S . -B "$BUILD" -G Ninja -DCMAKE_BUILD_TYPE=Release -DNES_BUILD_NATIVE=ON -DENABLE_LARGE_TESTS=ON -DNES_INLINE_ON_ARM=ON \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache && \
run cmake --build "$BUILD" -j4 --target nes-single-node-worker nes-cli
rc=$?
date +%FT%T
ls -la --time-style=long-iso "$REPO/$BUILD/nes-single-node-worker/nes-single-node-worker" "$REPO/$BUILD/nes-frontend/apps/nes-cli"
[ $rc -eq 0 ] && echo "NES_BUILD_DONE" || echo "NES_BUILD_FAILED rc=$rc"
