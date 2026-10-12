# Raw data archive — the 16-cell input x output matrix (run 2026-08-04 22:37 -> 08-05 02:44)

Complete, figure-regenerable record of the paper's matrix experiment (and every other run
this session). NOTHING here is aggregated-only: every individual run (repetition) is a row.
Companion narrative + the computed 4x4 table: ../2_engine_to_e2e/MATRIX_RESULTS_2026-08-05.md.

## ⚠️ V2 (2026-08-06): use matrix_rpar_fixed_480 for r_par

The original runs' r_par arms were measured under the ccx_aware+pin single-source
PATHOLOGY (~2x low on filter-class queries; see MATRIX_RESULTS v2). The CORRECTED r_par
data (W23 + ccx_aware=false + pin_threads=false, 480 runs) is `matrix_rpar_fixed_480.
{csv,parquet}` (experiment names carry `_rparfix`; strip the suffix to join). For any v2
figure: r_base/r_comp from matrix_runs_all1440, r_par from matrix_rpar_fixed_480 (see
plot_matrix_figure.py's UNION query). The same caveat applies to the W-sweep/probe rows in
session_runs_all.csv that ran ccxON+pinON. Diagnostic experiments (par_w1_decomposition,
par_lowW_ccx_pin, par_ccx_pin_q0, fixprobe_*, w8probe_*) and the v2 runs are in
`piparse_bench_snapshot_2026-08-06_final.duckdb` (the complete final snapshot; the 08-05
one predates them).

## Files

| file | what |
| --- | --- |
| `matrix_runs_all1440.csv` / `.parquet` | THE experiment: one row per run, 1440 rows = 16 cells x 10 queries x 3 rungs x 3 reps. Full metric + config columns (below). |
| `session_runs_all.csv` | superset (1703 rows): + the 3-cell probes, W-sweeps (W8..48 + SMT), W23/W24 reruns, legacy-arm reruns, stateful re-verification, InMemory probes of 2026-08-04. |
| `matrix_rpar_fixed_480.csv` / `.parquet` | **V2 r_par arms** (fixed config), one row per run, 480 rows. |
| `piparse_bench_snapshot_2026-08-05.duckdb` | full DuckDB store snapshot (tables `runs`, `aggregated`) — the authoritative source both CSVs were dumped from; also holds all PRE-session history (8300 rows). |
| `piparse_bench_snapshot_2026-08-06_final.duckdb` | complete FINAL store snapshot incl. v2 + all diagnostics. |
| `pbench_mon_dirs_2026-08-05.tar.gz` | the per-run MonitoringSink CSVs + worker logs (3966 runs' kept dirs, rescued from volatile /tmp). Each `query_0000_monitoring.csv`: processing time, throughput, latency avg/min/max/p50/p99/p999, first/last-event timestamps. |

## Row identity in matrix_runs_all1440

`experiment` = `cell_<input>_<output>` (csv/json/hl7/xml both axes); `variant` = query id
(q0, qproject, qroute, q1, q2og, q2mod, q10, q14, q22, qex); `series` = rung
(r_base = fully-interpreted fair-codec baseline W1; r_comp = compiled full-opt W1;
r_par = parallel W23 InMemory); `repetition` = 1..3. Config lineage columns: git_commit,
input_formatter, output_formatter, source_type, worker_threads, invoke_mode, ...

## Metric columns (per run)

throughput_mbps (per-format WIRE bytes / processing_time), throughput_mrows_s, input_rows
(31.3M for all matrix runs), processing_time_s, avg/min/max/p50/p99/p999_latency_us, plus
codec_* diagnostics where sampled.

## Derivation rules (to rebuild ANY figure variant)

- **r_par x20**: r_par runs use InMemory with NES_INMEM_REPEAT=20 and the runner counts the
  file bytes ONCE -> TRUE r_par throughput = stored value x 20 (both mbps and mrows_s).
  r_base/r_comp (BlockingFile) need no correction. The x20 cancels in nothing — apply it
  before ANY use of r_par absolutes; it cancels only inside ratios taken across r_par runs.
- **Ratios**: Comp = r_comp/r_base, Par = (r_par x20)/r_comp, Total = Comp x Par — per
  (cell, query), from per-run medians or from all 3x3 rep pairs for error bars.
- **Cell aggregate (frozen spec)**: geomean of REGIME geomeans; regimes: output{q0},
  projection{qproject}, filter{qroute,q2og,q2mod}, compute{q1,q10,q14}, string{q22},
  mixed{qex}. (A flat 10-query geomean is a legitimate sensitivity variant.)
- **Cross-format ABSOLUTE comparisons**: use throughput_mrows_s (MB/s denominators are
  per-format wire bytes: csv 3595281395 B, json 5567181395, hl7 5723681395, xml 5661081395;
  rows always 31300000).
- Queries/experiments that produced these: piparse-bench queries/nexmark/matrix/*.yaml +
  experiments/matrix/cell_*.yaml (generated; conventions + caveats in
  ../2_engine_to_e2e/SESSION_HANDOVER_2026-08-04b.md — Q_ex = 220 matched rows, q2og ids
  match ~0 rows, channel literal is lowercase "google").
