# E05 — Head-to-head records/s: NES naive / NES optimised / NES native→native / Flink / Spark (stateless + stateful tiers)

**Claim in the paper.** On the 10 stateless bid_strings queries at W23 the optimised NES (csv→JSON) reaches
138–580 M records/s, i.e. **41–146× the naive NES** (interpreted formatter + original stod/stringstream codecs, W1),
**127–311× Flink** and **235–426× Spark**, and 0.50–0.90 of the true no-serde bound (native→native 230–701 M rows/s;
worst on the float-parse-heavy q1/q14). On the stateful tier the serde story vanishes under state cost: optimised/native
0.96–1.04 everywhere; YSB stays input-bound (274 M rows/s, 115× naive, 187× Flink), q8_join is state-bound
(3.3 M rows/s, 1.6× Flink, 0.8× naive), cm_q2 in between (8.8, 9.8× Flink).

**Machine.** Threadripper PRO 5965WX; NES W23 + 1 io thread (naive W1), Flink parallelism 23, Spark `local[23]`
single reader. Two engine states: the original 5-arm run (2026-08-14, engine `66ab110f30`) and the one-code-state NES
regeneration (2026-09-02, `b5d757c9f6` + overlay = tag `piparse-artifact-v1`).

**Measured with.**

| layer | pbench experiment | series | run_group | runs | wall |
| --- | --- | --- | --- | --- | --- |
| (A) original 5-arm, stateless | `nes_vs_flink_vs_spark_stateless_5arm.yaml` | NES-Native (→JSON), NES-SIMD, NES-Naive (fast codecs!), Flink, Spark | `20260814T000106-1b605eba` | 500 | 2 h 25 min |
| (A) original 5-arm, stateful | `nes_vs_flink_vs_spark_stateful_5arm.yaml` | same five | `20260814T023018-8d5faba3` | 150 | 1 h 00 min |
| (A') naive CORRECTED (genuine original codecs), both tiers, 2026-08-14 | (same yamls with `NES_INPUT_CODEC=original NES_OUTPUT_CODEC=original`) | NES-Naive | → `data/nes_vs_flink_vs_spark_5arm_2026-08-14_CORRECTED_per_rep_raw.csv` | | |
| (B) native→native regen | `w23_native_native_regen.yaml` | `native_native` | `20260902T171734-780e8bea` | 100 (10 q × 10 reps) | 7 min |
| (B) optimised + csv→native regen | `w23_simd_csvnative_regen.yaml` | `simd`, `csv_native` | `20260902T180433-970509c0` | 200 | 15 min |
| (B) naive corrected regen at tip | `naive_corrected_regen_tip.yaml` | naive (W1, `SequentialUncompiledOldCSV` + original codecs) | `20260902T202750-35950c65` | 100 | 18 min |
| (B) stateful regen | `stateful_serde_regen.yaml` (+ `_rest`, `_rest2` resume slices after two harness kills) | `simd`, `csv_native`, `native_native` | `20260902T212534-339c0468`, `…213435-15c79b8e`, `…213621-96107ad1` | 20 + 10 + 60 | ~12 min |
| (diag) W1 column replication | `w1_column_replication.yaml` | `simd`, `native_json`, `csv_native_out` @W1 | `20260902T124928-25fb7252` | 90 | 19 min |

NES configuration: MmapFile zero-copy + `NES_MMAP_POPULATE` + warm read, `generator.repeat 8` (stateless) / **1**
(stateful: event-time windows, replay = heap-corruption engine bug), 128 KiB operator buffers, fnattr, COMPILER, io 1,
pin/ccx off, Monitoring sink; SystemNative `string_length` bid "13,73", ysb "37,37,37,37,9,9,8", q8 "16,32,32,16,4,256",
cm "16"; q8 needs the stateful pool (4 KiB op buffers + 2 M global buffers). Metric `throughput_mrows_s` (the only
cross-arm metric: csv 114.865 vs native 110 B/row). Flink: pyflink 2.1.3 with the `blackhole-format` json sink
(`flink-ext/`); Spark: pyspark 3.5.9, Model-A single reader, json void sink (`spark-ext/`); 10 reps each.

**The paper CSVs** (`data/stateless_5arm_paper_regen.csv`, `data/stateful_5arm_paper_regen.csv`) are assembled by
`make_paper_csv.py` / `make_stateful_csv.py`: naive = Aug-14 CORRECTED per-rep (A'; stateless: the tip regen (B)
matches it within 1–3 % and is NOT used, per author decision), simd / csv_native / native_native = (B), Flink / Spark =
(A) verbatim (external engines, unchanged). lo/hi = med−min / max−med over reps (the paper's error-bar convention,
verified). Derived columns: `simd_over_*`, `conn_lo/up`, `stack_gain`, `ceil_lo/up`, plus the appended `csvnat_*`
(deserialize-only) and `natjson_*` (Aug-14 native→JSON) columns.

## Files

| path | what |
| --- | --- |
| `yaml/experiments/*.yaml` | the 9 experiment definitions (piparse-bench tag `piparse-artifact-v1`) |
| `yaml/queries/nexmark/matrix/bidstr_*.yaml`, `yaml/queries/{yahoo/ysb_1k_varsized,nexmark/q8_join,cluster_monitoring/q2_original}.yaml` | the 13 queries (NES SQL + `flink_sql` + `spark_sql` dialects) |
| `data/stateless_5arm_paper_regen.csv`, `data/stateful_5arm_paper_regen.csv` | **the paper tables** |
| `data/native_native_w23_regen.csv`, `data/simd_csvnative_w23_regen.csv`, `data/w23_regen_per_rep_raw.csv` | the (B) columns with lo/hi + paper anchors, and their 400 per-rep rows |
| `data/nes_vs_flink_vs_spark_5arm_2026-08-14_CORRECTED_{per_rep_raw,aggregated}.csv` | the Aug-14 run with the corrected naive arm (665 per-rep rows; Flink/Spark/native→JSON source of truth) |
| `data/nes_vs_flink_vs_spark_5arm_2026-08-14_{aggregated,per_rep_raw}.csv`, `…_stateless_2026-08-14.csv` | the UNCORRECTED Aug-14 run (naive = wrong fast-codec naive; see caveat 1) |
| `expected/nes_vs_flink_vs_spark_5arm_2026-08-14_CORRECTED.{png,pdf}`, `…_2026-08-14.{png,pdf}` | the Aug-14 figures (corrected / uncorrected naive) |
| `make_paper_csv.py`, `make_stateful_csv.py`, `extract_native_regen.py`, `extract_simd_csvnative_regen.py`, `compare_w1_columns.py` | the original CSV generators / column extractors, path-portable (print CSV to stdout) |
| `make_figure.py` | runs the four generators → `out/*.csv`, draws `out/head_to_head_5arm.{png,pdf}`; `--verify` diffs the four CSVs against `data/` |
| `run.sh` | re-measure recipe (layers A and B) |

## Reproduce the tables and figure from the shipped data (seconds)

```
python3 make_figure.py --verify      # DB default ../../results/tr/piparse_bench.duckdb (or --db PATH / $PBENCH_DB)
```
Verified 2026-10-12: `stateless_5arm_paper_regen.csv` (10 rows), `stateful_5arm_paper_regen.csv` (3),
`native_native_w23_regen.csv` (10), `simd_csvnative_w23_regen.csv` (10) all reproduce `data/` exactly (max relative
deviation 0). **The figure maker of `expected/*_CORRECTED.png` was not preserved** (ad-hoc script of the 2026-08-14
session); `make_figure.py::plot_5arm` is a minimal re-implementation (grouped bars, log-y, min/max whiskers) drawn
from the paper CSVs, i.e. from the one-code-state NES columns — it is therefore not pixel-identical to the Aug-14 PNG
(whose NES columns are the Aug-14 engine; naive there = corrected codecs, native = native→JSON).

## Re-measure (B ≈ 55 min; A ≈ 3.5 h incl. Flink + Spark; Threadripper)

```
./run.sh                 # or ./run.sh --dry-run; env NES_BUILD_DIR, PBENCH_DIR, WORKER_PORT
python3 make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb
```
Data: `bid_strings_3GB.{csv,nes}`, `ysb1k_with_varsized_3GB.{csv,nes}`, `person_840MB`/`auction_707MB` (+ `.nes`),
`google-cluster-data-original_1G` (+ `.nes`) under `<build>/nes-systests/testdata/large/` (`../../data/README.md`).
The Flink/Spark medians are literals in `make_paper_csv.py` (`QUERIES`) and come from the Aug-14 per-rep CSV; a new
layer-A run must be exported (`pbench export <experiment>`) and those literals updated.

## Caveats / provenance notes

1. **The submission's stateless table was traced (2026-09-02) to the UNCORRECTED Aug-14 aggregate**
   (`data/nes_vs_flink_vs_spark_5arm_2026-08-14_aggregated.csv`): its naive column is `SequentialUncompiledOldCSV` with
   the default FAST codecs (4.0–5.8 M rows/s), not the intended interpreted + original-codec naive (3.3–4.6,
   `_CORRECTED_`). The paper CSV shipped here (`stateless_5arm_paper_regen.csv`) carries the corrected naive;
   swapping raises `simd_over_naive` by ~15–25 %. The native column was likewise replaced: the 5-arm measured
   native→JSON (its Aug-14 @W23 medians are the `natjson_*` columns); the paper CSV uses true **native→native**
   (230–701) → `simd_over_native` 0.50–0.90 instead of the earlier 0.72–1.17 "parse free under pushdown" reading.
   NB: the `paper_native_med` reference column in `data/native_native_w23_regen.csv` (17.1–94.1) is NOT the paper —
   it is the retracted wrong-paste table that an earlier "W1 anomaly" investigation chased; `paper_simd` in
   `data/simd_csvnative_w23_regen.csv` IS the Aug-14 simd column (141–499).
2. **Code-state coherence.** Stateless NES columns are all at one code state (B); Flink/Spark are Aug-14 (external
   engines, unchanged). The Aug-14 simd column is drift-stable 0.98–1.03× vs (B) on 8/10 queries; movers: q2mod +9 %
   (machinery commits), q_ex +17 % (VARSIZED equality early-return fix).
3. **Stateful q8_join: all compiled NES arms are −20–26 % vs Aug-14** (simd 3.32 vs 4.49, native→JSON 3.97; naive
   3.99 unchanged) and now converge at ~3.2–3.3 M rows/s (state-bound law) — **UNBISECTED** (knobs? machinery commits?
   Aug-14 variance?). Flag before citing q8 absolutes. ysb (+2 %) and cm_q2 reproduce their anchors.
4. Overload knob (lazy-overload constant equality): the 5-arm / regen NES arms ran with the experiment yamls' default
   (`overload: false`) — the paper must state ON or OFF for the optimised column; q2_og is the query it moves most
   (see E06 overload A/B).
5. W23 windows are 0.4–2 s (repeat 8 at 150–700 M rows/s) — accepted footing (median of 10); do not raise the repeat
   (16× staging = 54 GB > page cache). Stateful must stay `repeat 1`.
6. SystemNative REQUIRES `string_length` even for schemas without VARSIZED fields (any dummy value); `NES_MMAP_COPY=1`
   ignores `NES_FILE_REPEAT` and yields ×repeat fake throughput — never combine.
7. The stateful regen was split into three run_groups by two external kills of the harness (survived via `setsid
   nohup`); `make_stateful_csv.py` reads all runs of the experiment by name (10 reps per cell verified), so the DB's
   `aggregated` view (latest run_group only) must NOT be used for this experiment.
- **PAPER POLICY (author, 2026-10-12): lazy overloads ON for id comparisons.** The 5-arm tables and all regen layers were measured OFF (no `overload` key). The knob changes only the id-filter queries: q2_og +18 % on the TR (E06 `nes_simd_overload_stateless`, `tr_ctrl_vs_ovl_vs_aug14.csv` gives the per-query ON/OFF pairs), q_ex/cm_q2 within noise.
