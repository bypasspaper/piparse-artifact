# E06 — Lazy-overload knob A/B on the optimised NES arm (per-query tiers, both boxes)

**Claim in the paper.** The lazy-overload optimisation (constant equality evaluated on the raw text of a lazy value,
`INPUT_FORMATTER.LAZY_INT/UINT/FLOAT_OVERLOADS`) moves exactly one of the 13 workload queries on the Threadripper:
NEXMark q2-original (5-way INT32 `==` chain) **+18 %** (518 → 611 Mrows/s, p99 0.24 → 0.17 ms) and lands above the Aug-14
native-input arm; q_ex +2 %; every other query 0.99–1.00×. The per-query "optimised" tables of the paper ran with the knob
OFF (engine default) — this A/B is what lets the paper state the knob's effect either way.

**Machine.** Threadripper PRO 5965WX, W23 + io1, MmapFile source (`NES_MMAP_POPULATE=1`, warm page cache), SIMDCSV,
fast parser set, JSON output + ZMIJ, fnattr, inline + tcb default-on, pin/ccx off; binary `cmake-build-release` of
2026-09-03 at `b5d757c9f6` (has the word-compare fast path `f6a7b98343`). Raspberry Pi 5, W3 + io1, same stack, Aug-23
binary (**pre**-fix, see caveats).

**Measured with.** TR: `nes_simd_overload_stateless.yaml` (200 runs, run_group `20261005T114637-61a8f600`) +
`nes_simd_overload_stateful.yaml` (60 runs, `20261005T120141-75e0e42c`), 2026-10-05 11:46→12:09, 0 failed, 10 reps,
series `NES-SIMD` (ctrl) vs `NES-SIMD-ovl`. Pi: `pi_stateless_tier_ovl` (140) + `pi_stateful_tier_ovl` (42), Pi clock
2026-09-29 07:00→07:45 (real 2026-10-05), 7 reps, series `ctrl` vs `ovl` — rows only in the Pi's DB, exported to
`data/pi_tier_overload_ab.csv`.

## Files

| path | what |
| --- | --- |
| `yaml/experiments/nes_simd_overload_{stateless,stateful}.yaml` | TR experiments (pbench tag `piparse-artifact-v1`) |
| `yaml/experiments/pi_{stateless,stateful}_tier_ovl.yaml` | Pi experiments (copied from the Pi's pbench checkout via the result dir; not in the host pbench repo) |
| `yaml/queries/...` | the 13 workload queries (10 stateless bidstr_* + q8_join, cm_q2 = cluster_monitoring/q2_original, ysb_1k_varsized) |
| `data/tr_simd_overload_ab.csv` | 260 raw per-repetition rows (TR) |
| `data/pi_tier_overload_ab.csv` | 182 raw rows (Pi) |
| `data/tr_ctrl_vs_ovl_vs_aug14.csv` | the TR summary table incl. the paper's Aug-14 5-arm SIMD/Native Mrows/s columns for drift |
| `expected/RESULT_overload_ab_2026-10-05.md` | result doc (both tables, findings, decisions for the paper) |
| `expected/reference_renderings/` | tables + ratio bar chart as regenerated on 2026-10-12 |
| `make_figure.py` | regenerates both per-query tables (markdown + CSV) and a ratio chart; `--db` pulls the TR rows live from the DB |
| `run.sh` | re-measure on the TR (port of pbench `results/run_tr_ovl.sh`) |

## Reproduce from the shipped data (seconds)

```
python3 make_figure.py          # out/{tr,pi}_overload_ab_table.csv, out/overload_ab_tables.md, out/overload_ab_ratio.{png,svg}
python3 make_figure.py --db     # TR rows from ../../results/tr/piparse_bench.duckdb instead of the CSV
```

Verified 2026-10-12: both regenerated tables equal the tables in `RESULT_overload_ab_2026-10-05.md`; against
`data/tr_ctrl_vs_ovl_vs_aug14.csv` the max relative deviation is 0.09 % (rounding), CSV and DB modes agree.

## Re-measure (~25 min, Threadripper)

```
./run.sh                        # stateless then stateful; then edit TR_RG in make_figure.py or pass the CSV export
```

## Caveats / provenance notes

- **The Pi A/B is invalid as an overload verdict**: the Pi worker binary was linked 2026-08-23, before the overload
  word-compare fix (`f6a7b98343`, 2026-08-30) — q_ex's −25 % is the pre-fix opaque `memcmp` path. The Pi was relinked and
  rebuilt with the aarch64 inlining fix afterwards; the valid Pi ctrl/ovl numbers are the build-e `_nbi` series in **E07**
  (q2_og 1.84× with overload on the Pi).
- **Binary drift vs the paper's Aug-14 TR table** (`66ab110f30`): the Sep-3 engine is +12 % q2_mod, +19 % q_ex, +3–4 %
  q14/q2_og/q_project, flat on output-bound queries and **−25 % on q8_join** (known open regression). The Native arm was
  not re-run in this session.
- Decision to state in the paper: per-query optimised column with overload ON (matches Fig1 v2) or OFF (engine default
  every tier ran with) — only q2_og changes on the TR.
- Overload can only touch q2_og (5× INT32 ==), q_ex (2× INT32 == on channel survivors; its `price <` is a float ordering
  compare, never overloaded) and cm_q2 (INT16 == 3); VARSIZED equality (q_route, ysb) is always overloaded; q14/q2_mod
  need the parsed value.
