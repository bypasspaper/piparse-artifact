<!-- SPDX-License-Identifier: Apache-2.0 -->
# Pi 5 NES-naive scaling ladder, re-run at W=3 — DONE (2026-10-02 → 2026-10-03 real time)

Pi clock (≈6 days behind real time): launched 2026-09-26 13:42:57, finished 2026-09-27 08:46:19, 19 h 03 min wall.
Experiments `pi_naive_scaling_w3_{a,b,c,d}` (74 rows), run on `pi-box`, commit `8217cce465`,
worker binary of 2026-08-23 (unchanged since the August ladders). Memory: `pi-naive-w3-rerun`.

## Why
The August naive ladder (`pi_naive_scaling_{a,b,c,d}`, 2026-08-27..29, export `naive_scaling.csv`) gave the
naive engine ONE worker thread while the bypass ladder (`pi_scaling_file_*`) had W3+io1. Mechanism, verified in
`nes-query-engine/RunningSource.cpp` (the `SourceReturnType::Execute` handler): in sequential threading mode the
blocking source thread runs the uncompiled input formatter inline and hands the formatted buffers to the admission
queue, so the `JSONUncompiled` stringstream OUTPUT stage and the sink execute on the WORKER POOL. W1 therefore
funnelled every stream's serialisation — the dominant naive cost (~3.5× the parse) — through one core. The
reference box had already given its naive many-source arm the optimised arm's worker budget (W16) on 2026-09-01
(`nes_naive_native_scaling_step20.yaml`); the Pi ladder predated that and was never redone. User decision
2026-10-02: re-run at W3 = the bypass arm's worker budget. The original YAML's argument against W3 ("W1 is the
baseline's definition") is kept verbatim inside the new files as superseded.

## Configuration (verbatim the W1 ladder except the worker count)
BlockingFile source (one OS thread per stream), `SequentialUncompiledOldCSV` with `threading_mode: sequential`
(interpreted scalar-find indexer, parse on the source thread), `JSONUncompiled` output, empty input/output parser
maps, `NES_INPUT_CODEC=original` (std::stod) + `NES_OUTPUT_CODEC=original` (per-tuple std::string +
std::stringstream), `NES_MMAP_POPULATE=1`, 128 KiB operator buffers, 16384-buffer pool, fnattr, pin/CCX off,
Monitoring sink, repeat 1, warm_read. **`number_of_worker_threads: 3`, `number_of_io_threads: 1`** (the blocking
path never uses the io pool; io1 is inert and kept so the worker block is identical to `pi_scaling_file_*`).
Ladder identical to all five Pi curves: N = 1..20 ×3 reps, 25/50/100/250 ×3, 500 ×1, 1000 ×1; the frozen
10-query stateless PAPER_WORKLOAD as a heterogeneous round-robin mix over `bid_strings_3GB.csv` (3429 MB).
Timeouts 1800 / 10800 / 21600 / 108000 s (a/b/c/d).

## Machine state (matches the August ladders)
Fresh reboot; stock 27 W PD supply (`max_current` 0x1388 = 5000 mA); `vcgencmd get_throttled` 0x0 at every part
boundary and in all 6225 sampler rows of the N=1000 window; 2.40 GHz under 4-core load; EXT5V 5.10–5.11 V; 0
undervoltage messages; governor `performance` on all four cores (set via sudo before launch — it resets to
`ondemand` on reboot); max temperature 71.9 °C. Snapshots: `naive_w3_continuity.log`; 5 s sampler
(`naive_w3_scale.tsv`: avail/buff-cache MB, worker RSS, threads, fds, runnable, temp, throttle).

## Results — W1 (August) vs W3 (this run), medians over reps
Throughput = `throughput_mbps` (aggregate csv input bytes / cross-query wall span). Latency = per-128 KiB-buffer
ingest→sink (MonitoringSink), median across queries of each query's percentile. Full table:
`naive_w1_vs_w3.csv`; raw rows: `naive_scaling_w3.csv` (W3) and `naive_scaling.csv` (W1).

| N | reps | W1 MB/s | W3 MB/s | W3/W1 | p99 ms W1 | p99 ms W3 | secs W1 | secs W3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 3 | 71.7 | 180.1 | 2.51 | 62.8 | 27.3 | 50 | 20 |
| 2 | 3 | 109.8 | 250.1 | 2.28 | 99.3 | 37.7 | 65 | 29 |
| 4 | 3 | 130.8 | 281.2 | 2.15 | 179.5 | 68.5 | 110 | 51 |
| 6 | 3 | 184.3 | 355.2 | 1.93 | 202.7 | 80.9 | 117 | 61 |
| 8 | 3 | 183.6 | 347.5 | 1.89 | 293.5 | 109.9 | 156 | 82 |
| 10 | 3 | 185.7 | 347.2 | 1.87 | 372.7 | 136.8 | 193 | 103 |
| 16 | 3 | 187.5 | 341.2 | 1.82 | 619.7 | 223.2 | 304 | 167 |
| 20 | 3 | 184.7 | 342.2 | 1.85 | 810.0 | 287.3 | 386 | 208 |
| 25 | 3 | 178.2 | 318.6 | 1.79 | 1053.2 | 387.2 | 499 | 278 |
| 50 | 3 | 168.2 | 307.4 | 1.83 | 1003.9 | 621.8 | 1053 | 576 |
| 100 | 3 | 161.9 | 284.8 | 1.76 | 1252.8 | 798.2 | 2175 | 1242 |
| 250 | 3 | 135.0 | 222.9 | 1.65 | 2214.7 | 1411.1 | 6515 | 3959 |
| 500 | 1 | 88.1 | 168.5 | 1.91 | 5181.2 | 2823.7 | 20213 | 10467 |
| 1000 | 1 | 48.3 | 111.4 | 2.31 | 16240.4 | 7385.6 | 73397 | 31571 |

N=1000 W3 detail: run_id `61059270-0141-4575-a00f-edad61ce0982`, 111.39 MB/s, 31 571 s (8.77 h) processing,
p50 1.90 s / p99 7.39 s / p999 10.67 s / max 28.4 s. (Bypass ladder for scale: ~1300 MB/s flat from N=25 to 1000.)

## Findings
1. **N=1 gains 2.5× from the worker count alone** (71.7 → 180.1 MB/s on q0 = SELECT *): with one stream, three
   workers serialise its buffers concurrently where one worker was the ceiling. The W1 ladder's N=1 point was a
   serialisation bottleneck, not the naive parser. This N=1 point is the same configuration as the per-query
   tier's q0 (`pi_naive_stateless`, 71.1 MB/s) → the per-query naive tiers have the same handicap (see NEXT).
2. **The plateau moves from ~185 to ~340 MB/s (×1.85, N=6..20)** = the four-core box saturating on parse +
   stringstream serialisation instead of on a single output worker. The real naive ceiling on the Pi is ~340 MB/s
   vs the bypass's ~1300 → naive/bypass gap at the plateau is ~3.8× (W1 ladder said ~7×).
3. **The decline with N is real, not a W1 artefact** — thread-per-source oversubscription: 319 / 307 / 285 / 223 /
   168.5 / 111 MB/s at 25 / 50 / 100 / 250 / 500 / 1000. The gain narrows slowly to 1.65× at N=250 and widens
   again at 500/1000 (1.9×, 2.3×) where W1's single worker was most starved. At N=1000: naive 111 vs bypass 1303
   = 11.7× (was 27× on the W1 ladder).
4. **Tail latency roughly halves everywhere** (p99 27 ms vs 63 ms at N=1; 7.4 s vs 16.2 s at N=1000) — the
   serialisation queue in front of the one worker was most of the W1 tail.
5. Wall time 19.1 h vs ~36 h for the W1 ladder (a 2.0 h, b 5.1 h, c 3.0 h, d 9.0 h).

## Caveats (say these when quoting)
- **N=1000 is NOT a clean page-cache point, same as the W1 run:** worker RSS grew to 13.7 GB (1017 threads) and
  pushed the 3429 MB csv out of the cache — min buff/cache 1830 MB, 72 % of the 6225 samples below the file size.
  The read rate never moved (101 → 111 MB/s across the run; NVMe ceiling ~888 MB/s), so disk is not the binding
  limit, but the point mixes cache and NVMe reads. N ≤ 500 were fully resident (warm_read 3429 → 3429 MB).
- Governor `performance` (as in August); io1 inert; Pi clock ≈6 d behind real time in every timestamp.
- NES p99 is the median across queries of per-query p99 (sink emits percentiles only); Flink/Spark pool raw
  samples — see the 2026-10-02 latency-method check in the session notes (not a W1/W3 issue).

## Files (this directory)
`naive_scaling_w3.csv` (74 raw rows, the plot-ready curve), `naive_scaling.csv` (W1, 74 rows, reference),
`naive_w1_vs_w3.csv` (the table above incl. p50/p999), `pi_naive_scaling_w3_{a,b,c,d}.yaml` (with the W3
rationale paragraph), `run_naive_w3.sh` + `naive_w3_sampler.sh` (runner/sampler), `naive_w3_run.log` (pbench
stdout of all four parts), `naive_w3_continuity.log` (per-part throttle/clock/temp/governor/memavail snapshots),
`naive_w3_scale.tsv` (5 s sampler), `pi_dump.py` (the Pi export script with the new `naive_scaling_w3.csv` job).
On the Pi: `~/powertest/export/naive_scaling_w3.csv`, duckdb `runs` under the `pi_naive_scaling_w3_*` names,
`~/powertest/dump.py.bak_pre_naive_w3` (export script backup).

## NEXT (user decision 2026-10-03) — resolved the same day, see the addendum below
- ~~Retake the naive PER-QUERY tiers on BOTH boxes~~ → DONE for the Pi (addendum); the Threadripper tiers ALREADY
  ran at W23 (the series override to 1 was dead: pbench applies the x-axis value last — `runs.config` is the truth).
- Regenerate the Pi scaling figure with both naive lines (W1 reference + W3 fair curve) from the exported CSVs, and
  the per-query figure/table from `naive_tier_w3.csv`.

---

# Addendum: Pi naive PER-QUERY tiers retaken at W=3 — DONE (2026-10-03 real; Pi clock 2026-09-27 09:29 → 10:10)

`pi_naive_stateless_w3` (10 queries × 10 reps) + `pi_naive_stateful_w3` (3 × 10), 41 min wall, exit 0 both tiers,
throttled=0x0 throughout, governor performance, max 65 °C. Verbatim copies of `pi_naive_{stateless,stateful}.yaml`
with `number_of_worker_threads` 1 → 3 (defaults AND the x-axis value), same binary/commit (`8217cce465`,
2026-08-23) as the W1 tiers → directly comparable. Runner `run_naive_tier_w3.sh`; logs `naive_tier_w3_run.log`,
`naive_tier_w3_continuity.log`, sampler `naive_tier_w3_scale.tsv`. Raw rows `naive_tier_w3.csv` (130), W1 reference
`naive_tier_w1.csv` (130), comparison `naive_tier_w1_vs_w3.csv` (also vs the optimized `pi_stateless_tier` /
`pi_stateful_tier`).

**Threadripper needs NO retake:** `runs.config` for `naive_corrected_{stateless,stateful}` and
`naive_corrected_regen_tip` shows `number_of_worker_threads: 23` — pbench applies the x-axis value AFTER the series
override (expander.py: `_set_nested(point_config, x_param, value)` last), so the override to 1 never took effect.

| query | naive W1 MB/s | naive W3 MB/s | W3/W1 | optimized MB/s | opt/naive W1 | opt/naive W3 | p99 ms W1 | p99 ms W3 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| q0 SELECT * | 71.1 | 180.4 | 2.54 | 1274.0 | 17.9 | 7.1 | 60.1 | 24.3 |
| q_project | 241.9 | 238.9 | 0.99 | 3945.6 | 16.3 | 16.5 | 16.9 | 1.1 |
| q_route | 239.1 | 238.5 | 1.00 | 3259.5 | 13.6 | 13.7 | 1.0 | 1.0 |
| q1 price×0.908 | 114.5 | 231.0 | 2.02 | 1637.2 | 14.3 | 7.1 | 37.3 | 1.9 |
| q2_og 5-way OR | 239.5 | 240.9 | 1.01 | 3714.3 | 15.5 | 15.4 | 0.7 | 0.7 |
| q2_mod | 241.4 | 241.9 | 1.00 | 4675.5 | 19.4 | 19.3 | 0.7 | 0.7 |
| q10 ts cast | 101.5 | 225.0 | 2.22 | 1368.5 | 13.5 | 6.1 | 42.4 | 2.1 |
| q14 | 239.1 | 238.1 | 1.00 | 2434.0 | 10.2 | 10.2 | 0.9 | 0.9 |
| q22 CONCAT | 103.3 | 226.4 | 2.19 | 1416.2 | 13.7 | 6.3 | 41.5 | 2.1 |
| q_ex | 241.4 | 242.0 | 1.00 | 5129.2 | 21.2 | 21.2 | 0.6 | 0.6 |
| ysb_1k_varsized | 306.0 | 304.5 | 0.99 | 4631.1 | 15.1 | 15.2 | 2.1 | 2.3 |
| q8_join | 33.0 | 65.9 | 1.99 | 78.7 | 2.4 | 1.2 | 11.3 | 2.5 |
| cm_q2 | 82.6 | 86.7 | 1.05 | 351.9 | 4.3 | 4.1 | 38.6 | 3.3 |

**Findings.** (1) Two regimes, cleanly split: the four OUTPUT-heavy stateless queries (q0, q1, q10, q22 — full rows,
computed float, timestamp cast, CONCAT) gain 2.0–2.5× and the six light-output ones do not move (0.99–1.01) — at W1
the stringstream output stage on the single worker was their bottleneck; at W3 every stateless query sits at the
source thread's interpreted parse ceiling, ~225–242 MB/s. (2) The optimized/naive ratio therefore drops from
13.5–17.9× to 6.1–7.1× on those four queries and stays 10–21× on the rest. (3) Stateful: ysb is input-bound (flat);
q8_join doubles (33 → 66 MB/s) and lands within 1.2× of the optimized arm (78.7) — join/state-bound, parsing is not
the cost; cm_q2 +5 % (82.6 → 86.7 vs 351.9). (4) Tail latency collapses on the formerly output-bound queries
(q1 37 → 1.9 ms, q10 42 → 2.1, q22 41.5 → 2.1, cm_q2 38.6 → 3.3, q8 11.3 → 2.5; q0 60 → 24): the W1 p99 was the
serialisation queue in front of one worker. (5) W1 reps show one slow outlier per query (min ~210 vs median ~240 MB/s)
in both runs — unchanged, cosmetic.

---

# Addendum 2: in-flight window probe — the naive arm's low-N latency is `default_max_inflight_buffers` (DONE 2026-10-03)

**Question (user):** on the Pi ladder naive-NES p99 sits ABOVE Flink up to N≈100 and crosses below it by N=250 — is the
fixed worker pool (serialisation + sink) the cause? **Take:** the pool sets the slope (residence = backlog / pool
throughput), but the low-N deficit is the per-source in-flight WINDOW in front of the slower serialisation stage:
p50 × drain rate = 4.3 MB at both W1 (59.5 ms × 72 MB/s) and W3 (24.3 ms × 180 MB/s); naive p50≈p99 at N=1 (steady
backlog, not jitter); Flink's fetcher queue is 1–2 batches deep → 7 ms, same as the bypass (whose queue stays empty).
The crossover is Flink's thread-per-pipeline + GC tail (p99/p50 1.4 → 3.8 with N) vs the naive FIFO pool's fair
backlog (p99/p50 1.1–1.6 to N=100).

**Probe** `pi_naive_inflight_probe` (Pi clock 2026-09-27 11:18 → 11:55, 27/27, 0x0, performance): the W3 naive arm,
N ∈ {1, 4, 16}, `worker.default_max_inflight_buffers` ∈ {4, 16, 64 (= default, same-session control)}, 3 reps.
Files: `pi_naive_inflight_probe.yaml`, `naive_inflight_probe.csv` (27 raw rows), `inflight_probe_run.log`,
`inflight_probe_continuity.log`, `run_inflight_probe.sh`.

| N | cap | MB/s | p50 ms | p99 ms | Flink p50 / p99 ms |
| --- | --- | --- | --- | --- | --- |
| 1 | 64 | 179.8 | 24.4 | 26.5 | 7.2 / 10.1 |
| 1 | 16 | 169.6 | 7.3 | 8.3 | |
| 1 | 4 | 152.7 | 3.1 | 3.4 | |
| 4 | 64 | 281.2 | 57.7 | 68.0 | 8.1 / 23.7 |
| 4 | 16 | 283.5 | 13.8 | 21.3 | |
| 4 | 4 | 281.2 | 3.6 | 7.1 | |
| 16 | 64 | 344.6 | 190.5 | 221.6 | 31.4 / 103.5 |
| 16 | 16 | 347.8 | 45.0 | 67.4 | |
| 16 | 4 | 341.9 | 11.7 | 15.8 | |

**Findings.** (1) Latency is proportional to the cap: at N=16 p50 190.5 / 45.0 / 11.7 ms for caps 64 / 16 / 4 =
16.3 : 3.8 : 1 (cap ratio 16 : 4 : 1); at N=1 a ~2–3 ms pipeline service floor adds to the window. (2) Throughput is
UNCHANGED at N ≥ 4 (±1 %); at N=1 cap 4 costs 15 % and cap 16 costs 6 % (one source cannot keep three serialisers
fed with 4 buffers in flight). (3) With cap 4 the naive arm is BELOW Flink at every probed N (p99 3.4 vs 10.1 at N=1,
7.1 vs 23.7 at N=4, 15.8 vs 103.5 at N=16); with cap 16 it is at Flink parity at N=1 (p50 7.3 vs 7.2). (4) The
cap-64 control reproduces the ladder points (24.4/57.7/190.5 vs 24.3/57.9/192.3 ms) — same-session, no drift.
⇒ the "naive above Flink up to N≈100" region is entirely the 64-buffer in-flight window, a throughput-oriented
buffering default, not an engine property; the fixed pool only sets the slope. Decision for the paper: either keep
the default and say so, or pick one cap for ALL NES arms (16 keeps throughput within 1–6 % and gives Flink parity at
N=1) and re-run the latency curves — the bypass arm runs the same 64 default (its p50 is sub-ms because its workers
outrun its single io thread, so its window is normally empty; its 100–270 ms p99 tail at N ≥ 16 is a separate question).
