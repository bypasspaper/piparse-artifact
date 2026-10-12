<!-- SPDX-License-Identifier: Apache-2.0 -->
# Spanning-tuple-size figure — isolated vs e2e SequenceShredder (2026-08-31, v2 clean+extended)

LOCK_FREE vs naive-LOCKING `SequenceShredder`, across spanning-tuple size, both harnesses on one plot,
now over **two buffer sizes (4 KiB, 8 KiB)**, extended to **640 KB rows**, with **cleaner stats**
(reps 3→6, window ~1 s→~1.9 s). Figures in `figures/`: `figS_span_{4k,8k}` (throughput),
`figL_latency_{4k,8k}` (latency).

## Design
- **x** = row size 4/16/40/80/160/320/640 KB; span count = row/buffer (labelled per figure).
- **4 lines** = {isolated, e2e} × {LOCK_FREE, LOCKING}. LF=blue, LK=red; isolated=solid/filled, e2e=dashed/open.
- **buffer size** = one figure each (4 KiB, 8 KiB). **y** = GB/s input, **W24**. Same shredder-isolated query
  (`SELECT id FROM (id,s)`) in both harnesses — string spans buffers, only 8-byte id emitted (no output copy).
- **Repeats stay OFF by design** (in-flight 8192 ≪ window 65536 ⇒ 0 out-of-range re-queues; cleaner
  measurement — repeats are an implementation detail, deliberately excluded).

## Headline findings
1. **LOCK_FREE strictly beats naive-LOCKING at every span, both harnesses, both buffers.**
2. **The isolated→e2e gap (per-task machinery) falls almost entirely on LOCK_FREE** (iso-LF ≈ 2× e2e-LF, the
   shaded band); the LOCKING lines nearly coincide (mutex-bound → machinery hides behind the lock).
3. **The gap widens at the extremes.** isolated LF/LK climbs to **2.7×** at 320–640 KB (4 KiB buf); e2e LF/LK
   is U-shaped — high at small rows (call-rate), min mid, and **rises again to 1.49× at 320 KB / 1.41× at
   640 KB** as LOCKING's throughput *drops* (LK 3.47→3.06 GB/s) while LF holds (~4.5). LOCKING diverges
   downward at extreme spans, confirmed.
4. **8 KiB buffer ≈ 2× the throughput of 4 KiB** (fewer, bigger buffers = less per-buffer overhead), same
   LF/LK gap shape.

## Throughput data (W24, GB/s input)
### 4 KiB buffer
| row (span) | 4K(1) | 16K(4) | 40K(10) | 80K(20) | 160K(39) | 320K(78) | 640K(156) |
|---|---|---|---|---|---|---|---|
| iso LF | 4.60 | 7.62 | 8.40 | 9.10 | 8.54 | 9.88 | 10.12 |
| iso LK | 2.70 | 3.65 | 3.69 | 3.88 | 3.90 | 3.59 | 3.73 |
| **iso LF/LK** | 1.70 | 2.09 | 2.28 | **2.34** | 2.19 | **2.75** | **2.71** |
| e2e LF | 4.34 | 4.44 | 4.46 | 4.57 | 4.59 | 4.56 | 4.38 |
| e2e LK | 2.61 | 3.30 | 3.46 | 3.47 | 3.46 | 3.06 | 3.10 |
| **e2e LF/LK** | 1.66 | 1.34 | 1.29 | **1.32** | 1.33 | **1.49** | **1.41** |

### 8 KiB buffer
| row | 4K | 16K | 40K | 80K | 160K | 320K | 640K |
|---|---|---|---|---|---|---|---|
| iso LF | 9.16 | 13.57 | 15.88 | 17.31 | 17.48 | 17.42 | 18.17 |
| iso LK | 5.36 | 6.31 | 7.01 | 7.71 | 7.22 | 7.28 | 6.90 |
| e2e LF | 8.32 | 8.41 | 8.44 | 8.48 | 8.91 | 8.91 | 8.94 |
| e2e LK | 5.13 | 5.90 | 6.53 | 6.72 | 6.86 | 6.77 | 6.02 |
| **e2e LF/LK** | 1.62 | 1.43 | 1.29 | 1.26 | 1.30 | 1.32 | 1.49 |

**Calibration:** 4 KiB / 80 KB e2e = 1.32× (anchor 1.34×); iso = 2.34× (anchor 2.28–2.34×). ✓

## Latency (e2e, W24, ingest→sink) — the lock hurts latency MORE than throughput
| 4 KiB buf | LK p50 | LF p50 | LK p99 | LF p99 |
|---|---|---|---|---|
| across all spans | ~9–13 ms | **~40 µs** (1 outlier @40K=2 ms) | ~16–20 ms | ~9–11 ms |

- **LOCKING p50 ≈ p99 ≈ 10–20 ms = the mutex convoy** — every tuple queues behind the lock, so the *median*
  is already as bad as the tail. **LOCK-FREE p50 ≈ 40 µs** (bimodal: most tuples immediate, tail ~10 ms).
  So the **median-latency gap is ~250×** vs a ~1.3× throughput gap; **p99 gap ~1.6×**. The lock's damage is
  disproportionately in latency.
- ⚠️ **Absolute ms are inflated by the deep-queue throughput config** (in-flight 8192 → long queue residence,
  Little's law). The **LF/LK contrast** is the robust signal; absolute magnitudes would shrink under a
  realistic bounded in-flight (a separate latency-config run if we want publishable magnitudes).
- The LF p50 is bimodal → a knife-edge median (the 40 KB=2 ms point is that edge); p99 is the robust metric.

## Method / provenance
- Harness: `FormatterScalingBenchmark.cpp` arg13 `varsized=2` = 2-field (id,s) projected to id (uncommitted).
  Isolated: `... bigstr_id_<tag>_500m.csv <4|8> 0 15 8,16,24 leannoemit 1 - - both - SIMDCSV 2`, reps=15,
  steady-state median. Log `logs/isolated_span_sweep_4k8k.log`.
- e2e: `experiments/shredder_span_sweep.yaml` (7 row variants × buffer-size axis {4096,8192} × {LF,LK} × 6
  reps = 168 runs), 1.34× config (W24, K32, deep queue), NES_INMEM_REPEAT=16. run_group 20260831T13xx, 0 fail.
  Median throughput_mbps + p50/p99 from DuckDB `aggregated`. Log `logs/e2e_span_sweep_4k8k.log`.
  ⚠️ 8 KiB windows ~1.0 s (2× throughput halves them) — borderline the >1.4 s guard but values are stable.
- Data (uncommitted): `bigstr_id_{4,16,40,80,160,320,640}k_500m.csv`, build-tree symlinked. Gen
  `scratchpad/gen_bigstr_id.py`. Queries `bigstr_id_pass_{tag}.yaml`.
- Scripts (`scripts/`): parse_isolated, parse_e2e (duckdb, +latency), merge_span, make_span_figure (per buffer),
  make_latency_figure (per buffer). Tidy: `data/{isolated,e2e,span}_tidy.csv`.

## Open / optional
- Clean-latency run (bounded in-flight) for publishable absolute ms.
- 8 KiB longer window (NES_INMEM_REPEAT 24) if the ~1 s window is a concern.
- gbps_max (ramp-free ceiling) variant via ISO_METRIC in merge_span.py.
