## Throughput (e2e, GB/s input, median of n reps)
| W | q_ex LF | q_ex LK | q_ex LF/LK | SELECT id LF | SELECT id LK | SELECT id LF/LK | q_ex/selid LF | q_ex/selid LK | figW Aug-31 LF/LK |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1.28 | 1.30 | **0.99** | 1.29 | 1.32 | **0.98** | 0.99 | 0.99 | 0.97 |
| 2 | 1.40 | 1.38 | **1.01** | 1.41 | 1.37 | **1.03** | 1.00 | 1.01 | 1.02 |
| 4 | 2.11 | 1.89 | **1.11** | 2.15 | 1.90 | **1.13** | 0.98 | 1.00 | 1.14 |
| 8 | 3.27 | 2.68 | **1.22** | 3.28 | 2.67 | **1.23** | 1.00 | 1.01 | 1.27 |
| 12 | 3.93 | 3.15 | **1.25** | 3.93 | 3.16 | **1.24** | 1.00 | 1.00 | 1.30 |
| 16 | 4.31 | 3.38 | **1.28** | 4.33 | 3.39 | **1.28** | 1.00 | 1.00 | 1.34 |
| 20 | 4.43 | 3.46 | **1.28** | 4.42 | 3.46 | **1.28** | 1.00 | 1.00 | 1.35 |
| 24 | 4.44 | 3.41 | **1.30** | 4.43 | 3.41 | **1.30** | 1.00 | 1.00 | 1.37 |

## Latency (e2e, ms, median of reps) — p50 / p99
| W | q_ex LF p50 | q_ex LK p50 | q_ex LF p99 | q_ex LK p99 | selid LF p50 | selid LK p50 | selid LF p99 | selid LK p99 |
|---|---|---|---|---|---|---|---|---|
| 1 | 25.46 | 25.11 | 34.46 | 34.31 | 25.34 | 24.84 | 35.53 | 34.87 |
| 2 | 23.67 | 24.04 | 31.72 | 29.19 | 23.56 | 24.15 | 28.23 | 28.79 |
| 4 | 15.65 | 17.46 | 22.50 | 22.92 | 15.36 | 17.42 | 20.08 | 22.16 |
| 8 | 10.00 | 12.22 | 14.87 | 17.41 | 9.97 | 12.32 | 14.69 | 16.99 |
| 12 | 8.28 | 10.38 | 13.22 | 15.39 | 8.29 | 10.38 | 12.99 | 15.73 |
| 16 | 5.41 | 9.68 | 11.62 | 15.01 | 7.09 | 9.62 | 11.61 | 14.73 |
| 20 | 0.60 | 9.45 | 9.89 | 15.31 | 0.15 | 9.44 | 10.30 | 15.35 |
| 24 | 0.04 | 9.59 | 10.17 | 16.41 | 0.04 | 9.57 | 10.10 | 16.27 |

## Window lengths (min processing_time_s per cell) and rep counts
qex_12k_span3    lock_free  W1   win_min=3.23s n=6
qex_12k_span3    lock_free  W2   win_min=2.93s n=6
qex_12k_span3    lock_free  W4   win_min=1.96s n=6
qex_12k_span3    lock_free  W8   win_min=1.28s n=6
qex_12k_span3    lock_free  W12  win_min=1.06s n=6
qex_12k_span3    lock_free  W16  win_min=0.93s n=6
qex_12k_span3    lock_free  W20  win_min=0.94s n=6
qex_12k_span3    lock_free  W24  win_min=0.93s n=6
qex_12k_span3    locking    W1   win_min=3.10s n=6
qex_12k_span3    locking    W2   win_min=2.99s n=6
qex_12k_span3    locking    W4   win_min=2.18s n=6
qex_12k_span3    locking    W8   win_min=1.55s n=6
qex_12k_span3    locking    W12  win_min=1.32s n=6
qex_12k_span3    locking    W16  win_min=1.23s n=6
qex_12k_span3    locking    W20  win_min=1.20s n=6
qex_12k_span3    locking    W24  win_min=1.22s n=6
selid_12k_span3  lock_free  W1   win_min=3.15s n=6
selid_12k_span3  lock_free  W2   win_min=2.97s n=6
selid_12k_span3  lock_free  W4   win_min=1.93s n=6
selid_12k_span3  lock_free  W8   win_min=1.27s n=6
selid_12k_span3  lock_free  W12  win_min=1.06s n=6
selid_12k_span3  lock_free  W16  win_min=0.96s n=6
selid_12k_span3  lock_free  W20  win_min=0.94s n=6
selid_12k_span3  lock_free  W24  win_min=0.93s n=6
selid_12k_span3  locking    W1   win_min=3.14s n=6
selid_12k_span3  locking    W2   win_min=2.98s n=6
selid_12k_span3  locking    W4   win_min=2.20s n=6
selid_12k_span3  locking    W8   win_min=1.56s n=6
selid_12k_span3  locking    W12  win_min=1.32s n=6
selid_12k_span3  locking    W16  win_min=1.23s n=6
selid_12k_span3  locking    W20  win_min=1.21s n=6
selid_12k_span3  locking    W24  win_min=1.22s n=6
commits: [('b5d757c9f6',)]
wrote /home/user/Notes/nebulastream/benchmark/2_engine_to_e2e/qex_spanning_2026-10-05/figures/figW_qex_gbps.png/.svg
wrote /home/user/Notes/nebulastream/benchmark/2_engine_to_e2e/qex_spanning_2026-10-05/figures/figW_qex_p99.png/.svg
