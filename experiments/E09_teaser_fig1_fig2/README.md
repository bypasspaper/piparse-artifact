# E09 — §2 teaser figures: Fig. 1 (CPU per tuple by stage) and Fig. 2 (per-field cost law)

**Claim in the paper.** Fig. 1: on three queries (q0 `SELECT *`, NEXMark Q2-original 5-way point filter, YSB windowed
count) a naive text-processing engine and Apache Flink spend 25–98 % of their CPU on (de)serialization, at 160–1350 ns
per tuple; the fully optimised NebulaStream path needs 4.8–22 ns per tuple (naive→optimised CPU/tuple 49× / 34× / 25×).
Fig. 2: per-row cost grows linearly with the number of fields N, `ns/row = a + b·N`; for the predicate sweep
(`SELECT * WHERE c0 < 8000` over 1 INT32 + N−1 FLOAT64 columns) the per-field slope is naive 82.6, Flink 90.6 vs bypass
1.24 ns/field (overload ON; 1.42 with overload OFF) — 67× / 73×. State the claim as the fitted slope, never as "rows/s
falls x times" (decision 7 below).

**Machine.** Threadripper PRO 5965WX (Ubuntu 24.04), NES at W1 + 1 io thread (sequential compiled formatter; the whole fused
pipeline runs on the source thread), Flink 2.1.3 PyFlink MiniCluster parallelism 1, JDK 11. Binary: `cmake-build-release`
worker + nes-cli built 2026-09-03 10:50 from `b5d757c9f6` + the then-uncommitted overlay (all of it is in engine tag
`piparse-artifact-v1`). Runs 2026-09-25 … 09-28 (Flink q0/YSB profiles and the full-projection Flink line: 2026-09-03).

**Measured with** (pbench, tag `piparse-artifact-v1`; copies in `yaml/`):

| element | experiment(s) | run_group(s) in `results/tr/piparse_bench.duckdb` | runs / wall |
| --- | --- | --- | --- |
| Fig. 1 v2 throughput annotations | `fig1_teaser_thru` (NES naive+optimised, 3 reps) | `20260928T131039-664fb074` | 17/18 (ysb optimised rep 3 died exit 8) / 4 min |
| Fig. 1 v2 Flink throughput | `fig1_flink_thru_q2og`; q0/YSB from `fig1_flink_thru` | `20260928T131550-392652fe`; `20260903T152709-428dc109` | 3 / 2 min; 15 / 25 min |
| Fig. 1 v2 stage shares + CPU ns/tuple | perf (NES, 20 s @ 4 kHz; YSB whole-life + busy window) and async-profiler 4.1 (Flink) — **not in the DB**, see `scripts/profiling/` | — | ~40 min chain (`run_teaser2.sh`) |
| Fig. 1 JIT-block split (q0 framing 2.8 ns) | `fig1_opt_diff` (json-out vs csv-out vs eager) | `20260925T162711-78285297` | 25 / 4 min |
| **Fig. 2 C predicate sweep (paper)** | `fig2_pred_nes` (naive, bypass±overload, 10 reps) + `fig2_pred_flink` (3 reps) | `20260928T102349-e2555ee8` + `20260928T111401-305030d8` | 300 / 50 min + 30 / 13 min |
| Fig. 2 A full projection (alternative) | `fig2_fieldsweep_v2` (naive, eager, lazy, anchor; 10 reps) + Flink `fig2_flink_fieldsweep` | `20260925T172743-7bd023f8` + `20260903T155730-7d699aad` | 399/400 / 85 min + 30 / 20 min |
| Fig. 2 B one projected field (alternative) | `fig2_proj1_nes` + `fig2_proj1_flink` | `20260926T101406-26ac44bf` + `20260926T105201-2bdfb3e6` | 200 / 38 min + 30 / 12 min |
| Fig. 2 stage-CPU vs N (evaluation) | 20 perf profiles + `fig2_lazy_csvout` differencing | `20260925T213541-8c91e4b9` (30 runs) | ~15 min |

## Files

| path | what |
| --- | --- |
| `yaml/experiments/fig1_*.yaml`, `fig2_*.yaml` | the 25 pbench experiment definitions (sweeps, probes, smokes, profiling windows) |
| `yaml/queries/multicol/{pass,pred,proj1,allf}_n{1..10}.yaml` | the 40 sweep queries (sink schema MUST be qualified `t.cN`; unqualified fails nes-cli silently) |
| `yaml/queries/nexmark/*.yaml`, `yaml/queries/yahoo/ysb_1k_varsized.yaml` | the Fig. 1 queries (q0 = `bid_star`, Q2-original = `q2_original`, YSB; `q2_filter` = the superseded MOD variant) |
| `yaml/profiling_templates/` | the perf/async-profiler window yamls used by the Fig. 1 chain |
| `data/fig1_teaser2_naive_flink_optimised_2026-09-28_data.csv` | **Fig. 1 input**: query, arm, deser/proc/ser %, ns per tuple (total and per stage), Mrows/s |
| `data/fig2_pred_rowss_mbps_4arm_2026-09-28_{data,raw}.csv` | **Fig. 2 input**: medians per arm×N (+ every rep with run_id) |
| `data/fig2_v2_rowss_mbps_2026-09-25_data.csv`, `data/fig2_flink_data.csv`, `data/fig2_fieldsweep_v2_raw.csv` | full-projection sweep medians (NES rungs; Flink 2026-09-03) + raw reps |
| `data/fig2_proj1_rowss_mbps_3arm_2026-09-26_data.csv` | one-field projection sweep medians |
| `data/fig2_v2_stage_cpu_naive_vs_lazy_2026-09-25_data.csv` | stage CPU ns/row and shares per N, naive vs lazy (from the 20 profiles) |
| `data/fig1_*2026-08-19*.csv`, `data/fig1_flink_*.csv`, `data/fig1_teaser_data.csv`, `data/fig2_v2_cpu_per_row_*.csv`, `data/fig2_pred_probe_data.csv` | the NES-naive originals (2026-08-19), the Flink repeat (2026-09-03), the v1 teaser, superseded per-thread CPU view, the 1-rep probe |
| `expected/*.{pdf,png}` | the two paper figures; `expected/alternatives/` the evaluation variants; `expected/superseded/` v1 + per-thread views |
| `expected/*.md` | the result documents: handover (decisions + numbers), the 2026-09-25 method doc, the Flink repeat, the 2026-08-19 originals |
| `scripts/plot_teaser2.py` | Fig. 1 v2 plot from the data CSV |
| `scripts/extract_fig2_pred.py` | Fig. 2 extraction (DB → medians + a+bN fit + figure) or `--from-csv` plot of shipped medians; produced Fig. 2 C and B |
| `scripts/extract_fig2_v2.py`, `scripts/plot_fig2_v2.py` | Fig. 2 A extraction (medians, fits, anchor drift gates) and plot (`--teaser` drops the eager rung) |
| `scripts/plot_fig2_stage.py`, `scripts/plot_fig2_stage_log.py` | stage-CPU vs N (linear 3-panel; log per-tuple variant) |
| `scripts/profiling/` | the perf/async-profiler classification pipeline behind the Fig. 1 shares (verbatim, documented in its README; needs the perf data + `results/artifacts`) |
| `scripts/gen_float_csv.py` | generator of the `nf{N}.csv` all-FLOAT64 sweep files (pbench `scripts/`, 2026-08-12) |
| `scripts/gen_mixed_pred_rows.py` | **reconstruction** of the lost inline generator of the `nm{N}.csv` INT32+FLOAT64 files (see data caveat) |
| `make_figure.py`, `run.sh` | driver / re-measure recipe |

## Reproduce the figures from the shipped data (seconds)

```
python3 make_figure.py            # out/fig1_teaser2_naive_flink_optimised.{pdf,png}, out/fig2_pred_rowss_mbps_4arm.{pdf,png,_data.csv}
                                  # + alternatives: out/fig2_v2_rowss_mbps_{3rung,teaser}, out/fig2_proj1_rowss_mbps_3arm, out/fig2_v2_stage_cpu_*
python3 make_figure.py --db       # additionally re-extracts the three Fig. 2 median tables from results/tr/piparse_bench.duckdb and diffs
                                  # them against data/ (verified 2026-10-12: 40 + 30 + 40 cells, max relative deviation 0.000 %)
```
Python deps: `../../scripts/requirements.txt` (duckdb only for `--db`).

## Re-measure (Threadripper; see wall times above)

```
./run.sh pred      # Fig. 2 C: fig2_pred_nes (50 min) + fig2_pred_flink (13 min)
./run.sh pass      # Fig. 2 A: fig2_fieldsweep_v2 (85 min); Flink line: experiments/fig2_flink_fieldsweep.yaml (20 min)
./run.sh proj1     # Fig. 2 B
./run.sh fig1      # prints how to run the Fig. 1 profiling chain (scripts/profiling/run_teaser2.sh; needs perf + async-profiler)
python3 make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb
```
Datasets (under `<build>/nes-systests/testdata/large/`): `multicol/nf{1..10}.csv` — `scripts/gen_float_csv.py -o nf{N}.csv -c N -s 200M`
(FLOAT64, 6 decimals; original seed not recorded); `multicol/nm{1..10}.csv` — `scripts/gen_mixed_pred_rows.py N nm{N}.csv`;
`nf{N}_x10.csv` / `nm{N}_x10.csv` = the file concatenated 10× (Flink arms); Fig. 1: `nexmark/bid_1GB.csv` (NES, InMemory
repeat), `nexmark/bid_6GB.csv` (Flink; ExternalData), YSB `large`/`xlarge` as named in `yaml/queries/yahoo/ysb_1k_varsized.yaml`.
Pre-flight for every NES run: `pkill -9 -x main; ss -ltnHp 'sport = :9099'` must be empty (ghost workers hold the port and
silently serve the queries — gotcha 1 in the handover).

## Caveats / provenance notes

- **Decisions taken with the author (do not re-litigate):** (1) §2 figures are teasers (naive + Flink + fully optimised);
  the rigorous versions are in the evaluation. (2) Stage taxonomy: deserialize = index + parse; serialize = formatting +
  JSON framing; process = operator work INCLUDING the raw passthrough copy (a native engine would copy too) + engine glue
  (disclosed). (3) Fig. 1 filter bar = ORIGINAL NEXMark Q2 (equality chain) with overloading ON — the MOD rewrite cannot
  use the overload. (4) Fig. 2 = predicate sweep on MIXED rows (INT32 predicate column): the INT lazy representation
  overloads `<`, the FLOAT one only `==`/`!=` vs int constants. (5) Per-run artifacts (sink CSV + per-thread CPU series)
  are persisted so the visualisation can be chosen afterwards. (6) 10 reps NES, 3 reps Flink. (7) Phrase Fig. 2 as the
  per-field slope / fitted law.
- **Fig. 1 shares cannot be re-derived from this artifact alone**: they come from perf symbol dumps and async-profiler
  collapsed stacks (session scratch, ~200 MB, not shipped) and from pbench `results/artifacts/<exp>/<run_id>/threadcpu.csv`
  (gitignored in pbench, archived separately — `../../results/README.md`). `data/fig1_teaser2_*_data.csv` is the entry point.
  Absolute NES CPU/tuple = the profiled run's own procfs CPU in the sink window × (1 − idle) / rows over ALL busy threads
  (naive uses ~1.5 cores, so CPU/tuple > wall/tuple); the optimised arm's idle-spinning worker thread is excluded.
  Flink absolute = stage samples / 4000 Hz / rows, GC/JIT/read/kernel excluded. The opaque JIT block is split by knob
  differencing (q0: json − csv output = 2.8 ns → serialize; q2og/YSB no output → process). Panel (b) stacks on a LOG axis:
  segments are not to scale, read the split from (a). Q2 optimised "70 % deserialization" IS the SIMD index alone
  (3.3 ns; no parse symbol in the profile) — put the absolute next to the share in the caption.
- **Knob states.** All optimised arms ran with `inline_invoke_calls` and `trace_constant_bytes` at their worker default
  (true) = the ablation's r6 "context" layer; `fnattr` invoke mode; overload ON in Fig. 1 v2 and in the `compiled_lazy_ovl`
  series of Fig. 2 C (the `_noovl` twin is the one-knob ablation: −6.8 ns fixed = the FastINT32 parse, same slope).
- **Flink.** Projection pushdown exists at the planner but reaches only the converter (every column is still tokenised);
  there is no filterable decoding format, so `SELECT * WHERE` converts every payload float before the Calc drops 99.2 % of
  rows (Fig. 2 C slope 90.6 ns/field). Flink jobs in the sweeps run 10–30 s (JVM warm-up share; 3 reps).
- **Degenerate / superseded points.** Naive N=1 on a 1-column row has no field delimiter (old scalar indexer, ~+75 ns):
  read naive slopes from N ≥ 2 (hence the negative intercept −37.9 in Fig. 2 C). `fig1_teaser_naive_vs_optimised_2026-09-25`
  (v1: overload OFF, q2 = MOD variant) and the per-thread CPU views are superseded. 1 of 400 full-projection runs was lost
  to an operator `pkill` (anchor n10 rep 10; median unaffected). YSB optimised single-pass SIGSEGVs in ~30 % of runs
  (`ChainedHashMap::updateTimestamp`, open engine bug) — the chain retries.
- **Data generators.** `nm{N}.csv` was produced by an inline numpy snippet (seed 1000+N) that was not saved;
  `scripts/gen_mixed_pred_rows.py` implements the documented spec (statistically equivalent, not byte-identical).
