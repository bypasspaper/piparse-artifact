# E04 — q_ex worker sweep over the serde matrix (figQ) + the superseded q2_mod ideal-conditions sweep (figI)

**Claim in the paper.** Under ideal conditions (128 KiB buffers, ~115 B NEXMark bid_strings rows, no spanning) on
the HOSP working-example query q_ex, (1) **output serde is free**: native→native and native→JSON coincide (< 1 %),
and so do csv→JSON (the optimised "bypass" arm) and csv→native — four arms overplot into two curves; (2) **the residual
gap is input deserialization only and closes with threads**: optimised/no-serde rises monotonically from 0.46 @W1 to
0.89 @W23 (44.6 → 585.5 vs 96.1 → 656.6 M rows/s) while the native pair saturates ~657 M rows/s (≈ 72 GB/s) from W16;
(3) **lock-free ≈ locking shredder at 128 KiB**: LF/LK 0.99–1.01 to W8, then 1.04 / 1.06 / 1.07 / 1.08 @12/16/20/23 —
the shredder is off the critical path at 1/32 the call-rate of the 4 KiB spanning figures (E03). figI is the earlier
q2_mod 4-arm sibling (no-serde 129.5 → 707 M rows/s flat from W16; bypass 41 → 546, 0.32 → 0.78 of no-serde; eager
parse costs 16–34 % vs lazy elision; LF/LK 1.00–1.07) — superseded as the headline by figQ, kept as companion.

**Machine.** Threadripper PRO 5965WX, W ∈ {1,2,4,8,12,16,20,23} workers + 1 io thread, host `cmake-build-release`
worker at `b5d757c9f6` + overlay (tag `piparse-artifact-v1`; the q_ex figure REQUIRES the VARSIZED early-return
equality fix in that overlay — without it the optimised q_ex arm is −29 %). Runs 2026-09-02/03.

**Measured with.**

| figure | pbench experiment | arms (series) | run_group | runs | wall |
| --- | --- | --- | --- | --- | --- |
| figQ | `qex_serde_matrix_scaling.yaml` (variant `qex_matrix`) | `native_native`, `native_json`, `simd` (csv→JSON), `csv_native` | `20260902T220312-52fa4604` | 192 (4 × 8 W × 6 reps) | 14 min |
| figQ | `qex_locking_scaling.yaml` | `bypass_locking` (csv→JSON, LOCKING shredder) | `20260903T084122-767c3984` | 48 | 4 min |
| figI | `shredder_ideal_scaling_q2mod.yaml` (variant `ideal_q2mod`) | `no_serde`, `bypass`, `lockfree`, `locking` (the last two = `eager_parse: true`) | `20260902T102956-283f8cf0` | 160 (4 × 8 W × 5 reps) | 13 min |
| figI smoke | `shredder_ideal_smoke_q2mod.yaml` | | `20260902T102810-f6c748a3` | | |

Configuration = the 5-arm head-to-head NES arms verbatim (E05): MmapFile zero-copy + `NES_MMAP_POPULATE` + warm read,
`generator.repeat 8` (250.4 M rows per run), 128 KiB operator buffers, fnattr, COMPILER, io 1, pin/ccx off, Monitoring
sink, metric `throughput_mrows_s` (format-invariant; MB/s is NOT cross-arm comparable: csv 114.865 vs native 110 B/row).
SystemNative input needs `string_length "13,73"`. Query `nexmark/matrix/bidstr_qex` (220 survivors of 31.3 M → output ≈ 0)
on `bid_strings_3GB.{csv,nes}`; figI: `bidstr_q2mod` (`auctionId % 123 == 0`, 0.82 % survivors).

## Files

| path | what |
| --- | --- |
| `yaml/experiments/*.yaml`, `yaml/queries/nexmark/matrix/bidstr_{qex,q2mod}.yaml` | experiment + query definitions (piparse-bench tag `piparse-artifact-v1`) |
| `data/figQ_qex_serde_matrix_medians.csv` | arm × W medians behind figQ (40 rows) |
| `data/figI_ideal_workers_q2mod_medians.csv`, `data/per_rep_raw.csv` | figI medians (32 rows) and its 160 per-rep rows |
| `expected/figQ_qex_serde_matrix.{png,svg}`, `expected/figI_ideal_workers_q2mod.{png,svg}` | the figures as submitted |
| `expected/IDEAL_SCALING_RESULTS.md` | figI write-up (contains the corrected table; see caveat 1) |
| `expected/QEX_PLATEAU_ANALYSIS_2026-10-05.md` | the analysis of WHY the no-serde arm plateaus and the optimised arm catches up (hypotheses, USL fits, probe plan) — analysis only, the probe was NOT run |
| `make_qex_matrix_figure.py`, `make_ideal_figure.py` | the original scripts, path-portable (read the DB's `aggregated` view = latest run_group per experiment) |
| `make_figure.py` | runs both → `out/`; `--verify` diffs the regenerated medians CSVs against `data/` |
| `run.sh` | re-measure recipe |

## Reproduce the figures from the shipped data (seconds)

```
python3 make_figure.py --verify      # DB default ../../results/tr/piparse_bench.duckdb (or --db PATH / $PBENCH_DB)
```
Verified 2026-10-12: both medians CSVs reproduce `data/` exactly (max relative deviation 0); `out/figQ_qex_serde_matrix`
and `out/figI_ideal_workers_q2mod` written (png + svg); the printed per-W tables match the claim above.

## Re-measure (~35 min + first-time staging, Threadripper)

```
./run.sh                 # or ./run.sh --dry-run; env NES_BUILD_DIR, PBENCH_DIR, WORKER_PORT
python3 make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb
```
Needs `bid_strings_3GB.csv` and its packed twin `bid_strings_3GB.nes` (see `../../data/README.md`); the repeat-8 MmapFile
staging writes 26.8 GB csv + 25.6 GB nes once (slow first run, not a hang; keep ~55 GB free). Do not raise
`generator.repeat` (16× staging = 54 GB blows the page cache). W23 windows are 0.4–0.7 s (median of 6 — the accepted
5-arm footing); W1 csv arms run 10–25 s per rep.

## Caveats / provenance notes

1. **A sentence in `IDEAL_SCALING_RESULTS.md` is wrong**: "native out lifts the ceiling 516 → 705" — native→JSON ≡
   native→native within 0.25 % at every W (figQ shows it); the lift over the Aug-14 5-arm anchor came from the
   per-task machinery commits (dbfd09ff2c, 98ab8e3cb3, b5d757c9f6), not from the output format.
2. **No hardware counter was ever taken on any figQ/figI arm.** The "DRAM-bound / memory-bandwidth wall" label is a
   level comparison (72.2 GB/s = 87 % of the 83 GB/s all-core read peak). Because every run uses 131072-byte buffers,
   a byte wall and a per-buffer serialized-cost wall are numerically indistinguishable in the data; the 22-minute
   discriminating probe (buffer-size sweep at constant pool bytes + counters) is planned in
   `expected/QEX_PLATEAU_ANALYSIS_2026-10-05.md` and was **not run**. Paper-safe phrasing is in that document §4;
   do not write "both hit the DRAM wall" without the probe.
3. About 40 % of the W23 row-rate gap (1.122) is the CSV file being 4.4 % larger per row (114.865 vs 110 B); the
   byte-rate deficit is 1.074.
4. The companion M1 bypass thread-scaling points at W16–24 (earlier bypass study, not in this directory) imply 89–110
   GB/s on an 83 GB/s box — a ramp artifact (0.3 s windows); re-run with ≥ 3 s windows before citing 1.56×.
5. figQ is the best case by construction (lazy values + constant-overload equality erase the string-predicate cost);
   the per-query ratio table in E05 (`simd_over_native` 0.50–0.90, q1/q14 float-parse worst) is the companion.
6. `eager_parse: true` with SIMDCSV/PARALLEL was exercised for the first time in figI (smoke + 80 clean runs).
- **PAPER POLICY (author, 2026-10-12): lazy overloads ON for id comparisons.** figQ/figI were measured with the knob OFF (no `overload` key = OFF in pbench); q_ex carries two id equalities, so its optimised arm would gain a few percent with the knob on (E06: TR q2_og +18 % is the upper bound of the effect).
