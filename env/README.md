# Environment

## 1. Hardware the paper measured on

| | Threadripper ("TR", reference box) | Raspberry Pi 5 ("Pi", edge box) |
| --- | --- | --- |
| CPU | AMD Ryzen Threadripper PRO 5965WX, 24 cores (SMT present, **unused**: W23 workers + 1 io thread), 3.8 GHz base / ~4.3–4.4 GHz all-core measured | Broadcom BCM2712, 4× Cortex-A76 @ 2.4 GHz (Pi 5 Rev 1.1) |
| Caches | 64 KB L1 (32 I + 32 D) + 512 KB L2 per core; 4 CCX × 6 cores × 32 MB L3 | 64 KB L1, 512 KB L2 per core, 2 MB shared L3 |
| Memory | 64 GB DDR4, ~83 GB/s measured read peak | 16 GB LPDDR4X |
| Storage | NVMe (datasets page-cache resident during runs: `warm_read: true`) | 500 GB NVMe (data + builds), OS on microSD |
| OS / kernel | Ubuntu 24.04, Linux 6.8 | Raspberry Pi OS 64-bit (Debian 13) |
| Governor | `performance` | `ondemand` (holds 2.4 GHz under load — verified every run) |
| Power | — | **27 W official PSU.** A 900 mA source throttled the Pi to 1.0 GHz for 2026-09-09→22 while `cpufreq` kept reporting 2.4 GHz; every Pi run cited by the paper post-dates the fix and passed the pre-flight `vcgencmd get_throttled == 0x0` + `vcgencmd measure_clock arm ≈ 2.4 GHz under load` |

Parallelism budgets (identical per engine on a box): TR = NES W23 + io1, Flink parallelism 23, Spark `local[23]`
with a single reader; Pi = NES W3 + io1, Flink p=3, Spark `local[3]`.

## 2. Software

| component | version / pin |
| --- | --- |
| NebulaStream engine | github.com/ANON-ACCOUNT/nebulastream-snapshot, branch `benchmark-piparse-lazyparse-fast-csv`, **tag `piparse-artifact-v1`** (184ec91f5051d40f8af04f0b3ffc3c0dfea7d9ab) |
| Nautilus JIT | vcpkg overlay port `vcpkg/vcpkg-registry/ports/nautilus`: REF 85c19150d9bb7e8cca3051e67e04e76045462379 + patches 0001–0005 (0005 = aarch64 EH strip, inert on x86) |
| LLVM / MLIR (JIT backend) | 21.1.8 (vcpkg `llvm` overlay port on the host route; prebuilt `nes-llvm-21-with-fix-173075` in the dev image) |
| Host compiler (TR) | Ubuntu clang 19.1.1, libc++ (triplet `x64-linux-none-libcxx`), mold linker, CMake 3.28.3, Ninja |
| vcpkg | manifest `vcpkg/vcpkg.json`, builtin-baseline `4334d8b4c8916018600212ab4dd4bbdc343065d1`; TR clone at f6735d5aa1 |
| Dev container | `nebulastream/nes-development` (built from `docker/dependency/*.dockerfile`; tag = `docker/dependency/hash_dependencies.sh` of the checkout; local TR image digest `sha256:ed44856bf534bf86e18c5e06c7cf0522a0ec7298edc0b9553af508dfc0d71715`) |
| Pi image | `nebulastream/nes-development:local-piparse` (arm64 dev image, nautilus prebuilt with patches 0001–0003) → **`local-piparse-inl`** (image id cf9906b2c4c2) = the same image with nautilus rebuilt from `pi/nautilus-85c19150-p0001-0005.tar.gz` by `pi/build_nautilus_p0005.sh` |
| Benchmark harness | github.com/ANON-ACCOUNT/piparse-bench-snapshot, **tag `piparse-artifact-v1`** (33e76034c04bb255b9d11dc3500b3afdc49a718c); Python 3.12.3, uv 0.9.24 (`uv sync`), duckdb 1.5.4, matplotlib 3.11.0, pydantic 2.13.4 |
| TCP generator | `piparse-bench/generator` (Rust, cargo 1.89.0; `cargo build --release` → `target/release/tcp-generator`) |
| Flink arm | PyFlink `apache-flink 2.1.3` (pin `>=2.0,<2.2`), OpenJDK 11.0.32.1, custom sinks `piparse-bench/flink-ext` (`./build.sh`, javac against the venv's own Flink jars) |
| Spark arm | PySpark 3.5.9, custom file-microbatch source `piparse-bench/spark-ext` (`./build.sh`) |
| Profiling (Fig1 CPU shares) | linux `perf` (per-thread attribution, `perf_event_paranoid ≤ 1`), async-profiler 4.1 for Flink |

## 3. Building the engine

`tr/build_release.sh` configures and builds the worker, `nes-cli`, the systest driver and the two isolated rigs
with the exact CMake options of the paper's binaries (Release, `-march=native`, large tests on). Two routes:

- **Host route (what produced the TR numbers).** `clang-19`, cmake, ninja, mold, python3, Java (ANTLR jar is
  fetched by cmake). vcpkg builds all dependencies from the manifest on first configure (1–2 h; LLVM/MLIR are
  vcpkg ports). `NES_SRC=<checkout> NES_BUILD_DIR=<dir> ./tr/build_release.sh`.
- **Container route (the project's supported route; same options).** Build the dev image from the checkout
  (`docker build -f docker/dependency/Base.dockerfile`, then `Dependency.dockerfile` with
  `ARCH=x64 STDLIB=libcxx SANITIZER=none`, then `Development.dockerfile`; or pull the tag printed by
  `docker/dependency/hash_dependencies.sh`), then `NES_DEV_IMAGE=<image> ./tr/build_release.sh`. The engine's own
  helper `.claude/skills/nes-build/in-docker.sh` wraps the same `docker run --workdir <repo> -v <repo>:<repo>`.

Both routes produce `<build>/nes-single-node-worker/nes-single-node-worker` and `<build>/nes-frontend/apps/nes-cli`,
which pbench starts per run (`--build-dir`). ⚠️ A `-march=native` binary must be built on the box it is measured
on. ⚠️ Do not reconfigure an existing host build after changing a vcpkg port: manifest mode rebuilds the port
(nautilus ≈ 10 min, LLVM ≈ 1 h).

## 4. Building for the Raspberry Pi (aarch64)

The Pi has no internet, so the recipe is offline: `pi/build_nautilus_p0005.sh` rebuilds nautilus from the shipped
patched source tarball **inside** the arm64 dev image (clang-19, `-std=c++23 -stdlib=libc++`, external
MLIR/fmt/spdlog from `/vcpkg/installed/arm64-linux-none-libcxx`, `CMAKE_SYSTEM_NAME=Linux` so nautilus's own ARM gate
on the pass plugin stays off), installs it over the image's prebuilt copy and `docker commit`s the result as
`nes-development:local-piparse-inl`; `pi/run_pi_build_e.sh` then builds worker + nes-cli with `-DNES_INLINE_ON_ARM=ON`
(ccache with `CCACHE_RECACHE=1` so the inlining-pass targets are recompiled against the new plugin). With network
access the equivalent is a normal arm64 dev-image build of the engine at this tag (the port carries 0005).
`pi/checksum_ab.sh` is the correctness gate used on the Pi (10-query checksums, inlining on vs off: identical).
Pre-flight before any Pi measurement: `vcgencmd get_throttled` must print `0x0`, `vcgencmd measure_clock arm` ≈ 2.4 GHz
under load, governor `performance` or `ondemand`.

## 5. Benchmark harness

```
git clone https://github.com/ANON-ACCOUNT/piparse-bench-snapshot && cd piparse-bench && git checkout piparse-artifact-v1
uv sync                                   # .venv with duckdb/matplotlib/pydantic; add: uv pip install -e ".[flink]" for Flink
(cd generator && cargo build --release)   # TCP generator (many-source TCP experiments)
(cd flink-ext && ./build.sh); (cd spark-ext && ./build.sh)   # only for the Flink / Spark arms
```

Running: `pkill -9 -x main; PBENCH_KEEP_LOGS=1 uv run python bench.py run experiments/<exp>.yaml --build-dir
$NES_BUILD_DIR --worker-port 9099 [--detach --log-file <log>]`. Results land in `results/piparse_bench.duckdb`
(tables `runs`, `aggregated`; every `pbench run` stamps one `run_group` and the engine's `git_commit`). pbench
checks that the engine checkout is on the branch the experiment names (`defaults.branch:`); check out the branch
at the tag (`git checkout -B benchmark-piparse-lazyparse-fast-csv piparse-artifact-v1`) rather than a detached tag.
Each experiment yaml's `description:` carries its exact `RUN:` line and the gotchas learned while running it.
