# Handover 2026-09-23: round-robin pinning arm + skewed workloads (cost skew, bursts), unthrottled Pi column, Flink N=1000

Written 2026-09-23 ~11:20 real. Supersedes the open items of `HANDOVER_2026-09-22_FLINK_N1000_RR_ARM_PI_THROTTLE.md` (§1 Flink done,
§2 rr swept with both skews, §3 Pi column re-run) and extends `HANDOVER_2026-09-21_GANG_VS_DPP_RESULTS.md`.
Everything lives in `1_isolated_to_engine/gang_vs_dpp_2026-09-08/fig/` unless stated. User decisions 2026-09-22: both skews; no Flink
N=500 re-run; Pi governor stays `ondemand` (holds 2.4 GHz under load; `performance` needs sudo); D=1 companion deferred.

## 0. Status
- **Flink N=1000 on the Pi: DONE** (73.5 MB/s, p50 3.56 s, p99 13.46 s, p999 17.56 s, 13.9 h, 0 heartbeat timeouts, page cache
  clean). Results + logs: `2_engine_to_e2e/pi_flink_n1000_2026-09-22/` (RESULT.md, flink_scaling.csv N=1..1000).
- **rr arm (round-robin pinning) swept on both machines** in the main window, plus **two skews on all five arms** (dpp, thread-per-
  query = gprivate k=1, gang k=4, chunker k=4, rr): cost skew `NES_LAT_HEAVY=0.1,4` and bursts `NES_LAT_BURST=20,20`.
- **Pi column re-run unthrottled** (`sweep_pi_ws2_D64_C1000.csv`, 6 arms incl. chunker_quote) → the Sep 9-10 Pi CSVs are SUPERSEDED.
- Figures: `core_story_ws2.{png,pdf}` (main, rr added) and `skew_story.{png,pdf}` (4×2 skew figure). Scripts `plot_core.py`
  (takes '+'-joined CSV lists per machine), `plot_skew.py`.
- All CSVs gate-clean (tuples/row 1.0000, 0 repeats) except the two aborted cells described in §5.

## 1. Data files (engine-admission window D=64, cap 1000, WS=2048 MiB, 3 reps × 5 s, spin 50 added at N ≤ 32, design-best = lower p99)
| file | content |
|---|---|
| `sweep_tr_ws_D64_C1000.csv` | TR main window, 5 arms (2026-09-10, unchanged) |
| `sweep_tr_ws_rr_D64_C1000.csv` | TR rr rows for the main window (48 rows) |
| `sweep_tr_ws_heavy_D64_C1000.csv` | TR cost skew, 5 arms (240 rows) |
| `sweep_tr_ws_burst_D64_C1000.csv` | TR bursts, 5 arms (240 rows; re-run after the seed bug, first run kept as `INVALID_seedbug_*`) |
| `sweep_pi_ws2_D64_C1000.csv` | Pi main window UNTHROTTLED, 6 arms (chunker_quote appended; 288 rows) |
| `sweep_pi_ws2_heavy_D64_C1000.csv` | Pi cost skew, 5 arms (225 + 15 gang k=4 spin-50 rows appended 11:1x) |
| `sweep_pi_ws2_burst_D64_C1000.csv` | Pi bursts, 5 arms (240 rows) |
| `logs/{tr,pi}_chain_2026-09-23.log`, `logs/{tr,pi}_<tag>_<arm>_k<k>_spin<s>.txt`, `logs/run_pi.meta` (throttle/clock per arm) | run logs |

## 2. Results — main window with identical queries (rr added)
TR (N=512): DPP 46.5 GB/s / p99 2.92 ms; rr 47.6 / 6.77 (worst stream 19.6); rr = DPP on throughput and CPU (0.50 s/GB) but p99
1.5-2.3× DPP at N ≥ 32 — more than the N mod W imbalance (5 %) predicts: **partitioned queues have a worse tail than one shared
queue** (per-worker queue lengths fluctuate under the 1000-buffer cap). Below W: one core per query (3.8 ms floor).
Pi unthrottled (N=512): DPP 3.20 GB/s / 41.7 ms; gang k=4 1.77 / 245 (5.9× DPP); chunker 2.22 / 60.4 (1.45×); tpq 2.68 / 497
(11.9×); rr 3.21 / 103 (2.5×, with N ≡ 0 mod 4 → no imbalance at all). vs the throttled column: DPP/chunker ×2.2 faster, gang only
×1.4-1.6 → ratios CHANGED (gang was 4.3×, chunker 1.26×, tpq 8.5×): the re-run was necessary, not a rescale.

## 3. Results — cost skew (10 % of the queries at 4× cost; light = the other 90 %)
| N=512 | TR GB/s | TR light p99 | TR worst-light-stream p99 | TR heavy share | Pi GB/s | Pi worst-light p99 | Pi heavy p99 |
|---|---|---|---|---|---|---|---|
| DPP | 37.8 | 3.56 ms | 3.57 ms | 0.099 | 2.69 | 49.8 ms | 50 ms |
| rr | 35.0 | 26.3 | 26.7 | 0.097 | 2.49 | 116 | 113 |
| thread-per-query | 32.3 | 33.1 | 75.6 | 0.091 | 2.34 | 144 | 1587 |
| gang k=4 | 22.4 | 6.1 | 20.7 | 0.078 | 1.67 | 300 | 2467 |
| chunker k=4 | 22.0 | 6.76 | 7.26 | 0.100 | 1.87 | 72 | 71 |
DPP and the chunker are FAIR (heavy share = nominal 0.10, light == heavy latency, no bystanders). rr: light p50 0.3 ms but the light
queries pinned next to a heavy one see p99 26 ms = **7.5× DPP's worst light query** (4.5× at N=32; Pi 2.3×). tpq/gang: light queries
fast, heavy ones starved into 0.17 s (TR) / 1.6-2.5 s (Pi) tails via scheduler slicing.

## 4. Results — bursts (20 ms on / 20 ms off, random phase per query, backlog D at each burst start)
TR N=512: DPP 48.3 GB/s / 2.80 ms (unchanged); rr 40.4 (−15 %; −37 % at N=16) / 10.5 ms = 3.7× DPP; tpq 47.1 / 13.5 (IMPROVES:
fewer runnable threads); gang 29.4 / 17.3; chunker 27.8 / 7.6 (worst stream 14 ms). Pi N=512: DPP 3.29 / 41.4; rr 3.22 / 109
(−21 % GB/s at N=4); gang 1.77 / 391; tpq 3.21 / 242; chunker 2.43 / 59. Note: with D=64 backlog the total demand still exceeds
capacity, so DPP stays saturated; the arm differences come from imbalance, not idle capacity. Timer late max ≤ 6 ms in the window
except under tpq/gang at N ≥ 256 on the Pi (110-370 ms: the timer thread starves under 512-2048 threads; stamps are actual offer
instants, so latency is unaffected, the schedule smears).

## 5. Rig changes and bugs (rig = `nes-input-formatters/tests/Benchmark/FormatterLatencyBenchmark.cpp`, UNTRACKED; snapshot
`rig_snapshots/FormatterLatencyBenchmark_with_rr_skew_2026-09-22.cpp` = final)
- `NES_LAT_HEAVY=<frac>,<mult>`: stratified heavy set (one per block of round(1/frac) ids, hash-chosen position; same set in every arm),
  heavy = per-call CPU burn of (mult−1)× the stage call's own wall time (parse runs once). Columns heavy_frac, heavy_mult, light_/heavy_
  bufs/p50/p99, light_strm_p99_max_us.
- `NES_LAT_BURST=<active_ms>,<idle_ms>`: per-stream periodic phase with hashed offset; idle completion → stream sleeps, slot returned
  (explicit `freeSlots` pool + lost-wakeup guards); one timer thread re-offers D − (inFlight + queued) at each burst start, stamped at the
  actual offer instant. Columns burst_active_ms, burst_idle_ms, timer_wakes, timer_late_max_ms (window only).
- **BUG (mine, fixed):** the timer ran during the seed (100 ms stagger > 40 ms period) → streams idle at the seed were admitted twice
  (up to 2D) → admission FIFO overflow → deadlock (Pi N=64 stall, TR N=512 silent hang in the seed). Fix: seed first (only while
  inFlight+queued < D), timer starts after the seed, FIFO N·D+2W+64. Both burst sweeps re-run; invalid CSVs kept as `INVALID_seedbug_*`.
- **OPEN (pre-existing, rare):** gang k=4 (gprivate) at N=2 spin 50 on the Pi: a member re-executed the previous buffer's chunk (shredder
  refused the duplicate seq forever → drain stall, no bad row). 1 in ~1500 cells. If it recurs: bound `runStage`'s in-place retry and dump
  member slot vs leader curSlot. The 5 missing cells were re-run (appended).
- `run_fig.sh`: `HEAVY=`/`BURST=` pass-through, TAG + cut method in log names, `pistate` logs throttle flag/clock/temp/governor before and
  after every Pi arm into the log and `logs/run_pi.meta`. Pi driver takes the stream list via `PI_STREAMS`.
- Pi rig binary rebuilt 2026-09-23 (`cmake-build-release-piparse`, 35 s incremental; recipe in memory `raspberry-pi5-benchmark-box`).

## 6. Open items
1. Paper text: replace every Pi absolute number with the unthrottled column (§2); decide whether rr goes into the main figure (it is in
   `core_story_ws2`) and whether the skew figure is a main or appendix figure.
2. D=1 companion: not re-run on the Pi (user: later). If kept in the paper it needs the unthrottled re-run (`DW=1 CAP=0 TAG=...`).
3. Still open from before: DuckDB/Arrow anchor, caption, arm naming (chunk-parallel vs buffer-parallel), commit of the rig + pbench
   Flink patch (renderer.py / runners/flink.py, uncommitted on host + Pi).
4. Gang duplicate-execution race (§5) — diagnose if it recurs.
