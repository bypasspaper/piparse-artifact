<!-- SPDX-License-Identifier: Apache-2.0 -->
# q_ex on spanning tuples — figW repeated with the figQ query (2026-10-05)

**Question (user):** can the spanning-tuple worker sweep (figW: `SELECT id` on `(id, 12 KB string)` rows, 4 KiB raw
buffers, LOCK_FREE vs LOCKING shredder) be repeated with the **q_ex** query (figQ, the HOSP working example) so the two
figures tie together? Expectation: very similar results.

**Answer: yes, and the curves overlay to within 2 % at every worker count on both shredder arms.** Same binary, same
session, 192 runs, 0 failed, 13.5 min. The spanning result is a property of the row/buffer geometry (rows spanning
~3 raw buffers), not of the query: both queries touch only the first ~40 B of a 12 KB row, never materialise the
string, run a single pipeline and emit ~0 output, so the shredder sees identical buffer and span rates.

## Design
- **Data** `nes-systests/testdata/large/formatter/bidstr_url12k_500m.csv` (gitignored, symlinked into
  `cmake-build-release/…/large/formatter/`): the first **43,546 rows of `bid_strings_3GB.csv`** with the `url` field
  padded with `x` to 12,000 chars → 524,279,918 B, **12,039.7 B/row = 2.94 raw buffers @4 KiB** (figW:
  `bigstr_id_12k_500m.csv`, 12,003 B/row, 2.93). Generator `scripts/gen_bidstr_url12k.py` (0.4 s).
- **Query** `queries/formatter/bidstr_qex_12k.yaml`: the **literal figQ SQL** (`matrix/bidstr_qex`), 6-field bid
  schema. The slice holds auctionIds 1000–3855 → the predicate (885300/213300 ∧ google ∧ price<1e6) matches **0 rows**
  (figQ: 220 of 31.3 M); the hot path is the filter either way: `channel` compared on every row, `auctionId` parsed on
  the 20 % google rows, `price` never. Output ≈ 0 in both experiments.
- **Rig** = figW verbatim (`experiments/shredder_worker_probe_qex.yaml`): worker-cli, InMemory prefill
  (`NES_INMEM_BUFSIZE=4096`, `NES_INMEM_REPEAT=8`, generator.repeat 8), `NES_SOURCE_EMIT_BATCH=32`, admission 32768,
  **in-flight 8192 (deep queue)**, 128 KiB operator buffers, pool 8192, fnattr + inline, pin/ccx off, io 1, Monitoring
  sink, W ∈ {1,2,4,8,12,16,20,24}, reps 6, median. Two variants × two series:
  - `qex_12k_span3`: q_ex + **figQ's parser block** (Eisel float, FastINT32, Traced ints) + **JSON out + ZMIJ** = the
    figQ optimised arm on spanning data;
  - `selid_12k_span3`: `formatter/bigstr_id_pass_12k`, CSV out = figW re-taken on the same binary.
  - series `lock_free` / `locking` = `sequence_shredder_mode`.
- **Binary** Threadripper `cmake-build-release` worker of 2026-09-03 10:50, `b5d757c9f6` + uncommitted overlay (the figQ
  binary). figW itself (2026-08-31, run_group `20260831T173338-1b014b79`) ran on an older build of the same commit.
- **Run** `run_group 20261005T170750-d5bb1e82`, 17:07:50 → 17:21, 192/192, log `logs/shredder_worker_probe_qex_2026-10-05.log`.
  Smoke (2 runs, `20261005T170729-cc631552`, `logs/smoke_*.log`): task queue 100 % fast-path at depth ~8050 (worker-bound),
  1,372,360 shredder calls for 1,024,000 raw buffers, window 1.01 s @W24.

## Throughput (e2e, GB/s input, median of 6)
| W | q_ex LF | q_ex LK | **q_ex LF/LK** | SELECT id LF | SELECT id LK | **SELECT id LF/LK** | q_ex/selid LF | q_ex/selid LK | figW Aug-31 LF/LK |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1.28 | 1.30 | 0.99 | 1.29 | 1.32 | 0.98 | 0.99 | 0.99 | 0.97 |
| 2 | 1.40 | 1.38 | 1.01 | 1.41 | 1.37 | 1.03 | 1.00 | 1.01 | 1.02 |
| 4 | 2.11 | 1.89 | 1.11 | 2.15 | 1.90 | 1.13 | 0.98 | 1.00 | 1.14 |
| 8 | 3.27 | 2.68 | 1.22 | 3.28 | 2.67 | 1.23 | 1.00 | 1.01 | 1.27 |
| 12 | 3.93 | 3.15 | 1.25 | 3.93 | 3.16 | 1.24 | 1.00 | 1.00 | 1.30 |
| 16 | 4.31 | 3.38 | 1.28 | 4.33 | 3.39 | 1.28 | 1.00 | 1.00 | 1.34 |
| 20 | 4.43 | 3.46 | 1.28 | 4.42 | 3.46 | 1.28 | 1.00 | 1.00 | 1.35 |
| 24 | 4.44 | 3.41 | **1.30** | 4.43 | 3.41 | **1.30** | 1.00 | 1.00 | 1.37 |

Rep spread (max−min)/median: W8 0.9–2.2 % (one selid-LK outlier run → 11 %), W24 1.4–3.5 % (one q_ex-LF low run → 8.3 %),
W1 5–9 % (3 s windows, prefill ramp). Windows: LF 0.93 s @W≥16, LK 1.2 s, W1 3.1–3.2 s. Full tidy data
`data/qex_span_medians.csv`, tables `data/tables.md`.

## Latency (e2e ingest→sink, ms, median of reps)
| W | q_ex LF p50 | q_ex LK p50 | q_ex LF p99 | q_ex LK p99 | selid LF p50 | selid LK p50 | selid LF p99 | selid LK p99 |
|---|---|---|---|---|---|---|---|---|
| 8 | 10.00 | 12.22 | 14.87 | 17.41 | 9.97 | 12.32 | 14.69 | 16.99 |
| 16 | 5.41 | 9.68 | 11.62 | 15.01 | 7.09 | 9.62 | 11.61 | 14.73 |
| 20 | 0.60 | 9.45 | 9.89 | 15.31 | 0.15 | 9.44 | 10.30 | 15.35 |
| 24 | **0.04** | **9.59** | 10.17 | 16.41 | **0.04** | **9.57** | 10.10 | 16.27 |

Same shape as figW: LOCKING p50 ≈ 9.5 ms at W ≥ 16 (mutex convoy; median ≈ tail), LOCK-FREE p50 is the known knife-edge
bimodal (5–7 ms @16 → 0.15–0.6 @20 → 40 µs @24); **p99 LK/LF 1.61× @W24 for both queries**. Absolute ms are inflated by the
deep queue (in-flight 8192, Little's law) — the LF/LK contrast is the robust signal.

## Findings
1. **The query does not matter for the spanning figure.** q_ex / SELECT id = 0.98–1.00 at every W for both arms —
   inside rep noise. Cost per row is SIMD indexing of 12 KB + shredding ~3 spans + per-task machinery; the
   filter (one VARSIZED compare + an INT32 parse on 20 % of rows) is invisible against that.
2. **Same-binary LF/LK = 1.30× @W24** (1.28 @16–20, 1.22 @8, 1.11 @4, ~1.0 @1–2). The published figW ratio is 1.37×:
   on the Sep-3 binary the LOCKING arm is **+6 %** (3.41 vs 3.21 GB/s) while LOCK-FREE is +1 % (4.44 vs 4.39). That is
   binary drift between the Aug-31 and Sep-3 builds of `b5d757c9f6` (uncommitted overlay rebuilt), not investigated.
   If figW is re-plotted on the current binary, state **1.30×**; the `selid_12k_span3` cells of this run are that re-take.
3. **Tie to figQ (same query, two buffer regimes):** at 128 KiB MmapFile (figQ, 115 B rows → ~1,140 rows/buffer, one
   shredder call per buffer) q_ex shows LF/LK 0.99–1.08 — the shredder is off the critical path. On 12 KB rows at 4 KiB
   raw buffers (every row spans ~3 buffers, 1.34 shredder calls per raw buffer) the SAME query shows LF/LK 1.30× e2e
   (and p99 1.6×). The lock matters exactly when rows span raw buffers, i.e. when buffer size / row size is small.
4. **Paper-safe sentence:** "On rows that span raw buffers (12 KB rows, 4 KiB buffers) the lock-free shredder sustains
   1.30× the throughput of the naive locking shredder at 24 workers for q_ex — identical to the projection
   microbenchmark (1.30×) — while at 128 KiB buffers the same query is insensitive to the shredder (0.99–1.08×)."

## Caveats
- **No isolated arm** for q_ex: `formatter-scaling-benchmark` knows only UINT64 columns and the two varsized modes
  (`varsized=2` = (id,s)→id). A 6-field bid mode projected to `channel` is ~40 lines if the full figW layout
  (isolated + e2e) is wanted; the existing figW isolated lines (SELECT id data) remain valid as the "shredder-isolated"
  reference since the e2e lines are query-independent.
- **No no-serde arm** (as figW): would need a 12 KB fixed-string `.nes` twin and the native formatter's multi-buffer
  spanning path, untested.
- 0 survivors → the CONCAT/alert path never executes (figQ: 220 of 250 M rows; output ≈ 0 in both). Substituting the
  two hottest ids of the slice (1000, 2400) would give 0.8 % selectivity if the alert path must run.
- LF windows at W ≥ 16 are 0.93 s (figW: same); rep spread ≤ 3.5 % except two single-run outliers (above).

## Figures
`figures/figW_qex_gbps.{png,svg}` (4 lines: q_ex filled circles solid, SELECT id open squares dashed; LF blue, LK red —
figW palette, validated), `figures/figW_qex_p99.{png,svg}` (log-y p99). Script `scripts/make_qex_span_figure.py
<run_group> <outdir>` (run from `~/work/piparse-bench` with `uv run python`).

## Reproduce
```
# data (0.4 s)
python3 scripts/gen_bidstr_url12k.py cmake-build-release/nes-systests/testdata/large/nexmark/bid_strings_3GB.csv \
        nes-systests/testdata/large/formatter/bidstr_url12k_500m.csv 12000
ln -sfn $PWD/nes-systests/testdata/large/formatter/bidstr_url12k_500m.csv cmake-build-release/nes-systests/testdata/large/formatter/
# sweep (13.5 min, Threadripper, cmake-build-release Sep-3 worker)
cd ~/work/piparse-bench && pkill -9 -x main; PBENCH_KEEP_LOGS=1 uv run python bench.py run \
   experiments/shredder_worker_probe_qex.yaml --build-dir ~/work/nebulastream-public/cmake-build-release --worker-port 9099 --detach
# tables + figures
uv run python <this dir>/scripts/make_qex_span_figure.py <run_group> <this dir>
```
Files: `scripts/{gen_bidstr_url12k.py, make_qex_span_figure.py, shredder_worker_probe_qex.yaml, bidstr_qex_12k.yaml}`
(the yamls are copies; the live ones are in `~/work/piparse-bench`, UNCOMMITTED), `data/`, `figures/`, `logs/`.
Related: figW provenance `bypass_scaling_2026-08-28/span_figure/` (SPAN_FIGURE_RESULTS.md, make_worker_figure.py),
figQ `bypass_scaling_2026-08-28/ideal_scaling/` + `QEX_PLATEAU_ANALYSIS_2026-10-05.md`.
