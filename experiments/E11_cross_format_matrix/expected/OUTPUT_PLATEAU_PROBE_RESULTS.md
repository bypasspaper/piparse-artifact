# Output-serialization plateau probe — RESULTS (2026-08-06c)

Follow-up to MATRIX_RESULTS_2026-08-05.md v2. The user challenged the memory-wall reading of
the Par column: "csv->json's baseline is LOWER than csv->csv's, so the ceiling should be
FARTHER away — why is its Par still lower (12.2 vs 15.8)?" The challenge was correct. This
session located the real limiter for fat-output cells and verified it at the
microarchitecture level.

## 1. What the matrix data already showed (re-analysis, no new runs)

Per-query decomposition of the v2 cells (matrix_rpar_fixed_480 + matrix_runs_all1440):

- Filter-class queries (q2mod/q2og/qex): csv->json == csv->csv BYTE-IDENTICALLY
  (65.1 vs 65.3 GB/s wire; Par 17.0 vs 17.1). The wire wall is real there — and irrelevant
  to the Par gap.
- The whole csv-row Par deficit lives in fat-output queries. q0: csv->csv Par 16.1
  (589 Mrows/s, 67.6 GB/s in + 67.6 out = 135 GB/s wire) vs csv->json Par 7.1
  (143 Mrows/s, 16.4 in + 25.5 out = 42 GB/s wire). So (a) the "65-68 GB/s wall" is NOT a
  total-traffic ceiling (csv->csv q0 does 2x it), and (b) csv->json q0 is nowhere near any
  wire wall yet stuck.
- q0 r_par row rates across ALL 16 cells cluster by OUTPUT PATH: coalesced csv->csv 589;
  field-wise ->csv from non-csv inputs 183-185; ->xml 132-163; ->hl7 131-154; ->json
  122-143. Every field-wise serializer plateaus at ~21-30 GB/s of OUTPUT bytes
  (~120-185 Mrows/s) regardless of input format; only the lazy-input x csv-output coalesced
  raw-forward path escapes.

Ratio logic resolved: the baseline difference is only 1.8x (W1 r_comp 36.5 vs 20.2 Mrows/s
— fair-codec JSON glue is cheap single-threaded), but the BINDING CEILING differs 4.1x.
Ceiling/baseline: csv->csv 589/36.5 = 16.1; csv->json 143/20.2 = 7.1. The ceiling isn't
farther away — it's a different, much closer one.

## 2. W-sweep (wsweep_output_plateau.yaml, 32/32, healthy config, InMemory x20)

Reported MB/s (true = x20), q0, 2-rep medians:

| W | csv->csv | scale | csv->json | scale |
| --- | --- | --- | --- | --- |
| 1  | 263.8 | 1.00 | 130.9 | 1.00 |
| 2  | 475.8 | 1.80 | 240.2 | 1.83 |
| 4  | 897.4 | 3.40 | 429.7 | 3.28 |
| 8  | 1693.4 | 6.42 | 692.8 | 5.29 |
| 12 | 2358.8 | 8.94 | 792.0 | 6.05 |
| 16 | 2905.0 | 11.01 | 811.0 | 6.20 |
| 20 | 3244.9 | 12.30 | 830.5 | 6.34 |
| 23 | 3404.1 | 12.90 | 829.3 | 6.34 |

csv->json is DEAD FLAT from W12 (W20->W23 = -0.1%); csv->csv still climbing at W23. Flat
plateau (not peak-then-decline) = saturated shared resource or serial stage — the profile
distinguishes below. W23 values cross-validate the matrix (829.3 vs 822; 3404 vs 3376).

## 3. Profiling at the plateau (prof_output_plateau_*.yaml, perf attach per nes-profile)

All at q0, healthy r_par config, InMemory REPEAT window, 8-12 s captures:

| metric | csv->csv W23 | csv->json W23 | csv->json W4 |
| --- | --- | --- | --- |
| true rows/s | 592 M | 144 M | 74.7 M |
| worker duty (/proc utime) | 99% x23 | 99% x23 | busy |
| IPC | 1.81-1.82 | 0.78-0.81 | 2.07 |
| instructions/row | 296 | 552-561 | 604 |
| store_queue_rsrc_stall /cycle | 0.062 | 0.285 | 0.048 |
| load_queue_rsrc_stall /cycle | 0.0006 | 0.0007 | 0.0003 |
| ls_any_fills mem_io (L1<-DRAM direct) | ~30.6 GB/s | ~31.3 GB/s (217 B/row) | 3.8 GB/s (51 B/row) |

Eliminated by measurement:
- Serial stage / Amdahl: all 23 workers at 99% duty, no hot single thread (source 82%).
- Lock contention: native_queued_spin_lock_slowpath 0.03%, TurnSequencer 0.01%, futex ~0.
- Work amplification/spinning: insn/row CONSTANT across W (604 -> 561).
- Wire bandwidth: 42 GB/s total vs csv->csv's demonstrated 136 GB/s on the same fabric.

Confirmed mechanism: **store-queue-full dispatch stalls**. W4->W23 the stall rate rises
5.8x (0.048 -> 0.285/cycle) while IPC falls 2.6x (2.07 -> 0.78); the csv->csv control at
the SAME W23 shows 4.5x fewer store stalls at 4.1x the row rate and 2x the wire bytes.
Load-queue stalls are negligible everywhere — it is the WRITE side.

Reading: the field-wise serializer emits many small (8-30 B) stores into cold,
pool-recycled output-buffer lines (2 GB pool cycling ~80 ms — never cache-resident). Every
output line requires an RFO read from DRAM before the store can complete. At 23 concurrent
writers the loaded DRAM latency exceeds what the ~48-64-entry store queue can hide; stores
back up, dispatch stalls, per-worker productivity collapses 3.7x (22.9 -> 6.3 Mrows/s)
with workers still 99% "busy". The 4x per-row growth of direct-from-DRAM L1 fills
(51 -> 217 B/row) is the same story on the fill side: L2-prefetch/L3 staging stops
covering the pattern at high concurrency. The coalesced csv->csv path is immune because
ERMS rep-movsb bulk copies write full lines with few instructions (296/row incl. input
indexing) and take the no-RFO fast-string path.

Plateau shape follows: aggregate outstanding-miss concurrency (MSHRs x cores vs loaded
latency) saturates around W8-12; additional workers add stall time, not drain rate.

## 4. What this changes in the matrix story

- Law v2 #2's "residual Par structure is real cost" is wrong as stated: cost present in
  both rungs cancels in a ratio. What doesn't cancel is a NUMERATOR CEILING. Two ceilings
  exist: the ~65-68 GB/s READ-wire wall (filter-class, all cells) and the field-wise
  serialization store-stall ceiling (~21-30 GB/s output bytes, all fat-output cells except
  coalesced csv->csv).
- The dagger rule (>=85% of the read wall) under-daggers the ->json/->hl7/->xml columns:
  their fat-output queries are just as ceiling-clipped, by the serialization plateau.
- "csv-in Par lowest = clipped numerator / fastest denominator" survives for FILTER
  queries only; the fat-output share of the deficit is the store-stall ceiling.
- The fixprobe label "passthrough genuinely CPU-bound" is refined: it is
  memory-LATENCY-bound in the store path, masquerading as CPU-bound (99% duty, low IPC).
- It is still a "memory system" limit — but latency-under-concurrency on the WRITE side,
  not wire bandwidth. Paper phrasing should say "serialization store-stall ceiling", not
  "memory bandwidth wall", for the fat-output cells.

## 5. Engine levers this implies (unexplored, sized by the gap)

Gap to close: field-wise output at 21-30 GB/s vs coalesced at 68 GB/s on identical
hardware. Candidates: (a) non-temporal/streaming stores in the serializers (skip RFO
entirely); (b) serialize into a small L1-resident staging block, then ERMS-bulk-copy to
the output buffer (turns scattered stores into full-line copies); (c) LIFO/warm output
buffer recycling so lines are cache-resident when written (pool policy, cheapest to try);
(d) fewer, wider stores (glue+value coalescing in the JIT emitter). Any of these could
plausibly move every fat-output cell's Par by 2x+; none affect the filter-class wall.

## Artifacts

- Sweep + prof yamls: piparse-bench/experiments/{wsweep_output_plateau,
  prof_output_plateau_csvjson,prof_output_plateau_csvjson_w4,prof_output_plateau_csvcsv}.yaml
  (results embedded in descriptions; prof runs are scaffolds, one csvjson W23 rerun was
  killed post-capture and is marked failed in the store — expected).
- perf record data: scratchpad prof_csvjson/perf_csvjson_q0_w23.data (session-temporary).
- Sweep rows in the piparse duckdb under experiment=wsweep_output_plateau.
- Companion: MATRIX_RESULTS_2026-08-05.md (v2 tables), SESSION_HANDOVER_2026-08-04b.md.
