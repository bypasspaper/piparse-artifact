# ⚠️ V2 SUPERSEDES THE TABLE BELOW (2026-08-06): r_par re-measured after the ccx+pin fix

The original r_par rung ran ccx_aware_task_queues+pin_threads — a ~2x PATHOLOGY for
single-source runs (one source's sequence-ordered buffers round-robin across the 4 CCX cell
queues; spanning/shredder coordination straddles cells; pinned workers cannot migrate; found
2026-08-06 chasing "why is Par capped at 9-10x"; experiments par_w1_decomposition,
par_lowW_ccx_pin, par_ccx_pin_q0). **r_par convention now: W23 + ccx_aware=false +
pin_threads=false** (all three healthy combos within 4%; ccx+pin remains the MULTI-source
production config, proven in the N=1024 fragment-shredder work). All 480 r_par arms re-run
(30/30 x 16 cells, 0 failures, 1h13m); raw rows in matrix_2026-08-05/matrix_rpar_fixed_480.
{csv,parquet}; r_base/r_comp unchanged (W1, insensitive).

## THE 4x4 TABLE v2 (Total = Comp x Par; regime-stratified geomeans)

| in\out | csv | json | hl7 | xml |
| --- | --- | --- | --- | --- |
| **csv**  | **95.6** = 6.1 x 15.8 | **66.9** = 5.5 x 12.2 | **58.5** = 5.3 x 11.0 | **65.4** = 5.5 x 12.0 |
| **json** | **61.2** = 3.3 x 18.3 | **54.9** = 3.4 x 16.2 | **50.0** = 3.4 x 14.9 | **55.4** = 3.4 x 16.1 |
| **hl7**  | **170.2** = 10.3 x 16.6 | **148.8** = 10.0 x 14.9 | **138.5** = 10.3 x 13.4 | **151.0** = 10.3 x 14.6 |
| **xml**  | **223.7** = 13.2 x 17.0 | **193.2** = 12.7 x 15.2 | **178.4** = 12.9 x 13.9 | **196.6** = 13.2 x 14.9 |

## The laws, v2 (sharpened by the fix)

1. UNCHANGED: **Compilation is an input-format property** (rows constant across outputs;
   xml 13.2 > hl7 10.3 > csv 5.3-6.1 > json 3.4 — the elidable-junk vs irreducible-stage-1
   split). Comp was measured at W1 and never touched by the pathology.
2. REVISED: **Parallelization is 11.0-18.3 at W23** — higher and WIDER than v1's 7.6-9.9.
   The residual structure is real cost, not scheduling: Par is highest into the csv output
   column (15.8-18.3; cheap coalesced output) and lowest into hl7 (11.0-14.9), and highest
   for json input (slowest W1 denominator). "Roughly format-independent" weakens to: Par
   varies +-25% around ~15 while Comp varies 4x — parallelization is still by far the more
   uniform lever, but v1's near-perfect uniformity was partly an artifact of the pathology
   equalizing everything at a false ceiling.
3. AMPLIFIED: **Totals now span 50-224x** (was 31.5-124); xml->csv 223.7x.
3b. **THE MEMORY WALL + DAGGERS (2026-08-06b)**: at W23 (healthy config) there is a real
   ~65-68 GB/s aggregate WIRE-rate ceiling — csv/json/hl7 all land on it byte-identically on
   q2mod (65.5/65.1/66.0 GB/s; W8->23 efficiency 72/82/77% ordered by W8 proximity to it).
   Filter-class queries (q2mod/q2og/qex) touch the wall in EVERY cell; qproject/qroute/q0
   join progressively as per-byte work shrinks. DAGGER RULE (figure): cell = lower bound (†)
   when >= 5 of 10 queries run >= 85% of the wall (56 GB/s) -> the ->csv OUTPUT column
   (csv->csv 6/10, {json,hl7,xml}->csv 5/10). This — not an artifact — is why csv-IN Par is
   lowest: cheapest per-byte work -> clipped numerator over the fastest W1 denominator.
   Probes: w8probe_{json_json,hl7_hl7} + the 2x2's csv W8 point.
4. The v1 q0-convergence observation survives partially: json/hl7/xml passthrough was
   genuinely CPU-bound (+1-18% under the fix) while filter-class queries were
   scheduler-bound everywhere (~2.1x under the fix) — see the fixprobe_* experiments.

(The v1 table below is retained for the record; every v1 number is reproducible from
matrix_runs_all1440.parquet with series=r_par.)

# V1 (SUPERSEDED): The 16-cell input x output matrix — FULL RUN RESULTS (2026-08-05)

The paper's headline figure data. Run 2026-08-04 22:37 -> 2026-08-05 02:44 (4h07m),
**1440/1440 runs completed, 0 failures** (16 cells x 10 frozen workload queries x 3 rungs x
3 reps, median). Branch benchmark-piparse-lazyparse-fast-csv, uncommitted working tree
(sequential plugins + concat fallback + fair-codec legacy writers). Raw per-query data:
MATRIX_RESULTS_2026-08-05.json (perq = per-query Comp/Par/Total; raw = rung medians MB/s);
full run log matrix_run_2026-08-05.log.gz. Machinery: piparse-bench
experiments/matrix/cell_{in}_{out}.yaml + queries/nexmark/matrix/ (30 generated entries).

## Conventions (all locked this session, see SESSION_HANDOVER_2026-08-04b.md)

- r_base = fully-interpreted FAIR-CODEC baseline: SequentialUncompiled* input (SIMD indexer,
  interpreted parse-all loop) + sink-side legacy writer (to_chars/zmij hardcoded,
  byte-identical to compiled-with-ZMIJ), W1.
- r_comp = Sequential* compiled input, W1, full-opt JIT (fnattr+inline+tcb), fast parsers,
  ZMIJ out. r_par = parallel indexer, W23 (23 workers + 1 source thread = 24 physical
  cores), InMemory prefill, NES_INMEM_REPEAT=20 (TRUE = reported x20).
- Cell value = geomean of REGIME geomeans (output{q0} projection{qproject}
  filter{qroute,q2og,q2mod} compute{q1,q10,q14} string{q22} mixed{qex}).
  Comp = r_comp/r_base, Par = r_par*20/r_comp, Total = Comp x Par.

## THE 4x4 TABLE (rows = input format, columns = output format)

| in\out | csv | json | hl7 | xml |
| --- | --- | --- | --- | --- |
| **csv**  | **51.6** = 6.1 x 8.5 | **43.8** = 5.5 x 8.0 | **40.2** = 5.3 x 7.6 | **43.3** = 5.5 x 7.9 |
| **json** | **33.1** = 3.3 x 9.9 | **32.5** = 3.4 x 9.6 | **31.5** = 3.4 x 9.4 | **32.9** = 3.4 x 9.6 |
| **hl7**  | **94.4** = 10.3 x 9.2 | **89.2** = 10.0 x 8.9 | **88.7** = 10.3 x 8.6 | **92.0** = 10.3 x 8.9 |
| **xml**  | **123.7** = 13.2 x 9.4 | **116.2** = 12.7 x 9.2 | **113.8** = 12.9 x 8.9 | **120.3** = 13.2 x 9.1 |

(cell = Total = Comp x Par)

## The three laws the table shows

1. **Compilation is an INPUT-format property** — rows are near-constant across output
   columns (csv 5.3-6.1, json 3.3-3.4, hl7 10.0-10.3, xml 12.7-13.2) — and its magnitude
   is set by the format's ELIDABLE-vs-IRREDUCIBLE cost split: XML (23 junk of 29 leaves)
   13x > HL7 (16/22) 10x > CSV (no junk, cheap indexing) 6x > JSON (no junk but the
   irreducible simdjson stage-1 floor sits in both rungs of the ratio) 3.4x.
2. **Parallelization is format- AND output-independent**: 7.6-9.9 across all 16 cells
   (W23; ~90% incremental core-scaling efficiency per the worker sweep). The slight
   json-row elevation (9.4-9.9) = its W1 compiled rung is stage-1-floor-bound, which
   parallelizes perfectly.
3. **Total spans 31.5-124x** and factorizes cleanly; the biggest totals are the
   junk-heaviest inputs (xml->csv 123.7x) — compilation's laziness converts structural
   overhead into speedup.

## Per-query companion notes (from perq in the json)

- Range across all 160 (cell, query) pairs: Total 22.3 (json->csv q14) to 143.4
  (xml->json qproject); Comp 2.1 (json q14 — compute-heavy, both rungs pay the arithmetic)
  to 15.6 (xml qproject/qroute — junk elision + lazy projection).
- Within-cell Amdahl spread is the fig-2 story: e.g. csv->csv Comp runs 3.4 (q1) to 11.4
  (q0/passthrough-shaped), tracking the (de)serialization share.
- Diagonal reproduces the locked probe table within noise (51.6/32.5/88.7 vs
  52.3/34.3/87.7) — cross-validation of the whole pipeline.

## Caveats to carry into the paper

- Q_ex selectivity: 220 matched rows of 31.3M (channel "google" 20% x 2 hottest ids x
  price<1e6). The frozen 0.1-1% band is UNREACHABLE with 2 id-equalities on this flat id
  distribution (hottest id = 871 rows) — state the actual selectivity; the
  hot-path-is-the-filter purpose is fully served.
- q2-og's classic NEXMark ids (1007..2087) match ~0 rows on this dataset (id range starts
  at 1000 but those exact ids are rare) — the 5-way OR still evaluates per row, which is
  the regime's point (repeated parse under GVN).
- MB/s are per-format wire bytes: ratios within a cell are exact; cross-format ABSOLUTE
  comparisons need Mrows/s (raw medians are in the json; rows = 31.3M everywhere).
- InMemory x20 correction is uniform within every cell -> cancels in all ratios.
