<!-- SPDX-License-Identifier: Apache-2.0 -->
# Lazy-overload A/B on the optimised NES arm, per-query tiers, both boxes — DONE 2026-10-05

## Why
Audit 2026-10-05 (memory `overload-gap-audit`): the pbench `overload: true` knob (→ `INPUT_FORMATTER.LAZY_INT/UINT/
FLOAT_OVERLOADS`, engine default **false**) was never set in any per-query tier or scaling ladder on either box; it was ON
only in the Sept Fig1/Fig2 teaser runs and the ablation's r6b rung. So the paper's "fully optimised" per-query numbers
ran without overloading while Fig1 v2 ran Q2 with it. User decision: retake as a same-session ctrl-vs-ovl A/B, Pi first,
then Threadripper. Predicate audit of the 13 queries: overload can only touch q2_og (5× INT32 ==), q_ex (2× INT32 == on
the rows surviving the always-overloaded VARSIZED channel filter; its `price <` is a float ordering compare = never
overloaded) and cm_q2 (INT16 == 3). q14 (computed float range) and q2_mod (modulo) need the parsed value; q_route / ysb
compare VARSIZED (always overloaded); the rest have no constant predicate.

## Pi — `pi_stateless_tier_ovl` (140) + `pi_stateful_tier_ovl` (42), Pi clock 2026-09-29 07:00→07:45, 0 failed, 0x0, performance
Series `ctrl` (verbatim `pi_stateless_tier` / `pi_stateful_tier`: W3+io1, MmapFile, SIMDCSV, fast parsers, JSON out,
repeat 8) vs `ovl` (+ `overload: true` in a series override). 7 reps, medians:

| query | ctrl MB/s | ovl MB/s | ovl/ctrl |
| --- | --- | --- | --- |
| q0 | 1295.6 | 1297.4 | 1.00 |
| q1 | 1637.9 | 1632.1 | 1.00 |
| q10 | 1370.4 | 1370.1 | 1.00 |
| q14 | 2418.1 | 2402.2 | 0.99 |
| q22 | 1410.9 | 1366.1 | 0.97 |
| q2_mod | 4688.2 | 4697.1 | 1.00 |
| **q2_og** | 3725.5 | 3679.3 | **0.99** |
| **q_ex** | 5132.5 | 3857.5 | **0.75** |
| q_project | 3908.0 | 3906.6 | 1.00 |
| q_route | 3232.7 | 3215.6 | 0.99 |
| cm_q2 | 353.8 | 351.0 | 0.99 |
| q8_join | 79.3 | 79.9 | 1.01 |
| ysb_1k_varsized | 4645.4 | 4691.1 | 1.01 (p99 11.9 → 4.4 ms) |

**The Pi worker binary predates the overload fix.** `cmake-build-release-piparse/nes-single-node-worker` was last
linked 2026-08-23 16:32 (`~/powertest/build_asyncmmap.log`, "[47/47] Linking"). The word-compare fast path for
lazy-overload equality (`f6a7b98343`, committed 2026-08-30 on the TR) reached the Pi's source tree on 2026-08-26
(file mtime), objects were recompiled 2026-09-03 / 09-17 for the latency rig, but the worker was never relinked:
371 objects are newer than the binary and its symbol table has neither `wordEqual` nor `SourceEmitBatch`
(the Aug-30 query-engine perf commits `dbfd09ff2c`, `98ab8e3cb3`, `b5d757c9f6`). ⇒ the Pi runs the PRE-fix overload:
digit-count reject, else an opaque `memcmp` call that LLVM cannot fold. q2_og's 4-digit constants mostly reject by
length and gain nothing over one GVN-deduplicated parse; q_ex's 6-digit constants match the column's digit count, so
every surviving row pays two opaque calls instead of one parse → −25 %. (Same regime the hoisting notes describe:
"the ablation's 1.93× was a length-reject, not a byte compare".)

## Threadripper — `nes_simd_overload_stateless` (200) + `nes_simd_overload_stateful` (60), 2026-10-05 11:46→12:09, 0 failed
Binary `cmake-build-release` of 2026-09-03 10:50 at HEAD `b5d757c9f6` (HAS the fix). Series `NES-SIMD` (verbatim the
5-arm NES-SIMD arm: W23+io1, MmapFile, SIMDCSV, fast parsers, JSON out, repeat 8 stateless / 1 stateful, fnattr,
inline+tcb default-on, pin/ccx off) vs `NES-SIMD-ovl` (+ `overload: true`). 10 reps, medians; last two columns = the
paper's Aug-14 5-arm (binary `66ab110f30`) SIMD and Native Mrows/s for drift:

| query | ctrl MB/s | ovl MB/s | ovl/ctrl | ctrl Mrows/s | ovl Mrows/s | Aug-14 SIMD | Aug-14 Native | ctrl/Aug-14 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| q0 | 16041 | 16071 | 1.00 | 139.7 | 139.9 | 141.3 | 141.1 | 0.99 |
| q1 | 26713 | 26844 | 1.00 | 232.6 | 233.7 | 233.1 | 209.7 | 1.00 |
| q10 | 23217 | 23182 | 1.00 | 202.1 | 201.8 | 201.2 | 180.4 | 1.00 |
| q14 | 43301 | 42683 | 0.99 | 377.0 | 371.6 | 367.8 | 508.6 | 1.03 |
| q22 | 26170 | 26227 | 1.00 | 227.8 | 228.3 | 228.0 | 194.3 | 1.00 |
| q2_mod | 63961 | 63892 | 1.00 | 556.8 | 556.2 | 497.6 | 515.9 | 1.12 |
| **q2_og** | 59531 | **70150** | **1.18** | 518.3 | **610.7** | 498.8 | 515.0 | 1.04 |
| q_ex | 68011 | 69565 | 1.02 | 592.1 | 605.6 | 495.6 | 522.4 | 1.19 |
| q_project | 52711 | 52173 | 0.99 | 458.9 | 454.2 | 446.8 | 385.5 | 1.03 |
| q_route | 42775 | 42674 | 1.00 | 372.4 | 371.5 | 370.1 | 468.9 | 1.01 |
| cm_q2 | 727 | 722 | 0.99 | 8.9 | 8.8 | 8.63 | 9.02 | 1.03 |
| q8_join | 339 | 336 | 0.99 | 3.4 | 3.3 | 4.49 | 3.97 | **0.75** |
| ysb_1k_varsized | 51093 | 51222 | 1.00 | 275.2 | 275.9 | 269.0 | 284.5 | 1.02 |

**Findings.**
1. **Overloading moves exactly one query on the TR: q2_og +18 % (518 → 611 Mrows/s, p99 0.24 → 0.17 ms)** — and it
   lands ABOVE the Aug-14 native arm (515), so the earlier "q2_og is at the native ceiling, overload invisible at W23"
   was wrong: the ceiling was the Aug-14 binary's. q_ex +2 % (the int compares only run on the ~rows surviving the
   channel filter). Everything else 0.99–1.00, cm_q2 included.
2. **Binary drift since the paper's Aug-14 TR table:** the Sep-3 engine is +12 % on q2_mod and +19 % on q_ex (the Aug-30
   task-machinery / batched-admission commits help the selective, small-output filters), +3–4 % on q14/q2_og/q_project,
   flat on the output-bound queries — and **−25 % on q8_join** (the known open regression noted 2026-09-02:
   "ALL COMPILED ARMS −20–26 % on q8"). The Native arm was NOT re-run today, so "ceiling" statements need a same-binary
   native rerun.
3. Pi: no verdict on overload possible until the Pi worker is relinked from the TR's source state (the aarch64
   `spinPause` fix is already in the Pi tree). With the fix, expect q2_og to gain on the Pi (it is 2.8× below native
   there, not memory-bound) and the q_ex penalty to disappear.

## Decisions for the paper (user)
- Per-query optimised column: use overload ON (matches Fig1 v2) and say so, or keep OFF and say so. On the TR only q2_og
  changes (+18 %). Either way the Aug-14 TR table is 4–19 % stale on the filters and 25 % optimistic on q8_join vs the
  current engine → if re-taking, re-take ALL NES arms (native, SIMD, naive) on ONE binary; Flink/Spark are unaffected.
- Pi: relink the worker from the TR source state (≈1–2 h in the dev image), then re-run the bypass tiers (≈45 min
  with ctrl+ovl) and, for consistency, the bypass ladder (≈2 h) and the native tiers. The naive W1/W3 pair stays valid
  as an internally consistent pair on the Aug-23 binary.

## Files (this directory)
`tr_simd_overload_ab.csv` (260 raw rows), `tr_ctrl_vs_ovl_vs_aug14.csv` (the TR table incl. Aug-14 columns),
`pi_tier_overload_ab.csv` (182 raw rows), `nes_simd_overload_{stateless,stateful}.yaml`, `pi_{stateless,stateful}_tier_ovl.yaml`,
`run_tr_ovl.sh`, `tr_ovl_{run,continuity}.log`, `tier_ovl_{run,continuity}.log`. DB rows: TR `nes_simd_overload_*`
(series NES-SIMD / NES-SIMD-ovl), Pi `pi_*_tier_ovl` (series ctrl / ovl).
