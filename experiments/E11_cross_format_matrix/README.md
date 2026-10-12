# E11 — The 4×4 cross-format matrix (CSV / JSON / HL7 / XML × r_base / r_comp / r_par) and the q0 W-sweep

**Claim in the paper.** Compilation and parallelization gains generalize across input AND output formats. Over the frozen
10-query stateless workload (`expected/PAPER_WORKLOAD.md`) on `bid_strings` (31.3 M rows) the total speed-up of the fully
optimised parallel engine over the fully-interpreted fair-codec baseline spans 50–224× (v2 table below; cell = geomean of
regime geomeans, Total = Compilation × Parallelization by construction). Compilation is an INPUT-format property (xml 13.2 >
hl7 10.3 > csv 5.3–6.1 > json 3.4 — the elidable-junk vs irreducible-stage-1 split; rows constant across outputs);
parallelization is 11–18× at W23 and varies ±25 % around ~15 (highest into the cheap coalesced csv output, lowest into hl7).
Companion W-sweep: csv→csv q0 scales to 68 GB/s (12.9× at W23) while csv→json q0 plateaus from W12 at ~16.6 GB/s — the
field-wise output serializers hit a store-queue stall ceiling of ~21–30 GB/s of OUTPUT bytes (`OUTPUT_PLATEAU_PROBE_RESULTS.md`).

| in \ out | csv | json | hl7 | xml |
| --- | --- | --- | --- | --- |
| **csv**  | **95.6**† = 6.1 × 15.8 | **66.9** = 5.5 × 12.2 | **58.5** = 5.3 × 11.0 | **65.4** = 5.5 × 12.0 |
| **json** | **61.2**† = 3.3 × 18.3 | **54.9** = 3.4 × 16.2 | **50.0** = 3.4 × 14.9 | **55.4** = 3.4 × 16.1 |
| **hl7**  | **170.2**† = 10.3 × 16.6 | **148.8** = 10.0 × 14.9 | **138.5** = 10.3 × 13.4 | **151.0** = 10.3 × 14.6 |
| **xml**  | **223.7**† = 13.2 × 17.0 | **193.2** = 12.7 × 15.2 | **178.4** = 12.9 × 13.9 | **196.6** = 13.2 × 14.9 |

† memory-wall-clipped lower bound (≥ 5 of 10 queries at ≥ 85 % of the ~66 GB/s aggregate wire ceiling at W23).

**Machine.** Threadripper PRO 5965WX. r_base / r_comp at W1 + 1 io thread, BlockingFile, sequential formatter; r_par at
W23 + 1 source thread (24 physical cores, SMT unused), InMemory prefill with `NES_INMEM_REPEAT=20` (TRUE r_par = reported
× 20), `ccx_aware_task_queues=false`, `pin_threads=false`. Binary `cbf156f20c` + overlay (2026-08-04 … 08-06; all in engine
tag `piparse-artifact-v1`).

**Measured with** (pbench tag `piparse-artifact-v1`, copies in `yaml/`): `experiments/matrix/cell_<in>_<out>.yaml` (16
cells × 10 queries × 3 rungs × 3 reps = 1440 runs, 2026-08-04 22:38 → 08-05 02:44, 0 failures) and
`cell_<in>_<out>_rparfix.yaml` (the corrected r_par, 480 runs, 2026-08-06 19:59 → 21:12, 0 failures); W-sweep
`wsweep_output_plateau.yaml` (run_group `20260806T233701-6b2fbb7e`, 32 runs, 6 min). Queries `queries/nexmark/matrix/
{bidstr,hl7,xml}_q*.yaml` (30; the JSON cells read the json twin through the `bidstr_*` entries' `data_size`).

## Files

| path | what |
| --- | --- |
| `data/matrix_runs_all1440.{csv,parquet}` | **one row per run**, the 2026-08-04/05 matrix (series r_base / r_comp / r_par-v1); full metric + config lineage columns |
| `data/matrix_rpar_fixed_480.{csv,parquet}` | **the v2 r_par arms** (ccx/pin OFF), one row per run; experiment names carry `_rparfix` |
| `data/matrix_corrected_raw_1440.csv`, `data/session_runs_all.csv` | the 1440 rows with r_par replaced by v2; the session superset (1703 rows: probes, W-sweeps, diagnostics) |
| `data/MATRIX_RESULTS_2026-08-05.json` | v1 per-query Comp/Par/Total (`perq`) + rung medians (`raw`) — **STALE for r_par** (v1 pathology), kept for the record |
| `data/wsweep_output_plateau_raw.csv` | the 32 W-sweep rows exported from the results DB (`scripts/extract_wsweep_from_db.py`) |
| `../../results/tr/matrix_snapshot_2026-08-06_final.duckdb` | the complete pbench store snapshot of 2026-08-06 (tables `runs`, `aggregated`; incl. all probes and pre-session history) |
| `expected/MATRIX_FIGURE_2026-08-05.{png,pdf}` | **the paper figure** (cell anatomy: Total bold over Comp \| Par; blue ramp = Total; daggers) |
| `expected/wsweep_parallelization_2026-08-06.{png,pdf}` | the q0 W-sweep (csv→csv vs csv→json, throughput + speed-up over W1) |
| `expected/MATRIX_RESULTS_2026-08-05.md` | the result document: v2 table + laws, the superseded v1 table, conventions, per-query notes, caveats |
| `expected/OUTPUT_PLATEAU_PROBE_RESULTS.md` | why fat-output cells plateau (store-queue stalls, IPC 2.07 → 0.78) |
| `expected/PAPER_WORKLOAD.md` | the FROZEN workload: 10 stateless + 3 stateful queries, regimes, rung definitions, dataset anchors |
| `expected/ARCHIVE_README_matrix_2026-08-05.md`, `expected/SESSION_HANDOVER_2026-08-04b.md` | the archive card (row identity, metric columns, derivation rules) and the session handover |
| `yaml/experiments/matrix/*.yaml` (32), `yaml/experiments/wsweep_output_plateau.yaml` | the experiment definitions |
| `yaml/queries/nexmark/matrix/*.yaml` (30), `yaml/queries/nexmark/bid_{hl7,xml}_*.yaml`, `person_{hl7,xml}_passthrough.yaml` | query catalog entries incl. the HL7 and XML(-via-HL7-config) families |
| `yaml/gates/hl7/convert_csv_to_hl7.sh` + `*_to_hl7.yaml`, `yaml/gates/xml/convert_csv_to_xml.py` | how the HL7 twin (the engine's own HL7 output formatter) and the packed XML twin were produced from the CSV |
| `yaml/gates/{gates_sequential,hl7,xml}/*gate*.yaml`, `yaml/gates/hl7/run_checksum_gate.sh` | the per-format checksum gates every workload query passed before benchmarking (anchor `31300000,269477267979`) |
| `scripts/plot_matrix_figure.py` | the figure from the two parquet files (medians + regime geomeans computed from raw) + `out/matrix_table_v2.csv` |
| `scripts/wsweep_parallelization.py`, `scripts/extract_wsweep_from_db.py` | W-sweep figure from the exported rows (asserts them against the 2026-08-06 values) / the export |
| `make_figure.py`, `run.sh` | driver (also checks the regenerated table against the md) / re-measure recipe |

## Reproduce the figures from the shipped data (seconds)

```
python3 make_figure.py          # out/MATRIX_FIGURE_2026-08-05.{pdf,png}, out/matrix_table_v2.csv, out/wsweep_parallelization.{png,pdf}
                                # prints the 16 cells and checks them against expected/MATRIX_RESULTS_2026-08-05.md v2
                                # (verified 2026-10-12: max |dev| 0.05 = the md's 1-decimal rounding)
python3 make_figure.py --db     # + re-exports the W-sweep rows from results/tr/piparse_bench.duckdb first (verified identical)
```
DuckDB reads the parquet files directly (no pyarrow needed).

## Re-measure (Threadripper; whole matrix ≈ 5.5 h)

```
./run.sh cell csv json          # one cell: r_base + r_comp (~15 min) then the r_par fix yaml (~5 min)
./run.sh all                    # all 16 cells (4 h for r_base/r_comp + 1 h 13 min for r_par)
./run.sh wsweep                 # 6 min
```
Then dump per-run rows as in `expected/ARCHIVE_README_matrix_2026-08-05.md` (experiment `cell_<in>_<out>[_rparfix]`,
series, variant = query) into `data/` and run `make_figure.py`. Datasets: `bid_strings_3GB.{csv,json,hl7,xml}` under
`<build>/nes-systests/testdata/large/nexmark/` (csv 3,595,281,395 B; json 5,567,181,395; hl7 5,723,681,395;
xml 5,661,081,395; 31,300,000 rows) — see `../../data/README.md`; run the checksum gates first.

## Caveats / provenance notes

- **v2 supersedes v1 (2026-08-06).** The original r_par arms ran `ccx_aware_task_queues` + `pin_threads`, a ~2× pathology
  for SINGLE-source runs (one source's sequence-ordered buffers round-robin across the 4 CCX cell queues while pinned
  workers cannot migrate). Use `matrix_rpar_fixed_480` for r_par; `matrix_runs_all1440` for r_base / r_comp. The v1 table
  (Par 7.6–9.9, totals 31.5–124×) and `MATRIX_RESULTS_2026-08-05.json` are STALE. ccx+pin remains the MULTI-source
  production config.
- **r_par ×20.** r_par runs use InMemory with `NES_INMEM_REPEAT=20` and the runner counts the file bytes once: TRUE r_par
  throughput = stored value × 20 (mbps and mrows_s). Apply before any absolute use; it cancels only in ratios across r_par runs.
- **Cross-format absolutes** need Mrows/s (MB/s denominators are per-format wire bytes). Within-cell ratios are exact.
- **Wall / daggers.** At W23 there is a real ~65–68 GB/s aggregate wire-rate ceiling (csv/json/hl7 land on it
  byte-identically on q2mod); a cell is a lower bound when ≥ 5 of 10 queries run ≥ 85 % of it → the →csv output column.
  The csv→json Par deficit is NOT the wall but the field-wise output serializer's store-queue stall ceiling (~21–30 GB/s
  of output bytes); only the lazy-input × csv-output coalesced raw-forward path escapes (`OUTPUT_PLATEAU_PROBE_RESULTS.md`).
- **Selectivities.** Q_ex matches 220 of 31.3 M rows (channel "google" 20 % × 2 hottest ids × price < 1e6; the frozen
  0.1–1 % band is unreachable on this id distribution); q2-og's classic NEXMark ids match ~0 rows — the 5-way OR still
  evaluates per row, which is the regime's point.
- **r_base is a fair-codec baseline**: SequentialUncompiled* input (SIMD index, interpreted parse-all loop) + sink-side
  legacy writers with the same hardcoded fast codecs (byte-identical output); the interpreted rung materialises full records.
- The W-sweep values hardcoded in the original 2026-08-06 script are asserted against the DB export (within 0.2 %).
