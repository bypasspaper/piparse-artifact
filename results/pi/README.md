# results/pi — Raspberry Pi 5 raw run exports (CSV dumps of the Pi-side pbench DuckDB `runs` table)

The Pi (`pi-box`) keeps its own `results/piparse_bench.duckdb`; these are the `COPY (SELECT * FROM runs WHERE …)`
exports that were pulled to the reference box. Column schema = the pbench `runs` table (run_id, timestamp, experiment,
variant, series, repetition, query_ref, …, throughput_mbps, p50/p99/p999_latency_us, processing_time_s, config JSON, git_commit).
**All timestamps are Pi-clock, ~6 days behind real time.**

| file | experiments | used by |
| --- | --- | --- |
| `pi_tiers_aug_raw.csv` | `pi_stateless_tier`, `pi_stateful_tier`, `pi_native_{stateless,stateful}`, `pi_naive_{stateless,stateful}_w3` (Aug-23 binary) | E07 (control) |
| `pi_tiers_nb_raw.csv` | the same six tiers as `*_nb` / `pi_stateful_tier_nb2` (engine b5d757c9f6, inlining OFF) | E07 (control) |
| `pi_tiers_nbi_raw.csv` | the same six tiers as `*_nbi` (**build e**: b5d757c9f6 + nautilus 0005, inlining ON) | **E07 (final)** |
| `pi_inline_verify_raw.csv` | `pi_inline_verify` (12-run smoke of the aarch64 inlining fix) | E07 |
| `naive_tier_w1.csv`, `naive_tier_w3.csv` | `pi_naive_{stateless,stateful}` (W1) and `_w3` (Aug-23 binary) | E07 |
| `flink_scaling.csv` | `pi_flink_scaling_a` (run_group 20260824T024940-530263c1 only), `_b`, `_c`, `_c_n1000` — N 1..1000 | E08 |
| `naive_scaling.csv` | `pi_naive_scaling_{a,b,c,d}` (W1 reference ladder) | E08 |
| `naive_scaling_w3.csv` | `pi_naive_scaling_w3_{a,b,c,d}` (the fair naive ladder, W3) | E08 |
| `naive_inflight_probe.csv` | `pi_naive_inflight_probe` (naive W3, N ∈ {1,4,16} × cap ∈ {4,16,64}) | E08 |
| `flink_n1000_probe.tsv` | 30 s health sampler of the 13.9 h Flink N=1000 run (RSS, MemAvailable, clock, throttle, temp, GC) | E08 |

**Not on this box (gap):** `nes_scaling.csv` (`pi_scaling_file_{a,b,c}`), `spark_scaling.csv` (`pi_spark_mb_{a,b,c}`),
`native_scaling.csv` (`pi_noserde_scaling_{a..d}`), `ALL_pi_runs_raw.csv`, and the overload/tier-ovl exports — produced on the
Pi by `experiments/E08_scaling_ladders_n1_1000/scripts/pi_dump.py` (job list with per-file caveats) and
`experiments/E07_pi_per_query_tiers/scripts/export_pi_tiers_build_e.sh`; copy them here when the Pi is back online.
