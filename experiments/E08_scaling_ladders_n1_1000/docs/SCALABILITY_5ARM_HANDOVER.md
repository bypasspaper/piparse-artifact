<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handover 2026-09-01 — 5-arm many-source scaling (Naive / SIMD / Native / Flink / Spark)

Supersedes the "next task" in `SCALABILITY_NAIVE_NATIVE_HANDOVER.md` (that task is now DONE).
Memory index node: **[[many-source-scaling-3way]]** (updated with everything below).
All work is UNCOMMITTED in `~/work/piparse-bench` (branch does not matter — pbench is data+YAML).
NES engine build used: `~/work/nebulastream-public/cmake-build-release` (worker rebuilt 2026-08-31).
Box: 5965WX, **24 physical cores / 48 threads**, 62 GB RAM. Worker port 9099.

---

## 0. TL;DR — what exists now

Two complementary sweeps of the **10-query stateless PAPER_WORKLOAD** run as a heterogeneous
`query_mix` round-robin over N concurrent sources/queries (csv→json), warm page cache:

1. **Full range N=1→1000 (step-20, 51 pts)** — 3 NES arms + Flink + Spark, all bounded-vs-collapse.
2. **Low-N N=1→100 (fine)** — because the interesting ramp/knee lives in 1..~20. Native+SIMD at
   **steps-of-1 (100 pts)**; Naive+Flink+Spark on a **user-chosen 22-pt log grid**
   `[1,2,3,4,5,6,8,10,13,16,20,25,32,40,45,50,56,63,71,79,89,100]`.

Headline records/s @N=1000: **Native 243 / SIMD 199 / Naive 14.4 / Flink 1.5·? / Spark ~1.7 GB/s→**
(NES arms in Mrec/s: Native 243, SIMD 199, Naive 14.4; Flink/Spark ~13–15× below SIMD).
Headline records/s @N=100: **Native 275 / SIMD 203 / Naive 31 / Flink 15 / Spark 11.5 Mrec/s.**

---

## 1. Run groups (the source of truth in `results/piparse_bench.duckdb`)

| what | experiment | run_group | series | N grid |
|---|---|---|---|---|
| Naive+Native full | `nes_naive_native_scaling_step20` | `20260901T024303-4285bc04` | NES-Naive, NES-Native | 1,20,…,1000 |
| SIMD + Flink full | `nes_vs_flink_vs_spark_scaling_step20` | `20260817T164347-3ec56b98` | NebulaStream(=SIMD), Flink | 1,20,…,1000 |
| Spark full (µbatch) | `nes_vs_flink_vs_spark_scaling_step20_spark_mb` | `20260820T144859-a82252ff` | Spark | 1,20,…,1000 |
| Native fine | `nes_native_scaling_lowN_fine` | `20260901T165004-628e9d01` | NES-Native | 1..100 step 1 |
| SIMD fine | `nes_simd_scaling_lowN_fine` | `20260901T171812-7a007e66` | NES-SIMD | 1..100 step 1 |
| Naive+Flink+Spark low-N | `nes_naive_flink_spark_lowN_fine` | `20260901T175023-5d971803` | NES-Naive, Flink, Spark | 22-pt grid |

All runs 0 failures. Native/SIMD "coarse" points for the fine-vs-coarse overlays come from the
full-range run_group (`…4285bc04` for Native; the SIMD coarse is series `NebulaStream` in `…3ec56b98`).

## 2. Deliverables (in `~/work/piparse-bench`)

**Figures** (`results/figures/`):
- `nes_naive_simd_native_scaling.{png,pdf}` — 3 NES arms, full N=1→1000 (throughput records/s + p99).
- `nes_native_fine_vs_coarse_1to100.{png,pdf}`, `nes_simd_fine_vs_coarse_1to100.{png,pdf}` — fine(step1) vs coarse(step20).
- `five_arm_lowN_1to100.{png,pdf}` — all 5 arms, 22-pt grid, log-y both panels.

**Plotters** (`scripts/`):
- `plot_nes_naive_simd_native_scaling.py` — full-range 3-arm (pulls SIMD from `…3ec56b98`).
- `plot_nes_fine_vs_coarse.py <series> <fine_exp> <csv|native>` — generalized fine-vs-coarse.
- `plot_5arm_lowN.py` — the 5-arm low-N figure (Native/SIMD subset to the 22 grid pts).
- (`plot_native_fine_vs_coarse.py` — native-only, superseded by the generalized one.)

**CSVs** (`results/`, all 12-col schema: arm,N,throughput_mbps,agg_mrecords_s,p50/p99/p999/p99_worst/avg/min/max_ms,processing_time_s):
- `nes_naive_native_scaling_step20.csv` (Naive+Native, N=1→1000)
- `nes_native_scaling_lowN_fine.csv`, `nes_simd_scaling_lowN_fine.csv` (fine, N=1..100)
- `naive_flink_spark_lowN_fine.csv` (3 arms, 22-pt)

**Experiments** (`experiments/`): `nes_naive_native_scaling_{probe,step20}.yaml`, `nes_naive_reprobe.yaml`,
`nes_{native,simd}_scaling_lowN_fine.yaml`, `nes_naive_flink_spark_lowN_fine.yaml`, `flink_spark_smoke_n1.yaml`.

---

## 3. The five arms — EXACT config

Base defaults (shared): worker-cli, csv, warm_read, `query_mix` = the 10 `nexmark/matrix/bidstr_*`
(q0,qproject,qroute,q1,q2og,q2mod,q10,q14,q22,qex), `generator.repeat: 1`, 16w/8io/fnattr/pin/ccx,
`operator_buffer_size 131072`, `ccx_shared_source_pools 192`, `number_of_buffers 32768`, File source,
SIMDCSV+`LOCK_FREE_FRAGMENTS` in, Traced/Eisel parsers, JSON+ZMIJ out.

- **NES-SIMD** (= the paper contributions): the base defaults verbatim. SIMDCSV + lazy `Traced*`
  field values (`TracedUINT64/INT64/INT16/UINT32/UINT16/BOOL`,`FastINT32`,`EiselFloatF64/F32`) +
  `invoke_mode fnattr` (LLVM DCE of unused lazy extractions = projection pushdown) + `JSON`+`ZMIJF64/F32` out.
- **NES-Native** (no parse/serde, upper bound): base config, only swap `data_size: native`,
  `input_formatter {type: SystemNative, string_length: "13,73"}`, `output_formatter {type: NATIVE}`,
  `input_parser {}`, `output_parser {}`. Same File+CCX+pin+pools → isolates parse+serde vs SIMD.
- **NES-Naive** (interpreted, original codecs): `W16` (NOT W1 — see §4), `ccx_aware_task_queues false`,
  `pin_threads false`, `ccx_shared_source_pools false`, `number_of_buffers 65536`, `source_type BlockingFile`,
  `input_formatter {type: SequentialUncompiledOldCSV, threading_mode: sequential}`,
  `output_formatter {type: JSONUncompiled}`, `input_parser {}`, `output_parser {}`,
  `worker_env {NES_INPUT_CODEC: original, NES_OUTPUT_CODEC: original}` (genuine stod/stringstream).
- **Flink**: `system flink`, `mode flink`, `flink_execution_mode streaming`,
  `flink_output_format latency_json` (real JSON encoder + per-readBatch nanoTime). Jar `flink-ext/pbench-flink-ext.jar`.
- **Spark**: `system spark`, `mode spark`, `spark_output_format json_void_latency`,
  `spark_source file-microbatch-csv`, `spark_batch_bytes 67108864` (64 MiB — the custom DataSourceV2 that
  yields REAL per-batch latency, not whole-file), `spark_parallelism 24`. Jar `spark-ext/pbench-spark-ext.jar`.

---

## 4. LOAD-BEARING GOTCHAS (each cost real debugging)

1. **NAIVE NEEDS W16, NOT W1.** The single-source 5-arm naive used W1. In the many-source regime the
   uncompiled formatter's tasks execute **on the worker pool** (`UncompiledInputFormatterTask.hpp:262`
   "the QueryEngine concurrently executes InputFormatterTasks"), so W1 funnels all N sources through 1
   worker → ~16× too slow → N≥256 blew the completion timeout (looked like a deadlock; it was a timeout —
   N=128 alone took 1402 s at W1). Re-probe at W16 fixed it. `threading_mode sequential` only makes
   per-source spanning-tuple resolution single-threaded, NOT the pipeline.
2. **`throughput_mrows_s` in the DB is PER-QUERY, unusable for aggregates** (`compute_input_rows` returns
   ONE query's 31.3 M rows but the wall span covers all N → it SHRINKS with N). Use the aggregate
   `throughput_mbps` (`monitoring.py:227` = total_bytes / cross-query wall-span) and convert:
   **records/s = throughput_mbps / bytes_per_row**, bytes_per_row = **csv 114.865** (3595281395/31.3e6),
   **native 110.0** (3443000000/31.3e6). The per-format ratio carries the format-invariance.
3. **Flink/Spark toolchain**: jars must exist (`flink-ext/pbench-flink-ext.jar`,
   `spark-ext/pbench-spark-ext.jar`), pyspark 3.5.9 + pyflink import OK; set
   `PBENCH_FLINK_TIMEOUT=1800 PBENCH_SPARK_TIMEOUT=1800`. ALWAYS N=1 smoke first
   (`flink_spark_smoke_n1.yaml`) — validates JVM/jars in ~5 min before a multi-hour run. Smoke N=1
   should match coarse: Flink ≈122 MB/s, Spark ≈62 MB/s.
4. **Worker process comm is literally `main`** → `pkill -9 -x main` is the pre-flight kill. NEVER `pkill -f`
   (self-match). Confirm port 9099 free (`ss -ltnp | grep 9099`).
5. **DuckDB is WRITE-LOCKED during a run** (single-writer). Mid-run: parse the LOG (`→ N MB/s` lines) +
   the kept `/tmp/pbench_mon_*` dirs (`PBENCH_KEEP_LOGS=1`). Export CSVs / build figures only AFTER the run.
6. `SystemNative` REQUIRES `string_length` even for zero-varsized schemas; bidstr = `"13,73"` (2 VARSIZED:
   channel,url). Uncompiled path REQUIRES EMPTY `input_parser {}`/`output_parser {}` (a non-empty override
   crashes — it hardcodes codecs). The uncompiled `sourceCreationTimestamp` fix
   (`UncompiledInputFormatterTask.hpp:76`) IS in the build → naive latency is valid.
7. **Native/SIMD N=1 = ramp** (single source under-fills the pool → Native 61, SIMD 49 Mrec/s), climbs to
   the plateau by N≈16-20. Documented, not a bug.

---

## 5. KEY FINDINGS

- **Bounded-vs-collapse (full range).** Native (~270 Mrec/s, p99 ~3 ms) and SIMD (~200 Mrec/s, p99
  ~7-9 ms) hold FLAT throughput AND latency to N=1000 (the green-curve law). Naive PEAKS ~42 Mrec/s at
  N≈16 then MONOTONE-declines to 14.4 @1000, p99 explodes 2→447 ms. SIMD 13.8× Naive, Native 16.9× Naive,
  Native 1.22× SIMD @N=1000.
- **Fine grid earns its keep only in the ramp N≈1-20.** The step-20 grid draws a straight line across the
  ramp and hides the knee (Native/SIMD saturate ~N=16-20). Above N≈20 the curve is FLAT + single-rep NOISY
  (Native p99 3.4-4.3 ms, SIMD 5-10 ms w/ spikes) — reps beat finer N there.
- **The "strange" naive shape is a cores-vs-threads knee (well-grounded).** Naive is the ONLY arm that is
  (a) CPU-bound (interpreted parse + stringstream serialize on the 16 workers — can't hide behind memory
  bandwidth like the fast arms) AND (b) thread-per-source (`BlockingFile` = one reader thread per source).
  Active threads = **N + 16**; box = **24 physical cores** → knee at **N = 8** (N+16 = 24). Per-source rate
  is flat ~3500 kr/s and latency sub-ms for N≤8 (perfect 1-thread-per-core scaling); at N>8 threads spill
  to SMT siblings → **latency cliff** (p99 0.8→11.9 ms at N=8→13) while throughput still climbs on the
  ~1.3× SMT gain to the **N≈16 peak**; past 16 growing oversubscription (1000 reader threads @N=1000) →
  monotone throughput decline + unbounded latency. The fast arms avoid this: bandwidth-bound + FIXED async-io
  pool (`File`+8 io, N sources share it, no oversubscription) → graceful plateau. Same workload, opposite
  scaling — the citable contrast.

---

## 6. OPEN / NEXT

1. **Prove the naive decomposition (2 controls, ~30 min each, user-offered, not yet run):**
   (a) naive with async `File` instead of `BlockingFile` → predicts the DECLINE flattens into a plateau at
   the ~42 Mrec/s worker-saturation ceiling (isolates the thread-per-source effect from the CPU-bound
   ceiling). (b) naive at `W8` and `W24` → predicts the knee moves to N≈16 and N≈0 (confirms N+W=24).
2. **Reps on the plateau** (N≳25) — single-rep n=1 jitter is what the fine steps trace there; a few reps
   would tighten Native/SIMD/latency. (All sweeps here are repetitions:1.)
3. **Grid decision for a full 5-arm fine sweep** (if wanted): steps-of-1 for all 5 over 1-100 is ~10-11 h
   (Flink ~3.6 h + Spark ~5 h dominate; NES arms cheap). The 22-pt log grid captures every engine's knee
   (Flink/Spark saturate ~N=24) at ~2.5 h. Native+SIMD already have all 100 pts.
4. **Commit** the piparse-bench additions (experiments + plotters + CSVs + figures) — currently uncommitted.
5. Optional: linear-y throughput variant of the 5-arm figure (emphasizes NES dominance vs the log-y shape).

## 7. RUN RECIPE (reproduce / extend)

```
cd ~/work/piparse-bench
pkill -9 -x main                                   # clear stray worker (comm=main)
ss -ltnp | grep 9099 || echo free                  # port must be free
# dry-run first:
uv run python bench.py run experiments/<exp>.yaml \
  --build-dir ~/work/nebulastream-public/cmake-build-release --worker-port 9099 --dry-run
# real run (detached; Flink/Spark need the timeouts):
setsid bash -c 'PBENCH_KEEP_LOGS=1 PBENCH_FLINK_TIMEOUT=1800 PBENCH_SPARK_TIMEOUT=1800 \
  uv run python bench.py run experiments/<exp>.yaml \
  --build-dir ~/work/nebulastream-public/cmake-build-release --worker-port 9099 \
  > <exp>.log 2>&1 & echo $! > <exp>.pid'
# watch: tail the "→ N MB/s" lines; grep -c FAILED <exp>.log ; then the plotters in §2.
```

Records/s from the DB: `throughput_mbps / (114.865 csv | 110.0 native)`. Latency: `p99_latency_us/1000` ms
(median-across-queries; `p99_latency_us_worst` = max query's p99).
