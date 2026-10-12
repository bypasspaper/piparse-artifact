# Pi Flink N=1000 concurrent-query point — DONE 2026-09-22/23 (real), Pi clock 2026-09-16 09:11 → 23:05

Experiment `pi_flink_scaling_c_n1000` (copy of `pi_flink_scaling_c` with `values: [1000]`, `completion_timeout_s: 150000`,
`flink_config: {heartbeat.interval: 60000, heartbeat.timeout: 1800000, pekko.ask.timeout: 600 s}`,
`flink_jvm_args: -Xmx8g -Xlog:gc*`), run_group `20260916T091155-dd7e327b`, pid 1843, launched real 2026-09-22 09:15 on the
stock 27 W PSU after a passing pre-flight (5000 mA, throttled 0x0, 2.4 GHz under load, governor ondemand — see
flink_n1000_preflight.txt). Status: **Done: 1 completed, 0 failed.**

| N | MB/s | p50 s | p99 s | p999 s | processing_time_s |
|---|---|---|---|---|---|
| 100 (b, Aug 24) | 138.47 | 0.206 | 0.659 | 1.003 | 2596 |
| 250 (b, Aug 24) | 96.78 | 0.712 | 2.403 | 3.338 | 9287 |
| 500 (c, Aug 24) | 73.13 | 1.861 | 6.545 | 8.435 | 24581 |
| **1000 (c_n1000)** | **73.55** | **3.564** | **13.461** | **17.560** | **48883** |

Reading: the Pi Flink throughput plateau (~73 MB/s) holds from N=500 to N=1000 while the latency tail scales ~linearly with N
(p99 6.5 → 13.5 s, p999 8.4 → 17.6 s, p50 1.9 → 3.6 s) — the same tail-collapse shape as the Threadripper Flink ladder, at
1000 queries on 4 cores.

Health over the 13.9 h (sampler flink_n1000_probe.tsv, 1613 samples @30 s): 0 heartbeat timeouts, 0 failed tasks, all 2002
tasks RUNNING→FINISHED; JVM RSS 7.3-9.9 GB; **MemAvailable never below 5007 MB** (the 3429 MB page-cached CSV stayed resident
= clean page-cache measurement); ARM 2400 MHz and `get_throttled` 0x0 at every sample; max temp 75.2 °C; ~3220 full GCs
(≈ 3.9/min, 150-230 ms each; log rotated 3× at 50 MB); JVM threads 5065 steady, ramping down from ~21:30 real as pipelines
finished.

Footnote for the paper: N ≤ 500 ran on the default 3.96 GiB heap, N=1000 on 8 GiB with a 30 min heartbeat timeout. The
throttled-era smoke runs (`pi_flink_scaling_fixsmoke*`) are NOT ladder points. User decided 2026-09-22: no N=500 re-run at
8 GiB unless the N=1000 result showed a need — it did not (throughput continuous with N=500).

Files here: flink_scaling.csv (export via ~/powertest/dump.py on the Pi, selection extended with `pi_flink_scaling_c_n1000`;
dump.py.bak_pre_n1000 kept), pyflink_cluster_n1000.log (the per-launch PyFlink cluster log, 11 MB), flink_n1000_probe.tsv,
flink_n1000_preflight.txt, pi_flink_scaling_c_n1000.yaml, pbench_run_20260916T091155.log. GC logs (4 × ≤50 MB) and the driver
script/stdout stay on the Pi in ~/powertest/flink_n1000_result/. pbench code patch (renderer.py EXTRA_CONF, runners/flink.py
JVM_ARGS) still UNCOMMITTED on both machines.
