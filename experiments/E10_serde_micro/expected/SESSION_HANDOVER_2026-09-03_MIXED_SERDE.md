<!-- SPDX-License-Identifier: Apache-2.0 -->
# Session handover 2026-09-03 — mixed-type serde micro (i2f / f2i)

**DONE, publishable, persisted.** Extends the 2026-08-28 serde micro (float | int panels) with two
TYPE-CONVERTING panels so each pipeline side pays a different type's codec. Detail lives in
`SERDE_MICRO_RESULTS.md` § "MIXED-TYPE panels"; memory `serde-micro-mixed`.

## What was measured
- **i2f**: int64 CSV/native in → `TOFLOAT64(c_i)` → float64 out. **f2i**: float64 in → `TOINT64(c_i)`
  → int64 out. 5 arms × K=1..20 × 3 reps, r3 footing, InMemory W1, reuses the pure-panel datasets.
- Runs: `serde_micro_mixed_full` 480/480 (run_group `20260903T105905-615bada9`, REPEAT=20) +
  `serde_micro_mixed_naive` 120/120 (`20260903T131049-928bd2c3`, REPEAT=3). 0 failures.

## Headline results
1. **The float half alone bounds the mixed pipeline**: serde_i2f ≈ pure-float only-serialize at every K
   (26.3 vs 26.0 Mrows/s @K=1); serde_f2i < pure-float only-deserialize bound, int-serialize still visible.
2. **Cast+Map is free** (0–2 ns/row vs pure no_serde) — the no_serde-with-cast control arm validates
   cross-panel comparability.
3. **Codec ns/field transfer exactly** across panels (ZMIJ value-independent; only effect: f2i int
   serialize ~6% cheaper from shorter digits).
4. **Naive regime: output type sets the cost entirely** — i2f naive == pure-float naive, f2i naive ==
   pure-int naive; parse side invisible under the stringstream writer.

## Engine state — ⚠️ UNCOMMITTED plugins on `benchmark-piparse-lazyparse-fast-csv`
NES SQL has no explicit field cast (`FLOAT64(x)` = typed literal only; internal `CastToType` can't
reflect). Added two isolated function plugins (user chose plugins over a parser patch):
- `nes-logical-operators/{include,src}/Functions/To{Float64,Int64}LogicalFunction.{hpp,cpp}` — mirror
  Abs, REAL reflection (needed for nes-cli→worker gRPC).
- `nes-physical-operators/src/Functions/To{Float64,Int64}PhysicalFunction.cpp` — registrar-only,
  returns the existing `CastFieldPhysicalFunction` (VarVal::castToType; float→int truncates to zero).
- 2 CMakeLists `add_plugin` lines. Registry is case-insensitive → SQL `TOFLOAT64(c0)`.
- Correctness systest: `nes-systests/formatter/MixedCastSmoke.test` (2/2 PASS; integral doubles
  serialize BARE — "1000000000", no ".0").
**OPEN: commit these** (isolated, default-inert) if the mixed panels go into the paper.

## Artifacts
- Figure `figures/serde_micro_4panel.{png,svg}` (+ `make_serde_micro_4panel.py`): float | int | i2f |
  f2i, shared log-y, 5 arms everywhere; mixed panels overlay the pure-float half as gray dotted bound.
- **`figures/serde_micro_all_raw.csv` = ALL 400 medians** (4 types × 5 arms × 20 K; mrows_s_true is
  REPEAT- and bytes/row-corrected). Also `serde_micro_mixed_raw.csv` (mixed only, 200 rows).
- piparse-bench: experiments `serde_micro_mixed_{full,naive,smoke}.yaml`; queries
  `queries/serde_micro/{i2f,f2i}k{1..20}.yaml`; scripts in `scratchpad/serde_micro/`:
  `gen_mixed_queries_and_exp.py`, `gen_mixed_naive_exp.py`, `decompose_mixed.py` (per-K ns/row
  decomposition + pure-panel cross-refs), `combine_all_raw.py` (rebuilds the 400-row CSV from logs).

## Gotchas (cost nothing this session, will cost a rerun)
- Binary MUST contain the plugins — `FunctionNotImplemented` at submit = stale binary. Always
  `NES_BUILD_DIR=cmake-build-release` (in-docker.sh defaults to cmake-build-debug).
- Naive arm needs per-arm `NES_INMEM_REPEAT=3` (uniform 20 → ~50 min stringstream tail).
- Run recipe unchanged: `pbench run --detach --worker-port 9099`, `pkill -x main` preflight
  (NEVER `pkill -f`), watch `results/logs/pbench_run_*.log` for `Done:`.
