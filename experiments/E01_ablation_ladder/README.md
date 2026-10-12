# E01 — Ablation ladder r1 … r7 with the compile-rung split (the per-lever figure)

**Claim in the paper.** Ten levers, applied cumulatively on one CSV→JSON pipeline over the 10 frozen paper queries,
multiply throughput 48–89× (geomean 68×). Per-lever geomeans over the 10 queries: SIMD index 1.08×, **compilation with
identical work 1.88×**, **lazy value code generation 1.50×**, **raw passthrough 1.26×** (these three are the old 3.56×
"compile bar", exact per query by construction), fnattr/GVN parse dedup 1.12×, general inlining 1.18×, output fast path
1.25×, lazy overloads 1.08×, parallelisation to 23 workers 9.73×.

**Machine.** Threadripper PRO 5965WX (24 cores, 64 GB), host build `cmake-build-release` (clang 19.1.1, `-O3`,
`NES_BUILD_NATIVE=ON`). r1–r6b: 1 worker + 1 source thread, `InMemory` prefill source (page-cache read wall removed);
r7: 23 workers + 1 io thread, `ccx_aware_task_queues: false`, `pin_threads: false`. Dataset `bid_strings_3GB.csv`
(31.3 M rows, 114.87 B/row). Input parsers Traced*/FastINT32/EiselFloat, output ZMIJ float codec, JSON output.

**Measured with.**

| rung(s) | pbench experiment | run_group | date | engine | runs |
| --- | --- | --- | --- | --- | --- |
| r1, r2, r3, r4, r6, r6b | `ablation_suite_json_inmem_seq_bidstr.yaml` | `20260824T165156-908bd862` | 2026-08-24 | `8217cce465` | 180 (3 reps) |
| r5 (fastpath-OFF binary) | `ablation_r5_inmem_fpoff_bidstr.yaml` | `20260824T171809-9e392631` | 2026-08-24 | `8217cce465` | 30 |
| r7 (= cross-format matrix `r_par`) | `matrix/cell_csv_json_rparfix.yaml` | `20260824T163459-fa906b40` | 2026-08-24 | `8217cce465` | 30 |
| r3_eager_all, r3_eager_fast, r3_eager (+ r2, r3 anchors) | `ablation_eager_all_bidstr.yaml` | `20261005T182825-4660e569` | 2026-10-05 | `b5d757c9f6`+overlay (= tag `piparse-artifact-v1` minus formatting) | 150, 19 min |
| r3_lazy_nopass (+ r3_eager_all, r3 anchors) | `ablation_lazy_nopass_bidstr.yaml` | `20261005T191325-76194e52` | 2026-10-05 | same | 90, 12 min |

All rows are in `results/tr/piparse_bench.duckdb` (table `runs`). Rung map:

```
r1  SequentialUncompiledOldCSV -> JSONUncompiled   interpreted formatter, scalar find() index
r2  SequentialUncompiledCSV    -> JSONUncompiled   interpreted, SIMD band index          (= matrix r_base)
r3_eager_all  SequentialCSV -> JSON, eager_parse + Fast parser twins + NES_EAGER_COPY_VARSIZED  compiled, PARSE-ALL (work-equal to r2)
r3_lazy_nopass SequentialCSV -> JSON, disable_passthrough + assume_clean_strings:false        compiled, lazy values, NO passthrough
r3  SequentialCSV -> JSON, default invoke           compiled, lazy + passthrough
r4  + invoke_mode fnattr                            GVN can dedup repeated parses
r5  + inline_invoke_calls   [FASTPATH-OFF binary]   general proxy/accessor inlining only
r6  + trace_constant_bytes + JSON output fast path  (= matrix r_comp)
r6b + lazy overloads (INPUT_FORMATTER.LAZY_*_OVERLOADS)
r7  SIMDCSV/PARALLEL, 23 workers, InMemory NES_INMEM_REPEAT=20  (= matrix r_par; stored MB/s x20 = true)
```

## Files

| path | what |
| --- | --- |
| `yaml/experiments/*.yaml`, `yaml/experiments/matrix/cell_csv_json_rparfix.yaml` | the exact experiment definitions (pbench tag `piparse-artifact-v1`); `*_irdump_*` are the IR-dump smoke variants used for the parse-all proof |
| `yaml/queries/nexmark/matrix/bidstr_*.yaml` | the 10 paper queries (SQL + schema + dataset binding) |
| `data/ablation_ladder_v8_bidstr.csv` | **the figure input**: MB/s medians per query, columns r1,r2,r3_eager_all,r3_eager_fast,r3_eager,r3_lazy_nopass,r3,r4,r5,r6,r6b on the v7 footing (new rungs = r3_v7 × same-session ratio) |
| `data/ablation_ladder_v8_bidstr_mrows.csv` | same in Mrows/s |
| `data/ablation_ladder_v7_bidstr{,_mrows}.csv` | the published v7 ladder incl. **r7** (`r7_true`, x20-corrected) — v8 has no r7 column, the figure takes r7 from here |
| `data/ablation_new_rungs_raw_2026-10-05.csv` | per-repetition rows of the two 2026-10-05 run groups (240 rows) |
| `data/eager_all_decomposition.csv`, `data/lazy_nopass_decomposition.csv` | the factor decompositions (compilation × pushdown × laziness; lazy code gen × passthrough) |
| `expected/RESULT_new_rungs_2026-10-05.md` | result doc: the IR-dump proof that r3_eager was not parse-all, the two new rungs, the chain |
| `expected/ABLATION_LADDER_V7_HANDOVER.md`, `expected/PASSTHROUGH_ABLATION_SPLIT_RESULTS.md` | the v7 ladder (methodology, anchors, r5 binary dance) and the earlier passthrough split |
| `expected/eager_all_tables.md`, `expected/lazy_nopass_tables.md` | the markdown tables the decompose scripts print |
| `expected/reference_renderings/` | the figure as rendered from the shipped CSV on 2026-10-12 (no earlier figure file existed; the v7 handover left the plot "deferred") + `lever_geomeans.csv` |
| `make_figure.py` | grouped-bar ladder (log-y) from `data/`, prints and writes the per-lever geomeans with the reference values next to them; `--all` adds r3_eager_fast/r3_eager, `--mrows` plots Mrows/s |
| `decompose_eager_all.py`, `decompose_lazy_nopass.py` | portable copies of the decomposition scripts (DuckDB + v7 CSV) |
| `extract_raw.py` | dumps the per-rep rows of the new-rung run groups (or `--v7` the v7 run groups) from the DB |
| `resolve_proxies.py` | resolves nautilus proxy-call addresses in a dumped `.ll` against the worker's `nm` table (the IR proof) |
| `run.sh` | re-measure recipe |

## Reproduce the figure from the shipped data (seconds)

```
python3 make_figure.py              # out/ablation_ladder_v8.{png,svg}, out/lever_geomeans.csv
python3 make_figure.py --all        # every column incl. the two intermediate eager rungs
python3 make_figure.py --mrows
python3 decompose_eager_all.py      # needs ../../results/tr/piparse_bench.duckdb (or --db / $PBENCH_DB)
python3 decompose_lazy_nopass.py
python3 extract_raw.py; python3 extract_raw.py --v7
```

Verified 2026-10-12 (pbench venv, duckdb 1.5.4, matplotlib 3.11): `decompose_*` regenerate `data/*_decomposition.csv` and
`expected/*_tables.md` byte-identically; `extract_raw.py` regenerates `data/ablation_new_rungs_raw_2026-10-05.csv`
byte-identically; `make_figure.py` geomeans vs the documented values: 1.083/1.08, 1.887/1.88, 1.495/1.50, 1.263/1.26,
1.120/1.12, 1.185/1.18, 1.251/1.25, 1.082/1.08, 9.733/9.73, old compile bar 3.564/3.56, cumulative 67.5×/68×.

## Re-measure (~60 min on the Threadripper + one engine rebuild for r5)

```
./run.sh        # suite (r1-r4,r6,r6b) ~22 min, r7 ~4 min, eager_all 19 min, lazy_nopass 12 min; prints the r5 binary recipe
```

Then `decompose_eager_all.py --run-group <new>`, `decompose_lazy_nopass.py --run-group <new> --run-group-prev <new eager_all>`
and splice the projected columns into a new `ablation_ladder_v8_bidstr.csv` (the v7 columns were assembled by pbench
`scratchpad/assemble_v7.py`: median per variant × series, r7 × 20). Expect anchors within 1–3 % (binary drift measured
0.99–1.03 on r2/r3 between 2026-08-24 and 2026-10-05).

## Re-measurement 2026-10-12: the two top rungs with lazy overloads ON (paper policy) → ladder **v9**

Paper policy (author, 2026-10-12): r6b (lazy overloads) and r7 (parallelisation) are both overloads-ON rungs. The v7/v8
ladder had r6b on the pre-fix overload path (2026-08-24) and r7 from the matrix cell with the knob OFF. Re-measured in one
session on the frozen binary (tag `piparse-artifact-v1` code), 10 queries × 3 reps per arm, 120 runs, 0 failures:

| arm | pbench experiment | run_group | config |
| --- | --- | --- | --- |
| r6_ctrl / r6b_ovl | `ablation_r6_overload_rerun_bidstr.yaml` | `20261012T150636-97b18744` | SequentialCSV→JSON, fnattr+inline+tcb, W1+io1, InMemory repeat 1; `overload` false / true |
| r7_ctrl / r7_ovl | `ablation_r7_overload_rerun_bidstr.yaml` | `20261012T151153-401837a8` | SIMDCSV PARALLEL→JSON, W23+io1, ccx/pin off, InMemory ×20; `overload` false / true |

Anchors: the ctrl arms reproduce the v7 ladder (geomean r6 0.999, r7 1.018 — per query in
`data/ablation_overload_rerun_medians_2026-10-12.csv`), so the new rungs are placed on the v7 footing by the same-session
ratio (`splice_overload_rerun.py`): `r6b_ovl = r6_v7 × r6b_ovl/r6_ctrl`, `r7_ovl = r7_v7 × r7_ovl/r7_ctrl` →
`data/ablation_ladder_v9_bidstr{,_mrows}.csv` (= v8 columns + `r6b_ovl`, `r7` (OFF, = v7), `r7_ovl`).

Effect of the knob: W1 q2og 3952 → 7746 MB/s (1.96×), q_ex 5359 → 6300 (1.18×), the other eight within ±0.6 %
(geomean 1.088 — the same 1.08 lever the v7 handover reported, now on the fixed path). W23: q2og 61.6 → 73.6 GB/s (1.19×),
q_ex +2.5 %, rest flat (geomean 1.020). Resulting paper ladder (`make_figure.py`, picks v9 automatically): levers
1.08 / 1.89 / 1.50 / 1.26 / 1.12 / 1.18 / 1.25 / **1.09 (r6→r6b_ovl)** / **9.87 (r6b_ovl→r7_ovl)**; cumulative r1→r7_ovl
geomean **68.9×** (v8: 67.5×), per query 48× (q1) … 92× (q_ex); q2og 75× → 89×. Rendered: `expected/reference_renderings/
ablation_ladder_v9.{png,svg}`, `_all` (adds the superseded r6b and OFF-r7 bars), `lever_geomeans_v9.csv`.
`make_figure.py --v8` reproduces the previous ladder.

## Caveats / provenance notes

- **r3_eager (v7's split rung) was NOT a parse-all rung** — the post-optimisation IR shows the JIT keeps only the
  parses whose parser plugin is an opaque proxy (3 of 6 fields on q2og); traced parsers and unused string views are
  DCE'd. That is why the two rungs r3_eager_all (Fast twins + `NES_EAGER_COPY_VARSIZED`) and r3_lazy_nopass
  (`disable_passthrough` + `assume_clean_strings: false`) were added. Use the r3_lazy_nopass chain for the paper's
  layer names (compilation → lazy values → passthrough); the eager-rung chain gives the same geomeans with a different
  per-query split (`RESULT_new_rungs_2026-10-05.md` finding 4).
- **The new rungs are spliced on the v7 footing**: r3_v7 × (rung / r3 measured in the same 2026-10-05 session). Same-
  session anchors r2, r3 reproduced v7 within 0.99–1.03.
- **r7 is an InMemory run with `NES_INMEM_REPEAT=20`**: the DB stores the reported value, the CSV column `r7_true` is
  ×20. Apply the ×20 before any use of r7 absolutes.
- **Known defect at the top of the ladder (not re-run)**: r6b (2026-08-24) ran on the pre-fix overload path (word-compare
  fast path `f6a7b98343` landed 2026-08-30) and r7 reused the matrix cell with `overload: false`. Consequence: r7 q2og
  (520.6 Mrows/s) ≈ today's no-overload 518, not the 611 of E06; the r6b→r7 multiplier for q2og is therefore ~1.2× too
  low and the r6→r6b q2og 1.93× was "a length reject, not a byte compare". A 40-min same-session re-run (r6 ctrl, r6b ovl,
  r7 ctrl, r7 ovl) was proposed and is still awaiting the authors' go.
- **r5 needs a different binary** (JSON output fast path compiled out) so that the output fast path lands at r5→r6; the
  recipe is in `run.sh` and `expected/ABLATION_LADDER_V7_HANDOVER.md` §5.
- W1 rungs use InMemory; the cross-format matrix's W1 rungs (E11) use BlockingFile → r6 sits +12–45 % above the matrix
  r_comp (read-wall removal), r2 +2–5 % above r_base, r7 within ±2 % of r_par.
- q10's datetime function is the hand-rolled ISO-8601 formatter (ladder v5 fix), not `std::format`.
- **PAPER POLICY (author, 2026-10-12): r6b and r7 are both overloads-ON rungs.** The shipped r7 (`cell_csv_json_rparfix`, 2026-08-24) has `overload: false` in its config and no later r7 run exists in the shipped DB; r6b ran on the pre-fix overload path. RESOLVED 2026-10-12 by the re-measurement above (ladder v9).
