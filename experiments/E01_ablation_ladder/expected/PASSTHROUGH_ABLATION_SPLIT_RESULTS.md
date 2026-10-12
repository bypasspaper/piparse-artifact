<!-- SPDX-License-Identifier: Apache-2.0 -->
# Passthrough-serde ablation split — DONE (2026-08-27)

Splits the v7 ladder's monolithic **compile** bar into **naive (compilation)** × **lazy (passthrough
serde)**, on the frozen PAPER footing (bidstr_3GB, 10 stateless queries, InMemory W1, csv→JSON).
Companion to `ABLATION_LADDER_V7_HANDOVER.md`; memory `ablation-study` / `hoisting-microbench`.

## The design (user's framing)
Paper ablation layers: `vectorized · lazy-compiled · context · parallel`. IPS central figure code-gen
phases: `naive codegen · lazy-value opts · context enrichment · compiler opts` (compiler opts = a given,
not a layer). **Insert "naive code generation" between vectorized and lazy-compiled**, splitting the
current compile bar at rung 3. fnattr+inlining live in **context** (above), so BOTH split arms run at
default invoke / no fnattr / no inline / no tcb — isolating ONLY the eager-vs-lazy flag with
copy-efficiency (opaque, non-inlined) held constant in both.

- **naive** = r3 + `INPUT_FORMATTER.eager_parse=true` → materialise every leaf (numeric AND varsized) at
  scan → output re-serialises = "naive code generation".
- **lazy** = r3 as-is (default, lazy passthrough). Split: `naive = r2→r3_eager`, `lazy = r3_eager→r3`.

## The knob (already in the engine, uncommitted, default-off)
`INPUT_FORMATTER.eager_parse` (InputFormatterDescriptor). Materialises fixed-size AND varsized leaves via
`parseValue()` in `RawValueParser::parseRawValueIntoRecord` (writeFieldValue lambda). Output then sees
non-lazy values: numeric → parse+`formatAndWriteVal`; VARSIZED → `writeJsonStringValue` (escape-scan
reserialize), NOT the verbatim passthrough. `DISABLE_PASSTHROUGH` (OutputFormatterDescriptor) is the
NARROWER numeric-output-only sibling (keeps input lazy) — NOT used here (would leave varsized forwarding).
⚠️ `RawValueParser.hpp:51` comment ("VARSIZED stays lazy") is STALE/WRONG — the .cpp materialises varsized
under eager (proven: q0 SELECT* eager is 2.1× slower, impossible if varsized still forwarded).

pbench wiring: `renderer.py` — added explicit `eager_parse` bool rule to BOTH `render_worker_cli`
(parser_config bool) and `_render_source_set_clause` (SET TRUE/FALSE) + added to `_handled_input_keys`
(else the generic pass-through str()'s it to "True"). Experiments:
`experiments/ablation_passthrough_{gate,full}_bidstr.yaml`; r3_eager rung folded into
`ablation_suite_json_inmem_seq_bidstr.yaml`.

## Methodology — the RATIO (offset cancel)
Machine ran ~2-3% slower than when v7 was measured. So integrate onto the PUBLISHED footing via the
same-session ratio (NOT the raw absolute r3_eager):
```
ratio         = r3_eager_today / r3_today      # both same session → offset cancels
r3_eager_hist = r3_hist × ratio
naive bar     = r2_hist → r3_eager_hist        # pure compilation, eager serde
lazy  bar     = r3_eager_hist → r3_hist  == r3/r3_eager   # passthrough serde
```
r3 retaken (ratio denominator + anchor); r2 retaken (cross-query anchor only, NOT a figure input — naive
floor uses historical r2). ANCHOR PASS: r2 Δ −2.1..+0.8%, r3 Δ −2.3..+3.4% across all 10 → no pathological
drift, r3_eager on v7 footing.

## RESULTS (on v7 footing) — `scratchpad/passthrough_decomposition.txt`
| query | naive(compile)× | **passthrough×** | class |
| --- | --: | --: | --- |
| qroute   | 2.53 | **2.38** | pure projection |
| qproject | 2.41 | **2.32** | pure projection (float, ZMIJ) |
| q0       | 2.01 | **2.10** | SELECT* (varsized+num) |
| q2mod    | 2.93 | **1.84** | filter, WIDE output |
| q22      | 1.98 | **1.40** | CONCAT (computed+pass) |
| q10      | 2.02 | **1.39** | CASTFROMUNIXTS (computed) |
| q1       | 1.91 | **1.34** | price×0.908 (computed) |
| qex      | 2.76 | **1.09** | filter + CONCAT (small out) |
| q14      | 2.56 | **1.08** | float range filter (small out) |
| q2og     | 2.92 | **0.89** | 5-way OR filter — INVERTED |

**Geomeans:** naive/compilation **2.37×**; passthrough **1.77×** (6 output-bound) / **1.18×** (filter bucket).

## Findings
- **The old compile bar = compilation × passthrough serde.** On pure projections ~2.4× × ~2.3×;
  passthrough serde is ~40% (log-share) of what the figure currently credits to "compilation" alone.
- **Win scales with raw-forwardable OUTPUT fraction:** pure projections 2.1–2.4× (incl. varsized q0, float
  qproject) > computed-output q1/q22/q10 ~1.4× (computed col can't forward) > small-output filters
  q14/qex ~1.1× ≥ q2og 0.89×.
- **q2og INVERTS (0.89×, eager FASTER):** on a filter, eager also HOISTS the parse — auctionId materialised
  once vs lazy re-parsing it 5× across the OR-chain at pre-fnattr r3 (no GVN dedup). So the "lazy" bar on
  filters measures HOISTING not passthrough; fnattr in "context" recovers it (v7 q2og r4/r3 = 1.65×). This
  is the "lazy-value opts lumped" bar the user accepted; the MICRO isolates pure output passthrough.
- q2mod (1.84×) = a filter can still win big when its OUTPUT is wide (passthrough on the projected cols).

## Provenance
pbench run_group `20260827T154329-5792e024` (full, 90 runs 0 fail), gate `ablation_passthrough_gate_bidstr`
(27 runs). Binary cmake-build-release @ `f6a7b98343` + uncommitted EAGER threading (worker+nes-cli
2026-08-26T18:36). Logs: `scratchpad/passthrough_full_run.log`. Decompose:
`scratchpad/decompose_passthrough.py` (parses log summary, applies ratio; v7 MB/s from
`figures/ablation_ladder_v7_bidstr.csv`).

## NEXT
1. Produce the stacked figure: insert naive/lazy segments into the v7 ladder plot (use r3_eager_hist).
2. **The MICRO** (isolated passthrough) — user's 2nd task: standalone one-knob A/B, type × K sweep
   (int/float/varsized × #fields) on real bid data, `eager_parse` (or `disable_passthrough` for the
   output-only half), no filter / 100% output. Shows the mechanism + scaling law the ablation can't.
