# E02 — Why the parallel rung pays q14 16.9× and q0 only 6.1× (two-factor law for r7/r6b)

**Claim in the paper.** The r6b→r7 multiplier of the ablation ladder (E01) is a ratio "23-worker ceiling / 1-worker
per-row cost". q14 and q0 have 1-worker rates within 3 % (2579 vs 2664 MB/s) yet differ 2.75× in the multiplier; 96.8 %
of that difference is the W23 numerator. q0 (`SELECT *` → JSON, 1.55 output bytes per input byte) saturates the
field-wise JSON serializer from 12 workers on (25.4 GB/s of output, per-worker row rate collapses 3.7×); q14 (range filter,
3 numeric output columns, 0.14 output bytes per input byte) scales at 73 % of linear and is still gaining at 23 workers.
The parallel CSV formatter / sequence shredder is NOT the differentiator (identical buffer geometry, measured
query-independent, 1.00× / 0.95× at one worker).

**Machine.** Threadripper PRO 5965WX, `cmake-build-release` worker of 2026-10-05 (`b5d757c9f6` + the overlay that is
now committed at tag `piparse-artifact-v1`), idle box, 2026-10-06 18:17–18:36.

**Measured with.** pbench `experiments/wsweep_q14_vs_q0_parrung.yaml` (smoke: `_smoke.yaml`), run_group
**`20261006T181751-4298f356`** (72/72, 0 failed; smoke `20261006T181655-8eddef1b`, 4/4). Config = the r7 cell verbatim:
InMemory prefill `NES_INMEM_REPEAT=20` (true = reported × 20), `NES_INMEM_BUFSIZE=131072`, SIMDCSV `PARALLEL`,
fnattr + `inline_invoke_calls` + `trace_constant_bytes`, 128 KiB operator buffers, ccx/pin off, 1 io thread, Monitoring sink.
Arms `q14_json`, `q0_json` over W ∈ {1,2,4,8,12,16,20,23}; `q14_native`, `q0_native` (NATIVE output = no field-wise text
serialization) over W ∈ {1,8,16,23}; 3 reps, median.

## Files

| path | what |
| --- | --- |
| `yaml/experiments/wsweep_q14_vs_q0_parrung{,_smoke}.yaml`, `yaml/queries/nexmark/matrix/bidstr_{q0,q14}.yaml` | exact experiment + query definitions |
| `data/wsweep_q14_vs_q0.csv` | medians per arm × W: reported and true MB/s, true Mrows/s, per-worker Mrows/s, scale vs W1, p50/p99 µs, window, rep spread (written by `extract.py`) |
| `expected/PAR_RUNG_Q14_VS_Q0_2026-10-06.md` | the result doc: §2 decomposition over all 10 queries (output-byte model), §3 shredder ruled out, §4 the probe tables, §6 paper-safe statement, §7 what is NOT established |
| `expected/wsweep_q14_vs_q0.{png,svg}` | reference rendering of the probe (no figure existed before the artifact; the paper cites the §4 tables) |
| `extract.py` | DB → `data/wsweep_q14_vs_q0.csv` (applies the ×20) |
| `make_figure.py` | two panels: true input GB/s vs W (with the 21–30 GB/s output-plateau band mapped through q0's 1.55 B/B) and per-worker Mrows/s vs W |
| `run.sh` | re-measure (`--smoke` for the 4-run variant) |

## Reproduce from the shipped data (seconds)

```
python3 extract.py          # out/wsweep_q14_vs_q0.csv from ../../results/tr/piparse_bench.duckdb
python3 make_figure.py      # out/wsweep_q14_vs_q0.{png,svg} from data/wsweep_q14_vs_q0.csv
```

Verified 2026-10-12: the extracted true MB/s, scale and per-worker Mrows/s match the doc's §4.1/§4.2 tables exactly
(q0_json 2671 … 16538 MB/s, per-worker 23.26 → 6.26; q14_json 2454 … 43580, 21.36 → 16.50; natives 1344/9906/18382/21705
and 2442/17898/34488/46143).

## Re-measure (18 min, Threadripper)

```
./run.sh            # or ./run.sh --smoke (< 1 min)
python3 extract.py --run-group <new id> --out out/wsweep_q14_vs_q0.csv && python3 make_figure.py --csv out/wsweep_q14_vs_q0.csv
```

Drift observed between the ladder's r7 cell (2026-08-24) and this probe (2026-10-06): q0 +1.0 %, q14 +0.1 %.

## Caveats / provenance notes

- The probe's W1 point is **not** the ladder's r6b: it keeps SIMDCSV `PARALLEL` at one worker, whereas r6b is
  `SequentialCSV`/`SEQUENTIAL` (q0 1.00×, q14 0.95× between the two at W1 — §5 of the doc).
- The §2.2 table of the doc (output bytes per row, out GB/s for all 10 queries) uses the E01 v7 ladder CSV plus an
  output-byte model replayed over a 1.75 M-row sample of the data (pbench scratchpad `outbytes.py` / `allq.py`, not
  shipped — the model is anchored to an independently measured 178 B/row for q0 within 0.6 %). Output bytes are modelled,
  not captured from the sink (the Monitoring sink is void).
- The store-stall mechanism for q0 is cited from the 2026-08-06 perf-counter probe (`OUTPUT_PLATEAU_PROBE_RESULTS.md`,
  E11 context), not re-measured here; q14's limiter ("per-row CPU at 23 of 24 cores") is identified by elimination, no
  counters were taken.
- q14_json @W23 has the shortest window (1.65 s) and the largest rep spread (4.0 %); its W20 point tells the same story.
- **PAPER POLICY (author, 2026-10-12): lazy overloads ON for id comparisons.** This W sweep ran with `overload: false` (both queries are output/compute shapes without an id comparison, so the knob does not change their numbers).
