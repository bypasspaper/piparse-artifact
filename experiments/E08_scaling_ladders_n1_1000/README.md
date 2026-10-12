# E08 — Many-source scaling ladders, N = 1 … 1000 concurrent sources/queries (throughput + per-batch latency), Threadripper and Raspberry Pi 5

**Claim in the paper.** Bounded vs collapse: with N concurrent file sources each running one of the 10 stateless paper
queries (round-robin mix, csv → json), the optimised NES arm holds aggregate throughput AND p99 per-batch latency flat to
N = 1000 (TR: ~23 GB/s ≈ 200 Mrec/s, p99 ~9 ms; no-serde native in/out ~270 Mrec/s, p99 2–4 ms), while Flink's tail
collapses past the core count (p99 12 → 1815 ms from N = 20 to 1000 at ~1.5 GB/s), Spark's micro-batch latency is in the
hundreds of seconds, and the naive NES stack (interpreted CSV, stringstream JSON, thread-per-source) peaks at N ≈ 16 and
declines monotonically (14.4 Mrec/s, p99 447 ms at N = 1000). On the Pi the same shapes hold at 1/6 of the per-core speed
(NES optimised ~1.3 GB/s flat; Flink plateau 73 MB/s from N = 500 with p99 6.5 → 13.5 s to N = 1000; naive W3 340 MB/s
plateau declining to 111 MB/s). Low-N fine grids show the ramp/knee lives in N ≈ 1–20 (fast arms saturate at N ≈ 16–20 on
24 cores; naive's knee at N = 8 = 24 − 16 workers).

**Machine.** Threadripper PRO 5965WX (24 physical cores / 48 threads, 64 GB, Ubuntu 24.04), host build
`cmake-build-release`; NES many-source production config = CCX cells + fragment shredder LOCK_FREE_FRAGMENTS + pin_threads +
16 workers / 8 io threads + 192 × 128 KiB shared source pools + File sources (the OPPOSITE of the single-source tiers' ccx/pin
OFF); Flink = PyFlink 2.1.3 MiniCluster, N pipelines × parallelism 1 (`latency_json` sink); Spark = PySpark 3.5.9 local[24],
custom `file-microbatch-csv` DataSourceV2 source with 64 MiB micro-batches. Raspberry Pi 5: NES W3 + io1, Flink p=3,
Spark local[3]; Pi binary = Aug-23 worker (8217cce465; the ladders were NOT retaken on build e — user decision 2026-10-06).
Dates: TR 2026-08-17/18 (NES+Flink), 08-20/21 (Spark), 09-01 (naive/native + fine grids); Pi 2026-08-24 … 09-23 (Flink
N=1000 real 09-22/23), naive W3 real 10-02/03. The July bid-passthrough ladder (1 → 1024 File sources, csv → csv, NES
~40 GB/s flat / Flink ~1.4 GB/s) is the historic precursor; its figure is shipped too.

**Measured with.** pbench worker-cli mode with `query_mix` (the 10 `nexmark/matrix/bidstr_*` queries), x = `num_queries`.
Threadripper run_groups in `../../results/tr/piparse_bench.duckdb`:

| what | experiment | run_group | series | N grid |
|---|---|---|---|---|
| NES-SIMD + Flink full | `nes_vs_flink_vs_spark_scaling_step20` | `20260817T164347-3ec56b98` | NebulaStream, Flink | 1, 20, …, 1000 (51) |
| Spark full (µ-batch source) | `nes_vs_flink_vs_spark_scaling_step20_spark_mb` | `20260820T144859-a82252ff` | Spark | 1, 20, …, 1000 |
| Naive + Native full | `nes_naive_native_scaling_step20` | `20260901T024303-4285bc04` | NES-Naive, NES-Native | 1, 20, …, 1000 |
| Native fine | `nes_native_scaling_lowN_fine` | `20260901T165004-628e9d01` | NES-Native | 1..100 step 1 |
| SIMD fine | `nes_simd_scaling_lowN_fine` | `20260901T171812-7a007e66` | NES-SIMD | 1..100 step 1 |
| Naive + Flink + Spark low-N | `nes_naive_flink_spark_lowN_fine` | `20260901T175023-5d971803` | NES-Naive, Flink, Spark | 22-pt log grid |
| July passthrough ladder | `latency_flink_passthrough_scaling`, `shredder_fragments_source_scaling` (+ `shredder_fragments_n1024_*`) | 2026-07-12/15 | Flink; lock_free_fragments | 1 … 1024 |

Pi (Pi-side DuckDB; exports under `../../results/pi/`): `pi_flink_scaling_{a,b,c}` (run_group `20260824T024940-530263c1`)
+ `pi_flink_scaling_c_n1000` (`20260916T091155-dd7e327b`) → `flink_scaling.csv` (66 rows, N 1..1000);
`pi_naive_scaling_{a,b,c,d}` (W1, Aug 27–29) → `naive_scaling.csv`; `pi_naive_scaling_w3_{a,b,c,d}` → `naive_scaling_w3.csv`
(74 rows); `pi_naive_inflight_probe` → `naive_inflight_probe.csv`. Ladder on every Pi arm: N = 1..20 ×3 reps, 25/50/100/250
(NES ×3, Flink/Spark ×1), 500 ×1, 1000 ×1 (parts a/b/c/d).

## Files

| path | what |
| --- | --- |
| `yaml/tr/*.yaml` | the TR experiment definitions (the 7 above + the probe/smoke/superseded-Spark variants + the July passthrough ladder) |
| `yaml/pi/*.yaml` | the Pi yamls that exist on this box: `pi_flink_scaling_c_n1000`, `pi_naive_scaling_w3_{a..d}`, `pi_naive_inflight_probe` |
| `yaml/queries/nexmark/matrix/bidstr_*.yaml` | the 10-query mix; `yaml/queries/nexmark/bid_passthrough.yaml` the July workload |
| `data/tr/nes_flink_spark_scaling_step20_raw.csv` | per-run rows of the 3-engine step-20 sweep (NES+Flink `…3ec56b98`, Spark `…a82252ff`) |
| `data/tr/nes_flink_spark_step20_latency.csv` | the same as a wide table: per N, throughput GB/s + p50/p99/p999 ms per engine |
| `data/tr/nes_naive_native_scaling_step20.csv`, `nes_{native,simd}_scaling_lowN_fine.csv`, `naive_flink_spark_lowN_fine.csv` | 12-column tidy exports (arm, N, throughput_mbps, agg_mrecords_s, p50/p99/p999/p99_worst/avg/min/max_ms, processing_time_s) |
| `data/pi_naive_w1_vs_w3.csv` | Pi naive W1 vs W3 per N (throughput, p50/p99/p999, seconds) |
| `data/pi_flink_n1000_preflight.txt` | the Pi pre-flight record for the N=1000 Flink run (throttle flag, clock, PSU current, memory) |
| `expected/nes_vs_flink_vs_spark_scaling_step20.{png,pdf}` | **3-engine figure** (throughput GB/s; p99 ms, log-log) |
| `expected/latency_real.{tex,pdf}` | the paper-ready pgfplots version of the 3-engine p99 panel (data embedded; `pdflatex latency_real.tex`) |
| `expected/nes_naive_simd_native_scaling.{png,pdf}` | **NES-internal 3-arm figure** in records/s (format-invariant) |
| `expected/five_arm_lowN_1to100.{png,pdf}` | **5-arm low-N figure**, 22-pt grid, log-y |
| `expected/nes_simd_fine_vs_coarse_1to100.*`, `native_fine_vs_coarse_1to100.*` | fine (step 1) vs coarse (step 20) overlays |
| `expected/flink_vs_nes_latency_scaling.{png,pdf}` | the July bid-passthrough ladder (NES ~40 GB/s flat, p99 ~4 ms; Flink 1198 ms @1024) |
| `expected/superseded/nes_flink_spark_step20_FINAL_stockreader_spark_2026-08-19.png` | the 08-19 figure with Spark's stock reader (whole-file "latency") — superseded by the µ-batch source |
| `scripts/plot_*.py` | the original pbench plot scripts (import `piparse_bench.store`; kept for reference) |
| `scripts/pi_dump.py` | the Pi export job list (DuckDB → the `*_scaling.csv` files, with the per-file caveats as comments) |
| `scripts/run_naive_w3.sh`, `naive_w3_sampler.sh`, `run_inflight_probe.sh` | the Pi runners |
| `docs/SCALABILITY_5ARM_HANDOVER.md` | the TR 5-arm write-up (run groups, exact arm configs, gotchas, findings) |
| `docs/SCALABILITY_NAIVE_NATIVE_HANDOVER.md`, `docs/FLINK_LATENCY_SCALING_HANDOVER.md`, `docs/MANY_SOURCE_SCALING.md` | the naive/native plan, the July Flink latency arm + passthrough ladder, the original async-vs-blocking file-source scaling study |
| `docs/PI_FLINK_N1000_RESULT.md`, `docs/PI_NAIVE_W3_RESULT.md` | the Pi result docs (Flink N=1000; naive W3 ladder + per-query tiers + in-flight probe) |
| `make_figure.py` | pbench-free regeneration of all TR figures from the DB + two Pi views; `--check` pixel-compares with `expected/` |

## Reproduce the figures from the shipped data (seconds)

```
python3 make_figure.py --check
# -> out/{nes_vs_flink_vs_spark_scaling_step20, nes_naive_simd_native_scaling, five_arm_lowN_1to100,
#         nes_simd_fine_vs_coarse_1to100, native_fine_vs_coarse_1to100, flink_vs_nes_latency_scaling}.{png,pdf}   (all 6 verified PIXEL-IDENTICAL to expected/, matplotlib 3.11.0)
#    out/pi_scaling_available_arms.{png,pdf,csv}   Pi ladder, the arms whose exports are shipped (Flink; naive W1; naive W3)
#    out/pi_naive_inflight_probe.md                the in-flight-window probe table
```
Needs `duckdb`, `matplotlib`, `numpy`, `pillow` (`../../scripts/requirements.txt`).

## Re-measure (~52 h Threadripper; several days on the Pi)

```
./run.sh        # prints the exact pbench commands (TR: 7 experiments; Pi: 6 ladders + probe + export)
```
Needs `bid_strings_3GB.csv` (+ `.nes` twin for the native arm) under `<build>/nes-systests/testdata/large/nexmark/`, the
Flink/Spark jars (`flink-ext/build.sh`, `spark-ext/build.sh`), JDK 11 (TR) / 21 (Pi), and for the Pi the `flink312` venv.

## Caveats / provenance notes

- **GAP — Pi exports not on this box:** the Pi's `nes_scaling.csv` (NES optimised `pi_scaling_file_{a,b,c}`), `spark_scaling.csv`
  (`pi_spark_mb_{a,b,c}`) and `native_scaling.csv` (`pi_noserde_scaling_{a..d}`) live in the Pi DuckDB and
  `/home/pi/powertest/export/` only (the Pi is powered off at freeze time). `scripts/pi_dump.py` is the exact export job
  list; re-run it on the Pi and copy the three files to `../../results/pi/` to complete the Pi column. The Pi yamls for those
  ladders are also Pi-only (untracked there).
- **Latency policy — in-flight window:** every NES arm runs the engine default `default_max_inflight_buffers = 64`. The naive
  arm's low-N p99 above Flink (up to N ≈ 100 on the Pi) is this window in front of the slower serialisation stage, not an
  engine property: the probe (`out/pi_naive_inflight_probe.md`) shows latency ∝ cap (cap 4 puts naive below Flink at every N)
  at unchanged throughput for N ≥ 4; cap 16 costs ≤ 6 % at N=1. The paper must state the policy or fix one cap for all arms
  and re-run the latency curves (undecided). Exception: the Pi no-serde N=1000 point ran cap 16 (cap 64 needed ~15.5 GB).
- **Pi Flink N=1000** needed `-Xmx8g` + `heartbeat.timeout` 30 min (pbench `flink_config` / `flink_jvm_args`): the default
  3.96 GiB heap GC-thrashed and timed out the TaskManager heartbeat. N ≤ 500 ran on the default heap (plateau continuous,
  no re-run; Spark's ladder already had an explicit 8 g driver heap).
- **Pi naive N=1000 is not a clean page-cache point** (worker RSS 13.7 GB with 1017 threads evicted the 3.4 GB csv; 72 % of
  samples below file size; NVMe not binding). Flink's and the no-serde N=1000 points are clean. Naive W1 (`naive_scaling.csv`)
  is the single-worker reference; `naive_scaling_w3.csv` is the fair curve (W3 = the optimised arm's budget).
- **Pi ladders stay on the Aug-23 binary** (inlining off on ARM at that time): comparable across the Pi arms, but the Pi
  optimised numbers are ablation-r4-class (see E07); only the per-query tiers were retaken on build e (user decision 2026-10-06).
- **Throughput conversion:** `throughput_mrows_s` in the DB is per-query and shrinks with N — use the aggregate
  `throughput_mbps` and divide by bytes/row (csv 114.865, native 110.0) for records/s. Native MB/s is over native bytes
  (× 1.0442 for a csv-byte basis).
- **Naive needs W16 on the TR** (uncompiled formatter tasks run on the worker pool; W1 funnelled N sources through one worker
  and blew the timeouts). The naive knee at N = 8 is a cores-vs-threads effect (N + 16 workers = 24 cores); past it threads
  spill to SMT siblings and then oversubscribe.
- **Spark "per-batch latency" is a micro-batch property** (64 MiB batches via the custom source); the stock reader's
  whole-file numbers (`…_step20_spark.yaml`, the superseded figure) must not be quoted as latency.
- **N=1 points of the fast arms are a ramp** (one source under-fills the pool); plateau from N ≈ 16–20. Above N ≈ 20 the
  curves are flat and single-rep noisy — reps beat finer N there.
- NES p99 is the median across queries of each query's per-128 KiB-buffer p99 (sink emits percentiles); Flink/Spark pool
  raw samples. Same per-batch definition on all three (NES per TupleBuffer, Flink per readBatch, Spark per micro-batch).
- The July passthrough ladder (`flink_vs_nes_latency_scaling`) predates the paper workload (one parse-free csv → csv query,
  engine state of 2026-07); its NES N=1024 point is the certified best of the `shredder_fragments_n1024_*` experiments.
- **DECISION (author, 2026-10-12): the paper keeps the default in-flight window of 64 buffers for all NES latency
  curves.** The cap-16 probe (`naive_inflight_probe`) is context only.
