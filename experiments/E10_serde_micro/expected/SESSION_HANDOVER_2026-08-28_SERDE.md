<!-- SPDX-License-Identifier: Apache-2.0 -->
# Session handover 2026-08-28 — passthrough serde: ablation split + serde-overhead micro

Two deliverables this session, **both DONE, publishable, persisted**. This is the entry point; the
detail lives in two companion docs. Memory: `ablation-study`, `hoisting-microbench`.

- **(1) Ablation integration** — split the v7 ladder's monolithic "compile" bar into
  **naive-codegen × lazy-passthrough**. Detail: `PASSTHROUGH_ABLATION_SPLIT_RESULTS.md`.
- **(2) Serde-overhead micro** — 2×2 (parse × serialize) swept over K fields, for float64 AND int64.
  Detail: `SERDE_MICRO_RESULTS.md`.

Branch `benchmark-piparse-lazyparse-fast-csv`, binary `cmake-build-release` @ `f6a7b98343` + the
uncommitted `eager_parse` threading (worker+nes-cli mtime 2026-08-26T18:36; verified in-binary:
`eager_parse`/`EAGER_PARSE`, `SystemNative`, `NATIVE` output, `NES_OUTPUT_CODEC`, `formatOriginalStringstream`).
**No engine code changed this session** — every knob used already existed (uncommitted, default-off).

---

## 1. Ablation split (compile bar -> naive × passthrough)

**The move (user's paper vocabulary):** insert a "naive code generation" layer between `vectorized` and
`lazy-compiled`, splitting rung 3 with ONE extra run using `INPUT_FORMATTER.eager_parse=true` (materialise
every leaf incl. VARSIZED -> output re-serialises = eager; default lazy = passthrough). Both arms at default
invoke / no fnattr/inline/tcb (those live in "context"), so it isolates ONLY eager-vs-lazy.

**Methodology — same-session RATIO onto the v7 footing** (machine ran ~2-3% slow vs the v7 table; cancels):
`r3_eager_hist = r3_hist × (r3_eager_today / r3_today)`; naive bar = `r2_hist -> r3_eager_hist`, lazy bar =
`r3_eager_hist -> r3_hist` (= `r3/r3_eager`). r2+r3 re-measured as anchors (retook all 10; both are the
drift-STABLE rungs). ANCHOR PASS: r2 Δ −2.1..+0.8%, r3 Δ −2.3..+3.4%.

**RESULT (on v7 footing):** old compile bar = **compilation 2.37× × passthrough serde 1.77×** (geomean over
the 6 output-bound queries) — passthrough is ~40% (log-share) of what the figure credited to "compilation".
Per-query passthrough×: pure projections biggest (qroute 2.38 / qproject-float 2.32 / q0-SELECT* varsized
2.10) > computed-output (q1 1.34 / q22 1.40 / q10 1.39) > filters (qex 1.09 / q14 1.08 / q2og **0.89 INVERTED**
— eager HOISTS the 5-OR parse, recovered by fnattr in context; q2mod 1.84 = filter w/ wide output).

**Artifacts:** experiments `ablation_passthrough_{gate,full}_bidstr.yaml` (+ `r3_eager` rung folded into
`ablation_suite_json_inmem_seq_bidstr.yaml`); CSV `figures/passthrough_split_bidstr.csv`; decompose
`piparse-bench/scratchpad/passthrough_split/decompose_passthrough.py`. run_group `20260827T154329-5792e024`
(90 runs 0 fail). ⚠️ `RawValueParser.hpp:51` comment "VARSIZED stays lazy" is STALE — .cpp materialises
varsized under eager (proven by q0's 2.1×).

---

## 2. Serde-overhead micro (2×2, float64 + int64)

**Design (user's, asymmetry resolved):** input{CSV parse, SystemNative no-parse} × output{Native raw-rows,
JSON serialize}. "Serialize without deserialize" is impossible from a CSV field (native value only comes
from a parse) -> only-ser MUST use SystemNative binary input. "No text-serialize output" = the sink's
**Native format** (no `OUTPUT_FORMAT` -> raw tuple rows, formatter bypassed, `SinkDescriptor.cpp:73`).

| arm | input | output | pays |
| --- | --- | --- | --- |
| no-serde   | SystemNative | Native | neither (raw-row memcpy) |
| only-deser | CSV (eager)  | Native | parse |
| only-ser   | SystemNative | JSON | serialize |
| serde      | CSV (eager)  | JSON | parse + serialize |
| serde-naive| CSV (eager)  | JSONUncompiled + NES_OUTPUT_CODEC=original | parse + STRINGSTREAM serialize |

All `SELECT *`, r3 footing (compiled default-invoke, no fnattr/inline/tcb), InMemory W1, Monitoring sink.
Codecs: float EiselF64/ZMIJF64, int FastINT64/writeIntegralValue(to_chars). x = K fields (1..20). y =
**rows/s** (input-MB/s is NOT comparable across CSV vs native; decompose divides by per-arm bytes/row:
native=K*8, CSV=size/2M). Reported throughput is PER-PASS; true = ×`NES_INMEM_REPEAT`.

**Why r3 not r1:** r1 can't build it (SystemNative is compiled; no uncompiled native reader) and would dirty
the deser axis (interpreted scalar index dominates the CSV-vs-native read gap). r3 is cleaner + the stronger
claim (even a fast compiled engine pays ~2× for serde).

**RESULTS (dead-stable per-field across all K):**
- parse ~= **13 ns/field** (Eisel float), serialize ~= **22 ns/field** (ZMIJ) -> serialize ~1.7× the parse,
  DOMINATES the float serde cost.
- **serde ~= parse + serialize (slightly SUB-additive: −11%@K1 -> ~−2% high K)** — halves OVERLAP in the
  fused pipeline (NOT super-additive). Same signal in the parse cross-check (109 vs 95 ns/row).
- **naive stringstream = ~4.3× the fast ZMIJ serde** — the prominence line.
- Serialize cross-check tight (native-pair 186 vs csv-pair 174 ns/row, ~7%).

**INT64 panel + two-panel figure:** user split the type story into two single-type panels (float | int,
shared log-y) rather than a mixed float->int x-axis (which confounds the type change with the cumulative
baseline). Findings: **no-serde IDENTICAL across panels** (float64 & int64 are both 8-byte native rows ->
same memcpy = passthrough is type-INDEPENDENT, the shared anchor); **int (de)serialize ~1.8× cheaper than
float** (whole int panel shifted up); **float has a WIDE only-serialize gap (ZMIJ) that COMPRESSES for int**
(from_chars ~= to_chars); **serde < the slower half (only-serialize) in BOTH panels** (the invariant, holds
universally). y = shared log recommended (linear buries the lower-arm slopes; makes no-serde-identical +
int-higher read directly).

**Figures** (`figures/`): `serde_micro.{png,svg}` (float log-y), `serde_micro_linear.{png,svg}` (float,
equi-distant linear gridlines — shows the true magnitude of the passthrough lead), `serde_micro_2panel.{png,svg}`
(float | int, shared log-y). Raw data: `serde_micro_2panel_raw.csv` (200 rows tidy: type,K,arm,mbps,bytes/row,
repeat,mrows_s_true) + `serde_micro_decomposition.csv` (float, per-K parse/serialize/additivity/cross-checks).

**Provenance:** float run_group `20260827T192919-501b18f2` (300 runs 0 fail, REPEAT=20 uniform); int
`serde_micro_int_full` DONE 2026-08-28 (300 runs 0 fail). Smoke `serde_micro_smoke` (K=4). Experiments
`serde_micro_{smoke,full,int_full}.yaml`; queries `queries/serde_micro/{float,int}k{1..20}.yaml`. Scripts
in `piparse-bench/scratchpad/serde_micro/`: `gen_serde_micro{,_int}.py` (data), `gen_{queries_and_exp,
int_queries_and_exp}.py`, `decompose_serde.py` (+`decompose_partial.py` mid-run), `emit_2panel_csv.py`,
figure scripts in `figures/make_serde_micro{,_linear,_2panel}.py`. Full run logs kept there too.

**⚠️ GOTCHA (cost the float run ~50 min):** `NES_INMEM_REPEAT=20` × the stringstream naive arm × high K is
pathologically slow (K=20 naive ~6-7 min/3reps). FIX applied on the int run: **PER-ARM REPEAT** — fast arms
20, `serde_naive` 3 (via its worker_env override; the 40×-slower arm needs no repeat to measure). Int run
~15 min. The decompose/plot scripts apply REPEAT per arm.

---

## Reusable rig (to extend, e.g. a string/varsized panel)
1. Data: `gen_serde_micro*.py base` writes an N×20 base CSV; `cut -d, -f1-K` slices; `csv_to_binary.py
   <csv> <nes> --schema "<type>,..."` makes the .nes twin (SystemNative needs a dummy `string_length`).
2. Queries: `gen_*_queries_and_exp.py` emits `<pre>k{1..20}.yaml` (K-col schema, csv+native data) + the
   experiment (5 arms; `data_size` native/csv per arm; per-arm REPEAT).
3. pbench: `eager_parse` bool rule already added to `renderer.py` (both worker-cli + systest paths).
4. Run: `PBENCH_KEEP_LOGS=1 uv run python bench.py run experiments/<exp>.yaml --build-dir <release>
   --worker-port 9099` (pkill -x main pre-flight; NEVER pkill -f).
5. Decompose/plot: parse summary lines (or per-run lines mid-run), rows/s = mbps×1e6/bytes_per_row×REPEAT.

## State
git clean (all artifacts are in piparse-bench scratchpad / Notes, not the NES tree). serde_micro data =
17 GB in `testdata/large/serde_micro/` (40 datasets, re-derivable from the two base CSVs — drop per-K CSVs
to reclaim). NES tree: the pre-existing uncommitted micro knobs remain (default-off), unchanged this session.
