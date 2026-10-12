# Results (raw measurements)

## `tr/piparse_bench.duckdb` — the Threadripper results database (19 MB)

Every pbench run on the reference box from 2026-06 to 2026-10-06, one row per repetition in table `runs`
(`experiment, variant, series, x_value, repetition, run_group, git_commit, throughput_mbps, throughput_mrows_s,
input_rows, processing_time_s, p50/p99/p999_latency_us, config (JSON of the resolved experiment config), …`) and the
run-group-scoped medians in view `aggregated`. Each `experiments/E*/README.md` names the `run_group` id(s) its
figure is drawn from; the `make_figure.py` scripts query this file by default (`--db` / `PBENCH_DB` to point at a
fresh database after re-measuring).

```
duckdb tr/piparse_bench.duckdb "select experiment, run_group, count(*) from runs group by 1,2 order by max(timestamp) desc limit 20"
```

Column meaning that is easy to get wrong: `throughput_mbps` counts the **input file bytes once**; runs with an
InMemory source and `NES_INMEM_REPEAT=k` (the parallel rungs) must be multiplied by `k` (the per-experiment
scripts do this). Latency columns are per-buffer ingest→sink stamps from the MonitoringSink.

`tr/matrix_snapshot_2026-08-06_final.duckdb` (7 MB) is the frozen store behind the cross-format matrix (E11) —
the same schema, taken before later experiments were appended.

## `pi/` — Raspberry Pi exports

The Pi keeps its own copy of the database (`/home/pi/data/repos/piparse-bench/results/piparse_bench.duckdb`, Pi
clock ≈ real time − 6 days). The CSVs here are `pi_dump.py` exports (`experiments/E08_*/pi_dump.py`) of the
Pi runs the paper uses; the Pi experiment names are mapped to paper arms in `experiments/E07_*/README.md`.
Exports not present on the reference box at freeze time are listed as gaps in E08's README.

## Per-run raw artifacts (not in this repository)

From 2026-09-25 on, pbench persists every run's MonitoringSink CSV, worker log and a 0.25 s per-thread CPU time
series under `piparse-bench/results/artifacts/<experiment>/<run_id>/` (123 MB at freeze; `run_id` joins to
`runs.run_id`). They are the raw input of the Fig1 CPU-share teaser (E09) and are archived outside git:

```
cd $PBENCH_DIR && tar -I 'zstd -19' -cf pbench_artifacts_2026-10-12.tar.zst results/artifacts
```

Older raw per-run directories (3,966 runs up to 2026-08-05, incl. the cross-format matrix) are in
`~/Notes/nebulastream/benchmark/matrix_2026-08-05/pbench_mon_dirs_2026-08-05.tar.gz` (0.5 MB).
