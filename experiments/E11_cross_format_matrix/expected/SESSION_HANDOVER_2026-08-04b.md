# Session handover 2026-08-04b — workload-shape validation systests + serialize-into-concat fallback

Branch `benchmark-piparse-lazyparse-fast-csv`, working tree on top of cbf156f20c (prior
session's 4 sequential/uncompiled plugins still UNCOMMITTED underneath). This session
executed items 1–3 of SESSION_HANDOVER_2026-08-04.md's NEXT-SESSION list: the paper-workload
query shapes as systests through all three rungs per format, the `%` spelling, and the q10
datetime question. **All 54 workload-shape queries pass** (4 formats x 3 rungs). One real
engine gap fell out and was FIXED (see below). Everything UNCOMMITTED.

## Answers to the three open questions

1. **CONCAT-of-numeric on the uncompiled rung was indeed missing** — exactly the predicted
   risk. `CONCAT(VARSIZED("..."), price)` on any SequentialUncompiled* formatter failed with
   error 2020 "Cannot cast VariableSizedData to anything else": `VarVal::castToType(VARSIZED)`
   handled lazy values (raw-text forward) and materialised VariableSizedData (single-span
   view) but had NO case for a materialised numeric — which is what the interpreted formatter
   produces. **FIX = the serialize-into-concat fallback** in
   `nes-physical-operators/src/Functions/ConcatPhysicalFunction.cpp`: `withTextForm()`
   normalises each operand before the rope machinery — trace-time `customVisit` dispatch; a
   materialised numeric is serialized into the arena (`arena.allocateMemory(cap)` +
   `nautilus::invoke(serializeNumericText<T>)`) and wrapped as `VariableSizedData{ptr, len}`.
   Codecs are sink-byte-identical: `formatFloat` (fixed-6, zeros stripped, explicit float/
   double instantiations in nes-common) + `std::to_chars` integers. Lazy operands and
   materialised VariableSizedData pass through untouched, so ALL compiled-path behavior
   (raw-text verbatim forward, rope flatten, ConcatCast semantics) is unchanged —
   function/varsized suite green. Pattern copied from CastFromUnixTimestampPhysicalFunction.
   String-eq on materialised varsized (the other risk) worked out of the box
   (UncompiledSelection_Equals already covered it).
2. **`%` works directly** — AntlrSQLLexer::PERCENT -> ModuloLogicalFunction
   (AntlrSQLQueryPlanCreator.cpp:320). `auctionId % UINT64(123) == UINT64(0)` validated on
   all 3 CSV rungs.
3. **q10 datetime = `CASTFROMUNIXTS(ts)`** (UINT64 ms -> `1970-01-01T00:00:01.000Z`), and the
   civil_from_days rewrite **IS committed on this branch** (29e213ba09 "perf(physical-
   operators): hand-rolled ISO-8601 for CASTFROMUNIXTS") — the paper states the fast codec
   was active on every rung. Validated on all 3 CSV rungs.

## What was added (all UNCOMMITTED, on top of the prior session's plugin work)

| file | what |
| --- | --- |
| nes-physical-operators/src/Functions/ConcatPhysicalFunction.cpp | the serialize-into-concat fallback (only engine change) |
| nes-systests/formatter/WorkloadShapesCSV.test | 18 queries: q_project/q_route/q22/Q_ex/q2-mod/q10 x 3 rungs (SequentialUncompiledCSV, SequentialCSV, SIMDCSV) |
| nes-systests/formatter/SchemaJSON/WorkloadShapesSchemaJSON.test | 12: the 4 shapes x 3 rungs, 512B buffers (spanning) |
| nes-systests/formatter/HL7/WorkloadShapesHL7.test | 12: same over bid_10.hl7 (23 leaves: 15 header + seg + 6 data + pad) |
| nes-systests/formatter/XML/WorkloadShapesXML.test | 12: same via HL7-indexer XML config over bid_10.xml (F=6 -> arity 29, values at 4f+5) |
| nes-systests/testdata/small/{hl7,xml}/generate_fixtures.py + bid_10.{hl7,xml} | bid_strings-shaped 10-row fixtures |

Fixture data design (same rows in all 4 formats, inline for CSV/JSON): prices are exact
binary fractions in shortest text form (1.5, 3.375, ...) so the lazy raw-text forward and
materialise-then-serialize agree byte-for-byte across rungs (ConcatCast.test documents that
lazy forwards "12.50" verbatim — a materialised 12.50 would re-serialize as "12.5"; the
fixture sidesteps this by construction). Q_ex predicate legs each discriminate on some row
(row 3 fails only channel, row 4 only price, row 5 only auctionId; rows 1/6/8 match);
auctionId 984 = 8*123 feeds q2-mod.

## Validation state

- 54/54 workload-shape queries PASS (the 4 files above).
- Regressions: formatter dir 174/178 (only the 4 documented pre-existing MalformedStrings),
  function/varsized ALL PASS (concat semantics unchanged), operator/projection + tuples ALL
  PASS. operator/selection 43/45 — 2 PRE-EXISTING failures, unrelated to this session
  (SelectionNull:11 = NULL-comparison semantics mismatch; SequentialUncompiledOldCSVFloatFilter:1
  = Old scalar parser float-precision drift; neither query contains CONCAT and the only
  engine change is inside ConcatPhysicalFunction::execute). Not investigated further.
- Format gate: clean on all touched files (branch-wide pre-existing findings remain, see
  SESSION_HANDOVER_2026-08-01.md item 2).

## Gotchas (new this session)

- **Systest names collide by FILE BASENAME across directories**: three files named
  WorkloadShapes.test (SchemaJSON/, HL7/, XML/) crash a whole-directory run with
  "2035, query already registered" — hence the WorkloadShapes<Format>.test names.
- **New testdata files need a cmake reconfigure** to be linked into
  {build}/nes-systests/testdata (ExternalData RECURSE glob is configure-time). This session
  hand-copied bid_10.{hl7,xml} into cmake-build-release; a fresh configure picks them up.
  Symptom otherwise: "Could not determine absolute pathname ... bid_10.hl7" + the systest
  binary then SIGSEGVs in asio teardown (source-open-failure fragility, known shape).
- A query whose TRACE throws (like the pre-fix Q_ex) can SIGSEGV the systest binary in
  nautilus TagRecorder/Trie under CONCURRENT compilation (default -n 6); the same query
  fails cleanly under --sequential. Surfaced once, gone after the fix; engine fragility
  worth remembering when a whole systest run dies without a failure list.
- CASTFROMUNIXTS input must be UINT64 (ms); wrong input type = Error 2006 at type inference.

## PART 2 (same day, after the figure discussion): XML output + gates + InMemory probe

The user reframed figure 1 as INPUT x OUTPUT (16 cells x {Total, Compilation, Parallelization}
= 48 displayed values; raw grid = 16 combos x 10 queries x 3 rungs = 480 runs) and approved
three precursors (explicitly NOT the 480-run matrix itself — that needs separate consent):

**1. Packed-XML OUTPUT as HL7-output-formatter config — PROVEN (systests, first run green).**
The emission model (prologue = frame_start+header+seg_delim+seg_name+field_delim, one
separator, suffix = seg_delim+frame_end) expresses per-field XML tags as:
FRAME_START `<rec>`, MESSAGE_HEADER '', SEGMENT_DELIMITER '', SEGMENT_NAME `<f>`,
FIELD_DELIMITER `</f><f>`, FRAME_END `</f></rec>\n` -> well-formed
`<rec><f></f><f>v1</f>...<f>vn</f></rec>` with a leading EMPTY arity-pad element (the
prologue's field_delimiter closes it; the price of a single separator string). NULL -> empty
element. Tests: formatter/XML/XMLOutput.test (literal expected XML incl. float raw-forward
120.25 verbatim + NULL) and XMLRoundTrip.test (uniform-tag fixture two_ints_uniform_10.xml
-> XML-config input -> XML-config output BYTE-IDENTICAL; checksum 10 26248 = the fixture's
own newline-count/byte-sum, both HL7 + SIMDHL7 indexers). The 16-cell table's output column
is now complete: CSV, JSON, HL7, XML all have proven output formatters.

**2. Checksum gates 8/8 GREEN** — Sequential{CSV,SchemaJSON,HL7,HL7+XML} and
SequentialUncompiled{same} all reproduce **31300000,269477267979** over bid_strings_3GB at
full scale (~17-35s each). Yamls: ~/work/piparse-bench/scripts/gates_sequential/*.yaml
(generated from the proven parallel gate templates; BlockingFile + threading_mode SEQUENTIAL;
nes-cli yaml schema fields default NOT_NULLABLE = exactly what the uncompiled rung needs).
BONUS anchor measured for the matrix: **q2-mod full-scale = 257350,246669329**
(auctionId % 123 = 0, ~0.82% selectivity; gates_sequential/bid_q2mod_probe.yaml).

**3. InMemory W16 probe — BOTH questions answered:**
- Repeat knob EXISTS: `NES_INMEM_REPEAT=N` env (works in prefill AND blob mode; replays
  back-to-back, runner counts file bytes once -> true = reported x N). Plus
  NES_INMEM_PREFILL=1 / NES_INMEM_BUFSIZE. 3.6GB x20 = 72GB windows of 3-7s. 9/9 runs clean.
- One InMemory source is NOT the wall: W16 SIMDCSV true throughputs (x20-corrected, 3-rep
  medians) — bidstr_iso_pass (NATIVE out) 10.4 GB/s, bid_strings_passthrough (csv->csv)
  10.7 GB/s, bidstr_iso_q2 (filter, tiny out) **24.5 GB/s** -> query-DEPENDENT (2.3x spread)
  = engine-bound; source hand-out sustains >=24.5 GB/s into 16 workers. Even the heaviest
  observed cell (10.7) sits below the 11.3 GB/s file wall, so wall-clipping (the dagger) may
  bind less than feared. Experiment: ~/work/piparse-bench/experiments/inmem_w16_probe.yaml.

**PBENCH GOTCHA that burned ~40 min (memorize):** the bidstr_iso_* query-catalog entries
name their data representations `json`/`csv`/`native` (NOT `large`); `data_size` SELECTS the
entry, and an unknown value silently falls back to the FIRST (json) -> JSON bytes into the
CSV parser -> "cannot format malformed string value; fast integer parse" from FastINT32's
full-field-consumption check + shredder validate errors at teardown. Looks EXACTLY like an
engine corruption bug; is a config-resolution bug. Diagnosis path that settled it: the same
SQL through scripts/hl7/run_checksum_gate.sh (engine defaults) was clean; the rendered
/tmp/pbench_q_*.yaml showed the .json path. Fix comment now lives in inmem_w16_probe.yaml.
(Also: a root-owned nes-single-node-worker has been squatting on 127.0.0.1:8080 since
Jul 16 — not ours, left alone; use --worker-port 9099.)

**STATEFUL RE-VERIFICATION DONE (item 6, same session):** all 3 paper stateful queries run
clean on the current tip AND are COUNT-EXACT against the 2026-07-14 anchors (Checksum-sink
reruns): ysb_1k_varsized 68000 @ data_size large (268000 on xlarge = the 4x tiling,
consistent), q8_join 10999751, cm_q2 3094778. Throughputs (W16, 1 rep, Monitoring):
q8 283 MB/s (was 291), ysb_1k_var 9367 (was 10674, single-rep variance), cm_q2 699
(was 319 — 2.2x FASTER than the head-to-head era; consistent with the sg1 rolling-agg lock
fix 95b575b93b + later perf work landing since). Experiment yamls:
experiments/stateful_reverify_{tip,counts,ysb_large}.yaml. Protocol honored: event-time over
files, generator.repeat=1, q8 stateful pool, TracedBOOL.

## PART 3: the 3-CELL SANITY PROBE (user-approved; diagonal csv->csv, json->json, hl7->hl7)

5 regime-representative queries (passthrough=output, project=projection, q2mod=filter,
q1=compute, concat=string; mixed/Q_ex excluded) x 3 rungs x 2 reps. r_base ran BOTH output
arms where possible (compiled cell-format output = consistent baseline; sink LEGACY
interpreted writer = fully-interpreted baseline; legacy exists ONLY for CSV/JSON).
Machinery: experiments/cell_{csv_csv,json_json,hl7_hl7}.yaml + new catalog entries
bidstr_project_price / bid_hl7_project_price / bid_hl7_concat_alert (+ csv/json data entries
added to bid_strings_passthrough + concat_alert; hl7 junk leaves patched not_null for the
uncompiled rung). Cell math: scratchpad cells_math.py over the run log; r_par TRUE = x20.

**RESULTS (geomean over 5 queries; Comp x Par = Total, compiled-output baseline):**
| cell | Comp | Par | Total | (legacy baseline: Comp/Total) |
| --- | --- | --- | --- | --- |
| csv->csv   |  6.5 | 6.5 | 42.1 | 6.1 / 39.7 (WASH) |
| json->json |  3.7 | 7.3 | 27.0 | 6.7 / 48.9 (**1.8x swing**) |
| hl7->hl7   | 10.6 | 6.6 | 69.7 | n/a |

Reads: (1) **Parallelization is format/query-independent** (6.1-7.6 everywhere) — the
figure's predicted law holds. (2) **Compilation carries the format story**: hl7 10.6x (the
uncompiled rung parses ALL 22 leaves — r_base is a flat ~270-330 MB/s regardless of query —
while compiled rungs touch only projected leaves), csv 6.5x, json 3.7x-on-compiled-baseline.
(3) Amdahl within-cell: csv Comp spans 4.2 (q1) to 10.2 (passthrough) tracking
(de)serialization share. (4) **The r-base output fork is now quantified**: CSV legacy writer
== compiled CSV output (wash), but the JSON legacy writer is 2-2.4x SLOWER than compiled
JSON output -> "legacy where exists" would inflate json cells 1.8x vs csv cells ~0 =
row-inconsistent. Options: (b) compiled-output-everywhere (consistent, input-side-only
Compilation = conservative), or (c) implement legacy HL7/XML sink writers (nes-sinks
SinksParsing, JSONFormat-like; makes r-base fully interpreted everywhere and lets the
Compilation factor include output-side gains). USER DECIDES before the matrix.
(5) r_par true rates 16.6-27 GB/s — 5+ cells sit ABOVE the 11.3 GB/s file wall ->
**InMemory for r-par is validated by data**. (6) MB/s is per-format bytes: fine for
within-cell ratios, NOT cross-cell row-fair (use Mrows/s for cross-format absolutes).
(7) Wall-clock: 116 probe runs ~25 min -> full 1440-run matrix (16 cells x 10 q x 3 rungs
x 3 reps) ~= 4-5 h, or ~3 h at 2 reps. Overnight-comfortable.

Gotchas (new): pbench sink_schema names computed ALIASES unprefixed (`alert`, NOT
`bid.alert`) — a `bid.alert` entry fails at nes-cli submit (exit 1, silent reason); the
inmem_w16_probe variant "passthrough_csv" actually ran NATIVE output (defaults leak) — its
10.7 GB/s was parse-to-native, csv->csv passthrough with real CSV out = 26.9 GB/s true.

**DECISION (user, 2026-08-04): fully-interpreted baseline — build legacy output formatters
for ALL 4 formats** (add HL7Format to nes-sinks/SinksParsing, XML as a config of it,
mirroring the compiled-side packed-XML trick; CSV/JSON already exist). The user smelled an
issue in the CSV wash ("shouldn't only the compiled output be able to passthrough?") —
RESOLVED by code + data: the coalesced/raw-forward passthrough (tryWriteCoalescedRun +
writeEachChunk) is hard-gated on LAZY values, and on the r_base rung the UNCOMPILED INPUT
materializes every field, so passthrough cannot fire on EITHER r_base output arm (it is a
lazy-input x compiled-output conjunction — visible as r_comp passthrough 4216 vs q1 2134).
The csv wash = both arms doing materialize->serialize with baseline codecs; json's 2.2-2.4x
legacy penalty shows the probe IS sensitive where a real difference exists.

## PART 4: LEGACY WRITERS AT THE FAIR-CODEC STANDARD — DONE (user: "hardcode the best
## parsers there for a fair comparison")

Discovery that reframed it: **legacy CSVFormat was ALREADY at that standard** (to_chars ints
+ zmij shortest floats + direct scratch-buffer writes — its own comment says "fast
serializers") — which is WHY the csv legacy arm was a wash. JSONFormat was the outlier
(fmt::format per field + stringstream per row = the 2.2-2.4x penalty). Work landed
(UNCOMMITTED, on top of everything else):
- **JSONFormat REWRITTEN** to the CSVFormat standard: prebuilt `{"NAME":`/`,"NAME":` glue
  (names JSON-escaped at construction), lowercase `null`, RFC 8259 escape-scan with clean
  fast path, to_chars/zmij codecs, direct buffer writes.
- **HL7Format NEW** (nes-sinks/SinksParsing/HL7Format.{hpp,cpp}): compiled-HL7 emission model
  (prologue/fieldDelimiter/suffix, NULL -> zero bytes, varsized verbatim), fast codecs.
  Config = PRESETS keyed by the legacy_output_format string ("HL7" = compiled defaults MLLP;
  "XML" = the packed preset `<rec><f></f><f>` / `</f><f>` / `</f></rec>\n` incl. arity pad)
  — no config plumbing on purpose; config-generality is the compiled formatter's claim.
- Factories: FileSink + MonitoringSink + ChecksumSink dispatch HL7/XML (+JSON in Checksum).
  **ChecksumSink had a "very hacky" validateAndFormat that FORCE-REWROTE any non-None legacy
  format to "CSV"** — fixed to normalize-and-preserve (this is why all historic gates
  materialized CSV regardless; existing gates unaffected — they asked for CSV).
- pbench renderer: HL7Uncompiled/XMLUncompiled -> NATIVE + legacy HL7/XML mappings.

**zmij notation discovery:** zmij (== ZMIJF64) emits Ryu-STYLE ALWAYS-SCIENTIFIC shortest
("1.5e+00"), NOT fixed "1.5" — the compiled DEFAULT codec (fixed-6-stripped) does NOT match
it byte-wise. Matrix convention (already planned, now load-bearing): compiled rungs ALWAYS
run ZMIJF64 -> legacy == compiled byte-identical. CSV-sink systest comparisons are TYPED for
floats (stod both sides) so scientific-vs-fixed WASHES there — literal-text (JSON/XML) and
checksum comparisons are the real byte-identity enforcement.

**formatter/LegacyOutputByteIdentity.test — 8/8 PASS**: compiled-vs-legacy pairs for
CSV/JSON/XML (literal text incl. NULL + escape case) and HL7 (checksum 0 19198 = hand-built
wire bytes, not run-seeded). Full formatter dir: 182/186 (the 4 pre-existing
MalformedStrings). Format gate clean on touched files.

**CORRECTED 3-cell table (fully-interpreted baseline, fair codecs everywhere; geomeans):**
| cell | Comp | Par | Total |
| --- | --- | --- | --- |
| csv->csv   |  6.1 | 6.5 | 39.7 |
| json->json |  3.5 | 7.3 | 25.5 |
| hl7->hl7   | 10.4 | 6.6 | 68.3 |
The JSON correction is the headline: the old slow legacy writer would have inflated json's
Comp to 6.7 (Total 49) — a ~2x strawman in a whole row. The upgraded JSON legacy is now
FASTER than r_base-with-compiled-DEFAULT-codec output (e.g. q1 822 vs 683 MB/s): interpreted
glue + fair codecs beats compiled glue + slow codecs. HL7 barely moved (10.6 -> 10.4,
input-bound baseline); CSV unchanged. Experiments: cell_json_legacy_rerun.yaml +
cell_hl7_legacy.yaml; cell_hl7_hl7.yaml now carries the legacy series for full runs.

## PART 5: WORKER-COUNT SWEEP (machine = TR PRO 5965WX: 24 cores in 4 CCXs of 6, SMT 48)

W16 was leaving ~60% on the table. Sweeps (InMemory prefill, r-par config, 2 reps; reported
MB/s, x20 = true; experiments worker_count_sweep{,2,3}.yaml):
- iso_q2 (cheap filter, NATIVE out): W8 614 / W12 933 / W16 1222 / W20 1486 / W22 1620 /
  W24 ~1630 / W32 1852 / **W48 2031** -> W48/W16 = 1.66x; true 40.6 GB/s.
- csv->csv passthrough (CSV out): W16 1348 (== the cell run's 1346, cross-validation) /
  W20 1612 / W22 1757 / W24 1808 / W32 2011 / **W48 2198** -> 1.63x; true 44.0 GB/s.
Findings: monotone EVERYWHERE — no cliff at 24 (the pinned source thread coexists fine, the
feared runnable>cores collapse did not appear on InMemory), and **SMT adds +22-27% over W24**
(consistent with the memory-stall-IPC ceiling — SMT hides stalls). Run-to-run variance ~5% at 2 reps.
**DECISION (user): W23 = 23 workers + 1 source thread on 24 physical cores, nothing
oversubscribed; never exceed physical cores (SMT gains +22-27% exist but conflate
stall-hiding with the parallelization lever).** W23 measured == W24 within noise (iso_q2
1652 vs ~1630; passthrough-CSVout 1769 vs 1808; hl7 passthrough W24 1119 vs W23 1120 in the
cell reruns). Scaling story for the paper: ~90% incremental efficiency to 24 cores,
format/query-independent -> the transferable law; the sweep curve is the generalization
evidence for deployments with fewer cores; W22==W24 within 3% = reserving cores for ingest
is nearly free. PAPER_WORKLOAD.md rung table AMENDED to W23 (user-directed). NOTE the
sweep1 passthrough variant inherited NATIVE output from the probe template (same
defaults-leak trap as inmem_w16_probe — sweep2/3 fixed it with an explicit override).

**FINAL LOCKED 3-CELL TABLE (fair-codec interpreted baseline, r-par W23; geomeans):**
| cell | Comp | Par | Total |
| --- | --- | --- | --- |
| csv->csv   |  6.1 | 8.5 | 52.3 |
| json->json |  3.5 | 9.8 | 34.3 |
| hl7->hl7   | 10.4 | 8.5 | 87.7 |
Par band 8.5-9.8 (json slightly higher — its W1 compiled rung is stage-1-floor-bound, which
parallelizes perfectly). Experiments cell_*_rpar_w23.yaml; r_par(W23) raw MB/s in
scratchpad rpar_w23.log; the full-cell yamls (cell_csv_csv/json_json/hl7_hl7.yaml) still say
W16 in their r_par series — UPDATE to 23 before the matrix.

## Next

- (DONE) r-par worker count LOCKED at W23; spec amended; 3-cell r_par arms re-run.
- Update the cell_*.yaml r_par series from W16 to W23 before reusing them for the matrix.
- The full matrix (16 in/out combos x 10 queries x 3 rungs, ~1440 runs + legacy arms,
  ~4-5 h): ALL machinery now proven (formatters both sides, gates, InMemory, cell math,
  baseline convention = fully-interpreted fair-codec legacy output + ZMIJ compiled rungs);
  needs (a) catalog entries for the remaining queries/formats (q0 SELECT *, q_route, q2-og,
  q10, q14, Q_ex per format + the 12 off-diagonal output combos), (b) EXPLICIT USER CONSENT
  for the run.
- Figure 2 combo choice: deferred post-data (lean: the in=out diagonal; HOSP reading HL7->HL7).
- Proposed (not yet approved): one-line PAPER_WORKLOAD.md §1 edit pinning rows=input format,
  columns=output format.

Memory: [[cross-format-ablation-baselines]] updated. Companion: SESSION_HANDOVER_2026-08-04.md
(the plugin/session context this one builds on), ../PAPER_WORKLOAD.md (frozen workload).


## PART 6 (2026-08-04 22:37 -> 08-06): THE MATRIX ITSELF — v1, the pathology, v2, the wall

Chronology (full detail + tables: MATRIX_RESULTS_2026-08-05.md; every number regenerable
from benchmark/matrix_2026-08-05/):
1. **Matrix v1 run** (user-consented): 1440/1440, 0 failures, 4h07m. Machinery generated:
   30 catalog entries queries/nexmark/matrix/ (incl. the NEW xml 29-leaf family; Q_ex
   constants measured from data — channel LOWERCASE "google", A/B=885300/213300, 220
   matched rows), 16 experiments/matrix/cell_*.yaml. Raw archive matrix_2026-08-05/
   (per-run parquet/csv + duckdb snapshot + monitoring-dir tarball + README).
2. **Main figure built** (plot_matrix_figure.py, dataviz-palette 4x4, cell = Total over
   Comp|Par, sequential-blue magnitude, per-row Mrows/s anchors).
3. **User probing "why is Par capped at 9-10x / lower for csv" EXPOSED A ~2x MEASUREMENT
   PATHOLOGY**: ccx_aware_task_queues+pin_threads (the historical r-par config) is broken
   for SINGLE-source runs (sequence-ordered buffers round-robin across CCX cell queues,
   spanning coordination straddles cells, pinned workers can't migrate). 2x2 toggle proof:
   W23 q2mod 14.3 Mrows/s (ccxON+pinON) vs 27-28.5 (any other combo); fingerprint = the
   W1->W4 per-worker collapse exists ONLY in that combo. Probes: par_w1_decomposition,
   par_lowW_ccx_pin, par_ccx_pin_q0, fixprobe_{json,hl7,xml} (fix is ~2.1x on filter-class
   everywhere; +1-18% on heavy-parse passthrough = that was genuinely CPU-bound).
4. **v2 re-run** (user "go"): all 480 r_par arms at W23 + ccxOFF + pinOFF (16x 30/30, 0
   failures, 1h13m). Convention amended in PAPER_WORKLOAD + canonical yamls. V2 TABLE:
   Totals 50-224x (xml->csv 223.7 max); Comp UNCHANGED; Par 11.0-18.3 (v1's 7.6-9.9
   uniformity was partly the pathology's false ceiling).
5. **The memory wall measured**: ~65-68 GB/s aggregate wire ceiling at W23 — csv/json/hl7
   land on it BYTE-IDENTICALLY on q2mod (65.5/65.1/66.0 GB/s; W8->23 efficiency 72/82/77%
   ordered by proximity). Explains csv-in's lowest Par (clipped numerator / fastest W1
   denominator). **Figure daggers**: † = >=5/10 queries at >=85% of wall -> the ->csv
   OUTPUT column; filter-class queries touch the wall in every cell.

## Open items for the next session
- Fig-2 per-query companion (small multiples from the raw parquets; per-query daggers).
- Mrows/s absolute anchor treatment; e2e/latency arm with real sources.
- W-sweep/SMT conclusions re-derive under the healthy config if cited (measured under the
  pathology; healthy W8->23 = 72-82%).
- EVERYTHING STILL UNCOMMITTED on branch benchmark-piparse-lazyparse-fast-csv (sequential
  plugins, concat fallback, legacy writers + sink fixes, systests, fixtures) — commit
  session pending user direction.
