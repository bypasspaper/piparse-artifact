# Sec.2 TEASER probes: Fig1 naive-vs-optimised CPU split + Fig2 v2 field-sweep smoke (2026-09-25)

Companion to `fig1_fig2_motivation_2026-08-19.md` (NES naive originals) and `fig1_fig2_flink_2026-09-03.md` (Flink).
Decision (2026-09-25): the Sec.2 figures become SIGMOD-style teasers -- Fig2 gains a NAIVE baseline + the fully
optimised (lazy passthrough) rung; Fig1 gains an "optimised" bar per query for q0 / q2 / YSB with a 3-segment taxonomy.
Scratch: `fig1_fig2_teaser_2026-09-25_scratch/` (scripts, pbench YAMLs, perf data gz, symbol dumps, CSVs, logs).
pbench experiments copied to `~/work/piparse-bench/experiments/fig1_opt_{prof_q0,prof_q2mod,prof_ysb,diff}.yaml`,
`fig2_fieldsweep_v2{,_smoke}.yaml`; new queries `queries/multicol/pass_n{1..10}.yaml` (all UNCOMMITTED in pbench).
Binary: `cmake-build-release` worker+nes-cli mtime 2026-09-03 10:50 = HEAD b5d757c9f6 + uncommitted lazy/eager/overload
knobs. `strings` does NOT find descriptor keys in it (not even `sequence_shredder_mode`) -> verify knobs by behaviour.
Machine: governor performance, idle; stray idle worker on :8080 (pid 3006, 71 d) does not interfere; pbench on :9099.

## Taxonomy (agreed with the author, goes in the caption)
- **deserialize** = converting input text into an engine representation: delimiter INDEX + value PARSE (incl. the
  naive arm's varsized copy into child buffers = conversion into the engine representation).
- **serialize** = producing output text: number formatting, JSON keys/punctuation/row framing, computed-field text.
- **process** = operator work incl. everything that MOVES or INSPECTS bytes without converting them: the raw passthrough
  copy input-span -> output buffer (a native-format engine would copy too), overload byte compares, hash/window/agg.
  Engine mechanics (task/buffer/emit glue) are folded into process and disclosed.
- No separate "index" segment (index is deserialization); one sentence in the text says what is left of deser.

## Fig1 TEASER -- naive (2026-08-19 profiles) vs optimised (this session)
`fig1_teaser_naive_vs_optimised_2026-09-25.{pdf,png}` + `_data.csv` (panel a = share, Mrows/s above bars, labels
staggered; panel b = TOTAL ns/row per arm on log, unstacked, speed-up annotated). Plot: `_scratch/plot_fig1_teaser.py`.

| query | arm | deser% | proc% | ser% | ns/row (1 busy thread) | Mrows/s |
|---|---|--:|--:|--:|--:|--:|
| q0 SELECT * | naive | 26.9 | 1.0 | 72.1 | 437 | 2.3 |
| q0 SELECT * | optimised | 27.7 | 46.8 | 25.5 | 11.6 | 86.1 (38x) |
| q2 filter 0.8% | naive | 97.0 | 1.5 | 1.5 | 151 | 6.6 |
| q2 filter 0.8% | optimised | 78.4 | 21.0 | 0.6 | 12.5 | 80.1 (12x) |
| YSB windowed count | naive | 93.2 | 6.8 | 0.0 | 500 | 2.0 |
| YSB windowed count | optimised | 58.9 | 40.6 | 0.4 | 29.0 | 34.5 (17x) |

**Optimised arm** = compiled `SequentialCSV` (threading_mode sequential), LAZY default (passthrough + lazy parse), fnattr,
fast codecs (`TracedUINT64/INT64/INT16/UINT32/UINT16, FastINT32, TracedBOOL, EiselFloatF64/F32` in; `ZMIJF64/F32` out),
`JSON` fast writer, InMemory prefill (read nulled), W1. Windows: q0 repeat 300 (bid_1GB, ~0.4 s/pass), q2 repeat 120,
YSB xlarge (80 M rows) SINGLE pass (replay corrupts event-time windows). perf flat 20 s @ 4 kHz (q0, q2); YSB = whole
worker lifetime @ 8 kHz then `window_report.sh` restricts the report to the busy 3.7 s query burst (the 2.3 s query is
too short for the attach-and-wait helper; the first two attempts sampled prefill only).

**Method findings that change the attribution (vs the naive arm):**
1. In the optimised sequential arm the WHOLE fused pipeline runs on the SOURCE thread (`DataSrc-2`): index kernel,
   JIT blocks, emit. `WorkerThread-0` is ~50% of samples but is IDLE SPIN (vdso clock_gettime, sched_yield, semaphore
   try_acquire_for backoff, kernel scheduler) -- excluded. The naive arm's thread split (DataSrc = deser, Worker =
   process+serialize) does NOT transfer; both threads are classified BY SYMBOL (`classify_v2.py`). Engine observation:
   a 1-worker deployment burns a full core spinning while the source thread does all the work.
2. JIT'd pipeline code is opaque (`[JIT] tid N` addresses, no perf map). libc memcpy is ~0% -> the passthrough copies
   are INLINED into the JIT block together with the JSON key/framing writes. The block is split by KNOB DIFFERENCING
   (`fig1_opt_diff.yaml`, 3 reps): `serialize_jit = ns(json lazy) - ns(csv lazy)` (csv output = ONE whole-row memmove,
   no per-field keys), remainder of the JIT block (scan glue + raw span copies + operator code) -> process.
3. `FastINT32` is a `NAUTILUS_TAGGED_INVOKE` native call (fast_float `from_chars_int_advanced` + `parseWithFastInt`),
   NOT fused: in q2 it is 27% of all samples = 54% of compute = ~6.7 ns/row for ONE int32 -- slow for an int parse.
4. Engine glue = 17% (q0) / 6% (q2) / 4% (YSB) of compute, folded into process.

**Differencing (`fig1_opt_diff`, medians of 3, InMemory W1; YSB = `large` 20 M rows single pass):**
| query | lazy ns/row | eager ns/row | csv-out lazy ns/row | lazy/eager | notes |
|---|--:|--:|--:|--:|---|
| q0 | 11.6 (2995 MB/s) | 68.3 (509) | 8.9 (3926; one rep 2507 outlier) | 5.88x | eager adds 56.7 ns parse+format; JSON framing 2.8 ns over whole-row copy |
| q2 | 12.5 (2787) | 37.6 (925) | 13.0 (2686) | 3.01x | eager parses 3 extra fields = +25 ns; framing ~0 (0.8% output) |
| YSB | 29.0 (6407) | 30.8 (6028) | 28.9 (6413) | 1.06x | parse is NOT the residual: the delimiter INDEX over 185 B/8-field rows is (38% of samples) |

**Per-query optimised split (raw % of all samples, busy threads; JIT split as above):**
- q0: index 14.4 (indexBandInto 12.0 + computeBlocksAvx2 2.2) | JIT 27.6 | engine 8.6 | ser 1.0 | proc 0.4; profiled
  2956 MB/s vs clean 2995 (-1.3%). -> 28 / 47 / 26.
- q2: index 13.2 + int parse 27.3 (fast_float 22.3 + parseWithFastInt 5.0) | JIT 6.9 | engine 2.6; profiled 2739 vs
  2787 (-1.7%). -> 78 / 21 / 1.
- YSB (busy window 3.7 s, 30 K samples; DataSrc 64% / Worker 35% mostly kernel spin): index 37.9 | JIT 18.4 (filter
  byte-compare + hash/agg code + the FUSED event_time u64 parse, <= ~4 ns, counted as process = small overstatement) |
  named process 5.5 (hashBytes 2.9, updateTimestamp, readVarVal) | engine 2.3; profiled 6176 vs 6407 (-3.6%).
  -> 59 / 41 / 0.

**Caveats to state:** JIT split is an estimate (differencing, csv-out vs json-out); YSB's JIT block contains the fused
event_time parse (deser) -- process share overstated by <= ~10 pp; engine glue folded into process; naive shares are
the 2026-08-19 profiles (different session, same frozen naive code path; q0 naive throughput 2.29 then vs -- not
re-measured now); throughput per row here is WALL/row with ONE busy thread = CPU/row (worker idle spin excluded).

## ENGINE BUG (new manifestation, OPEN): optimised YSB single pass SIGSEGVs ~30% of runs
`Caught signal SIGSEGV` in `NES::ChainedHashMap::updateTimestamp(Timestamp const&)` <- `NES::updateTimestamp(Timestamp,
HashMap*)` <- [JIT] <- `CompiledExecutablePipelineStage::execute` <- `emitFunction` <- `dataBlockingSourceRunner`
(i.e. the fused aggregation pipeline on the SOURCE thread), `repeat=1`, InMemory prefill, xlarge AND large, with and
WITHOUT perf attached (4 of ~14 runs: 60 s-profile run, diff ysb/lazy rep1, diff ysb/lazy_csvout one rep, whole-life
profile attempt). Eager arm 0/3 crashes (may be luck). Related to the known replay heap corruption
(`NES_FILE_REPEAT>1` into event-time windows, see cmysb memory) but this is SINGLE pass -- likely the same slice-state
race (worker-side trigger/GC vs source-side update). Surviving runs give consistent numbers (6399/6415/6176 MB/s).

## Fig2 v2 -- field sweep, three rungs + Flink: FULL SWEEP DONE (2026-09-25, 10 reps, 399/400)
`experiments/fig2_fieldsweep_v2.yaml`, run_group `20260925T172743-7bd023f8`, ~2.5 h. Queries `multicol/pass_n{1..10}`
= plain `SELECT c0..cN-1 FROM t` (sink_schema qualified `t.cN` -- unqualified fails nes-cli SILENTLY). Rungs:
naive (`SequentialUncompiledOldCSV`+`JSONUncompiled`+both codecs `original`, repeat 5), compiled_eager
(`eager_parse: true`, repeat 20), compiled_lazy (defaults, repeat 100 -> ~5 s windows), anchor `allf_nN` (repeat 20).
1 run lost (anchor allf_n10 rep 10 -- I ran `pkill -9 -x main` while it was still executing; 9 reps survive, median
unaffected). Figures: `fig2_v2_rowss_mbps_3rung_2026-09-25.*` (naive/eager/lazy/Flink, two panels rows/s + MB/s log),
`fig2_v2_rowss_mbps_teaser_2026-09-25.*` (--teaser: eager dropped), `fig2_v2_cpu_per_row_2026-09-25.*` (CPU ns/row).
Data `fig2_v2_rowss_mbps_2026-09-25_data.csv` (throughput medians) + `fig2_v2_cpu_per_row_2026-09-25_data.csv` (per-run
per-thread CPU). Scripts in `_scratch/` (plot_fig2_v2.py, plot_fig2_cpu.py, extract_fig2_v2.py, cpu_from_artifacts.py).

**Throughput (median n=10), MB/s / Mrows/s:**
| N | naive | eager | lazy | anchor(allf) | Flink(2026-09-03) |
|--:|--|--|--|--|--|
| 1 | 61.0 / 5.6 | 320 / 29.6 | 2688 / 247 | 327 / 30.0 | 33.8 / 3.10 |
| 5 | 72.6 / 1.68 | 314 / 5.75 | 3834 / 70.4 | 308 / 5.66 | 60.0 / 1.10 |
| 10 | 79.4 / 0.73 | 305 / 2.79 | 3964 / 36.4 | 303 / 2.78 | 74.7 / 0.69 |

**Cost laws ns/row = a + b*N (10 points, R2>=0.999):** naive 58.7 + 134.2N; eager -3.1 + 36.1N; lazy 1.0 + 2.7N;
anchor -5.0 + 36.8N. So per-FIELD wall cost: naive 134, eager/anchor ~36, lazy 2.7 ns -- lazy is ~13x cheaper/field
than eager and ~50x cheaper than naive; near-zero fixed term on all compiled rungs. **Gates ALL PASS:** anchor vs
2026-08-19 within +-3.2% every N (drift OK); eager/anchor 0.99-1.03 (eager_parse on plain SELECT reproduces the
`*FLOAT64(1)` trick); lazy/eager 8.4-13.0x. naive & Flink MB/s RISE with N (Flink-like); eager/anchor MB/s flat ~310;
lazy MB/s flat ~3900 (rises slightly 2688->3964, the ~1 ns/row fixed term). The OLD Fig2 NES line was the eager/anchor
arm = a partial sneak peek; the naive line is the honest motivation baseline, the lazy line is the teaser.

**CPU (median n=10), per-thread in the sink window (procfs sampler, see below):** cpu ns/row total (cores busy):
| N | naive | eager | lazy |
|--:|--|--|--|
| 1 | 281 (1.6c) | 46 (1.37c) | 8.0 (1.98c) |
| 5 | 1186 (1.61c) | 238 (1.33c) | 27 (1.91c) |
| 10 | 2297 (1.64c) | 470 (1.32c) | 53 (1.94c) |
Per-thread split (median cpu-s over the window): naive DataSrc ~8.3 + WorkerThread ~13 (BOTH do real work: parse on
source, naive JSON writer on worker); eager DataSrc ~12.8 (dominant) + Worker ~4.5; lazy DataSrc ~5 + Worker ~5.
**KEY CPU FINDING wall time hides:** lazy burns ~1.95 cores but only ~1 is real (DataSrc = the fused pipeline); the
WorkerThread ~1 core is IDLE SPIN (semaphore backoff / sched_yield, see the Fig1 profile) -- at W1 a full core is
wasted spinning, and the faster the source produces the more the worker spins (eager worker 0.33c vs lazy 1.0c).
So "CPU cost of the query" = DataSrc CPU (real work); total CPU/row includes the W1 spin overhead. The stored
per-thread series lets EITHER be plotted without re-running (panel b of the CPU figure stacks the naive threads).

## Fig2 STAGE CPU vs N -- deserialize / process / serialize, naive vs lazy (DONE 2026-09-25)
The author's requested CPU view (NOT per-thread: "we measured serialization, deserialization and processing overhead").
Method = the Fig1 teaser method applied to the field sweep: 20 perf profiles (naive + lazy, N=1..10, flat 15 s @ 4 kHz,
windows `_scratch/optprof_sweep/`, YAML templates there), classified by stage -- naive with the 2026-08-19 thread+symbol
rules (DataSrc = index+parse = deser; worker = naive JSON writer = ser; ops = proc), lazy with classify_v2 (index kernels
+ parse codecs = deser; ZMIJ/JSON writer = ser; memcpy/ops/engine = proc) and the opaque JIT block split by differencing
against `experiments/fig2_lazy_csvout.yaml` (30 runs: framing = ns(json) - ns(csv) -> ser, rest of JIT -> proc). Absolute
CPU/row = each profiled run's OWN procfs thread-CPU in its sink window x (1 - idle fraction); idle spin / kernel EXCLUDED
(lazy: ~47% of samples = the spinning worker). Script `stage_cpu_sweep.py` -> `fig2_v2_stage_cpu_naive_vs_lazy_2026-09-25_data.csv`,
plot `plot_fig2_stage.py` -> `fig2_v2_stage_cpu_naive_vs_lazy_2026-09-25.{pdf,png}` (a: naive stacked ns/row, b: lazy
stacked ns/row, c: shares side by side).

| N | naive deser/proc/ser ns (share %) | lazy deser/proc/ser ns (share %) |
|--:|---|---|
| 1 | 98 / 5 / 174 (36/2/63) | 1.1 / 3.2 / 0.1 (25/73/1) |
| 4 | 326 / 17 / 591 (35/2/63) | 4.2 / 6.0 / 1.9 (35/50/16) |
| 10 | 858 / 39 / 1329 (39/2/60) | 10.2 / 11.7 / 7.4 (35/40/25) |
Per-field CPU increments (N=1->10 slope): naive deser +84, ser +128, proc +4 ns/field; lazy deser (index) +1.0, proc
(copy+glue) +0.95, ser (JSON framing) +0.8 ns/field. Naive shares are flat in N (~36/2/62, all-float rows -> more
parse share than Fig1's mixed bid). Lazy: at N=1 the per-row fixed cost (engine glue + scan setup, "process") dominates;
from N>=4 the shares settle at ~35 deser / 40-45 proc / 16-25 ser -- i.e. what remains after bypass is INDEX (deser),
raw COPY + glue (proc) and JSON per-field FRAMING (ser), each ~1 ns/field, ~80-130x below naive per field. Lazy N=4
(35/50/16) matches the Fig1 q0 optimised bar (28/47/26) in shape. Profiled-run throughput within ~2% of the clean sweep.
LOG-AXIS VARIANT (2026-09-26, author request 'cpu per tuple with stage attribution'): `fig2_v2_stage_cpu_per_tuple_log_2026-09-26.*`
(`plot_fig2_stage_log.py`): (a) per N naive|lazy stacked bars on a LOG axis with totals (segments NOT to scale on log),
(b) six per-stage cost lines on the log axis (naive dashed, lazy solid) where magnitudes read correctly. Same data CSV.
CAVEATS: JIT split is differencing-based (csv-out vs json-out); the N=1 lazy framing came out 0 (csv-out no faster
than json at 1 field -> capped); naive unlabeled worker frames -> process (conservative, 2026-08-19 rule).

## Fig2 PROJECTION sweep -- SELECT c0 over N columns, naive / bypass / Flink (DONE 2026-09-26)
Author's request: the field sweep with ONE projected field (the 2026-08-12 `uncompiled_vs_compiled_fieldsweep` memory:
bypass degrades more slowly in rows/s because only the delimiter index grows with N). New queries
`queries/multicol/proj1_n{1..10}` (`SELECT c0 FROM t`, plain -> passthrough-eligible; sink `t.c0`; flink_sql identical),
experiments `fig2_proj1_nes.yaml` (naive repeat 5 + compiled_lazy repeat 300, 10 reps, run_group 20260926T101406,
200/200 OK) and `fig2_proj1_flink.yaml` (Flink 2.1.3 csv->json_blackhole, xlarge nf{N}_x10 2 GB, parallelism 1, 3 reps,
30/30 OK). Figure `fig2_proj1_rowss_mbps_3arm_2026-09-26.{pdf,png}` + `_data.csv`; script `_scratch/proj1_extract_plot.py`.

| N | naive MB/s / Mrows/s / ns | bypass MB/s / Mrows/s / ns | Flink MB/s / Mrows/s / ns |
|--:|---|---|---|
| 1 | 61.5 / 5.65 / 177 | 2698 / 247.7 / 4.0 | 31.0 / 2.84 / 352 |
| 5 | 133.9 / 2.46 / 407 | 6412 / 117.8 / 8.5 | 162.0 / 2.98 / 336 |
| 10 | 132.8 / 1.22 / 820 | 7603 / 69.8 / 14.3 | 199.0 / 1.83 / 547 |
Cost laws ns/row = a + bN: naive 45.9 + 75.8N (R2 0.99; N=1 is a DEGENERATE point, 177 vs 180 at N=2 -- a 1-column row
has no field delimiter and the old scalar indexer pays ~75 ns extra there, same in the full-projection sweep; from N>=2
the slope is ~76 ns/field = parse of every field, no pushdown); bypass 2.8 + 1.17N (R2 0.998) = the delimiter INDEX only
(vs 2.7 ns/field with all fields output: copy + JSON key gone); Flink 273 + 23.6N but NOT linear (R2 0.79): FLAT
~330-350 ns/row for N=1..5 (the ~330 ns per-row framework fixed cost hides tokenising <=5 columns), then ~45 ns/field
from N=5 to 10; Flink projection pushdown VERIFIED 2026-09-26 (`_scratch/flink_explain/explain.py`, Flink 2.1.3 EXPLAIN on the same
filesystem DDL): `TableSourceScan(..., project=[c0])` for BOTH `format=csv` and `format=json`; the jars confirm
`CsvFileFormatFactory$CsvBulkDecodingFormat`, `CsvFormatFactory$1`, `JsonFormatFactory$1` implement ProjectableDecodingFormat.
BUT the pushdown reaches only the CONVERTER: csv = Jackson MappingIterator<JsonNode> still tokenises EVERY column of
the line into a TextNode, then converts only c0 (parseDouble skipped for the rest); json = ObjectMapper.readTree of the
WHOLE document, then converts projected fields. So the per-field saving from pushdown is ~the numeric conversion only;
most of the slope drop vs the full-projection sweep (126 -> 24-45 ns/field) is SERIALISING 1 field instead of N
(Fig1 Flink q0: ser 58% of CPU). Estimate: no-pushdown slope would be ~52 ns/field (deser share of 126); measured
~45 from N=5..10 -> pushdown worth ~5-10 ns/field. NOT 'Flink skips the unused columns'.
PREDICATES (2026-09-26, `_scratch/flink_explain/explain_filter.py`): `FileSystemTableSource` implements SupportsFilterPushDown
and the plan digest shows `filter=[and(>(c1,500),=(c2,3.5))]` on the scan, BUT the Calc keeps `where=[...]` and the scan
reads `fields=[c0,c1,c2]` -- the source only records the filter (partition pruning / statistics), it does not evaluate it;
there is NO filterable decoding format (only ProjectableDecodingFormat exists in the table API), so csv/json tokenise
every column, convert the predicate columns, and the generated Calc filters boxed RowData. Matches the Fig1 Flink q2
profile (86% deser, 12% Calc). No raw-byte predicate evaluation on Flink; NES overload/lazy has no counterpart there.
EAGER, COMPLETE conversion under SELECT * + predicate (2026-09-26, from the 2026-09-03 collapsed profiles, whole-job
sample counts on the Source Data Fetcher thread): q2 (WHERE auctionId%123=0, int predicate, 0.8% survivors) vs q0 (SELECT *):
FloatingDecimal/parseDouble of `price` 20.4k vs 21.6k samples, int parse 28.6k vs 31.5k, CsvToRowDataConverters 104k vs 116k
-- the same absolute conversion work per row although the predicate needs one int and 99.2% of rows are dropped. The
decoder builds the full GenericRowData per row before the Calc sees it; only VARSIZED strings stay lazy (BinaryStringData
materialised in the first Calc that touches them, see YSB note).
MB/s: naive flat ~130 from N>=2 (parse-bound), bypass RISES 2.7 -> 7.6 GB/s (index-bound: 109 B/row in 14.3 ns), Flink
rises 31 -> 199.
**THE CLAIM, phrased carefully:** in ABSOLUTE per-field cost bypass degrades 20-65x more slowly than Flink/naive
(1.17 vs 23.6-45 vs 76 ns/field). In RELATIVE rows/s span (N=1->10) it is bypass 3.55x, naive 4.63x, Flink 1.56x --
Flink 'degrades slowest' only because its ~300 ns fixed per-row cost swamps its per-field cost, and bypass's near-zero
fixed cost makes its tiny index slope visible. => state the fitted law (a + bN) or the per-field slope, NOT 'rows/s falls
x times'. Pushdown is real: bypass N=10 69.8 Mrows/s with one field out vs 36.4 with all ten out.
Caveats: Flink N>=7 jobs are only 10-11 s (JVM warm-up share larger than the 2026-09-03 sweep's >=27 s); 3 reps.

## Fig2 PREDICATE sweep -- SELECT * WHERE c0 < 8000 over mixed rows, naive / bypass +-overload / Flink (DONE 2026-09-28)
Author's pick after the projection sweep ("more prominent?"). Design (2026-09-27 discussion): MIXED row = c0 INT32 uniform
[0,1e6) predicate column + N-1 FLOAT64 (.6f) payload, 0.8% selectivity (= q2); the INT lazy overload evaluates `<` on
raw digits (sign, digit count, memcmp) with `overload: true`, while the FLOAT lazy rep only overloads ==/!= vs int
constants (rounding) -- hence the int predicate column; the float payload keeps naive/Flink's expensive per-field parse.
Data `nm{1..10}.csv` (~200 MB, 6.89 + 10.89(N-1) B/row) + `nm{N}_x10.csv` (Flink), generator inline in the session
(numpy, seed 1000+N). Queries `queries/multicol/pred_nN.yaml`. Experiments `fig2_pred_nes.yaml` (naive repeat 5,
compiled_lazy_ovl repeat 300 overload:true, compiled_lazy_noovl repeat 100, 10 reps, run_group 20260928T102349, 300/300)
+ `fig2_pred_flink.yaml` (3 reps, 30/30). Probe (1 rep, N=1,4,10, 2026-09-27) under `_scratch/pred_probe/`.
KNOBS: fnattr; inline_invoke_calls and trace_constant_bytes at worker DEFAULT = true (verified in
QueryEngineConfiguration.hpp) => all optimised arms this week ran the r6 "context" layer; overload ON/OFF is the only
difference between the two bypass series. Figure `fig2_pred_rowss_mbps_4arm_2026-09-28.{pdf,png}` + `_data.csv`.

| N | naive MB/s / Mrows/s / ns | bypass+ovl | bypass no-ovl | Flink |
|--:|---|---|---|---|
| 1 | 184 / 26.7 / 37.5 | 2917 / 423 / 2.4 | 726 / 105 / 9.5 | 69 / 10.0 / 100 |
| 4 | 130 / 3.30 / 303 | 6473 / 164 / 6.1 | 2952 / 74.6 / 13.4 | 102 / 2.57 / 389 |
| 10 | 133 / 1.27 / 790 | 7756 / 73.9 / 13.5 | 4757 / 45.4 / 22.1 | 114 / 1.09 / 918 |
Cost laws ns/row = a + bN (10 pts, R2>=0.998): naive -37.9 + 82.6N (N=1 = lone int column, cheap for the original
codec -> negative intercept; slope = float parse of every payload field, no pushdown); bypass+ovl 1.1 + 1.24N (index
only; the overload's compare is sign/len/memcmp, ~1 ns); bypass no-ovl 7.9 + 1.42N (FastINT32 parse of c0 every row =
the 6.8 ns fixed difference, matches the q2 profile's 6.7 ns); Flink 20.0 + 90.6N (eager conversion of ALL payload
floats per row before the Calc drops 99.2% -- no projection escape; the 273-350 ns "fixed" cost of the projection
sweep was the float c0 parse+serialise, not framework: with a lone int column Flink's N=1 is 100 ns).
Slope ratios vs bypass: naive 67x, Flink 73x (most prominent of the three sweeps: full-projection 50x/47x,
projection-1 65x/20-38x). Relative rows/s span N=1->10: bypass+ovl 5.7x, no-ovl 2.3x, Flink 9.2x, naive 21x -- with
the cheap int predicate no arm has a large fixed cost, so the rows/s panel alone now ranks bypass flattest (the
fixed-cost trap of the projection sweep is gone). MB/s: bypass plateaus ~7.8 GB/s (index-bound), no-ovl approaches it
from below, naive ~133 flat from N>=2, Flink 69->114.
Overload effect: 4.0x at N=1, 1.6x at N=10 (fixed-cost only; same slope) -- the evaluation's one-knob ablation.
Caveats: Flink 3 reps; Flink jobs 17-29 s (JVM warm-up share as in the projection sweep); naive N=1 degenerate point.

## Fig1 TEASER v2 -- naive / Flink / optimised WITH OVERLOADING, q0 / Q2-original / YSB (DONE 2026-09-28)
Author's re-evaluation: the v1 optimised profiles ran with overload OFF; it would only have mattered on a comparison
predicate, and q2mod (MOD 123) cannot use it -> replaced by the ORIGINAL NEXMark Q2 (`nexmark/q2_original`: 5-way OR
point selection on auctionId, projects auctionId+price, ~0 survivors) where the INT lazy overload evaluates all five
equalities on the raw digits (no parse at all). q0 and YSB kept (overload inert: no predicate / VARSIZED equality is a
lazy span compare anyway) but re-profiled same-session with overload ON. All NES arms re-profiled on THIS binary
(naive incl.); Flink q2og profiled with async-profiler (2026-09-03 recipe), q0/YSB Flink from 2026-09-03.
Figure `fig1_teaser2_naive_flink_optimised_2026-09-28.{pdf,png}` + `_data.csv`: (a) share of engine CPU (%),
(b) CPU ns per TUPLE on a log axis (segments not to scale; totals + naive/optimised speed-up annotated).
Method: NES shares = perf flat 20 s @4 kHz (YSB whole-life + windowed), naive = 2026-08-19 thread+symbol rules,
optimised = classify_v2 (+ q0 JIT split by the json-csv differencing 2.8 ns -> ser; q2og/ysb JIT -> process);
NES absolute = the profiled run's own procfs CPU in its sink window x (1 - idle) / rows = CPU per tuple over ALL busy
threads (naive uses ~1.4-1.6 cores, so its CPU/tuple > wall/tuple; optimised ~1 real core). Flink shares =
classify_flink 3-stage; Flink absolute = stage samples / 4 kHz / rows (GC/JIT/read/kernel excluded).
Throughput annotations = clean 3-rep medians (`fig1_teaser_thru`, `fig1_flink_thru{,_q2og}`).
pbench `configs/parameters.yaml`: the `overload: true` rule now accepts branch benchmark-piparse-lazyparse-fast-csv
(was a stale branch-name rule; the pred sweep only passed because overload sat in a series override).

| query | arm | deser / proc / ser (%) | CPU ns/tuple | Mrows/s |
|---|---|---|---|---|
| q0 SELECT * | naive | 25 / 3 / 72 | 613 | 2.2 |
| q0 | Flink | 41 / 1 / 58 | 978 | 1.8 |
| q0 | optimised | 27 / 49 / 24 | 12.6 | 86.2 |
| Q2 original (5-way OR) | naive | 98 / 1 / 0 | 162 | 6.3 |
| Q2 | Flink | 88 / 12 / 0 | 364 | 3.8 |
| Q2 | optimised + overload | 70 / 28 / 2 | 4.8 | 232 |
| YSB | naive | 91 / 9 / 0 | 559 | 1.8 |
| YSB | Flink | 82 / 18 / 0 | 1351 | 1.4 |
| YSB | optimised | 56 / 44 / 0 | 22 | 34.5 |
CPU/tuple speed-ups naive -> optimised: q0 49x, Q2 34x, YSB 25x (throughput 39x / 37x / 19x). Q2 optimised = index
70% + five raw-digit compares & glue 28%; NO parse symbols in the profile (fast_float/parseWithFastInt absent) vs the
q2mod variant's 54% single-field parse; 4.8 ns/tuple vs 12.5. YSB optimised 56/44 at 22 ns CPU (v1: 59/41 at 29 wall).
Runs: 6 NES profiles OK (YSB both arms on attempt 1), throughput 17/18 (ysb/optimised rep 3 died, exit 8, 2 reps
survive), Flink profile + thru OK. Scratch `_scratch/teaser_v2/` (profiles gz, symbols, YAMLs, scripts, chain log).

## Per-run artifacts + procfs CPU sampler (pbench runner change, 2026-09-25, UNCOMMITTED)
`piparse_bench/runners/worker_cli.py`: (1) `_ThreadCpuSampler` reads `/proc/<pid>/task/*/stat` every 0.25 s for the
worker's whole life -> `threadcpu.csv` (wall_s, mono_s, tid, comm, utime_ticks, stime_ticks; CLK_TCK in header). (2)
`_persist_artifacts` copies the sink CSV(s), threadcpu.csv and worker.log to `results/artifacts/<exp>/<run_id>/`;
run row `config._artifacts` points there. So CPU/row per thread in ANY window is derived AFTER the fact
(`cpu_from_artifacts.py`), and the figure (rows/s, MB/s, wall ns/row, CPU ns/row, per-thread stack, cost laws) is
chosen freely without re-running -- the collection goal. Disable: PBENCH_NO_THREADCPU / PBENCH_NO_ARTIFACTS.
**BUG FOUND + FIXED mid-session:** early instrumented smokes recorded ~0 CPU because STALE/ghost worker processes
(orphaned to systemd, comm `main`, from crashed YSB SIGSEGV + earlier runs) held :9099; each fresh worker failed to
bind SILENTLY and sat idle while the ghost served the queries -> the sampler watched an idle pid. Fix: sample whoever
`ss` says LISTENS on the worker port (`_pid_on_port`), warn if != launched pid. Pre-flight `pkill -9 -x main` + verify
:9099 free before a run. (nes-profile gotcha #3: deadlocked workers survive SIGTERM.) After the fix, CPU is sane
(naive DataSrc 9.4 + Worker 16.2 over 16 s etc.).

## Reproduce the Fig1 teaser
`profile_opt_one.sh <q0|q2mod|ysb> [secs] [freq] [stat]` (attach-and-wait, fine for q0/q2), `profile_opt_ysb_full.sh`
(whole lifetime + `window_report.sh`, needed for YSB; retry on SIGSEGV), `classify_v2.py optprof_*/symbols_*.txt`,
`assemble_fig1_teaser.py` (needs the `fig1_opt_diff` rows in pbench DuckDB + the Notes naive CSVs) ->
`fig1_teaser_data.csv`, `plot_fig1_teaser.py`. The perf data are gzipped in `_scratch/optprof_*/`.

## Next
1. Fig2 v2 full sweep (go pending), then the two-panel figure (teaser + 4-rung eval version).
2. Naive re-profile of q0/q2/YSB on THIS binary for same-session parity (naive code path is frozen; low risk).
3. q1/q10 optimised profiles (mixed case) for the evaluation version of Fig1.
4. Refine the JIT split (IR dump recipe, COMPILER_OPT_MICROBENCH_HANDOVER §6) if a reviewer needs it.
5. Probes list (2026-09-25 discussion): knob-differencing cross-check (DONE here), IR proof, out-of-sample N=16 law,
   output-format boundary (csv/json/native), type mix, selectivity sweep, overload on/off, thread scaling,
   output equivalence, dirty-input fallback, profiler overhead (DONE: -1.3/-1.7/-3.6%).
6. File the YSB SIGSEGV as an engine bug (stack above).
