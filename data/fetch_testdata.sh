#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Fetch the public benchmark datasets through the engine's CMake ExternalData mechanism.
#
# The engine tree carries .md5 stubs under nes-systests/testdata/large/<suite>/<file>.md5; with
# ENABLE_LARGE_TESTS=ON the `test-data` target downloads every stub's object from
#   https://DATA-HOST.example/share/download?files=MD5_<hash>
# into <build>/ExternalData/Objects/MD5/ and symlinks <build>/nes-systests/testdata/large/<suite>/<file>.
# Files needed by this artifact: nexmark/bid_6GB.csv (6.68 GB), nexmark/bid_653M.csv, nexmark/person_840MB.csv,
# nexmark/auction_707MB.csv, ysb/ysb_10k_data_479M.csv, cluster_monitoring/google-cluster-data-original_1G.csv.
# Expect ~12 GB of downloads; ExternalData_TIMEOUT_ABSOLUTE is 1200 s per object.
#
# Usage: NES_SRC=<engine checkout> NES_BUILD_DIR=<build dir> ./fetch_testdata.sh
set -euo pipefail
NES_SRC="${NES_SRC:-$HOME/work/nebulastream-public}"
NES_BUILD_DIR="${NES_BUILD_DIR:-$NES_SRC/cmake-build-release}"
[ -f "$NES_BUILD_DIR/CMakeCache.txt" ] || { echo "configure the build first (env/tr/build_release.sh)"; exit 1; }
grep -q "ENABLE_LARGE_TESTS:BOOL=ON" "$NES_BUILD_DIR/CMakeCache.txt" || { echo "build must be configured with -DENABLE_LARGE_TESTS=ON"; exit 1; }
cmake --build "$NES_BUILD_DIR" --target test-data
ls -la "$NES_BUILD_DIR/nes-systests/testdata/large/nexmark/" "$NES_BUILD_DIR/nes-systests/testdata/large/ysb/"
echo "Derived datasets (bid_strings_3GB.* twins, bid_1GB, synthetic spanning files) are NOT fetched; see data/README.md §2-3."
