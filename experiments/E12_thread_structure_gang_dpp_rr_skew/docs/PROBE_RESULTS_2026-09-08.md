# Early probe — gang-parallel / chunker / thread-per-stream vs DPP, latency vs #streams (2026-09-08)

`run_probe.sh` @ b5d757c9f6 + uncommitted `FormatterLatencyBenchmark.cpp`. Threadripper PRO 5965WX, `taskset -c 0-23`
(24 physical cores, SMT siblings excluded), governor performance. Numeric quote-free `bench_5xUINT64_512m.csv`,
128 KiB buffers, ring 64/stream, project f1 + fnattr, FastUINT64. Closed loop, D=1 per stream, 1 s warm-up + 5 s window,
2 reps (median shown), spin-then-futex waits with a 50 µs spin budget in EVERY arm. Pooled arms: 23 workers pinned
cpu 0-22. Raw: `probe.csv`, logs `logs/`, tables `summarize_probe.py`.

Arms: **dpp** (1 task/buffer, shredder) · **gshared k=4** (4 sub-chunks forked into the same pool, join counter) ·
**gprivate k=4** (4 dedicated threads per stream, leader fork + join) · **chunker k=4** (1 light cutter thread per
stream → record-aligned chunks → pool with per-worker SequentialCSV stages, no shredder/join) ·
**gprivate k=1** (= plain thread-per-stream sequential parsing, the intro figure's SPE model).

## p50 µs
| N | dpp | gshared 4 | gprivate 4 | chunker 4 | gprivate 1 |
|---:|---:|---:|---:|---:|---:|
| 1 | 58.0 | 21.2 | 19.7 | 21.7 | 57.1 |
| 4 | 59.4 | 23.6 | 21.1 | 25.3 | 58.2 |
| 8 | 62.4 | 29.6 | 21.4 | 24.8 | 59.7 |
| 16 | 67.9 | 65.8 | 21.5 | 32.1 | 61.6 |
| 24 | 85.4 | 104.5 | 123.0 | 43.5 | 64.6 |
| 32 | 116.0 | 141.2 | 273.5 | 52.9 | 66.6 |
| 64 | 188.7 | 241.5 | 784.0 | 279.1 | 65.6 |
| 128 | 373.2 | 482.6 | 1546.1 | 637.5 | 65.8 |
| 256 | 742.7 | 960.1 | 3177.3 | 1357.4 | 66.0 |

## p99 µs
| N | dpp | gshared 4 | gprivate 4 | chunker 4 | gprivate 1 |
|---:|---:|---:|---:|---:|---:|
| 1 | 78.9 | 27.8 | 23.9 | 29.0 | 62.0 |
| 4 | 95.7 | 30.3 | 25.7 | 57.0 | 63.1 |
| 8 | 82.4 | 37.4 | 291.7 | 410.3 | 65.1 |
| 16 | 88.7 | 76.2 | 816.7 | 4174.9 | 67.8 |
| 24 | 106.3 | 116.3 | 1334.2 | 2533.7 | 73.3 |
| 32 | 144.0 | 153.9 | 1318.3 | 2884.8 | 88.9 |
| 64 | 206.2 | 255.3 | 1345.5 | 2838.4 | 94.2 |
| 128 | 394.3 | 498.0 | 2580.2 | 3122.2 | 17101.4 |
| 256 | 785.0 | 982.8 | 5010.2 | 3730.4 | 26656.7 |

## Sustained GB/s · CPU-seconds per GB
| N | dpp | gshared 4 | gprivate 4 | chunker 4 | gprivate 1 | | dpp | gshared 4 | gprivate 4 | chunker 4 | gprivate 1 |
|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 2.23 | 6.16 | 6.59 | 5.84 | 2.28 | | 0.51 | 0.84 | 0.61 | 1.06 | 0.44 |
| 8 | 16.5 | 35.2 | 31.9 | 20.9 | 17.5 | | 0.61 | 0.65 | 0.74 | 1.07 | 0.46 |
| 16 | 30.4 | 31.7 | 22.5 | 17.8 | 33.9 | | 0.65 | 0.73 | 1.03 | 0.86 | 0.47 |
| 24 | 36.5 | 30.0 | 16.9 | 23.9 | 48.3 | | 0.63 | 0.77 | 1.40 | 0.95 | 0.50 |
| 32 | 35.9 | 29.6 | 13.3 | 24.1 | 43.3 | | 0.64 | 0.78 | 1.79 | 0.99 | 0.52 |
| 64 | 44.4 | 34.7 | 10.8 | 22.8 | 44.3 | | 0.52 | 0.66 | 2.22 | 1.05 | 0.51 |
| 128 | 44.9 | 34.8 | 10.7 | 22.8 | 45.2 | | 0.51 | 0.66 | 2.24 | 1.05 | 0.51 |
| 256 | 45.1 | 34.9 | 10.6 | 22.8 | 45.7 | | 0.51 | 0.66 | 2.26 | 1.05 | 0.52 |

## Mean µs (= N · window / buffers — Little, D=1: equal throughput ⇒ equal mean)
| N | dpp 1 | gshared 4 | gprivate 4 | chunker 4 | gprivate 1 |
|---:|---:|---:|---:|---:|---:|
| 1 | 58.8 | 21.3 | 19.9 | 22.5 | 57.4 |
| 4 | 61.4 | 23.8 | 21.2 | 31.9 | 58.5 |
| 8 | 63.5 | 29.8 | 32.9 | 50.3 | 60.0 |
| 16 | 68.9 | 66.2 | 93.6 | 118.0 | 61.9 |
| 24 | 86.1 | 105.0 | 189.0 | 131.6 | 65.1 |
| 32 | 116.9 | 141.7 | 317.6 | 173.9 | 97.0 |
| 64 | 189.1 | 242.0 | 777.1 | 367.9 | 189.5 |
| 128 | 373.8 | 482.8 | 1569.3 | 734.9 | 371.4 |
| 256 | 744.5 | 960.4 | 3157.5 | 1474.0 | 734.6 |

## p999 µs
| N | dpp 1 | gshared 4 | gprivate 4 | chunker 4 | gprivate 1 |
|---:|---:|---:|---:|---:|---:|
| 1 | 97.7 | 34.6 | 27.5 | 36.2 | 77.6 |
| 4 | 116.4 | 34.1 | 28.3 | 1015.4 | 70.4 |
| 8 | 109.3 | 41.9 | 399.7 | 3408.2 | 83.1 |
| 16 | 124.5 | 81.5 | 2369.5 | 6616.3 | 87.8 |
| 24 | 120.7 | 121.7 | 3109.8 | 3987.4 | 97.8 |
| 32 | 158.5 | 159.7 | 2824.2 | 4026.4 | 7720.1 |
| 64 | 219.0 | 262.8 | 2809.2 | 3736.6 | 29100.3 |
| 128 | 413.1 | 511.3 | 3638.9 | 3961.3 | 27958.3 |
| 256 | 811.6 | 1010.4 | 5965.4 | 4598.8 | 36730.9 |

## Findings

1. **N=1: every per-stream-parallel design beats DPP ~3× on latency** (20-22 vs 58 µs p50) at 1.2-2× the CPU per
   byte. Expected, and the honest part of the story.
2. **DPP: knee at N ≈ 23 (= workers), then p50 ∝ N/23 × 65 µs exactly (Little, D=1), p99/p50 ≤ 1.36 everywhere,
   throughput saturates at 45 GB/s, CPU/GB flat 0.51.** The reference shape.
3. **gprivate k=4 (SotA gang in a thread-per-source SPE): knee at N = 8 (= 24/k... 6-8), p99 fans out 14× at N=8 and
   38× at N=16 while p50 is still 21 µs; from N=24 p50 is 1.4-4.3× DPP and p99 5-13× DPP; throughput COLLAPSES
   32 → 10.6 GB/s (4.2× below DPP) with CPU/GB 2.26 (4.4× DPP).** The collapse is the 50 µs spin budget under
   oversubscription (N·k spinning members burn the cores the other gangs need) + ~4 context switches per buffer.
   ⚠️ fairness: the gang must also be run with spin = 0 (pure futex) — that is its best configuration at high N
   (gang-best envelope), and the throughput collapse will shrink. NOT yet run.
4. **gshared k=4 (gang kernel on the shared pool): best p50 up to N=8, knee at N ≈ 8-16 (each buffer occupies 4
   workers → saturates at N·k ≈ 23), then 1.3× ABOVE DPP in p50 with tight tails; throughput 35 GB/s = −23% vs DPP
   (4× the tasks + join), CPU/GB 0.66 (+29%).** Confirms the ablation reading: the win is the resource model, the
   join/chunking costs ~25% throughput at 128 KiB.
5. **chunker k=4: lowest p50 of all arms from N=8 to N=32 (25-53 µs; 4-way split, no join, no shredder) — but the
   p99 explodes from N=8 (410 µs) to 2.5-4.2 ms from N=16 on (p99/p50 up to 130), throughput only 23 GB/s (half of
   DPP), CPU/GB 1.05 (2× DPP).** The cutter thread sits in the critical path: with 23 spinning workers + N cutters
   the process is oversubscribed from N=2 on, a cutter waiting for a core stalls its stream by a scheduler quantum
   (ms). Also to be re-run with spin = 0.
6. **gprivate k=1 (thread-per-stream, the intro figure's model): p50 FLAT at 57-66 µs for ALL N and throughput =
   DPP (45.7 GB/s, CPU/GB 0.51) — but p99 explodes to 17 ms @128 and 27 ms @256, p999 7.7 ms already @32 and 29 ms
   @64.** CFS gives each of 256 compute-bound threads a ~3 ms slice: a thread rips through ~45 buffers at 66 µs
   each, then is descheduled for (N/24 − 1) slices — and under closed-loop D=1 only ONE buffer per descheduling
   pays that wait (the stream is "polite": it offers nothing while its thread is away).

## Measurement subtlety to carry into the design (Little's law with D=1)
Under closed loop with one buffer in flight, **mean latency per stream = 1 / per-stream throughput** for every arm
(mean = N · window / buffers): equal throughput ⇒ equal mean. Arms differ only in the SHAPE: DPP = fair
round-robin (p50 ≈ p99 ≈ mean); thread-bound designs = bimodal (most buffers fast, one per descheduling
catastrophic → flat p50, exploding p99/p999, same mean). A real sensor keeps producing while its thread is
descheduled, so every buffer arriving during a 27 ms stall would see it — the closed-loop p50 UNDER-states the
thread-per-stream latency; the p99/p999/max carry the story, and the mean is the arm-independent sanity check.
This is the argument for reporting p99 (or an open-loop appendix), not p50, in the paper figure.

## Next
- spin = 0 re-run of gprivate-4 / chunker-4 / gshared-4 / dpp (gang-best envelope; expect gprivate throughput to
  recover partly, tails to stay) → `NES_LAT_SPIN_US=0`.
- then the full sweep per DESIGN §4 (5 reps, 10 s windows, k ∈ {1,2,4,8}, finer N around the knees 6-32).
- DuckDB / Arrow single-stream anchor.

---
# Spin = 0 re-run (pure futex block, `probe_spin0.csv`, same grid) — the fairness pass

Side-by-side tables (spin50 / spin0) for p50, p99, GB/s, CPU s/GB and the best-of-both envelope: `compare_spin.txt`
(`compare_spin.py`). Headline numbers, spin50 → spin0:

| arm | N=1 p50 | N=8 p99 | N=16 p50 / p99 | N=256 p50 / p99 | GB/s @256 | CPU s/GB @256 |
|---|---:|---:|---:|---:|---:|---:|
| dpp | 58 → 58 | 82 → 99 | 68/89 → 68/102 | 743/785 → 743/787 | 45.1 → 45.0 | 0.51 → 0.51 |
| gshared 4 | 21 → 27 | 37 → 39 | 66/76 → 66/77 | 960/983 → 964/989 | 34.9 → 34.8 | 0.66 → 0.66 |
| **gprivate 4** | 20 → 31 | **292 → 88** | 22/817 → **79/160** | 3177/5010 → **1104/1876** | **10.6 → 30.2** | **2.26 → 0.80** |
| **chunker 4** | 22 → 36 | **410 → 140** | 32/4175 → **66/93** | 1357/3730 → **1047/1160** | **22.8 → 31.8** | **1.05 → 0.75** |
| gprivate 1 | 57 → 57 | 65 → 65 | 62/68 → 62/68 | 66/26657 → 66/25896 | 45.7 → 45.8 | 0.52 → 0.51 |

## Findings (revised with the envelope = best policy per N, the gang-best rule)

1. **The spin policy is the gang's dilemma, not ours.** Spinning gives the gang its best low-N latency (20 µs at
   N=1) and destroys it under oversubscription (throughput ÷4, p99 ×6). Blocking costs it 1.5× at N=1 (31 µs: one
   futex wake per fork on the critical path) and limits the high-N damage to 1.5× p50 / 2.4× p99 / −33% throughput
   / +60% CPU per byte vs DPP. No single configuration is good on both ends; DPP needs no such choice (its workers
   are always busy under load, so the policy is irrelevant: dpp rows are identical under both).
2. **Gang-best (min p99 over policies) vs DPP:** N=1 24 vs 64 (gang 2.7× better), N=4 26 vs 96, **N=8 88 vs 82
   (crossover — exactly the predicted cores/k knee at N ≈ 6-8)**, N=16 160 vs 89 (1.8×), N=24 226 vs 106 (2.1×),
   N=64 486 vs 206 (2.4×), N=256 1876 vs 785 (2.4×). Throughput past the knee 30 vs 45 GB/s, CPU/GB 0.80 vs 0.51.
3. **chunker (spin 0): the ms tails were an artifact of spinning workers starving the cutter threads; with
   blocking waits it behaves like gshared with a per-stream thread hop: p50 1.4× DPP past N=16, p99 1.5× DPP,
   throughput 31 GB/s (−30%), CPU/GB 0.75-0.85 (+50%).** Best p50 of all arms only up to N=8 now. The per-stream
   cutter thread costs MORE than gshared's join at 128 KiB granularity.
4. **thread-per-stream (gprivate k=1) is policy-independent** (its only wait is on itself): flat p50, DPP's
   throughput, and a p99 of 17-27 ms at N ≥ 128 (22-35× DPP) from CFS time-slicing — the intro figure's mechanism
   reproduced in isolation, on compute alone (no IO storms needed).
5. **Unchanged:** dpp knee at N=23 with p50 ∝ N/23 × 65 µs, p99/p50 ≤ 1.4 everywhere, 45 GB/s, 0.51 CPU-s/GB; gshared
   = tight-tailed, 1.3× DPP latency, −23% throughput.

## What the paper figure can say (probe-level confidence, 2 reps × 5 s)
- Panel (a) p99 vs N: DPP flat to 23 then ∝ N; gang-best (k=4) 2.7× better at N=1, crosses at N ≈ 8 = cores/k, then
  2-2.4× worse; thread-per-stream flat to N=64 then 20-35× worse (the oversubscription cliff).
- Panel (b) throughput + CPU-s/GB vs N: DPP 45 GB/s / 0.51; gang-best 30 / 0.80; thread-per-stream 45 / 0.51.
- Honest caveat: the mean latency is arm-independent for equal throughput under closed loop D=1 (Little); the
  figure must plot p99 (or add an open-loop appendix) — see the subtlety section above.

## Next (needs a decision)
- Full sweep: both policies (envelope), k ∈ {1, 2, 4, 8} for gprivate, gshared k ∈ {2,4,8}, chunker k ∈ {1,4},
  N ∈ {1,2,4,6,8,12,16,24,32,48,64,96,128,192,256}, 5 reps × 10 s: ≈ 15 N × 12 arm-k-policy combos × 5 × 12 s ≈ 3 h.
- DuckDB / Arrow single-stream anchor (venv has duckdb 1.5.4 + pyarrow 16.1).

---
# In-flight window D (fast-source model) — implemented and validated 2026-09-09

`NES_LAT_D` = buffers in flight per stream (closed loop). D=1 = one buffer at a time (the probes above);
D=64 = the engine's per-source in-flight cap = "an infinitely fast source that keeps the queue full"
(user, 2026-09-08). Latency clock = the instant the buffer became available (= completion of the buffer D
positions earlier), so under D>1 residence = D·N / throughput (Little) for every arm.

**Rig bug found and fixed on the way (rig-only, no engine code):** with D>1 the in-flight set of a stream is NOT a
contiguous window — a buffer's chunks queue behind every task forked meanwhile and a preempted worker holds its
item, so one buffer can lag 50-130 positions behind the newest in flight (seen: dpp D=64 lag 70, gshared D=8
lag 56). The first window implementation reused a data slot's zero-copy TupleBuffer views every R buffers and
re-stamped their sequence number on re-offer; the SequenceShredder reads the sequence number from the raw
buffer's control block (`SequenceShredder.cpp:110`), so a re-stamp under a still-in-flight buffer corrupted its
state → repeat storms (3.4 M repeats), tuples/row 0.9999, stalls, one segfault. Fix: 64 view GENERATIONS per
data slot (control-block reuse distance 4096 buffers) and ALL per-buffer bookkeeping keyed by the virtual slot
b % 4096, plus a reuse-while-busy detector that aborts the run instead of corrupting it, a 3 s stall watchdog
with a state dump, and re-queue-at-tail on a shredder repeat (as the engine does). 18/18 runs clean after the
fix (D ∈ {1, 8, 64} × 4 arms × N ∈ {1, 8} × 3 attempts), D=1 numbers unchanged.

**D=64 smoke (N=1 / N=8, 2 s window, k=4, spin 50):**
| arm | N | GB/s | p50 µs | p99 µs | p999 µs | CPU s/GB |
|---|---:|---:|---:|---:|---:|---:|
| dpp | 1 | 47.3 | 178 | 192 | 213 | 0.49 |
| dpp | 8 | 43.0 | 1559 | 1643 | 1677 | 0.54 |
| gshared 4 | 1 | 37.6 | 223 | 235 | 247 | 0.61 |
| gshared 4 | 8 | 35.1 | 1907 | 1962 | 1990 | 0.65 |
| gprivate 4 | 1 | 6.6 | 1258 | 1377 | 1614 | 0.60 |
| gprivate 4 | 8 | 33.2 | 1352 | **15829** | 22907 | 0.70 |
| chunker 4 | 1 | 16.5 | 466 | 592 | 615 | 0.95 |
| chunker 4 | 8 | 32.7 | 2016 | 4375 | 5050 | 0.73 |

Reads exactly as predicted for the backlog regime: DPP at N=1 spreads the 64 queued buffers over 23 workers
(47 GB/s, 178 µs = 64/360K); the private gang serialises them (6.6 GB/s, 1.26 ms = 64 × 20 µs) — its N=1 latency
win exists only when nothing is waiting; at N=8 its p50 is DPP-like but its p99 is 10× DPP and its throughput
−23%; the chunker's cutter pipelines (16 GB/s at N=1) but at N=8 its p99 is 2.7× DPP.
