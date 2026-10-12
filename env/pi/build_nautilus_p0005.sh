#!/bin/bash
# Rebuild the dev image nautilus (REF 85c19150 + port patches 0001-0005, incl. the aarch64 EH strip) INSIDE the image
# and commit the result as nebulastream/nes-development:local-piparse-inl (2026-10-06). Log: ~/powertest/nautilus_build_2026-10-06.log
set -uxo pipefail
IMG=nebulastream/nes-development:local-piparse
NEWTAG=nebulastream/nes-development:local-piparse-inl
TB=/home/pi/data/src/nautilus-85c19150-p0001-0005.tar.gz
WORK=/home/pi/data/nautilus-build
mkdir -p "$WORK"; cp -f "$TB" "$WORK/"
date +%FT%T
docker rm -f naut-build >/dev/null 2>&1 || true
docker run -d --name naut-build --user root -v "$WORK:/nb" "$IMG" sleep infinity
docker exec naut-build bash -c '
set -euxo pipefail
cd /nb && rm -rf src build stage && mkdir src && tar xzmf nautilus-85c19150-p0001-0005.tar.gz -C src --strip-components=1
cmake -S src -B build -G Ninja \
  -DCMAKE_SYSTEM_NAME=Linux -DCMAKE_CROSSCOMPILING=OFF \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=clang-19 -DCMAKE_CXX_COMPILER=clang++-19 \
  -DCMAKE_C_FLAGS="-fPIC" -DCMAKE_CXX_FLAGS="-std=c++23 -stdlib=libc++ -fPIC" \
  -DCMAKE_EXE_LINKER_FLAGS="-lc++ -fuse-ld=mold" -DCMAKE_SHARED_LINKER_FLAGS="-lc++ -fuse-ld=mold" -DCMAKE_MODULE_LINKER_FLAGS="-lc++ -fuse-ld=mold" \
  -DBUILD_SHARED_LIBS=OFF -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_PREFIX_PATH=/vcpkg/installed/arm64-linux-none-libcxx \
  -DCMAKE_INSTALL_PREFIX=/nb/stage \
  -DMLIR_DIR=/clang/lib/cmake/mlir \
  -DENABLE_TESTS=OFF -DENABLE_MLIR_BACKEND=ON -DENABLE_LOGGING=OFF -DENABLE_BC_BACKEND=OFF -DENABLE_C_BACKEND=OFF -DENABLE_STACKTRACE=OFF \
  -DUSE_EXTERNAL_MLIR=ON -DUSE_EXTERNAL_SPDLOG=ON -DUSE_EXTERNAL_FMT=ON 2>&1 | tee /nb/configure.log
grep -n -i "inlining\|not supported\|warning" /nb/configure.log || true
echo "InliningPass targets: $(ninja -C build -t targets all | grep -c InliningPass || true)"
ninja -C build -j4 2>&1 | tee /nb/ninja.log | tail -3
ninja -C build install 2>&1 | tail -2
ls -la /nb/stage/lib/
echo "markers libnautilus: $(nm -C /nb/stage/lib/libnautilus.a | grep -c "stripExceptionHandling\|isFoldableLibcName")"
echo "markers plugin: $(nm -C /nb/stage/lib/libInliningPass.so | grep -c isFoldableLibcName)"
test -f /nb/stage/lib/libInliningPass.so
test -f /nb/stage/lib/libnautilus.a
R=/vcpkg/installed/arm64-linux-none-libcxx
cp -a $R/lib/libnautilus.a /nb/libnautilus.a.old; cp -a $R/lib/libInliningPass.so /nb/libInliningPass.so.old
diff -rq /nb/stage/include/nautilus $R/include/nautilus || true
cp -a /nb/stage/lib/libnautilus.a $R/lib/libnautilus.a
cp -a /nb/stage/lib/libInliningPass.so $R/lib/libInliningPass.so
rm -rf $R/include/nautilus && cp -a /nb/stage/include/nautilus $R/include/nautilus
chown -R 1000:1000 $R/lib/libnautilus.a $R/lib/libInliningPass.so $R/include/nautilus
ls -la $R/lib/libnautilus.a $R/lib/libInliningPass.so
'
rc=$?
if [ $rc -eq 0 ]; then
  docker commit --change "USER pi" naut-build "$NEWTAG" && docker rm -f naut-build && echo "NAUTILUS_BUILD_DONE $NEWTAG"
else
  echo "NAUTILUS_BUILD_FAILED rc=$rc"
fi
date +%FT%T
