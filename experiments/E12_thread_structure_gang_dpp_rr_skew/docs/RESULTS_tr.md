# Motivation figure — Threadripper column (2026-09-09, `sweep_tr.csv`, 192 rows)

`MACHINE=tr run_fig.sh` @ b5d757c9f6 + uncommitted rig; taskset 0-23, W=23 pinned, 128 KiB buffers, ring 16 (2 MiB/query),
8 view generations, 32 KiB output buffers, numeric quote-free CSV project f1 + fnattr, FastUINT64, closed loop D=1, 1 s
warm-up + 5 s window, 3 reps (median), spin 0 at every N and spin 50 µs at N ≤ 32 → per-N design-best (policy in brackets).
Gate: tuples/row = 1.0000 in all 192 rows, repeats = 0 everywhere. Wall time 19:46 → 20:05 (19 min).

## p99 latency per buffer, µs (design-best)
| N | DPP | gang k=4 | chunker k=4 | thread-per-query |
|---:|---:|---:|---:|---:|
| 1 | 62 | 23 [50] | 29 [50] | 60 |
| 2 | 103 | 23 [50] | 32 [50] | 60 |
| 4 | 101 | 25 [50] | 51 | 61 |
| 8 | 74 | 86 | 133 | 62 |
| 16 | 67 | 155 | 85 | 64 |
| 32 | 116 | 287 | 160 | 76 |
| 64 | 240 | 487 | 338 | 81 |
| 128 | 494 | 973 | 720 | 17159 |
| 256 | 843 | 2101 | 1253 | 24993 |
| 512 | 1517 | 3430 | 2339 | 41333 |

## p50 µs · max µs
| N | DPP p50 | gang p50 | chunker p50 | tpq p50 | DPP max | gang max | chunker max | tpq max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 56 | 18 | 21 | 54 | 255 | 569 | 106 | 569 |
| 8 | 57 | 21 | 24 | 57 | 216 | 1104 | 849 | 616 |
| 32 | 92 | 25 | 54 | 60 | 1402 | 3926 | 3921 | 15101 |
| 128 | 460 | 547 | 588 | 62 | 2281 | 20522 | 8851 | 60674 |
| 512 | 1465 | 2217 | 2073 | 63 | 2837 | 50962 | 6488 | 145459 |

## Sustained GB/s · CPU-seconds per GB
| N | DPP | gang | chunker | tpq | | DPP | gang | chunker | tpq |
|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1 | 2.4 | 7.1 | 6.0 | 2.4 | | 0.49 | 0.57 | 0.83 | 0.42 |
| 8 | 18.2 | 32.6 | 22.1 | 18.3 | | 0.50 | 0.72 | 0.85 | 0.44 |
| 32 | 45.3 | 28.1 | 32.6 | 48.8 | | 0.51 | 0.81 | 0.73 | 0.46 |
| 128 | 36.4 | 29.9 | 28.1 | 48.5 | | 0.63 | 0.80 | 0.85 | 0.48 |
| 512 | 45.8 | 30.0 | 32.2 | 48.6 | | 0.50 | 0.80 | 0.74 | 0.49 |

## W=24 re-run of DPP + chunker (all cores; `sweep_tr_W24.csv`, merged into `sweep_tr.csv`; first pass = `sweep_tr_W23.csv`)
Within noise: DPP p99 @512 1517 → 1486 µs, 45.8 → 46.9 GB/s; chunker 2339 → 2358 µs, 32.2 → 32.2 GB/s (one outlier: chunker
p99 @128 720 → 1022 µs, the L3-transition zone). Tables above are the first pass; the figure uses the merged file.

## Findings
1. **Crossover at N ≈ 6-8 for both thread-bound designs (= cores / k for the gang):** gang p99 25 → 86 µs between
   N=4 and 8 while DPP is 101 → 74; chunker 51 → 133. Below it they win 2-4× (k-way split of one buffer with
   nothing else to do); above it they lose on every axis.
2. **At N=512:** DPP p99 1.5 ms, gang 3.4 ms (2.3×), chunker 2.3 ms (1.5×); max 2.8 vs 51 vs 6.5 ms; throughput 45.8
   vs 30.0 (−34 %) vs 32.2 (−30 %) GB/s; CPU per GB 0.50 vs 0.80 (+60 %) vs 0.74 (+48 %). The gap is a stable factor from
   N ≈ 32 on, plus a tail that keeps growing for the gang (max 20 → 51 ms from N=128 to 512).
3. **Thread-per-query (the SotA SPE model) is the tail story:** p50 flat at 62 µs and the HIGHEST throughput (48.6 GB/s,
   +6 % over DPP — the price of DPP's queue + shredder), but p99 17 ms at N=128 and 41 ms at N=512 (27× DPP), max 145 ms:
   CFS time-slicing of N compute-bound threads, one buffer per stream pays the whole descheduling wait.
4. **DPP's own low-N artefact:** p99 ≈ 100 µs at N=2-4 (vs 62 at N=1, 74 at N=8): with 23 mostly idle pooled workers,
   each completion wakes a parked worker (futex) and the next buffer lands on a different core (cold L2). That is the
   honest cost of not binding a stream to a thread; it vanishes once ≥ 8 workers stay busy.
5. DPP throughput dips to 36-39 GB/s at N=64-128 (working set 128-256 MiB crosses the 128 MiB L3) and is back at 45.8 at
   N=512; the thread-bound designs sit at 30-32 GB/s throughout.

## Chunker with the real structural scan (2026-09-10, `sweep_tr_W24idx.csv`, replaces the chunker rows in `sweep_tr.csv`)
User: "the chunker must scan the buffer sequentially — it should be similar to the SIMDCSV indexer, that is the fair
comparison." The cutter now runs the real `SIMDCSVInputFormatIndexer` (quote-aware, DPP's configuration) over the whole
buffer on the query's own thread and cuts from the band's newline positions; cuts verified identical to the shortcut's.
| N | chunker p99 µs (shortcut → scan) | DPP p99 | chunker p50 (scan) | chunker p999 (scan) | GB/s (shortcut → scan) | DPP GB/s | CPU s/GB (scan) | DPP |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 30 → 51 | 62 | 39 | 69 | 5.8 → 3.2 | 2.4 | 1.20 | 0.49 |
| 4 | 53 → 62 | 100 | 47 | 103 | 16.6 → 10.6 | 9.2 | 1.02 | 0.53 |
| 8 | 127 → 127 | 76 | 42 | 177 | 21.5 → 15.8 | 18.1 | 1.00 | 0.50 |
| 16 | 77 → 235 | 67 | 40 | 320 | 33.6 → 22.6 | 35.3 | 0.96 | 0.49 |
| 32 | 165 → 1660 | 113 | 63 | 3387 | 32.5 → 27.5 | 46.7 | 0.87 | 0.51 |
| 64 | 456 → 2131 | 239 | 291 | 3517 | 29.9 → 24.9 | 40.0 | 0.96 | 0.60 |
| 128 | 1022 → 2576 | 488 | 640 | 3756 | 28.1 → 24.1 | 37.2 | 0.99 | 0.64 |
| 256 | 1593 → 2905 | 811 | 1266 | 4134 | 31.5 → 25.3 | 43.9 | 0.95 | 0.55 |
| 512 | 2358 → 4284 | 1486 | 2853 | 5595 | 32.2 → 22.6 | 46.9 | 1.06 | 0.51 |
Findings: (a) the cutter's ~30 µs scan sits on the critical path — N=1 latency 30 → 51 µs (still below DPP's 62, but the
chunker's throughput at N=1 halves); (b) **the knee is now at N=16-32 with a 15× p99 jump at N=32 (1.66 ms vs DPP 0.11
ms, p999 3.4 ms)**: 32 cutters doing real work per buffer are no longer scheduler-favoured sleepers and wait behind the 24
busy workers; (c) at N=512 the chunker is 2.9× DPP on p99, 2.0× on p50, −52 % throughput, 2.1× CPU per byte. The
double scan (cutter index + worker index) is inherent to the design: a real chunker-plus-pool system (Arrow) scans twice too.

## Decision 2026-09-10: the figure pairs the QUOTE-FREE kernel with the QUOTE-FREE chunker
Every design in the figure runs the no-quote SIMDCSV kernel (`allow_commas_in_strings=false`, the setting of 418/420 e2e
runs in the paper). Under that assumption a record boundary is any newline, so a chunker needs no scan: the local newline
search at the k cut points (`NES_LAT_CUT=memchr`, layers W24 / W4) yields exactly the same chunks. Charging the chunker
a full structural scan (the `idx` layers above) while excusing DPP from quote tracking would be unfair — the scan is the
cost of a problem neither design solves here. The scan variant is kept as APPENDIX data for the general-CSV case
(`merge_sweeps.py --with-scan`). Figure chunker numbers = the "memchr" columns of the table above.

## FINAL chunker definition (2026-09-10, user-agreed): ONE sequential record-boundary scan per buffer (`NES_LAT_CUT=scan`)
The cutter walks every byte once (SIMD newline compare + bit walk, no field offsets — ~8 µs per 128 KiB on Zen 3) and cuts
from the boundaries it recorded. Between the two extremes: local search (~0.5 µs, "basically nothing") and the full
SIMDCSV index (~30 µs, fields too). Layer `sweep_tr_scan_D1.csv`, merged into `sweep_tr.csv` (figure).
| N | chunker p99 µs (memchr / scan / index) | DPP p99 | GB/s (memchr / scan / index) | DPP GB/s | CPU s/GB scan | DPP |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 30 / 36 / 51 | 62 | 5.8 / 4.4 / 3.2 | 2.4 | 0.96 | 0.49 |
| 8 | 127 / 122 / 127 | 76 | 21.5 / 19.2 / 15.8 | 18.1 | 0.91 | 0.50 |
| 16 | 77 / 288 / 235 | 67 | 33.6 / 27.0 / 22.6 | 35.3 | 0.84 | 0.49 |
| 32 | 165 / 590 / 1660 | 113 | 32.5 / 30.0 / 27.5 | 46.7 | 0.80 | 0.51 |
| 64 | 456 / 1660 / 2131 | 239 | 29.9 / 26.1 / 24.9 | 40.0 | 0.92 | 0.60 |
| 128 | 1022 / 2740 / 2576 | 488 | 28.1 / 21.5 / 24.1 | 37.2 | 1.11 | 0.64 |
| 256 | 1593 / 2520 / 2905 | 811 | 31.5 / 26.5 / 25.3 | 43.9 | 0.91 | 0.55 |
| 512 | 2358 / 3760 / 4284 | 1486 | 32.2 / 24.6 / 22.6 | 46.9 | 0.97 | 0.51 |
Scan chunker vs DPP: crossover N ≈ 8 (122 vs 76 µs); knee at N = 16-64 (p99 4-7× DPP); at N=512 2.5× p99, −48 %
throughput, 1.9× CPU per byte. The 8 µs cutter pass is what makes the per-query thread expensive: once the cutters do real
work they compete with the busy workers for cores instead of being favoured sleepers.

# D=64: 64 buffers in circulation per query (2026-09-10, `sweep_tr_D64m.csv` = all arms + chunker re-run after the
# offer/take race fix; 180 rows, tuples/row 1.0000, repeats 0)
The "fast source" model: each query keeps 64 × 128 KiB offered; buffer s+64 becomes available (clock starts) when s completes.
Under full load every design's median = 64·N / throughput (Little), so latencies are 64× the D=1 ones at equal throughput;
what differs is throughput and the tail. Pooled arms W=24, spin envelope as for D=1.

## design-best p99 ms · p50 ms · GB/s · CPU s/GB
| N | DPP | gang k=4 | chunker k=4 (scan) | thread-per-query |
|---:|---|---|---|---|
| 1 | 0.19 · 0.17 · 48.9 · 0.49 | 1.31 · 1.23 · 6.8 · 0.59 | 0.94 · 0.89 · 9.5 · 0.83 | 3.76 · 3.67 · 2.3 · 0.44 |
| 4 | 0.73 · 0.71 · 47.4 · 0.51 | 1.39 · 1.35 · 24.9 · 0.64 | 4.41 · 1.02 · 21.9 · 0.86 | 3.82 · 3.75 · 9.0 · 0.45 |
| 8 | 1.62 · 1.53 · 43.8 · 0.55 | 3.69 · 1.41 · 31.1 · 0.75 | 5.37 · 1.95 · 28.5 · 0.82 | 3.89 · 3.84 · 17.5 · 0.46 |
| 16 | 3.62 · 3.48 · 38.5 · 0.62 | 6.38 · 4.43 · 25.4 · 0.81 | 9.43 · 5.59 · 22.7 · 1.00 | 4.06 · 3.97 · 33.8 · 0.47 |
| 32 | 7.44 · 7.26 · 37.0 · 0.65 | 12.5 · 9.89 · 27.1 · 0.85 | 15.0 · 11.4 · 23.1 · 1.01 | 17.6 · 4.25 · 43.9 · 0.50 |
| 64 | 12.1 · 11.8 · 45.3 · 0.53 | 24.7 · 18.8 · 28.6 · 0.83 | 22.2 · 19.4 · 27.5 · 0.87 | 60.1 · 4.25 · 45.0 · 0.50 |
| 128 | 23.7 · 23.1 · 46.5 · 0.52 | 49.0 · 37.4 · 28.7 · 0.83 | 41.4 · 39.2 · 27.4 · 0.88 | 85.5 · 22.8 · 45.6 · 0.51 |
| 256 | 46.3 · 45.9 · 46.8 · 0.51 | 96.9 · 76.0 · 28.3 · 0.84 | 85.1 · 82.8 · 25.9 · 0.93 | 137 · 42.5 · 45.7 · 0.52 |
| 512 | 92.6 · 91.9 · 46.8 · 0.51 | 177 · 144 · 29.8 · 0.80 | 169 · 167 · 25.7 · 0.93 | 246 · 87.3 · 45.7 · 0.52 |

## Findings (backlog regime)
1. **With data waiting, DPP wins at EVERY N including N=1:** it spreads a query's 64 queued buffers over the whole pool
   (48.9 GB/s and 0.19 ms p99 at N=1) while the gang serialises them (6.8 GB/s, 1.3 ms = 64 × 20 µs) and thread-per-query
   is one core (2.3 GB/s, 3.8 ms). The gang's D=1 advantage below cores/k is an artefact of having nothing else to do.
2. **At N=512:** DPP 92.6 ms p99 (= 64·512/(46.8 GB/s ÷ 128 KiB) = 91.7 ms: pure Little), gang 177 ms (1.9×), chunker
   169 ms (1.8×), thread-per-query 246 ms (2.7×; its p50 stays at 87 ms — the same bimodal shape as at D=1 but the whole
   distribution now includes 64 buffers of queueing). Throughput ordering as at D=1: 46.8 / 29.8 / 25.7 / 45.7 GB/s.
3. **The chunker's tail at small N is the cutter:** p99/p50 = 4.3 at N=4 and 2.8 at N=8 (a cutter that lags stalls its
   64-buffer window at once), against 1.0-1.1 for DPP.
4. Thread-per-query keeps its throughput edge (+6 % over DPP, the queue+shredder cost) but its p99 is the worst of all
   arms from N=32 on, and its max exceeds 100 ms from N=64.
Rig note: the first D=64 chunker run was truncated at N=16 by an offer/take race in the rig (fixed: per-slot ready
handshake, take index = buffer index); `sweep_tr_D64.csv` keeps the raw run, `sweep_tr_fix_D64.csv` the re-run.

# Engine-admission window: D(N) = min(64, 1000/N) buffers in flight per query (2026-09-10, `sweep_tr_adm.csv`, 188 rows,
# tuples/row 1.0000, repeats 0; driver `run_admission.sh`)
The e2e engine keeps 64 buffers per source under a 1000-task global admission queue, so the total in flight is pinned near
1000 from N ≈ 16 on. This window reproduces that rule in the rig (one invocation per N). Latency = Little's law with a
capped backlog: ≈ 1000 / throughput ≈ 3 ms for DPP wherever the cap binds.

## design-best p99 ms · p50 ms · GB/s · CPU s/GB
| N | D | DPP | gang k=4 | chunker k=4 (scan) | thread-per-query |
|---:|---:|---|---|---|---|
| 1 | 64 | 0.19 · 0.17 · 48.7 · 0.49 | 1.28 · 1.25 · 6.7 · 0.60 | 0.92 · 0.89 · 9.5 · 0.82 | 3.82 · 3.73 · 2.2 · 0.45 |
| 4 | 64 | 0.72 · 0.70 · 48.0 · 0.50 | 1.41 · 1.36 · 24.7 · 0.65 | 4.27 · 1.01 · 22.2 · 0.83 | 3.90 · 3.79 · 8.8 · 0.45 |
| 8 | 64 | 1.59 · 1.52 · 44.0 · 0.55 | 3.73 · 1.41 · 31.1 · 0.75 | 5.41 · 1.99 · 28.3 · 0.82 | 3.97 · 3.89 · 17.2 · 0.47 |
| 16 | 62 | 3.47 · 3.37 · 38.5 · 0.62 | 6.18 · 2.34 · 25.2 · 0.82 | 9.21 · 5.49 · 22.4 · 1.01 | 4.09 · 3.99 · 32.5 · 0.49 |
| 32 | 31 | 3.52 · 3.42 · 38.0 · 0.63 | 6.18 · 4.73 · 27.4 · 0.84 | 8.57 · 5.29 · 23.2 · 1.03 | 11.5 · 2.09 · 43.4 · 0.52 |
| 64 | 15 | 3.51 · 3.39 · 37.1 · 0.65 | 6.27 · 4.37 · 28.6 · 0.83 | 8.46 · 5.62 · 21.6 · 1.11 | 31.8 · 1.00 · 44.1 · 0.51 |
| 128 | 7 | 3.33 · 3.22 · 36.5 · 0.66 | 6.30 · 3.99 · 29.1 · 0.82 | 8.22 · 5.76 · 19.9 · 1.20 | 30.4 · 0.47 · 45.2 · 0.51 |
| 256 | 3 | 2.43 · 2.30 · 43.6 · 0.55 | 5.83 · 3.38 · 29.4 · 0.82 | 6.88 · 4.95 · 20.0 · 1.20 | 31.0 · 0.20 · 46.0 · 0.51 |
| 512 | 1 | 1.51 · 1.45 · 46.3 · 0.52 | 3.43 · 2.26 · 29.4 · 0.82 | 3.72 · 2.67 · 24.9 · 0.96 | 41.5 · 0.06 · 46.8 · 0.51 |
Thread-per-query p999 / max: 17.6 / 27.4 ms at N=32, 51 / 98 ms at N=128, 59 / 133 ms at N=512.

## Findings
1. **DPP is FLAT: p99 3.3-3.5 ms from N=16 to N=128 (the e2e's "bounded ~4 ms"), falling to 2.4 and 1.5 ms at 256 and 512
   where the per-query window drops to 3 and 1 and fewer than 1000 buffers are in flight.** The rig thus reproduces the
   e2e regime once the e2e's window rule is applied; the ∝N growth of the uncapped D=1/D=64 windows was the window, not
   the design. Throughput 36-49 GB/s, p99/p50 ≤ 1.05.
2. **Gang k=4: 1.8-2.6× DPP p99 throughout (6.2-6.3 ms flat in the capped range), −25-40 % throughput, +60 % CPU.**
   No crossover anywhere: with data waiting, splitting one buffer 4-way never beats spreading buffers over the pool.
3. **Chunker k=4: 2.4-2.6× DPP p99 (8.2-9.2 ms flat), −40-45 % throughput, 1.0-1.2 s/GB (2× DPP)** — the sequential cutter
   pass plus the double index.
4. **Thread-per-query: p99 3.8 → 4.1 → 11.5 → 31.8 → 30-41 ms (N=1 → 16 → 32 → 64 → 128-512), p999 59 ms, max 133 ms,
   while its p50 collapses to 60 µs — the bimodal time-slicing signature; full throughput (46.8 GB/s, +1 % over DPP).**
   The e2e's blocking path reached 363 ms at 1000 sources: the extra factor is blocking-read wake storms and 2× N.

# ENGINE ADMISSION, exact: ≤64 buffers per query AND ≤1000 in flight in total, FIFO (2026-09-10, `sweep_tr_D64_C1000.csv`,
# 192 rows, 3 reps, tuples/row 1.0000, repeats 0, zero aborts, zero slot waits). SUPERSEDES the per-N-window section above.
| N | DPP | gang k=4 | chunker k=4 (scan) | thread-per-query |
|---:|---|---|---|---|
| 1 | 0.19 · 0.17 · 49.4 · 0.49 | 1.31 · 1.24 · 6.7 · 0.59 | 0.93 · 0.89 · 9.5 · 0.82 | 3.70 · 3.66 · 2.3 · 0.44 |
| 4 | 0.72 · 0.70 · 48.0 · 0.50 | 1.40 · 1.35 · 24.9 · 0.64 | 4.17 · 1.11 · 21.3 · 0.85 | 3.82 · 3.74 · 9.0 · 0.45 |
| 8 | 1.59 · 1.52 · 44.0 · 0.55 | 3.72 · 1.40 · 31.6 · 0.74 | 5.40 · 1.98 · 28.8 · 0.82 | 3.92 · 3.83 · 17.5 · 0.46 |
| 16 | 3.49 · 3.39 · 38.6 · 0.62 | 6.37 · 1.76 · 25.9 · 0.81 | 9.25 · 5.55 · 22.3 · 1.02 | 4.01 · 3.88 · 33.8 · 0.47 |
| 32 | 3.63 · 3.52 · 37.3 · 0.64 | 7.17 · 4.78 · 27.3 · 0.84 | 10.1 · 6.21 · 19.9 · 1.18 | 14.6 · 1.16 · 43.6 · 0.51 |
| 64 | 2.93 · 2.84 · 46.1 · 0.52 | 9.92 · 4.51 · 28.6 · 0.83 | 8.66 · 5.65 · 22.5 · 1.07 | 19.0 · 1.06 · 45.2 · 0.51 |
| 128 | 3.02 · 2.82 · 45.1 · 0.53 | 13.9 · 4.02 · 28.7 · 0.83 | 6.83 · 4.67 · 27.6 · 0.87 | 21.7 · 0.92 · 45.7 · 0.51 |
| 256 | 2.90 · 2.79 · 46.8 · 0.51 | 19.0 · 3.01 · 28.7 · 0.83 | 6.18 · 4.80 · 27.1 · 0.89 | 26.1 · 0.89 · 45.8 · 0.52 |
| 512 | 2.88 · 2.79 · 47.0 · 0.51 | 22.7 · 2.70 · 27.1 · 0.88 | 6.00 · 5.10 · 25.6 · 0.94 | 37.3 · 1.05 · 45.2 · 0.53 |
(p99 ms · p50 ms · GB/s · CPU s/GB.) Thread-per-query p999 / max: 19.6 / 32 ms at N=32, 35 / 55 ms at N=128, 56 / 92 ms at N=512.
Gang p999 / max: 18 / 32 ms at N=128, 31 / 43 ms at N=512.

## Findings
1. **DPP: flat 2.9-3.6 ms p99 from N=16 to N=512** (1000 buffers ÷ 45-47 GB/s; p99/p50 ≤ 1.07) — the e2e's "bounded ~4 ms"
   reproduced under the engine's own admission rule, with no fall-off at the high end.
2. **Gang: p99 grows monotonically 6.4 → 22.7 ms (1.8× → 7.9× DPP) while its p50 FALLS to 2.7 ms** — the join waits for
   descheduled members: 2048 threads on 24 cores. Throughput −40 %, CPU +70 %.
3. **Chunker: 6-10 ms flat (2.1-2.8× DPP), throughput −40-45 %, CPU +70-130 %** — the sequential cutter pass on N threads.
4. **Thread-per-query: p99 3.9 → 14.6 → 19 → 22 → 26 → 37 ms (N=16 → 512), p999 56 ms, max 92 ms, p50 ~1 ms** — 13× DPP at
   512 with the same throughput (45 GB/s): the SotA SPE model keeps its throughput and loses the tail.

## Chunker cost decomposition (2026-09-10, N=128, engine admission, spin 0, 1 rep × 4 s; `probe_chunker_decomp_tr.csv`)
| variant | GB/s | Δ vs DPP | CPU s/GB | p50 ms | p99 ms | p99/p50 | ctx sw/buf |
|---|---:|---:|---:|---:|---:|---:|---:|
| DPP (1 task/buffer) | 47.4 | — | 0.51 | 2.77 | 2.85 | 1.03 | 0.00 |
| gang on shared pool k=4 (split + join, no per-query thread) | 36.5 | −23 % | 0.66 | 3.59 | 3.68 | 1.03 | 0.00 |
| chunker k=1, local search (per-query thread hop only) | 40.4 | −15 % | 0.59 | 3.22 | 4.81 | 1.50 | 1.21 |
| chunker k=1, sequential scan (hop + scan) | 30.3 | −36 % | 0.79 | 4.21 | 6.57 | 1.56 | 0.99 |
| chunker k=4, local search (hop + 4-way split) | 32.3 | −32 % | 0.74 | 4.02 | 5.90 | 1.47 | 1.29 |
| **chunker k=4, sequential scan (figure)** | 27.2 | −43 % | 0.88 | 4.74 | 6.93 | 1.46 | 1.11 |
| chunker k=4, full index pass | 25.9 | −45 % | 0.93 | 4.93 | 7.31 | 1.48 | 1.03 |
Three separable costs: (1) **the per-query thread**: −15 % throughput and a 1.5× tail from ~1.2 context switches per
buffer (the cutter wake + the worker it preempts); (2) **the sequential scan**: another −25 %: not the ~8 µs of newline
compare measured at N=1 but ~26 µs per buffer at 47 GB/s aggregate — the cutter pulls all 128 KiB through its own core and
the workers then re-read the bytes on other cores, so every byte crosses the memory system twice on a box whose parse
throughput is already a large fraction of DRAM bandwidth; (3) **the k-way split**: −20 % (5 tasks per buffer: per-task fixed
cost, per-chunk leading-row assembly, chunk-level cache migration) — the same cost the shared-pool gang pays (−23 %) without
any per-query thread. Under admission control p99 ≈ p50 = backlog/throughput, so the chunker's flat 2-3× p99 IS this
throughput deficit, times its 1.5 tail factor. "Low overhead" holds only for variant 3 (hop only), and even that is −15 %.

## Trough investigation (2026-09-10): the N=16-32 dip is a working-set band of the rig, not the parsers

**Question (user):** why does the chunker's p99 go DOWN again after N=32 on the Threadripper?

**Finding.** Under full load p50 = in-flight / throughput (Little) for every arm (1000 buffers ÷ bufs/s matches p50 to
within 5 % at every N ≥ 16), so the p99 dip mirrors a THROUGHPUT trough that DPP has too (38 GB/s at N=16-32 vs 46-47
elsewhere; +25 % CPU/GB). The trough depends only on the size of the private per-query data rings: working set
= N × ring × 128 KiB, and the rig forces ring = max(NES_LAT_RING, D+8) = 72 at D=64 (NES_LAT_RING is silently ignored
there). Varying the ring at fixed N (D=1, `probe_trough2.sh`):

| N | ring | working set | DPP GB/s | CPU s/GB | DRAM fills / KiB |
|---|---|---|---|---|---|
| 32 | 16 | 64 MiB | 44.9 | 0.535 | 3.8 |
| 32 | 64 | 256 MiB | **36.0** | 0.666 | **11.4** |
| 32 | 128 | 512 MiB | 43.5 | 0.552 | 5.5 |
| 64 | 9 | 72 MiB | 42.9 | 0.559 | 4.2 |
| 64 | 16 | 128 MiB | **38.5** | 0.623 | **8.8** |
| 64 | 64 | 512 MiB | 44.6 | 0.538 | 3.9 |

Band ≈ 128 MiB - ~300 MiB for DPP (late DRAM fills per byte ×2-3), and up to ~600 MiB for the chunker whose single-thread
cutter scan is more latency-sensitive (per-thread profile: cutters 1.65× cycles/byte at N=32 vs N=128, workers 1.15×).
Below the band the data is cache-served, above it (≥ 2 GiB) it is plain DRAM streaming and flat. Main window with the
ring enlarged (`probe_trough3.sh`, `probe_trough5.sh`):

| arm | N | working set | GB/s | p99 ms | CPU s/GB |
|---|---|---|---|---|---|
| DPP | 16 | 512 MiB | 46.4 | 2.9 | 0.52 |
| DPP | 32 | 512 MiB | 44.9 | 3.0 | 0.53 |
| DPP | 16 / 32 | 2 GiB | 44.2 / 44.3 | 3.1 / 3.1 | 0.54 |
| chunker | 16 / 32 | 512 MiB | 22.0 / 21.3 | 9.1 / 9.1 | 1.06 / 1.12 (still in band) |
| chunker | 16 / 32 / 128 | 2 GiB | 28.1 / 27.6 / 26.6 | 7.7 / 7.6 / 7.0 | 0.85 / 0.87 / 0.90 (flat) |

Ruled out: scheduling (DPP's involuntary switches flat at ~970/s), pinning (unpinned chunker N=32: same), admission /
per-query window (D=64 uncapped and D=1 show the same band at the matching N), L3 capacity per se (recovers above).
Fill-source counters that work here: `ls_any_fills_from_sys.{lcl_l2,int_cache,ext_cache_local,mem_io_local}`
(`ext_cache_local` = another CCD's L3 on this single-socket part; `ext_cache_remote` is always 0). The Pi (2 MiB L3)
streams from N=1 and shows nothing.

**Fix:** `NES_LAT_WS_MIB` (rig) — the per-query ring grows (wrapping the file) so N × ring × 128 KiB ≥ 2 GiB at every N;
generations scale down to keep the control-block reuse distance. `run_fig.sh` passes `WS=2048` by default. Realistic
footing: a source's bytes always arrive from DRAM/NIC, never from cache.
