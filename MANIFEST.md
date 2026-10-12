# Manifest — exact versions behind the submission (frozen 2026-10-12)

| component | identifier |
| --- | --- |
| Engine repository | `https://github.com/ANON-ACCOUNT/nebulastream-snapshot` |
| Engine branch / tag | `benchmark-piparse-lazyparse-fast-csv` @ **`piparse-artifact-v1`** = `184ec91f5051d40f8af04f0b3ffc3c0dfea7d9ab` (129 commits ahead of `main`) |
| Engine state the numbers were measured with | `b5d757c9f6` + the uncommitted benchmark overlay (knobs default off) — identical code to the tag: the overlay is the tag's last five commits (`f3688e254d` hoisting knobs, `f6c51243a6` VARSIZED literal/eq, `309b434ef6` TOFLOAT64/TOINT64, `026df3e3ac` latency rig, `184ec91f50` aarch64 + port patch 0005) |
| Nautilus (JIT) | overlay port `vcpkg/vcpkg-registry/ports/nautilus`: `nebulastream/nautilus` REF `85c19150d9bb7e8cca3051e67e04e76045462379`, SHA512 `a7183af0…40b9e`, patches `0001-disable-ubsan-function-call-check`, `0002-add-constant-byte-globals`, `0003-nonvolatile-mem-intrinsics`, `0004-preserve-libc-memcmp-name`, `0005-strip-eh-from-spliced-bitcode-on-aarch64`. TR host build used 0001–0004 (0005 is `#if __aarch64__`-guarded and changes nothing on x86); Pi build e used 0001–0005 |
| Patched nautilus source tarball (offline Pi build) | `env/pi/nautilus-85c19150-p0001-0005.tar.gz`, sha256 `f72732692ec124c015468b4f27fbd0111276df4b506e4e6074a972e5a7392fcb` |
| vcpkg | manifest `vcpkg/vcpkg.json`, builtin-baseline `4334d8b4c8916018600212ab4dd4bbdc343065d1`, triplets `x64-linux-none-libcxx` (TR) / `arm64-linux-none-libcxx` (Pi) |
| Compiler / LLVM | TR host: Ubuntu clang 19.1.1, libc++, mold; JIT backend LLVM/MLIR 21.1.8 (vcpkg `llvm` overlay port = `nes-llvm-21-with-fix-173075`) |
| TR binaries | `cmake-build-release/nes-single-node-worker/nes-single-node-worker` built 2026-10-05 18:27 (Sep-3 state + `NES_EAGER_COPY_VARSIZED` knob; anchors reproduce the 2026-08-24 ladder within 1–3 %); Sep-3 copy kept as `*.sep03` |
| Pi binaries | build **e** (2026-10-06, image `local-piparse-inl` cf9906b2c4c2, `NES_INLINE_ON_ARM=ON`) for every per-query tier cited; `*.buildd` (inlining off) and `*.aug23` kept on the Pi. Scaling ladders and latency curves were taken with the Aug-23 binary (user decision 2026-10-06: not retaken) |
| Benchmark harness | `https://github.com/ANON-ACCOUNT/piparse-bench-snapshot` @ **`piparse-artifact-v1.1`** = `3f98722` (= v1 `33e7603` + the two 2026-10-12 ablation overload re-run yamls; private at freeze time) |
| Results database | `results/tr/piparse_bench.duckdb` = `piparse-bench/results/piparse_bench.duckdb` as of 2026-10-12 15:30 (adds the ablation overload re-run `20261012T150636-97b18744`, `20261012T151153-401837a8` and the getting-started smoke run `20261012T115658-3d2e5b23`) |
| Python / tools | Python 3.12.3, uv 0.9.24, duckdb 1.5.4, matplotlib 3.11.0, numpy 2.1.3, pandas 2.2.3, pydantic 2.13.4, apache-flink 2.1.3, pyspark 3.5.9, OpenJDK 11.0.32.1, cargo 1.89.0, Docker 28.2.2 |
| Datasets | see `data/README.md` (sizes + md5 of every file) |

## Paper element → experiment directory

| paper element | dir |
| --- | --- |
| Ablation ladder r1…r7 with the compile-rung decomposition (r3_eager_all, r3_lazy_nopass) | `experiments/E01_ablation_ladder` |
| Why the parallel rung gives q14 16.9× and q0 6.1× (output-serializer ceiling classes) | `experiments/E02_parallel_rung_q14_vs_q0` |
| Shredder thread scaling on spanning rows (figW) + spanning-size sweep (figS) + latency (figL) + q_ex twin | `experiments/E03_shredder_spanning_figW` |
| q_ex 1→23 worker sweep, serde matrix (figQ; figI superseded sibling) | `experiments/E04_qex_serde_matrix_figQ` |
| 5-arm head-to-head, stateless + stateful tiers (TR W23) | `experiments/E05_head_to_head_5arm` |
| Overload-knob A/B (TR + Pi) | `experiments/E06_overload_ab` |
| Pi per-query tiers (optimised / native / naive W3), build e | `experiments/E07_pi_per_query_tiers` |
| Many-source scaling ladders N = 1…1000 + latency curves, both machines, NES/Flink/Spark/naive/native | `experiments/E08_scaling_ladders_n1_1000` |
| §2 teaser figures Fig1 (CPU per tuple by stage) and Fig2 (predicate sweep laws) | `experiments/E09_teaser_fig1_fig2` |
| Serde micro-benchmarks (float/int K sweeps, i2f/f2i) | `experiments/E10_serde_micro` |
| Cross-format 4×4 matrix (CSV/JSON/HL7/XML × r_base/r_comp/r_par) + W sweep | `experiments/E11_cross_format_matrix` |
| Thread structures: gang vs DPP vs chunker vs thread-per-query vs rr, cost skew, bursts | `experiments/E12_thread_structure_gang_dpp_rr_skew` |
| Lines of code to add an input / output formatter | `experiments/E13_formatter_loc` |
