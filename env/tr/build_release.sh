#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Configure + build the two binaries every Threadripper experiment uses (nes-single-node-worker, nes-cli) and the
# two isolated rigs, exactly as the paper's numbers were taken: Release, -O3 -march=native (NES_BUILD_NATIVE),
# large test data enabled, error-level logging, no sanitizer, Ninja.
#
# Two routes (same CMake options; pick one):
#   HOST   (what produced the Threadripper numbers): Ubuntu 24.04, clang-19 (Ubuntu clang 19.1.1), cmake >= 3.28,
#          ninja, mold, python3, a vcpkg clone. vcpkg builds every dependency from the manifest (vcpkg/vcpkg.json,
#          builtin-baseline 4334d8b4c8916018600212ab4dd4bbdc343065d1, overlay ports vcpkg/vcpkg-registry/ports incl.
#          the patched nautilus, triplet x64-linux-none-libcxx) -- first configure takes 1-2 h (LLVM/MLIR 21 is a
#          dependency port).
#   DOCKER (the project's supported route): the nebulastream/nes-development image carries every dependency
#          prebuilt (NES_PREBUILT_VCPKG_ROOT). Build the image from the engine tree
#          (docker/dependency/{Base,Dependency,Development,DevelopmentLocal}.dockerfile; see env/README.md) or pull
#          the tag your checkout's CI computed (docker/dependency/hash_dependencies.sh prints the hash).
#
# Usage:
#   NES_SRC=<engine checkout at tag piparse-artifact-v1> NES_BUILD_DIR=<dir> ./build_release.sh            # host
#   NES_SRC=... NES_BUILD_DIR=... NES_DEV_IMAGE=nebulastream/nes-development:<tag> ./build_release.sh      # docker
# Optional: VCPKG_ROOT=<vcpkg clone> (host route; else cmake clones one into the build tree), JOBS=<n>.
set -euo pipefail
NES_SRC="${NES_SRC:-$HOME/work/nebulastream-public}"
NES_BUILD_DIR="${NES_BUILD_DIR:-$NES_SRC/cmake-build-release}"
JOBS="${JOBS:-$(nproc)}"
CMAKE_OPTS=(
  -G Ninja
  -DCMAKE_BUILD_TYPE=Release
  -DNES_BUILD_NATIVE=ON            # -march=native: the paper's binaries are tuned to the measuring machine
  -DENABLE_LARGE_TESTS=ON          # registers the large ExternalData sets (data/fetch_testdata.sh)
  -DNES_LOG_LEVEL=ERROR
  -DUSE_SANITIZER=none
  -DNES_ENABLE_PRECOMPILED_HEADERS=OFF
  -DNES_INLINE_ON_ARM=ON           # no-op on x86; gives an aarch64 build the Nautilus inlining pass (needs port patch 0005)
)
TARGETS=(nes-single-node-worker nes-cli systest formatter-scaling-benchmark formatter-latency-benchmark)

if [ -n "${NES_DEV_IMAGE:-}" ]; then
  run() { docker run --rm --user "$(id -u):$(id -g)" --workdir "$NES_SRC" -v "$NES_SRC:$NES_SRC" \
            -e NES_PREBUILT_VCPKG_ROOT "$NES_DEV_IMAGE" "$@"; }
  echo "[docker] image $NES_DEV_IMAGE"
else
  run() { "$@"; }
  export CC="${CC:-clang-19}" CXX="${CXX:-clang++-19}"
  if [ -n "${VCPKG_ROOT:-}" ]; then CMAKE_OPTS+=(-DCMAKE_TOOLCHAIN_FILE="$VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake"); fi
  echo "[host] CC=$CC CXX=$CXX"
fi
date +%FT%T
run cmake -S "$NES_SRC" -B "$NES_BUILD_DIR" "${CMAKE_OPTS[@]}"
run cmake --build "$NES_BUILD_DIR" -j"$JOBS" --target "${TARGETS[@]}"
date +%FT%T
ls -la "$NES_BUILD_DIR/nes-single-node-worker/nes-single-node-worker" "$NES_BUILD_DIR/nes-frontend/apps/nes-cli"
echo "BUILD_DONE  (worker at W23+io1 is the Threadripper configuration; pbench passes every worker flag per run)"
