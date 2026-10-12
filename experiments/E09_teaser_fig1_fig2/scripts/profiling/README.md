# Fig1 v2 profiling pipeline (verbatim copies, NOT runnable from the artifact alone)

These are the scripts that produced the stage shares in `data/fig1_teaser2_naive_flink_optimised_2026-09-28_data.csv`
and `data/fig2_v2_stage_cpu_naive_vs_lazy_2026-09-25_data.csv`. They read (a) `perf report` symbol dumps and
async-profiler collapsed stacks that live in the authors' session scratch directory (not shipped: ~200 MB of perf
data), and (b) the per-run artifacts `results/artifacts/<exp>/<run_id>/{threadcpu.csv,query_*_monitoring.csv}` written
by pbench (gitignored in pbench; archived separately, see `../../../results/README.md`). Paths inside are the
authors' absolute paths (`~/work/piparse-bench`, `~/Notes/...`) by design -- they document the method.

| file | role |
| --- | --- |
| `run_teaser2.sh` | the chain: 6 NES perf profiles (naive/optimised × q0/q2og/ysb), clean throughput, Flink q2og profile + throughput |
| `profile_opt_one.sh`, `profile_ysb_full.sh`, `profile_opt_ysb_full.sh`, `window_report.sh` | perf attach-and-wait (20 s @ 4 kHz) / whole-life + busy-window restriction for YSB |
| `profile_flink_one.sh` | async-profiler 4.1 cpu@4 kHz on the PyFlink MiniCluster JVM (JVM_ARGS at launch) |
| `classify_v2.py` | optimised-arm symbol → stage buckets (index kernels + codecs = deser; ZMIJ/JSON writer = ser; JIT block opaque) |
| `stage_cpu_sweep.py` | naive-arm thread+symbol rules (2026-08-19) + the Fig2 stage-CPU sweep assembly |
| `classify_flink.py` | Flink thread + frame → stage buckets (fetcher = deser, task thread by nearest classified frame) |
| `cpu_from_artifacts.py` | per-thread CPU inside the MonitoringSink window from threadcpu.csv |
| `assemble_teaser2.py`, `assemble_teaser2_flink.py` | build the Fig1 v2 data CSV (shares + CPU ns/tuple + throughput) |
| `assemble_fig1_teaser.py`, `plot_fig1_teaser.py` | the superseded v1 (overload OFF, q2 = MOD variant) |
| `extract_diff.py` | knob-differencing of the opaque JIT block (json-out vs csv-out, eager vs lazy; `fig1_opt_diff.yaml`) |
| `plot_fig2_cpu.py`, `plot_fig2_util.py` | the superseded per-THREAD CPU views |
| `explain.py`, `explain_filter.py` | Flink 2.1.3 EXPLAIN probes (projection pushdown reaches the converter only; no filterable decoding format) |
| `plot_pred_sketch.py` | the 2026-09-27 probe sketch for the predicate sweep |
