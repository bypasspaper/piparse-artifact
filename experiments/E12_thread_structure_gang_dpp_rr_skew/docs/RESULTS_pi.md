# Motivation figure — Raspberry Pi 5 column (2026-09-09, `sweep_pi.csv`, 192 rows)

`MACHINE=pi run_fig.sh` inside `nes-development:local-piparse` (`--cpuset-cpus 0-3`), binary `cmake-build-release-piparse`
(NES_BUILD_NATIVE=ON → cortex-a76), governor `ondemand` (no sudo), 4 cores; pooled arms W=4 (re-run; the first pass with
W=3 is `sweep_pi_W3.csv`), gang/tpq rows from the first pass. Same rig settings as the Threadripper column (128 KiB, ring 16,
gens 8, fmt 32 KiB, D=1, 1 s + 5 s, 3 reps, spin 0 ∀N + spin 50 at N ≤ 32 → design-best). Gate: tuples/row = 1.0000 in all
rows, repeats = 0. Wall time 20:11 → 20:37 (first pass) + 20:38 → 20:50 (W=4 re-run).

## p99 µs (design-best) · GB/s · CPU-s/GB
| N | DPP | gang k=4 | chunker k=4 | thread-per-query |
|---:|---:|---:|---:|---:|
| 1 | 344 · 0.39 · 2.59 | 119 · 1.36 · 2.94 | 125 · 1.29 · 3.08 | 344 · 0.40 · 2.54 |
| 2 | 352 · 0.78 · 2.59 | 298 · 1.34 · 2.97 | 215 · 1.38 · 2.88 | 348 · 0.79 · 2.54 |
| 4 | 373 · 1.55 · 2.57 | 511 · 1.32 · 3.01 | 417 · 1.39 · 2.87 | 372 · 1.55 · 2.58 |
| 8 | 721 · 1.55 · 2.58 | 990 · 1.30 · 3.08 | 875 · 1.40 · 2.86 | 4377 · 1.54 · 2.60 |
| 16 | 1435 · 1.54 · 2.59 | 2032 · 1.24 · 3.23 | 1733 · 1.40 · 2.85 | 12384 · 1.53 · 2.60 |
| 32 | 2848 · 1.53 · 2.60 | 4222 · 1.19 · 3.35 | 3342 · 1.39 · 2.88 | 28388 · 1.54 · 2.60 |
| 64 | 5692 · 1.53 · 2.61 | 10604 · 1.15 · 3.48 | 6521 · 1.37 · 2.92 | 64390 · 1.54 · 2.60 |
| 128 | 11318 · 1.53 · 2.62 | 21347 · 1.14 · 3.50 | 12863 · 1.37 · 2.92 | 250320 · 1.53 · 2.61 |
| 256 | 22632 · 1.53 · 2.62 | 42090 · 1.13 · 3.52 | 25210 · 1.37 · 2.92 | 541473 · 1.53 · 2.61 |
| 512 | 44747 · 1.52 · 2.62 | 84419 · 1.13 · 3.54 | 49725 · 1.37 · 2.92 | 600407 · 1.53 · 2.61 |

Max latency at N=512: DPP 59 ms (W3 run) / gang 160 ms / chunker 67 ms / thread-per-query **4.24 s**.

## Findings
1. **Worker count matters on 4 cores (the W=3 → W=4 re-run):** DPP throughput 1.16 → 1.55 GB/s and p99 @512 58.6 → 44.7 ms;
   chunker 1.06 → 1.37 GB/s, 63.6 → 49.7 ms. With 3 workers the pooled designs left a quarter of the machine idle while the
   thread-bound designs used all of it; the rule is now "pooled designs get every core" on both machines (TR: +2-3 %, noise).
2. **Crossover at N = 2-4 (cores/k = 1 for the gang; the gang still wins at N=2 because DPP idles 2 of its 4 workers):**
   gang p99 119/298/511 µs at N=1/2/4 vs DPP 344/352/373; chunker 125/215/417.
3. **At N=512:** DPP p99 44.7 ms, gang 84.4 ms (1.89×, max 160 ms), chunker 49.7 ms (1.11×); throughput 1.52 vs 1.13 (−26 %)
   vs 1.37 (−10 %) GB/s; CPU per GB 2.62 vs 3.54 (+35 %) vs 2.92 (+11 %). Every design is Little-bound (p50 ≈ N/throughput), so
   the p99 ratio ≈ throughput ratio × tail factor.
4. **Thread-per-query collapses at every N ≥ 8:** p50 flat at 336 µs and full throughput (1.53 GB/s = DPP), but p99 4.4 ms at
   N=8, 28 ms at 32, 250 ms at 128, 600 ms at 512 (13× DPP), max 4.2 s — 512 compute-bound threads on 4 cores, each stream
   waiting a full round of CFS slices. On 4 cores the cliff starts at 8 queries, not 128.
5. **Per-core parse rate:** Pi 0.39 GB/s per core (A76 2.4 GHz, NEON 128-bit) vs Threadripper 2.3 (Zen 3 AVX2): 6×; CPU per
   GB 2.6 s vs 0.5 s. The Pi saturates at N=4 (1.55 GB/s ≈ 4 × 0.39).

## Chunker with the real structural scan (2026-09-10, `sweep_pi_W4idx.csv`, replaces the chunker rows in `sweep_pi.csv`)
Cutter = the real SIMDCSV indexer over the whole buffer on the query's thread (see RESULTS_tr.md for the rationale).
| N | chunker p99 ms (shortcut → scan) | DPP p99 | chunker p50 (scan) | GB/s (shortcut → scan) | DPP GB/s | CPU s/GB (scan) | DPP |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.12 → 0.25 | 0.34 | 0.23 | 1.29 → 0.58 | 0.39 | 4.08 | 2.59 |
| 4 | 0.42 → 0.71 | 0.37 | 0.49 | 1.39 → 1.05 | 1.55 | 3.80 | 2.57 |
| 8 | 0.87 → 1.25 | 0.72 | 0.95 | 1.40 → 1.05 | 1.55 | 3.79 | 2.58 |
| 32 | 3.34 → 6.60 | 2.85 | 3.87 | 1.39 → 1.01 | 1.53 | 3.94 | 2.60 |
| 128 | 12.86 → 19.32 | 11.32 | 16.78 | 1.37 → 0.99 | 1.53 | 4.02 | 2.62 |
| 512 | 49.73 → 69.86 | 44.75 | 67.35 | 1.37 → 0.99 | 1.52 | 4.02 | 2.62 |
Findings: the cutter's scan (~130 µs per buffer on the A76) costs the chunker a third of the machine: throughput 1.37 →
0.99 GB/s (−35 % vs DPP), CPU per byte 4.02 vs 2.62 (+53 %), and by Little's law p99 1.56× DPP at N=512 (69.9 vs 44.8 ms).
The crossover moves to N=2-4 (0.41 vs 0.35 ms at N=2). On 4 saturated cores the tail stays Little-tight (p999 ≈ p99):
the chunker's cost on the Pi is throughput, not jitter; the Threadripper shows the jitter as well (its 24 workers leave
the cutters fighting for slots: 15× p99 at N=32).

## Decision 2026-09-10: the figure pairs the QUOTE-FREE kernel with the QUOTE-FREE chunker
Every design in the figure runs the no-quote SIMDCSV kernel (`allow_commas_in_strings=false`, the setting of 418/420 e2e
runs in the paper). Under that assumption a record boundary is any newline, so a chunker needs no scan: the local newline
search at the k cut points (`NES_LAT_CUT=memchr`, layers W24 / W4) yields exactly the same chunks. Charging the chunker
a full structural scan (the `idx` layers above) while excusing DPP from quote tracking would be unfair — the scan is the
cost of a problem neither design solves here. The scan variant is kept as APPENDIX data for the general-CSV case
(`merge_sweeps.py --with-scan`). Figure chunker numbers = the "memchr" columns of the table above.

# D=64: 64 buffers in circulation per query (2026-09-10, `sweep_pi_D64m.csv`; 192 rows, tuples/row 1.0000, repeats 0)
Same model as RESULTS_tr.md's D=64 section; pooled arms W=4. (The chunker rows come from the pre-fix binary — the
offer/take race did not trigger on the Pi's slower cutters; a fixed-binary re-run overlays them when it lands.)

## design-best p99 ms · p50 ms · GB/s · CPU s/GB
| N | DPP | gang k=4 | chunker k=4 (scan) | thread-per-query |
|---:|---|---|---|---|
| 1 | 5.6 · 5.4 · 1.55 · 2.58 | 6.8 · 6.3 · 1.33 · 3.00 | 7.4 · 6.9 · 1.22 · 3.28 | 21.4 · 21.3 · 0.39 · 2.55 |
| 4 | 22.3 · 21.7 · 1.54 · 2.59 | 30.0 · 25.4 · 1.32 · 3.02 | 29.5 · 28.0 · 1.20 · 3.34 | 22.4 · 21.6 · 1.54 · 2.59 |
| 8 | 44.3 · 43.5 · 1.54 · 2.59 | 55.0 · 51.5 · 1.30 · 3.07 | 59.2 · 56.1 · 1.19 · 3.34 | 48.8 · 44.3 · 1.53 · 2.60 |
| 32 | 176 · 175 · 1.53 · 2.61 | 237 · 228 · 1.19 · 3.36 | 231 · 228 · 1.17 · 3.40 | 210 · 176 · 1.53 · 2.61 |
| 128 | 705 · 703 · 1.53 · 2.62 | 1040 · 946 · 1.14 · 3.51 | 922 · 920 · 1.17 · 3.42 | 2013 · 618 · 1.53 · 2.61 |
| 512 | 2818 · 2817 · 1.52 · 2.62 | 4028 · 3766 · 1.14 · 3.51 | 3686 · 3591 · 1.17 · 3.43 | 6103 · 2686 · 1.52 · 2.63 |

## Findings
1. **With a backlog DPP wins at every N on the Pi too**, including N=1: it puts all 4 cores on the one query's 64 waiting
   buffers (1.55 GB/s, 5.6 ms) while the gang serialises (1.33 GB/s, 6.8 ms), the chunker's cutter throttles (1.22 GB/s,
   7.4 ms) and thread-per-query is one core (0.39 GB/s, 21 ms).
2. **Everything is Little-bound:** 64 × 512 buffers = 4.3 GB in flight on a 1.5 GB/s machine → DPP 2.8 s at N=512, and
   the others sit above it by their throughput deficit: gang 1.43× (1.14 GB/s), chunker 1.31× (1.17), thread-per-query
   2.2× (its p50 equals DPP's since its throughput does, its p99 is the time-slicing tail on top: 6.1 s).
3. On 4 cores the throughput ordering under backlog is DPP = thread-per-query (1.52-1.53) > gang (1.14, −25 %) > chunker
   (1.17, −23 %); CPU per byte 2.6 / 2.6 / 3.5 / 3.4 s per GB.
Fixed-binary chunker overlay landed (`sweep_pi_fix_D64.csv`, merged into `sweep_pi_D64m.csv`): p99 +2-4 % (N=512: 3686 → 3806 ms),
throughput 1.17 → 1.13-1.15 GB/s — the per-slot ready handshake adds a little cutter work; conclusions unchanged.

# Engine-admission window: D(N) = min(64, 1000/N) (2026-09-10, `sweep_pi_adm.csv`, 192 rows, tuples/row 1.0000, repeats 0)
Same rule as RESULTS_tr.md's admission section (the engine's per-source cap under its 1000-task admission queue). On a
1.5 GB/s machine the 1000-buffer backlog is 128 MB ≈ 85 ms of work, so the DPP plateau sits at ~85 ms instead of 3.5 ms.

## design-best p99 ms · p50 ms · GB/s · CPU s/GB
| N | D | DPP | gang k=4 | chunker k=4 (scan) | thread-per-query |
|---:|---:|---|---|---|---|
| 1 | 64 | 5.6 · 5.4 · 1.55 · 2.58 | 7.0 · 6.3 · 1.33 · 2.99 | 8.0 · 7.4 · 1.13 · 3.46 | 21.4 · 21.2 · 0.39 · 2.54 |
| 8 | 64 | 44.2 · 43.5 · 1.54 · 2.59 | 54.5 · 51.6 · 1.30 · 3.08 | 63.5 · 60.3 · 1.11 · 3.59 | 48.8 · 44.3 · 1.53 · 2.60 |
| 16 | 62 | 85.3 · 84.4 · 1.54 · 2.60 | 112 · 106 · 1.24 · 3.23 | 116 · 112 · 1.16 · 3.45 | 99.1 · 82.7 · 1.53 · 2.61 |
| 32 | 31 | 86.1 · 85.1 · 1.53 · 2.62 | 118 · 110 · 1.19 · 3.36 | 120 · 117 · 1.11 · 3.60 | 107 · 90.5 · 1.53 · 2.60 |
| 64 | 15 | 83.3 · 82.5 · 1.52 · 2.62 | 130 · 111 · 1.15 · 3.47 | 112 · 109 · 1.15 · 3.48 | 183 · 65.1 · 1.54 · 2.60 |
| 128 | 7 | 77.8 · 77.0 · 1.52 · 2.62 | 128 · 106 · 1.14 · 3.52 | 109 · 107 · 1.10 · 3.63 | 667 · 54.4 · 1.53 · 2.61 |
| 256 | 3 | 70.1 · 68.5 · 1.47 · 2.72 | 111 · 90.9 · 1.13 · 3.52 | 94.4 · 92.5 · 1.09 · 3.68 | 944 · 1.01 · 1.53 · 2.61 |
| 512 | 1 | 45.0 · 44.3 · 1.52 · 2.64 | 85.0 · 60.8 · 1.12 · 3.55 | 60.9 · 59.0 · 1.14 · 3.51 | 800 · 0.34 · 1.53 · 2.61 |
Thread-per-query p999 / max: 119 / 137 ms at N=32, 880 / 1616 ms at N=128, 2728 / 3748 ms at N=512.

## Findings
1. **DPP plateau at 78-86 ms from N=16 to 128** (the 1000-buffer cap ÷ 1.5 GB/s), then 70 and 45 ms as the window drops
   to 3 and 1. Throughput 1.47-1.55 GB/s, p99/p50 ≤ 1.03 everywhere.
2. **Gang 1.3-1.9× DPP p99 on the plateau, chunker 1.3-1.4×**, both with −25-30 % throughput and +35-40 % CPU per byte;
   no crossover at any N.
3. **Thread-per-query collapses past 4 threads per core: p99 99 → 107 → 183 → 667 → 944 → 800 ms (N=16 → 512)** with p50
   falling to 0.3 ms, p999 2.7 s and a worst buffer of 3.7 s at N=512 — 18× DPP's p99 and the e2e's order-of-magnitude
   shape, on pure compute. On 4 cores the scheduler cliff is where the e2e saw it on 24: a few threads per core.

# ENGINE ADMISSION, exact: ≤64 buffers per query AND ≤1000 in flight in total, FIFO admission (2026-09-10, `sweep_pi_D64_C1000.csv`,
# 192 rows, 3 reps, tuples/row 1.0000, repeats 0, zero aborts). SUPERSEDES the per-N-window "adm" section above (its integer
# window under-filled the cap at N ≥ 256 and made every design look faster there).
A completed buffer's admission slot goes to the longest-waiting query; the admitted buffer's clock starts at admission (the e2e
read-start stamp). Total in flight = min(1000, 64·N): pinned at 1000 from N=16 on.

## design-best p99 ms · p50 ms · GB/s · CPU s/GB
| N | DPP | gang k=4 | chunker k=4 (scan) | thread-per-query |
|---:|---|---|---|---|
| 1 | 5.6 · 5.4 · 1.55 · 2.58 | 6.8 · 6.3 · 1.34 · 2.99 | 7.4 · 6.9 · 1.21 · 3.28 | 21.4 · 21.2 · 0.39 · 2.54 |
| 4 | 22.3 · 21.7 · 1.55 · 2.59 | 27.2 · 25.3 · 1.32 · 3.02 | 29.5 · 28.0 · 1.20 · 3.34 | 22.3 · 21.6 · 1.55 · 2.59 |
| 8 | 44.2 · 43.5 · 1.54 · 2.59 | 57.8 · 51.3 · 1.30 · 3.07 | 59.0 · 56.1 · 1.20 · 3.34 | 49.0 · 44.2 · 1.54 · 2.60 |
| 16 | 86.1 · 85.2 · 1.54 · 2.60 | 112 · 106 · 1.24 · 3.23 | 113 · 109 · 1.20 · 3.34 | 96.1 · 86.4 · 1.53 · 2.61 |
| 32 | 86.5 · 85.6 · 1.53 · 2.61 | 122 · 111 · 1.19 · 3.35 | 114 · 111 · 1.18 · 3.38 | 121 · 86.1 · 1.53 · 2.61 |
| 64 | 86.7 · 85.9 · 1.53 · 2.62 | 171 · 117 · 1.14 · 3.50 | 114 · 112 · 1.17 · 3.41 | 265 · 73.7 · 1.53 · 2.61 |
| 128 | 86.8 · 85.9 · 1.52 · 2.62 | 232 · 116 · 1.14 · 3.51 | 114 · 113 · 1.17 · 3.43 | 529 · 34.4 · 1.52 · 2.62 |
| 256 | 86.7 · 85.9 · 1.53 · 2.62 | 303 · 105 · 1.13 · 3.53 | 114 · 112 · 1.17 · 3.43 | 630 · 32.4 · 1.50 · 2.66 |
| 512 | 86.6 · 85.7 · 1.53 · 2.61 | 334 · 95.0 · 1.13 · 3.53 | 114 · 112 · 1.17 · 3.42 | 746 · 40.4 · 1.47 · 2.72 |
Thread-per-query p999 / max: 128 / 142 ms at N=32, 788 / 1021 ms at N=128, 1225 / 1598 ms at N=512. Gang p999 at N=512: see CSV.

## Findings
1. **DPP: a perfectly flat 86 ms p99 from N=16 to N=512** (= 1000 buffers ÷ 1.53 GB/s; p99/p50 = 1.01) — the Pi analogue of
   the e2e's bounded latency, on 4 cores.
2. **Chunker: flat too, at 114 ms (1.32× DPP)** — its cost here is purely throughput (−24 %) and CPU (+31 %); the cutter pass
   does not add tail on a 4-core box where everything is queue-bound.
3. **Gang: the tail fans out with N — p99 112 → 334 ms (1.3× → 3.9× DPP) while its p50 stays ~100-115 ms and even falls;**
   throughput −26 %, CPU +36 %. 2048 gang threads at N=512 on 4 cores: the join waits for descheduled members.
4. **Thread-per-query: p99 96 → 746 ms (8.6× DPP at 512), p999 1.2 s, max 1.6 s, while p50 collapses to 32-40 ms** — the
   e2e's order-of-magnitude collapse reproduced on pure compute at DPP's throughput (1.47-1.53 GB/s).
