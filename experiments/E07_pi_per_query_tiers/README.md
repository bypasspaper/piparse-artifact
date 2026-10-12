# E07 — Raspberry Pi 5 per-query tiers: optimised vs native (no-serde) vs naive, 13 queries (build e)

**Claim in the paper.** The per-query evaluation on the 4-core Raspberry Pi 5 (the "restricted hardware" column): for the
frozen 10 stateless + 3 stateful paper queries, the fully optimised NES arm vs the no-serde upper bound (native in/out) vs
the naive baseline (interpreted CSV, stringstream JSON, W3). Headline (build e, MB/s medians): optimised 1349 (q0) …
5823 (q_ex); native 1936 … 10279; naive 181 … 242 (stateless), so optimised/naive 6–24× and native/optimised 1.0–2.5×
depending on the output share. Inlining (build e vs the same engine without it) gives +1 % (q0) … +53 % (q22); the
lazy-overload knob gives q2_og 1.84× and q_ex 1.12× and nothing elsewhere. Stateful q8_join / cm_q2 are state-bound (flat).

**Machine.** Raspberry Pi 5 Rev 1.1, 4× Cortex-A76 @ 2.4 GHz, 16 GiB, NVMe, Raspberry Pi OS 64-bit (Debian 13), LLVM 21.1.8
dev image `nebulastream/nes-development:local-piparse-inl`; NES W3 + 1 io thread, governor performance, `get_throttled`
0x0 throughout (continuity logs). **Binary = build e** (engine `b5d757c9f6` + the committed overlay = tag
`piparse-artifact-v1`, worker built with `NES_INLINE_ON_ARM=ON` against nautilus 85c19150 + port patches 0001–0005;
see `../../env/pi/`). Run 2026-10-06 real time (Pi clock 2026-09-30, the Pi's clock runs ~6 days behind: every
`timestamp` in the raw CSVs is Pi-clock).

**Measured with.** pbench (Pi checkout) experiments `pi_stateless_tier_nbi`, `pi_stateful_tier_nbi`,
`pi_native_stateless_nbi`, `pi_native_stateful_nbi`, `pi_naive_stateless_w3_nbi`, `pi_naive_stateful_w3_nbi` (442 runs,
all exit 0) — raw rows in `../../results/pi/pi_tiers_nbi_raw.csv`. Two earlier takes of the same tiers are shipped as
controls: `pi_tiers_aug_raw.csv` (Aug-23 binary = the Pi numbers used until 10-05, inlining never active on ARM) and
`pi_tiers_nb_raw.csv` (same engine as build e, inlining OFF; chain d, 2026-10-05). `pi_inline_verify_raw.csv` is the
12-run smoke that first proved the aarch64 inlining fix (q2_og ovl/ctrl 1.86×).

## Files

| path | what |
| --- | --- |
| `yaml/pi_stateless_tier_ovl.yaml`, `yaml/pi_stateful_tier_ovl.yaml` | the optimised tier definition with the ctrl/ovl series (the `*_nbi` yamls on the Pi are these two + the native/naive ones with the name suffixed) |
| `yaml/pi_naive_stateless_w3.yaml`, `yaml/pi_naive_stateful_w3.yaml` | the naive arm at the optimised arm's worker budget (W3) |
| `yaml/nes_vs_flink_vs_spark_stateless_5arm.yaml`, `yaml/naive_corrected_{stateless,stateful}.yaml` | the Threadripper definitions of the same three arms (the Pi yamls were derived from them; the native arm's exact config is the `NES-Native` series here) |
| `yaml/queries/**` | the 13 query-catalog entries (10 `nexmark/matrix/bidstr_*`, `yahoo/ysb_1k_varsized`, `nexmark/q8_join`, `cluster_monitoring/q2_original`) |
| `data/pi_tiers_build_e.csv` | **the figure input**: one row per arm × binary × query × series, medians over reps (143 rows) |
| `data/naive_tier_w1_vs_w3.csv` | naive W1 vs W3 vs optimised per query (the 2026-10-03 W3 retake on the Aug-23 binary) |
| `expected/pi_tiers_build_e_tables.md` | the three comparison tables (optimised aug/nb/nbi + ovl; native + naive; p99) |
| `make_figure.py` | rebuilds `out/pi_tiers_build_e.csv` + `out/pi_tiers_build_e_tables.md` from `../../results/pi/pi_tiers_*_raw.csv` |
| `run.sh` | the Pi-side re-measure chain + export recipe |
| `scripts/chain_nbi_only.sh`, `scripts/chain_after_build_e.sh` | the chain that ran the six `_nbi` tiers (the second variant with the abandoned q0 ≥ 1.1× throughput gate) |
| `scripts/checksum_ab.sh` | checksum A/B inline vs no-inline binary (row counts + checksums identical on all 10 stateless queries) |
| `scripts/export_pi_tiers_build_e.sh` | Pi DuckDB → CSV export + pull (ssh; Pi-side DuckDB) |
| `scripts/run_naive_tier_w3.sh` | the naive W3 tier runner (sampler + continuity log) |
| `../../results/pi/pi_tiers_{aug,nb,nbi}_raw.csv`, `pi_inline_verify_raw.csv` | raw run rows (every rep) |
| `../../results/pi/naive_tier_w1.csv`, `naive_tier_w3.csv` | raw rows of the naive tiers at W1 (pi_naive_stateless/stateful) and W3 |

No figure was rendered for this element at freeze time: the paper table/figure is drawn from `data/pi_tiers_build_e.csv`
(use the `nbi` rows: optimised = `pi_*_tier_nbi` series `ctrl`, or `ovl` if the paper states overload ON; native =
`pi_native_*_nbi`; naive = `pi_naive_*_w3_nbi`).

## Reproduce the tables from the shipped data (seconds)

```
python3 make_figure.py          # duckdb in-memory over ../../results/pi/*.csv -> out/ ; verified identical to data/ + expected/
```

## Re-measure (~1 h 45 min, Raspberry Pi 5)

```
./run.sh                        # prints the Pi-side chain (scripts/chain_nbi_only.sh) + export + rebuild steps
```
Requires the Pi worker built as build e (`../../env/pi/run_pi_build_e.sh` inside the `local-piparse-inl` image), the
datasets under `/home/pi/data/repos/nebulastream/cmake-build-release-piparse/nes-systests/testdata/large/` (bid_strings_3GB
csv + .nes twin, ysb_1k, person/auction, google-cluster), and the pre-flight in `run.sh`.

## Pi database experiment-name map (which rows mean what)

| names | binary | inlining | status |
| --- | --- | --- | --- |
| `pi_stateless_tier`, `pi_stateful_tier`, `pi_native_*`, `pi_naive_*` (+ `pi_scaling_file_*`, Flink/Spark ladders) | Aug-23 (8217cce465) | off | the Pi numbers up to 10-05; tiers SUPERSEDED by `_nbi` |
| `pi_naive_scaling_w3_*`, `pi_naive_*_w3`, `pi_naive_inflight_probe` | Aug-23 | n/a (uncompiled) | valid (naive is unaffected by inlining) |
| `pi_*_tier_ovl` | Aug-23 | off | overload A/B INVALID (pre-fix overload path) |
| `pi_stateless_tier_nb` (valid), `pi_stateful_tier_nb` (CONTAMINATED by an overlapping rebuild), `pi_stateful_tier_nb2`, `pi_native_*_nb`, `pi_naive_*_w3_nb` | b5d757c9f6 | off | new engine without the context layer (chain d, 2026-10-05) |
| `pi_inline_verify` | b5d757c9f6 + 0005 | on | 12-run smoke of the fix (2026-10-06) |
| **`*_nbi`** | **b5d757c9f6 + 0005 (build e)** | **on** | **the final tiers (this element)** |

## Caveats / provenance notes

- **Overload knob:** OFF in every tier and ladder on both machines except where a `ctrl`/`ovl` series says otherwise
  (`pi_*_tier_nbi` carry both). The paper must state which column it quotes (ovl moves q2_og 1.84× and q_ex 1.12× only).
- **Pi optimised numbers = build e only.** The Aug-23 tiers (`aug`) and the no-inlining retake (`nb`) are superseded
  controls: on ARM the Nautilus inlining pass was gated off until port patch 0005 (the JIT crashed on the address-renamed
  EH personality, `Symbols not found: DW.ref.0x…`), so every earlier Pi "optimised" number was ablation rung r4
  (compiled + fnattr + fast codecs, no proxy inlining / constant folding / output fast path / effective overloads).
- **Naive arm = W3**, the optimised arm's worker budget (the first Pi naive tiers ran W1 and funnelled every stream's
  stringstream output through one worker; `data/naive_tier_w1_vs_w3.csv` quantifies it: output-heavy q0/q1/q10/q22
  2.0–2.5×, light-output queries flat at the ~240 MB/s interpreted-parse ceiling). The Threadripper naive tiers already
  ran at W23 (pbench applies the x-axis value after the series override — check `runs.config`, not the yaml).
- **~6× per-core gap Pi/TR is expected** (4 A76 vs 24 Zen 3 cores); q0 gains nothing from inlining on the Pi (×1.01) and
  this was not investigated (user decision 2026-10-06).
- Only the per-query tiers were retaken on build e; the Pi scaling ladders and latency curves (E08) stay on the Aug-23
  binary (user decision 2026-10-06).
- Checksum A/B (`scripts/checksum_ab.sh`): build e vs build d produce identical row counts and checksums on all 10
  stateless queries — the EH strip changes no output.
- Rep spread on the stateless optimised tiers ≤ 4 %; ysb 7–16 % (its ovl 0.94 and native −11 % are noise).
- Pi clock: all DB/CSV timestamps are ~6 days behind real time (2026-09-30 in the file = 2026-10-06 real).
- **PAPER POLICY (author, 2026-10-12): lazy overloads ON** → the paper's Pi optimised column is the `ovl` series of `pi_stateless_tier_nbi` / `pi_stateful_tier_nbi` (q2_og 1.84× over `ctrl`); `ctrl` stays as the OFF reference.
