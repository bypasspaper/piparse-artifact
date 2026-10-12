# E03 — Lock-free vs locking SequenceShredder on spanning rows: worker scaling (figW), its q_ex twin, span sweeps (figS), latency (figL)

**Claim in the paper.** When input rows span raw buffers (12 KB rows at 4 KiB raw buffers ≈ 3 buffers per row), the
lock-free SequenceShredder sustains **1.37×** the end-to-end throughput of a naive locking shredder at 24 workers
(4.39 vs 3.21 GB/s; same-binary re-take 2026-10-05: **1.30×**, 4.44 vs 3.41) and **3.06×** in the isolated
Scan→Emit harness (11.2 vs 3.67 GB/s, max of 15 reps); the lock's damage is larger in latency than in throughput
(LOCKING p50 ≈ p99 ≈ 10 ms = mutex convoy, LOCK-FREE p50 ≈ 40 µs, p99 LK/LF ≈ 1.6×). Across row sizes 4…640 KB the
e2e LF/LK gap is 1.29–1.66× at 4 KiB buffers (isolated 1.70–2.75×) and LOCKING diverges downward at the largest
spans; 8 KiB buffers double the throughput with the same gap shape. The **q_ex twin** (the HOSP working-example
query on url-padded 12 KB bid rows) overlays `SELECT id` within 2 % at every worker count: the spanning result is a
property of the row/buffer geometry, not of the query.

**Machine.** Threadripper PRO 5965WX (24 physical cores), W ∈ {1,2,4,8,12,16,20,24} workers + 1 io thread, host
`cmake-build-release` worker at engine commit `b5d757c9f6` + the (then uncommitted) benchmark overlay — both now
contained in tag `piparse-artifact-v1`. figW / figS / figL = the 2026-08-31 build; q_ex twin = the 2026-09-03 build.

**Measured with.**

| figure | arm | pbench experiment / harness command | run_group (results DB) | runs | wall |
| --- | --- | --- | --- | --- | --- |
| figW (`figW_workers_12k_final*`, `figW_2span_e2e`) | e2e | `shredder_worker_probe.yaml` (variants `workers_12k_span3`, `workers_80k_span20`) | `20260831T173338-1b014b79` | 192 | 13 min |
| figW | isolated | `formatter-scaling-benchmark bigstr_id_12k_500m.csv 4 0 15 1,2,4,8,12,16,20,24 leanprod 1 - - both - SIMDCSV 2` | `data/logs/isolated_worker_probe_12k_leanprod.log` | 15 reps/cell | ~10 min |
| figS / figL (`figS_span_{4k,8k}`, `figL_latency_{4k,8k}`) | e2e | `shredder_span_sweep.yaml` (7 row sizes × buffer {4096, 8192} × {LF, LK} × 6 reps) | `20260831T135736-941d625d` | 168 | 14 min |
| figS | isolated | `formatter-scaling-benchmark bigstr_id_<tag>_500m.csv <4\|8> 0 15 8,16,24 leannoemit 1 - - both - SIMDCSV 2` per row size | `data/logs/isolated_span_sweep_4k8k.log` | 15 reps/cell | ~25 min |
| latency probe (bounded in-flight 64, K=1; text only) | e2e | `shredder_latency_probe.yaml` | `20260831T142959-dab6103c` | 12 | 1 min |
| q_ex twin (`figW_qex_{gbps,p99}`) | e2e | `shredder_worker_probe_qex.yaml` (variants `qex_12k_span3`, `selid_12k_span3`) | `20261005T170750-d5bb1e82` | 192 | 13 min |
| superseded first passes (still in the DB, not plotted) | e2e | `shredder_worker_probe` `20260831T144230-2d67f9d7` (42 runs), `shredder_span_sweep` `20260831T131622-670069e9` (36 runs) | | | |

e2e configuration (all three yamls): worker-cli mode, InMemory prefill (`NES_INMEM_PREFILL=1`, `NES_INMEM_BUFSIZE=4096`,
`NES_INMEM_REPEAT=8`; 16 for the span sweep), `NES_SOURCE_EMIT_BATCH=32`, admission queue 32768, **in-flight 8192
(deep queue)**, 128 KiB operator buffers, fnattr + inline, pin/ccx off, CSV output (JSON + figQ parsers for the q_ex
arm), Monitoring sink, 6 reps, median. Series = `sequence_shredder_mode` LOCK_FREE / LOCKING. The isolated harness
(`nes-input-formatters/tests/Benchmark/FormatterScalingBenchmark.cpp`, `varsized=2` = 2-field `(id, s)` projected to
`id`) runs the same compiled Scan→Emit stage over prefilled 4 KiB raw buffers with N drain threads and no engine
machinery.

## Files

| path | what |
| --- | --- |
| `yaml/experiments/*.yaml` | the 5 experiment definitions (piparse-bench tag `piparse-artifact-v1`) |
| `yaml/queries/formatter/*.yaml` | `bigstr_id_pass_{4k…640k}` (`SELECT id FROM (id UINT64, s VARSIZED)`), `bidstr_qex_12k` (q_ex on url-padded bid rows) |
| `data/isolated_tidy.csv`, `data/e2e_tidy.csv`, `data/span_tidy.csv` | span sweep: isolated (median + max per cell), e2e (GB/s, p50/p99/p999, window), merged W24 table behind figS |
| `data/e2e_latency_tidy.csv` | the bounded-in-flight latency probe (text only) |
| `data/shredder_all_data.csv` | every span-sweep + worker-sweep point of both harnesses in one tidy table (176 rows; columns documented in `build_all_data_csv.py`) |
| `data/qex_span_medians.csv` | the q_ex twin medians (GB/s, Mrows/s, p50/p99, window) |
| `data/logs/*.log` | the three isolated-harness logs the scripts parse (4–24 KB each) |
| `expected/figW_workers_12k_final{,_p99}`, `figW_workers_12k_mrows`, `figW_2span_e2e` | figW as submitted (GB/s; p99; Mrows/s; 3-span vs 20-span overlay) |
| `expected/figS_span_{4k,8k}`, `figL_latency_{4k,8k}`, `figS_span_iso_vs_e2e`, `figL_latency` | span sweep figures (the unsuffixed pair = first 4 KiB-only pass) |
| `expected/figW_qex_{gbps,p99}` | the q_ex twin |
| `expected/figW_workers_12k{,_p99,_leanprod}` | earlier figW drafts (42-run first pass / lean drain) — superseded |
| `expected/SPAN_FIGURE_RESULTS.md`, `QEX_SPANNING_RESULT.md`, `qex_span_tables.md` | the result write-ups with the full tables |
| `parse_isolated.py`, `parse_e2e.py`, `merge_span.py`, `make_span_figure.py`, `make_latency_figure.py`, `make_worker_figure.py`, `make_worker_2span.py`, `build_all_data_csv.py`, `make_qex_span_figure.py` | the original scripts, path-portable (header in each) |
| `make_figure.py` | runs them all → `out/`; `--verify` diffs every regenerated CSV against `data/` |
| `gen_bigstr_id.py`, `gen_bidstr_url12k.py` | data generators (see below) |
| `run.sh` | re-measure recipe (all e2e + isolated arms) |

## Reproduce the figures from the shipped data (seconds)

```
python3 make_figure.py --verify      # needs duckdb + matplotlib (../../scripts/requirements.txt); DB default ../../results/tr/piparse_bench.duckdb
```
Writes `out/figS_span_{4k,8k}`, `out/figL_latency_{4k,8k}`, `out/figW_workers_12k_final{,_mrows,_p99}`, `out/figW_2span_e2e`,
`out/figW_qex_{gbps,p99}` (png + svg) and the five tidy CSVs. Verified 2026-10-12: all five CSVs reproduce `data/`
bit-for-bit (max relative deviation 0); 10 figures written; the regenerated figW annotates 3.06× (isolated) / 1.37× (e2e)
@24 exactly as `expected/figW_workers_12k_final.png`.

## Re-measure (~80 min, Threadripper)

```
./run.sh                 # or ./run.sh --dry-run; env NES_BUILD_DIR, PBENCH_DIR, ENGINE_DIR, WORKER_PORT
```
Data: `bigstr_id_<KB>k_500m.csv` = rows `<id>,<N×'x'>` to 500 MiB (`gen_bigstr_id.py`, the one-liner from
SPANNING_SWEEP_HANDOVER.md §2 — the original ad-hoc generator was not kept); `bidstr_url12k_500m.csv` = the first
43,546 rows of `bid_strings_3GB.csv` with `url` padded to 12,000 chars (`gen_bidstr_url12k.py`, 0.4 s). Sizes the
query yamls assume: 12k → 43,667 rows / 524,298,559 B (12,003 B/row, 2.93 spans @4 KiB); 80k → 6,554 rows; the
q_ex twin → 43,546 rows / 524,279,918 B (12,039.7 B/row, 2.94 spans). Files are gitignored in the engine tree and
symlinked into the build tree (`run.sh` does both). After a re-run, point the scripts at the new data as printed at the
end of `run.sh` (the e2e scripts read the LATEST run_group of each experiment from the DB; `make_qex_span_figure.py`
takes the run_group as its first argument).

## Caveats / provenance notes

- **Open decision — which figW ratio the paper cites.** `expected/figW_workers_12k_final` (and all figW/figS/figL
  numbers) come from the **2026-08-31 build**: e2e LF/LK **1.37×** @W24. The 2026-10-05 same-binary re-take
  (`selid_12k_span3` cells of the q_ex run, 2026-09-03 build) gives **1.30×** — the LOCKING arm is +6 % on the newer
  build (3.41 vs 3.21 GB/s), LOCK-FREE +1 % (4.44 vs 4.39); binary drift of the uncommitted overlay, not investigated.
  Both are shipped; the paper must cite one binary (the q_ex twin and `SELECT id` agree to 1.30× on the Sep-3 build).
- **Isolated lines plot the per-cell MAX** (ramp-free steady state over 15 reps; `make_worker_figure.py`,
  `merge_span.py` `ISO_METRIC`); **e2e lines plot the MEDIAN** of 6 reps. Uncaptioned in the figures.
- **Two different "12k" datasets exist**; never mix: 2026-08-28 `bigstr_12k_500m.csv` (single VARSIZED field,
  12,289 B/row, harness `varsized=1`, LF/LK 1.73× @W16, used in the earlier figI session) vs 2026-08-31
  `bigstr_id_12k_500m.csv` (2-field, this figure, 2.47× @W16 isolated).
- No no-serde arm in any spanning experiment (no `.nes` twin of the bigstr data exists); no isolated arm for q_ex
  (the harness knows only UINT64 columns + the two varsized modes) — the figW isolated lines are the shredder-isolated
  reference for both, since the e2e lines are query-independent.
- **Absolute latencies are inflated by the deep-queue throughput config** (in-flight 8192 → queue residence, Little's
  law); the LF/LK contrast is the robust signal. LOCK-FREE p50 is bimodal (most tuples immediate, tail ~10 ms) →
  a knife-edge median (e.g. 40 KB row = 2 ms, W16 5–7 ms → W24 40 µs); p99 is the robust latency metric.
- The 80 KB / 20-span **isolated** LOCKING cells at W12–20 show repeat storms → the 3-span (12 KB) figure is the
  headline; `data/shredder_all_data.csv` (`sweep=worker, row_kb=80`) carries the 20-span data with `repeats_pct`.
- Repeats are OFF by design in the sweeps (in-flight 8192 ≪ window 65536 ⇒ 0 re-queues). 8 KiB-buffer e2e windows are
  ~1.0 s (borderline the >1.4 s guard; values stable). q_ex-twin windows: LF 0.93 s @W≥16, LK 1.2 s, W1 3.1 s; rep
  spread ≤ 3.5 % except two single-run outliers (see `expected/QEX_SPANNING_RESULT.md`).
- The q_ex twin's predicate matches 0 rows on the 43,546-row slice (figQ: 220 of 31.3 M) — output ≈ 0 in both
  experiments, the hot path is the filter either way (channel compared on every row, auctionId parsed on the 20 %
  google rows, price never).
- `throughput_mbps` for these experiments is true MB/s (generator.repeat == NES_INMEM_REPEAT); the older
  `shredder_scaling_pass*` experiments in the DB have repeat 1 with NES_INMEM_REPEAT 40/10 and undercount per pass.
- There was no results write-up for figW itself at the time; its provenance was reconstructed on 2026-10-05
  (`expected/QEX_SPANNING_RESULT.md` §Design and the table above are that reconstruction).
- **DECISION (author, 2026-10-12): the paper cites 1.37× (2026-08-31 build, run_group 20260831T173338-1b014b79).** The
  2026-10-05 same-binary re-take (1.30×, `qex_spanning` selid cells) stays here as supplementary evidence that the gap is
  build-stable within 5 %.
- **PAPER POLICY (author, 2026-10-12): lazy overloads ON for id comparisons.** The figW runs (`SELECT id`) have no comparison, so the knob is irrelevant there; the q_ex twin ran OFF.
