<!-- SPDX-License-Identifier: Apache-2.0 -->
# Ideal-conditions worker scaling — bypass vs eager-parse (LF/LK) vs no-serde (2026-09-02)

**Question.** Follow-up to the 4 KiB spanning shredder study: under IDEAL conditions (128 KiB
buffers, small NEXMark tuples, no spanning), (1) does bypass converge to the no-serde
(native→native) bound with enough threads, and (2) do the lock-free and locking SequenceShredders
behave the same (shredder off the critical path)?

**Answer: yes to both.** No-serde saturates the memory-bandwidth wall (~705 M rows/s = 77.5 GB/s)
at W16 and goes flat; bypass keeps scaling through W23 (546 M rows/s, still rising), closing from
32% → 78% of no-serde. Lock-free ≈ locking everywhere (1.00–1.03× to W16; 1.06–1.07× at W20–23 —
the locking curve just starts to bend where lock-free doesn't). Exact rows/s convergence is capped
at 96% by row-size asymmetry (csv 114.865 vs native 110 B/row); in GB/s both arms head to the same
bandwidth wall (byte-parity line in the figure = 675 M rows/s).

## Setup
- Query `nexmark/matrix/bidstr_q2mod`: `SELECT auctionId, price WHERE auctionId % 123 == 0`
  (~0.82% survivors → output cost ~0). Data `bid_strings_3GB` (31.3 M rows; csv 114.865 B/row,
  native .nes 110 B/row). Chosen from the 5-arm Flink/Spark stateless suite as the query where
  Native≈SIMD converged at memory bandwidth (anchor @W23: Native 515.9 / SIMD 497.6 M rows/s,
  both ~57 GB/s **with JSON output on both arms**).
- Config = `nes_vs_flink_vs_spark_stateless_5arm` NES arms verbatim: MmapFile + NES_MMAP_POPULATE
  + warm, generator.repeat 8 (250.4 M rows/run), 128 KiB operator buffers, fnattr, COMPILER, io 1.
  x = workers {1,2,4,8,12,16,20,23}, reps 5, median. Metric `throughput_mrows_s`
  (format-invariant). Binary: cmake-build-release @ `b5d757c9f6` (+ uncommitted eager_parse knob
  et al. compiled in). 160/160 runs, 0 failed.
- Arms:
  - `no_serde` — SystemNative (string_length "13,73") → **NATIVE** out (true native→native;
    NOTE: the 5-arm native anchor had JSON out → 516; native out lifts the ceiling to ~705).
  - `bypass` — SIMDCSV lazy elision + LOCK_FREE, csv → JSON (all contributions).
  - `lockfree` / `locking` — `eager_parse: true` (kills lazy elision → real per-field parse;
    first time this knob is exercised with SIMDCSV/PARALLEL — works) × shredder mode.

## Result (median M records/s, n=5)

| W  | no_serde | bypass | lockfree | locking | byp/ns | LF/LK |
|----|----------|--------|----------|---------|--------|-------|
| 1  | 129.5 | 41.0  | 27.1  | 26.9  | 0.32 | 1.01 |
| 2  | 196.9 | 77.3  | 51.3  | 51.3  | 0.39 | 1.00 |
| 4  | 335.6 | 148.3 | 99.5  | 99.6  | 0.44 | 1.00 |
| 8  | 530.2 | 279.7 | 193.0 | 190.8 | 0.53 | 1.01 |
| 12 | 639.4 | 394.4 | 280.5 | 274.8 | 0.62 | 1.02 |
| 16 | 707.4 | 486.2 | 360.6 | 351.0 | 0.69 | 1.03 |
| 20 | 706.7 | 531.6 | 428.6 | 404.9 | 0.75 | 1.06 |
| 23 | 704.8 | 546.2 | 460.6 | 431.4 | 0.78 | 1.07 |

## Findings
1. **No-serde = bandwidth wall, early.** 129.5→707 M rows/s, flat from W16 (77.5–77.8 GB/s).
   Adding threads past 16 buys nothing — the no-parse arm is DRAM-bound.
2. **Bypass converges.** Monotone byp/ns 0.32→0.78, no plateau by W23 while the ceiling is flat —
   the same shape as M1 (bid 4-int csv→csv, crossed at ~12t); here the crossing sits past the
   core count because per-buffer work is bigger (SIMD index over 115 B rows + filter + JSON out
   vs M1's raw-forward). Statement that survives review: **serde parallelizes; no-serde
   saturates — with enough threads parallel serde runs at the same memory-bandwidth wall**
   (62.7 vs 77.5 GB/s @23, byte-parity at 675 M rows/s).
3. **Lock-free ≈ locking under ideal conditions — expected and confirmed.** 128 KiB buffers →
   ~26 K shredder calls/pass (vs ~1 M at 4 KiB): call-rate too low for the mutex to matter
   (mechanism: LF/LK ≈ f(call-rate × span-length), cf. SPAN_FIGURE_RESULTS.md). The 1.06–1.07×
   at W20–23 is the locking bend just becoming visible. Complements the 4 KiB/spanning figures
   where LF/LK = 1.3–2.7×.
4. **Eager parse costs 16–34%** vs lazy elision (bypass/lockfree: 1.51× @W1 → 1.19× @W23) — the
   passthrough lever's e2e worth on this query, shrinking as both approach the wall.

## Gotchas / provenance
- eager_parse × SIMDCSV(PARALLEL) validated here for the first time (smoke + 80 clean runs).
- 5-arm anchor reproduces: bypass @23 546 vs 497.6 (+10% = emitter levers committed since
  2026-08-14: dbfd09ff2c/98ab8e3cb3/b5d757c9f6 — LogContext + closure-alloc; batching/inline-
  reducer are prefill-gated and inert here). no_serde 705 vs 516 = NATIVE-vs-JSON output, not drift.
- W23 windows ~0.5 s (repeat 8 @ ~500–700 M rows/s) — same footing the 5-arm accepted (median
  n=5); do NOT bump repeat: 16× staging file (54 GB) would blow the page cache.
- MB/s is NOT cross-arm comparable (csv vs native bytes/row) — throughput_mrows_s only.
- Files: `figures/figI_ideal_workers_q2mod.{png,svg}`, `data/figI_ideal_workers_q2mod_medians.csv`,
  `data/per_rep_raw.csv` (160 rows), `data/shredder_ideal_{scaling,smoke}_q2mod.yaml` (also in
  ~/work/piparse-bench/experiments/, uncommitted), `logs/`, script `scripts/make_ideal_figure.py`
  (run from ~/work/piparse-bench: `uv run python .../make_ideal_figure.py`).
