# E12 — Thread structure under many concurrent text-bound queries: DPP vs gang vs chunker vs thread-per-query vs round-robin (+ cost skew, bursts)

**Claim in the paper.** Parallelising text parsing *within* a buffer (a gang of k threads per query — the fork/join /
speculative-FSM family — or a per-query cutter thread feeding a pool) and the classic per-query thread structures
(thread-per-query, round-robin pinning / partitioned queues) all lose to DPP (one task per 128 KiB buffer, any pooled
worker, lock-free SequenceShredder) once the number of concurrent queries exceeds the core budget: under the engine's
admission rule (≤ 64 buffers in flight per query, ≤ 1000 in total) DPP's p99 stays flat to N = 512 on both machines
(2.9 ms TR / ~90 ms Pi) at constant CPU/GB, while gang k=4 reaches 7.8× (TR) / 4.3× (Pi) DPP's p99 with 1.6× / 1.3×
the CPU per byte, the chunker plateaus at 2.1–2.6× / 1.3× at −40 % / −22 % throughput, thread-per-query collapses to
13× / 8.5×, and rr matches DPP's throughput but carries a 1.5–2.5× tail. With 10 % of the queries at 4× cost, DPP and the
chunker stay fair (no bystander effect) while rr's light queries next to a heavy one see 7.5× (TR) / 2.3× (Pi) DPP's
worst light query; under 20 ms on/off bursts DPP is unchanged and rr loses 15–37 % throughput.

**Machine.** Threadripper PRO 5965WX (24 cores, `taskset -c 0-23`, W = 24 pinned workers, governor performance, host
build `cmake-build-release`) and Raspberry Pi 5 (4× A76 @ 2.4 GHz, 16 GiB, W = 4, governor ondemand holding 2.4 GHz,
`--cpuset-cpus 0-3` inside `nes-development:local-piparse`, 27 W PSU, `get_throttled` 0x0 before/after every arm —
`logs/run_pi.meta`). Engine source `b5d757c9f6` + the rig (now committed at tag `piparse-artifact-v1`); the Pi rig binary
was rebuilt 2026-09-23 in `cmake-build-release-piparse`. Dates: TR main window 2026-09-10, rr + skew sweeps 2026-09-23
(09:26–11:10); Pi all sweeps 2026-09-23 (09:26–11:14, unthrottled re-run — the 2026-09-09/10 Pi sweeps ran at 1.0 GHz
under a power throttle and are shipped only as `data/superseded/*_THROTTLED.csv`).

**Measured with.** The isolated rig `formatter-latency-benchmark` (`FormatterLatencyBenchmark.cpp`), driven by
`rig/run_fig.sh` with the chains `rig/{tr,pi}_chain_2026-09-23.sh` (+ `*chain2*` = burst re-runs after the seed/timer
fix). Not a pbench experiment; nothing from this element is in the DuckDB. Every CSV row = one (arm, k, N, spin policy, rep)
cell: 3 reps × 5 s windows after 1 s warm-up, closed loop, D = 64 in flight per query, global cap 1000, working-set floor
2048 MiB (`NES_LAT_WS_MIB`), spin 0 at every N plus spin 50 µs at N ≤ 32; the plotted value is the per-N "design-best"
policy (lower median p99). Gates in every valid row: `tuple_ratio == 1.0000`, `repeats == 0`.

## Files

| path | what |
| --- | --- |
| `data/sweep_tr_ws_D64_C1000.csv` (240 rows) + `data/sweep_tr_ws_rr_D64_C1000.csv` (48) | TR main window: chunker k4, chunker_quote k4, dpp k1, gprivate k1 (= thread-per-query), gprivate k4 (= gang); rr k1 in the second file |
| `data/sweep_pi_ws2_D64_C1000.csv` (288) | Pi main window, unthrottled, 6 arms incl. rr and chunker_quote |
| `data/sweep_{tr_ws,pi_ws2}_heavy_D64_C1000.csv` | cost skew `NES_LAT_HEAVY=0.1,4` (10 % of the queries at 4× cost), 5 arms |
| `data/sweep_{tr_ws,pi_ws2}_burst_D64_C1000.csv` | bursts `NES_LAT_BURST=20,20`, 5 arms (re-run after the seed/timer fix) |
| `data/INVALID_seedbug_*.csv` | the first burst runs, INVALID (seed/timer double admission), kept for the record |
| `data/superseded/` | D=1 companion window (`sweep_tr_D1.csv`, `sweep_pi_D1_THROTTLED.csv`, TR trough at N=64–128 not re-run), D=64 uncapped appendix window, the throttled Pi main window, the 2026-09-10 combined CSV (pre-rr) |
| `expected/core_story_ws2.{png,pdf}` | **the paper figure**: 2 cols (TR \| Pi) × 2 rows (p99 latency per buffer, linear, thread-per-query off scale + annotated; CPU time per GB), 6 series |
| `expected/skew_story.{png,pdf}` | **the skew figure**: rows = cost-skew p99 of the worst unaffected query, burst p99, and the two throughputs; cols TR \| Pi |
| `expected/core_story_ws.{png,pdf}` | the 2026-09-10 version of the main figure (5 arms, no rr, throttled Pi column) — superseded |
| `rig/plot_core.py`, `rig/plot_skew.py` | the figure scripts (take the CSVs as arguments) |
| `rig/run_fig.sh`, `rig/*_chain*.sh` | the sweep driver and the exact chains that produced the data |
| `rig/FormatterLatencyBenchmark_with_rr_skew_2026-09-22.cpp` | the rig source snapshot that produced the data (== the committed file at the engine tag, modulo clang-format and `//`→`///` comment style) |
| `rig/gen_formatter_csv.py` | the dataset generator (copy of `scripts/benchmarking/gen_formatter_csv.py` in the engine repo) |
| `rig/merge_sweeps.py`, `rig/summarize_trough.py`, `rig/plot_fig.py` | historic helpers (layered merges of the September partial sweeps; the TR working-set trough probe; the D=1 figure) |
| `rig/SHA256SUMS_archive_2026-09-25` | checksums of the original archive (`results_2026-09-23_rr_skew/`), incl. the console logs not copied here |
| `logs/run_{tr,pi}.meta` | start/finish stamps of every sweep; Pi throttle flag / clock / temperature / governor before and after every arm |
| `docs/EXPERIMENT_CARD_2026-09-23.md` | the experiment card (arms, window, skew knobs, exact commands, raw-file table, known issues) |
| `docs/HANDOVER_2026-09-23_RR_SKEW_RESULTS.md`, `docs/HANDOVER_2026-09-21_GANG_VS_DPP_RESULTS.md` | the results write-ups (per-N tables, findings, what was investigated and ruled out) |
| `docs/DESIGN.md`, `docs/FIGURE_SPEC.md`, `docs/RESULTS_{tr,pi}.md`, `docs/PROBE_RESULTS_2026-09-08.md` | design (fairness model §2b), figure spec incl. the window supersession history, per-machine results of the first (D=1) sweeps, the probe |
| `make_figure.py` | re-plots both figures from `data/` into `out/`; `--check` pixel-compares with `expected/` |

CSV columns: `arm,k,N,W,spin_us,cap,rep,window_s,buffers,bytes,GBps,bufs_per_s,p50_us,p99_us,p999_us,max_us,strm_p99_med_us,
strm_p99_max_us,cpu_s_per_GB,vcsw,ivcsw,tuple_ratio,repeats,D,pin[,heavy_frac,heavy_mult,burst_active_ms,burst_idle_ms,light_bufs,
heavy_bufs,light_p50_us,light_p99_us,heavy_p50_us,heavy_p99_us,light_strm_p99_max_us,timer_wakes,timer_late_max_ms]`.
Arms: `dpp` k1 (ours) · `gprivate` k4 (gang) · `gprivate` k1 (thread-per-query) · `chunker` k4 (cutter thread + pool, sequential
SIMD newline scan) · `chunker_quote` k4 (quote-aware cut) · `rr` k1 (round-robin pinning).

## Reproduce the figures from the shipped data (seconds)

```
python3 make_figure.py --check            # system python3 (matplotlib 3.6.3): both PNGs pixel-identical to expected/
```
With matplotlib 3.11 the curves are identical but tick/label rendering drifts (1 px width, ~7–10 % of pixels), so
`--check` reports DIFFER; pass `--python <interpreter>` to choose.

## Re-measure (~1 h 45 min TR, ~2 h 20 min Pi)

```
./run.sh                                   # prints: build target, data generation, the 9 run_fig.sh invocations, plot
```
Requires the engine host build (`../../env/tr/`), `bench_5xUINT64_512m.csv` generated as shown, and for the Pi column the
Pi dev container + the rig binary built there (`../../env/pi/`, `cmake-build-release-piparse`).

## Caveats / provenance notes

- **Pi column = the 2026-09-23 unthrottled re-run** (`ws2`). The 2026-09-09→22 Pi runs were power-throttled to 1.0 GHz
  (900 mA source; cpufreq kept reporting 2.4 GHz) — ratios changed, not just scale (gang 4.3× → 5.9×, chunker 1.26× → 1.45×,
  thread-per-query 8.5× → 11.9× DPP p99 at N=512). Superseded CSVs are kept under `data/superseded/*_THROTTLED.csv`.
- **Seed/timer double-admission bug** in the first burst runs (streams idle at the seed were admitted twice → FIFO overflow →
  stall): fixed in the shipped rig; both burst sweeps re-run; the invalid CSVs are kept as `data/INVALID_seedbug_*`.
- **OPEN, rare:** gang k=4 (gprivate) at N=2 spin 50 on the Pi once re-executed the previous buffer's chunk (shredder refused the
  duplicate sequence number → drain stall, no bad row written; ~1 in 1500 cells). The 5 lost cells were re-run and appended
  (`sweep_pi_ws2_heavy`: N=1 spin-0 has 6 reps for that reason).
- **Timer lateness** of 110–370 ms under thread-per-query/gang at N ≥ 256 on the Pi (timer thread starves); stamps are the
  actual offer instants, so latency is unaffected — the burst schedule smears.
- **D=1 companion** (`data/superseded/sweep_*_D1*`) still carries the TR working-set trough at N=64–128 (rig artefact fixed
  by `NES_LAT_WS_MIB`, see `docs/RESULTS_tr.md`) and the throttled Pi column; not re-run (user: later, only if it stays in
  the paper). Same for the D=64 uncapped appendix window.
- **Chunker definition:** the cutter runs ONE sequential SIMD newline pass over every byte (`NES_LAT_CUT=scan`); making it
  quote-aware (`quote`, the `chunker_quote` arm) changes almost nothing — the penalty is structural. `memchr`/`index` cuts
  are historic.
- **Fairness:** identical per-byte work (the same compiled SIMDCSV stage on chunks; speculation is free and always correct on
  the quote-free data = the gang's best case); all waits spin-then-futex, no locks; pooled designs get every core (no
  producer thread in the closed loop); CPU-seconds per GB priced via getrusage.
- `rr` at N ≡ 0 mod W has no imbalance at all, yet keeps the 1.5–2.5× tail: partitioned per-worker queues fluctuate under
  the global cap — the tail is a property of partitioning, not of N mod W.
- Naming in the paper is still open (chunk-parallel vs buffer-parallel; "cutter" for the chunker arm) — see the 09-21 handover §7.
