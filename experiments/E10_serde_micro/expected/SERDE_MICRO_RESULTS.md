<!-- SPDX-License-Identifier: Apache-2.0 -->
# Serde-overhead micro (#5 PASSTHROUGH) — DONE (2026-08-27)

Isolates the cost of (de)serialization that passthrough serde avoids, as a 2x2 over
input-parse x output-serialize, swept over K float fields. Companion to the ablation
passthrough split (`PASSTHROUGH_ABLATION_SPLIT_RESULTS.md`); memory `hoisting-microbench`.

## The 2x2 (user's design; asymmetry resolved via native output)
Goal: show serde overhead, especially both halves together. "Serialize without deserialize"
is impossible from a CSV field (a native value only comes from a parse) -> the only-ser arm uses
**SystemNative binary input**. And "no text-serialize output" = the sink's **Native format** (no
OUTPUT_FORMAT set -> raw tuple-buffer rows, formatter bypassed; `SinkDescriptor.cpp:73`). So:

| arm | input | output | pays |
| --- | --- | --- | --- |
| no-serde   | SystemNative | Native | neither (raw-row memcpy) |
| only-deser | CSV (eager_parse) | Native | parse |
| only-ser   | SystemNative | JSON | serialize |
| serde      | CSV (eager_parse) | JSON | parse + serialize |
| serde-naive| CSV (eager_parse) | JSONUncompiled + NES_OUTPUT_CODEC=original | parse + STRINGSTREAM serialize |

All `SELECT *`, r3 footing (compiled default-invoke, no fnattr/inline/tcb), InMemory W1, EiselF64 in /
ZMIJF64 out, Monitoring sink. x = K float fields (1..20). y = **rows/s** (input-MB/s is NOT comparable
across CSV vs native encodings; decompose divides by per-arm bytes/row: native=K*8, CSV=size/2M).
Reported throughput is PER-PASS; true = x NES_INMEM_REPEAT(20) (cancels in ratios).

## Why NOT r1 (regime decision)
r1 can't build it (SystemNative is a compiled formatter; no uncompiled native reader) AND would dirty
the deser axis (interpreted scalar index dominates the CSV-vs-native read gap). r3 is cleaner (fast SIMD
index shrinks the format confound) and the STRONGER claim: even a fast compiled engine pays ~2x for serde.

## RESULTS (K=1..20, true rows/s; figures/serde_micro.{png,svg} + serde_micro_decomposition.csv)
Per-field costs DEAD STABLE across all K:
- **parse ~= 13 ns/field** (Eisel float), **serialize ~= 22 ns/field** (ZMIJ) -> **serialize ~1.7x the
  parse; it DOMINATES the serde cost.**
- **serde ~= parse + serialize (slightly SUB-additive: -11% at K=1 -> ~-2% at high K)** -- the two halves
  OVERLAP in the fused pipeline, so doing both costs marginally LESS than the sum of isolated halves (NOT
  super-additive). Same signal in the parse cross-check (Native-out 109 vs JSON-out 95 ns/row: parse is
  cheaper when overlapped with serialize).
- **naive stringstream serializer = ~4.3x the fast ZMIJ serde** (stable across K) -- the prominence line.
- Cross-check (serialize two ways) TIGHT: native-pair 186 vs csv-pair 174 ns/row (~7%).
Sample (Mrows/s): K=1 no-serde 143.8 / deser 48.9 / ser 26.0 / serde 21.6 / naive 4.8;
K=20 27.2 / 3.21 / 2.15 / 1.39 / 0.33.

## Confounds (bounded by cross-checks)
Native arms skip field-indexing that CSV arms pay -> the parse-side gap includes CSV indexing (the ~7-13%
cross-check looseness + part of the low-K sub-additivity). no-serde line has ~10% run-to-run noise (fast
memcpy arm, InMemory throughput jitter) -- cosmetic bumps at K=9/12/15.

## Provenance
pbench run_group `20260827T192919-501b18f2` (300 runs, 0 fail). Smoke `serde_micro_smoke` (K=4, 15 runs).
Binary cmake-build-release @ `f6a7b98343` + uncommitted eager_parse threading (has SystemNative, NATIVE
output, NES_OUTPUT_CODEC, formatOriginalStringstream -- all verified in-binary). Data (8.7GB, 2M rows x
K=1..20 CSV + .nes twin): `testdata/large/serde_micro/` gen `scratchpad/serde_micro/gen_serde_micro.py`
(base) + cut+csv_to_binary. Queries `queries/serde_micro/floatk{1..20}.yaml` + experiments
`serde_micro_{smoke,full}.yaml` (gen `gen_queries_and_exp.py`). Decompose `decompose_serde.py`
(+ `decompose_partial.py` for mid-run). pbench renderer.py gained the `eager_parse` bool rule (both paths).

## GOTCHA for next time
`NES_INMEM_REPEAT=20` x the stringstream naive arm x high K = pathologically slow (K=20 naive ~6-7min/3reps
-> whole run ~50min). Use a LOW per-arm REPEAT for the naive line (it's 40x slower, needs no repeat to
measure). The 4 fast arms finished in ~15min; the naive line was the whole tail.

## INT64 PANEL + two-panel figure (2026-08-28)
User adaptation: instead of a mixed float->int x-axis (which confounds the type change with the cumulative
baseline -- 5->6 behaves unlike 1->2), SPLIT into two single-type panels, each a clean K=1..20 sweep from 1.
Ran the identical 5-arm 2x2 on INT64 (FastINT64 in, `writeIntegralValue`/to_chars out; int64 in [0,1e9)).
`experiments/serde_micro_int_full.yaml`, run_group DONE 2026-08-28 (300 runs 0 fail). **PER-ARM REPEAT fix
for the slow tail: fast arms 20, serde_naive 3** (the 40x-slower stringstream needs no repeat) -> int run
~15min vs float's ~50min. Figure `figures/serde_micro_2panel.{png,svg}` (float | int, SHARED log-y),
script `make_serde_micro_2panel.py` (parses both logs, per-arm REPEAT).
**Findings:** (1) **no-serde IDENTICAL across panels** within noise (float64 & int64 are both 8-byte native
rows -> same raw-row memcpy; K=1 143.8 vs 135.5, K=20 27.2 vs 24.9 Mrows/s) = passthrough is type-INDEPENDENT,
the shared anchor. (2) **int (de)serialize ~1.8x cheaper than float** -- whole int panel shifted up (K=20
serde 1.4 float vs 2.5 int). (3) **shape differs = the type story:** float has a WIDE only-serialize gap
(ZMIJ ~22ns dominates); int COMPRESSES (from_chars ~= to_chars, both cheap) so int's parse/serialize lines
nearly merge. (4) **invariant holds in BOTH panels: serde < the slower half (only-serialize)** regardless of
type. y-axis = shared log (recommended over two independent axes: makes no-serde-identical + int-higher read
directly); linear buries the lower-arm slopes. Int data `testdata/large/serde_micro/intk{1..20}.{csv,nes}`.

## NEXT (per the 3-optimization plan: rope, overload DONE, passthrough DONE)
- rope (CONCAT zero-copy span-rope) is the remaining micro.
- Deferred: the ablation STACKED FIGURE with the naive/lazy segments (PASSTHROUGH_ABLATION_SPLIT_RESULTS).

---

# MIXED-TYPE panels (i2f / f2i) — DONE 2026-09-03

**Design (user's):** make the pipeline TYPE-CONVERTING so each side pays a DIFFERENT type's codec:
`i2f` = int64 CSV/native in -> `TOFLOAT64(c_i)` -> float64 out (cheap parse, expensive float serialize);
`f2i` = float64 in -> `TOINT64(c_i)` -> int64 out (expensive float parse, cheap int serialize). Claim to
show: **the float half ALONE bounds the mixed pipeline** — its cost is paid on one side and sets the floor.

**Engine surface (UNCOMMITTED, branch benchmark-piparse-lazyparse-fast-csv):** NES SQL has NO explicit
field cast (`FLOAT64(x)` = typed literal only; `CastToTypeLogicalFunction` is internal, its reflection
throws). Added two isolated function plugins instead (user's call, no parser change): `ToFloat64` /
`ToInt64` — logical side mirrors the Abs plugin (REAL reflection, so nes-cli->worker gRPC works),
physical side = registrar returning the existing `CastFieldPhysicalFunction` (`VarVal::castToType`, i.e.
static_cast semantics; float->int truncates toward zero). Registry is case-insensitive -> SQL
`TOFLOAT64(c0)`. Files: nes-logical-operators {include,src}/Functions/To{Float64,Int64}LogicalFunction.*,
nes-physical-operators src/Functions/To{Float64,Int64}PhysicalFunction.cpp + 2 CMakeLists add_plugin
lines. Correctness systest: `nes-systests/formatter/MixedCastSmoke.test` (2/2 PASS; also proves integral
doubles serialize BARE, "1000000000" no ".0").

**Setup:** 4 arms (no serde_naive — story told): no_serde native->native, only_deser CSV->native,
only_ser native->JSON, serde CSV->JSON — ALL through the cast Map. Reuses the pure-panel datasets
(intk/floatk); same r3 footing; uniform REPEAT=20. **no_serde = the CAST-COST CONTROL** (native->native
with cast is no longer a raw-row memcpy; its delta vs the pure panel's no_serde prices cast+Map).
480 runs 0 fail, run_group `20260903T105905-615bada9`, experiment `serde_micro_mixed_full.yaml`,
queries `queries/serde_micro/{i2f,f2i}k{1..20}.yaml` (gen: scratchpad/serde_micro/gen_mixed_*.py).

**RESULTS (decompose_mixed.py; tidy CSV figures/serde_micro_mixed_raw.csv; figure serde_micro_4panel.*):**
- **Cast+Map is FREE: 0-2 ns/row** (vs pure no_serde; occasionally negative = noise; ~5 ns at f2i K>=18).
  The control validates the whole comparison — mixed arms are cleanly comparable to pure panels.
- **Per-field costs TRANSFER EXACTLY from the pure panels** (the value-distribution worry was a non-issue):
  i2f parse == pure-int parse (K=10: 65.5 vs 66.3 ns/row), i2f serialize == pure-float serialize (217.5
  vs 220.2 — ZMIJ on integral-valued doubles costs the same as on 6-decimal values, confirming ZMIJ is
  value-independent). f2i parse ~= pure-float parse (+2-3%); f2i int-serialize ~6% cheaper than pure-int
  (<=6-digit ints from truncation vs 9-10-digit — the only visible distribution effect, tiny).
- **THE BOUND CLAIM HOLDS, tightly:** serde_i2f ~= pure-float only_ser across all K (K=1: 26.3 vs 26.0
  Mrows/s; K=20: 1.7 vs 2.1) — the float SERIALIZE side alone ~= the whole mixed pipeline's cost; the
  cheap int parse nearly disappears inside it (sub-additive overlap). serde_f2i < pure-float only_deser
  bound (27.5 vs 48.9 @K=1) — bounded by float parse, but int serialize (~1/2 the float parse cost) is
  still visible on top. Both mixed serde curves land BETWEEN pure-int serde and pure-float serde.
- Figure: `figures/serde_micro_4panel.{png,svg}` (float | int | i2f | f2i, shared log-y; mixed panels
  overlay the pure-float half as a gray dotted reference — in i2f it lies ON the mixed curves).

**Gotcha for reruns:** the binary must contain the plugins (FunctionNotImplemented at submit = stale
binary; NES_BUILD_DIR=cmake-build-release). Smoke experiment `serde_micro_mixed_smoke.yaml` (8 runs).

**NAIVE arms added 2026-09-03** (`serde_micro_mixed_naive.yaml`, 120 runs 0 fail, run_group
`20260903T131049-928bd2c3`, REPEAT=3): in the naive-stringstream regime the OUTPUT type sets the cost
ENTIRELY — i2f naive collapses onto the pure-FLOAT naive curve (5.16 vs 4.81 / 0.68 vs 0.65 / 0.35 vs
0.33 Mrows/s @K=1/10/20) and f2i naive onto the pure-INT naive curve (8.73 vs 8.43 / 1.38 vs 1.29 /
0.72 vs 0.66) — the parse side (even float parse) is invisible under the stringstream writer.
naive/fast-serde: i2f ~5x, f2i ~2.6-3.1x. **Combined tidy CSV of ALL 400 results (4 types x 5 arms x
20 K): `figures/serde_micro_all_raw.csv`** (combine: scratchpad/serde_micro/combine_all_raw.py);
serde_micro_mixed_raw.csv now carries all 5 mixed arms; 4-panel figure regenerated with naive curves.
