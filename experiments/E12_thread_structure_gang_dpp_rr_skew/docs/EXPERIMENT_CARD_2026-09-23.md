# Experiment card: round-robin pinning vs DPP vs gang vs chunker vs thread-per-query, with skewed workloads — 2026-09-23

**Question.** How does per-buffer parse latency behave with N concurrent text-bound queries (1..512) on a fixed core budget for five
thread structures that run the SAME compiled CSV Scan→Emit stage, (a) with identical queries, (b) when 10 % of the queries cost 4× as
much (cost skew), (c) when queries are bursty (20 ms on / 20 ms off, random phase)? New in this run: the **rr arm** (round-robin
pinning = shared-nothing/partitioned SPE: each query pinned to one worker, one queue per worker, per-query sequential stage) and the
two skew knobs; plus the **unthrottled re-run of the Pi column** (the 2026-09-09/10 Pi sweeps ran at 1.0 GHz under a power throttle).

**Arms.** `dpp` (ours: one task per 128 KiB buffer, any pooled worker, lock-free SequenceShredder) | `gprivate k=1` = thread-per-query
| `gprivate k=4` = gang of 4 threads per query | `chunker k=4` (1 cutter thread per query + pool, sequential stages) | `chunker_quote`
(main window only) | `rr` (round-robin pinning).

**Machines / state.** Threadripper PRO 5965WX, taskset 0-23, W=24 pinned workers, governor performance, host build
`cmake-build-release`. Raspberry Pi 5 (4× A76 @ 2.4 GHz, 16 GiB), W=4, governor **ondemand** (holds 2.4 GHz under load), build
`cmake-build-release-piparse` run inside `nebulastream/nes-development:local-piparse` with `--cpuset-cpus 0-3`; pre-flight passed
(5000 mA PSU, `get_throttled` 0x0 before/after load, 2.4 GHz under load, 0 under-voltage msgs); `logs/run_pi.meta` records the throttle
flag, measured ARM clock, temperature and governor before and after EVERY arm (all 0x0 / 2400 MHz / ≤ 68 °C).
Data: `bench_5xUINT64_512m.csv` (5×UINT64 rows), 128 KiB raw buffers, project f1 + fnattr, FastUINT64, 32 KiB output buffers.

**Window (the engine's admission rule).** D=64 buffers in flight per query, global cap 1000 (FIFO admission, latency clock starts at
admission), working-set floor 2048 MiB (`NES_LAT_WS_MIB`, ring grows so every N is in the streaming regime), ring 16, gens 32, 1 s
warm-up, 5 s window, 3 reps, spin 0 at every N and spin 50 µs additionally at N ≤ 32; the plotted value per N is the "design-best"
spin policy (lower median p99). Closed loop: a completed buffer's successor is offered immediately.

**Skew knobs (applied identically to every arm).** `NES_LAT_HEAVY=0.1,4`: one query per block of 10 consecutive ids is heavy (hash-chosen
position; same set in every arm/rep/N); every stage call on a heavy buffer is followed by a CPU burn of 3× that call's own wall time
(the parse runs once). `NES_LAT_BURST=20,20`: each query alternates 20 ms active / 20 ms idle with a hashed phase offset; an idle
completion has no successor (the slot returns to the admission pool); one timer thread re-offers a backlog of D at each burst start,
stamped at the actual offer instant.

**Exact commands** (from `gang_vs_dpp_2026-09-08/fig/`, driver `run_fig.sh`, chains in `rig/`):
```
MACHINE=tr ARMS="rr 1" DW=64 CAP=1000 TAG=ws_rr ./run_fig.sh
MACHINE=tr ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 HEAVY=0.1,4 TAG=ws_heavy ./run_fig.sh
MACHINE=tr ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 BURST=20,20 TAG=ws_burst ./run_fig.sh
MACHINE=pi ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 TAG=ws2 ./run_fig.sh
MACHINE=pi CUT=quote ARMS="chunker 4" DW=64 CAP=1000 TAG=ws2 ./run_fig.sh
MACHINE=pi ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 HEAVY=0.1,4 TAG=ws2_heavy ./run_fig.sh
MACHINE=pi ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 BURST=20,20 TAG=ws2_burst ./run_fig.sh
```
Run 2026-09-23 09:26-11:14 (both machines in parallel; burst sweeps re-run 10:41-11:12 after the seed bug below; 5 gang k=4 spin-50 cells
of the Pi heavy sweep re-run 11:12-11:14 after a gang stall). TR main-window baseline `sweep_tr_ws_D64_C1000.csv` is from 2026-09-10 (unchanged rig code paths for those arms; the rr rows were added in a separate file).

**Raw files (`raw/`)** — CSV columns: arm,k,N,W,spin_us,cap,rep,window_s,buffers,bytes,GBps,bufs_per_s,p50_us,p99_us,p999_us,max_us,
strm_p99_med_us,strm_p99_max_us,cpu_s_per_GB,vcsw,ivcsw,tuple_ratio,repeats,D,pin[,heavy_frac,heavy_mult,burst_active_ms,burst_idle_ms,
light_bufs,heavy_bufs,light_p50_us,light_p99_us,heavy_p50_us,heavy_p99_us,light_strm_p99_max_us,timer_wakes,timer_late_max_ms].
Gates: tuple_ratio == 1.0000 and repeats == 0 in every valid row.

| file | rows | arms | N | notes |
|---|---|---|---|---|
| `sweep_tr_ws_D64_C1000.csv` | 240 | chunker k4, chunker_quote k4, dpp k1, gprivate k1, gprivate k4 | 1..512 | TR main window (2026-09-10) |
| `sweep_tr_ws_rr_D64_C1000.csv` | 48 | rr k1 | 1..512 | TR main window, rr rows |
| `sweep_tr_ws_heavy_D64_C1000.csv` | 240 | 5 arms | 1..512 | TR cost skew |
| `sweep_tr_ws_burst_D64_C1000.csv` | 240 | 5 arms | 1..512 | TR bursts (re-run) |
| `sweep_pi_ws2_D64_C1000.csv` | 288 | 6 arms incl. chunker_quote, rr | 1..512 | Pi main window UNTHROTTLED (supersedes sweep_pi_ws_*) |
| `sweep_pi_ws2_heavy_D64_C1000.csv` | 243 | 5 arms | 1..512 | Pi cost skew (+ re-run gang spin-50 cells, N=1 spin-0 has 6 reps) |
| `sweep_pi_ws2_burst_D64_C1000.csv` | 240 | 5 arms | 1..512 | Pi bursts (re-run) |
| `INVALID_seedbug_sweep_tr_ws_burst_D64_C1000.csv` | 27 | dpp | 1..256 | INVALID: seed/timer double admission, kept for the record |
| `INVALID_seedbug_sweep_pi_ws2_burst_D64_C1000_partial.csv` | 62 | dpp, gprivate k1 | 1..256 | INVALID: same bug (Pi, partial) |

**Headline results** (design-best, N=512; details and per-N tables in `HANDOVER_2026-09-23_RR_SKEW_RESULTS.md`).
- Identical queries: rr = DPP on GB/s and CPU/GB but p99 1.5-2.5× DPP on both machines (partitioned queues → worse tail even without
  N mod W imbalance). Pi unthrottled: gang k=4 5.9× DPP p99, chunker 1.45×, thread-per-query 11.9× (throttled column had 4.3/1.26/8.5×).
- Cost skew: DPP + chunker fair (heavy share 0.10, no bystanders); rr's light queries next to a heavy one: p99 26 ms TR (7.5× DPP's worst
  light query) / 116 ms Pi (2.3×); thread-per-query + gang starve heavy queries into 0.17 s (TR) / 1.6-2.5 s (Pi).
- Bursts: DPP unchanged; rr −15 % GB/s @512, −37 % @16 (TR), p99 3.7× DPP; thread-per-query improves (fewer runnable threads).

**Known issues.** (1) Seed/timer double-admission bug in the first burst runs — fixed in the archived rig, invalid CSVs kept. (2) One
gang k=4 cell (Pi, N=2, spin 50) stalled: a gang member re-executed the previous buffer's chunk (shredder refused the duplicate
sequence number); rare, pre-existing, no bad row written, cells re-run. (3) Timer lateness up to 110-370 ms under thread-per-query/gang
at N ≥ 256 on the Pi (timer thread starves; stamps are actual offer instants, latency unaffected).

**Re-plot.** `figures/` holds the outputs; from `fig/`: `python3 plot_core.py "sweep_tr_ws_D64_C1000.csv+sweep_tr_ws_rr_D64_C1000.csv" sweep_pi_ws2_D64_C1000.csv core_story_ws2`
and `python3 plot_skew.py sweep_tr_ws_heavy_D64_C1000.csv sweep_tr_ws_burst_D64_C1000.csv sweep_pi_ws2_heavy_D64_C1000.csv sweep_pi_ws2_burst_D64_C1000.csv skew_story`.
Rig source: `rig/FormatterLatencyBenchmark_with_rr_skew_2026-09-22.cpp` (= `nes-input-formatters/tests/Benchmark/FormatterLatencyBenchmark.cpp`
on branch benchmark-piparse-lazyparse-fast-csv, UNTRACKED at the time; build target `formatter-latency-benchmark`).
Related archive: Flink Pi N=1000 → `2_engine_to_e2e/pi_flink_n1000_2026-09-22/`.
