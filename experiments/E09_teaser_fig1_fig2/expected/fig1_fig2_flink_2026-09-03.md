# Paper §2 motivation figures REPEATED ON APACHE FLINK — method + data (2026-09-03)

Companion to `fig1_fig2_motivation_2026-08-19.md` (the NebulaStream originals). Same workload, same
figure design, Apache Flink 2.1.3 (PyFlink MiniCluster, JDK 11) instead of NES. Everything ran through
pbench (`~/work/piparse-bench`, `mode: flink`), experiments `experiments/fig1_flink_prof_{q0,q1,q10,q2mod,ysb}.yaml`,
`fig1_flink_thru.yaml`, `fig2_flink_fieldsweep.yaml`; scratch (profiles, classifier, plot scripts) copied to
`fig1_fig2_flink_2026-09-03_scratch/`.

## Figure 1 — per-query (de)serialization CPU share, Flink
`fig1_parsing_overhead_flink_2026-09-03.{pdf,png}` (drop-in) + `fig1_parsing_overhead_nes_vs_flink_2026-09-03.{pdf,png}`
(two panels, NES naive left / Flink right) + `_scratch/fig1_flink_data.csv` (plotted), `fig1_flink_raw.csv`
(pre-normalization buckets incl. excluded), `fig1_flink_throughput_reps.csv` (per-rep throughput).

- **Vehicle**: Flink's OWN `filesystem`+`csv` format (Jackson `CsvParser` + `CsvToRowDataConverters`) →
  SQL → `json_blackhole` sink = Flink's OWN `JsonRowDataSerializationSchema` (Jackson `ObjectNode` tree +
  `UTF8JsonGenerator` per row) into the flink-ext void sink. `parallelism.default=1` (= NES W1),
  object-reuse + operator-chaining on, checkpointing off, `table.local-time-zone=UTC` (pbench driver).
  Data `large` = bid_6GB.csv (184M rows, all-numeric bid schema, same as NES Fig1's bid_1GB shape); YSB on
  `xlarge` = ysb1k_varsized_ext4_15G.csv (80M rows, 7 VARSIZED + event_time). Files page-cache warm
  (`warm_read`). Single stream = single split → one fetcher thread + one task thread, like NES W1.
- **Profiler**: async-profiler 4.1 (the lib bundled with CLion, `~/.local/share/JetBrains/Toolbox/apps/clion/lib/async-profiler/amd64/libasyncProfiler.so`)
  loaded at JVM start via env `JVM_ARGS="-XX:+UnlockDiagnosticVMOptions -XX:+DebugNonSafepoints -agentpath:…=start,event=cpu,interval=250us,threads,ann,collapsed,file=…"`
  (pyflink's gateway server honours JVM_ARGS; pbench inherits env). cpu event @4 kHz (= NES perf freq),
  per-thread collapsed stacks with kernel/inlined annotations, WHOLE job (~60-170 s; JIT warm-up is in
  the sample but C2/GC/main threads are excluded by thread name, see below). ⚠️ late attach via
  `jcmd <pid> JVMTI.agent_load` mangles `=`-options (DCmd splits at '='), hence whole-run at launch.
  Runner: `_scratch/profile_flink_one.sh`; classifier `_scratch/classify_flink.py`.
- **Attribution (mirrors NES classify.py)**: split BY THREAD first. `Source Data Fetcher …` thread =
  Flink's CSV read+parse = **deserialize** (all its samples except file-read frames and kernel).
  Task thread(s) `… (1/1)#0` = operators + JSON sink; each sample bucketed by the NEAREST classified
  frame walking from the leaf up (a memcpy / HashMap / GenericRowData leaf inherits its caller's stage):
  *serialize* = `org/apache/flink/formats/json/*`, Jackson core/databind (generator, ObjectNode,
  ByteArrayBuilder, BufferRecyclers), sink-writer glue, `DateTimeUtils.formatTimestamp` (q10 DATE_FORMAT —
  NES counted CASTFROMUNIXTS as serialize); *deserialize (task-side tail)* = `formats/csv/*` and the lazy
  string materialization `StringDataSerializer.copy → BinaryStringData.materialize → encodeUTF8` (see
  YSB note); *process* = generated `StreamExecCalc$N`, `table/runtime/operators/*` (window agg, watermark
  assigner), `BytesMap`, `BinaryRowData.hashCode`; *internal* = `RowDataSerializer.toBinaryRow`,
  `BinaryRowDataSerializer`, `RecordWriter`/`ResultPartition` (the keyBy shuffle); *residual* = mailbox /
  StreamTask / SourceOperator glue → counted as PROCESS (conservative). **Excluded** then renormalized:
  GC threads (~10% of samples — Flink's JSON path allocates a tree per row; attributing GC to serde would
  RAISE the serde share), C1/C2 compiler threads, class-loading `Thread-3`, coordinator/metrics threads,
  kernel-leaf samples, and file-read frames on the fetcher (`FileInputStream.readBytes`; NES nulled the read
  via InMemory prefill). `internal` (YSB only, 2.3% normalized) folded into process for the figure.
- **Data (normalized %, + clean 3-rep median throughput, no profiler)**:
  | query | deserialize | process | serialize | serde total | Mrows/s | MB/s | job s |
  |-------|------------:|--------:|----------:|------------:|--------:|-----:|------:|
  | q0 SELECT *          | 41.2 |  1.1 | 57.7 | 98.9 | 1.80 |  63.1 | 102 |
  | q1 currency conv.    | 38.2 | 11.4 | 50.4 | 88.6 | 1.77 |  62.1 | 104 |
  | q10 datetime fmt     | 28.3 |  2.2 | 69.5 | 97.8 | 1.08 |  37.7 | 171 |
  | q2 filter (0.8% sel) | 86.3 | 12.4 |  1.3 | 87.6 | 3.14 | 110.0 |  59 |
  | YSB windowed count   | 81.4 | 18.3 |  0.2 | 81.6 | 1.41 | 261.6 |  57 |
  Raw (% of ALL samples; deser / proc / residual / ser / internal / read / kernel / other-threads):
  q0 33.91/0.01/0.93/47.55/0/0.80/0.17/16.63; q1 31.17/8.45/0.84/41.06/0/0.71/0.11/17.66;
  q10 23.12/1.04/0.72/56.69/0/0.51/0.09/17.83; q2 65.75/8.49/0.94/1.00/0/1.52/0.50/21.81;
  YSB 61.53/11.48/0.60/0.18/1.76/4.47/0.37/19.61. Profiled-run throughput was 3-11% below the clean
  runs (q0 56.4 vs 63.1 MB/s) — the annotations use the clean runs.
- **Per-symbol evidence**: q0 task thread = Jackson (`RowDataToJsonConverters` 8.4%, `BufferRecyclers.getBuffer`
  4.0%, `UTF8JsonGenerator._writeString` 3.9%, `ByteArrayBuilder.toByteArray` 3.3%, `ObjectNode.serialize`,
  `JsonFactory._createUTF8Generator` 2.1% — Flink builds an ObjectNode tree AND a fresh generator per row);
  fetcher = `CsvDecoder.nextChar` 16%, `Long.parseLong` 5.6%, `FloatingDecimal.readJavaFormatString` 3.7%,
  `TextBuffer`, `String.equals`, `HashMap` (Jackson's column-name lookup per field). q10:
  `DateTimeUtils.formatTimestamp` alone = 25% of all samples. YSB fetcher 39%, task 40%, of which 27% is
  the deferred string materialization; the GlobalWindowAggregate task (the actual COUNT) is 0.7%.
- **Judgment calls (documented, all conservative for the serde claim)**:
  1. q1/q2 "process" 11-12% is the generated Calc reading boxed fields (`GenericRowData.getDouble/getInt`
     5.5 of 8.4 raw %) + building its output row — a consequence of the CSV converter producing boxed
     `GenericRowData`, but it is the projection/filter operator's own code, so PROCESS.
  2. YSB: Flink's csv format emits LAZY strings; the UTF-8 materialization (`BinaryStringData.materialize`,
     `encodeUTF8`) fires in the first Calc that copies the field. Counted as DESERIALIZE (text → engine
     representation; the NES YSB profile counted its varsized string copy the same way). Without this
     reclassification the raw 27% would sit in a misleading "internal" bucket (it matched `typeutils/`).
  3. Real keyBy-shuffle serialization (`RowDataSerializer.toBinaryRow`, network writer) = 1.8% raw / 2.3%
     normalized, folded into process.
  4. GC/JIT threads excluded (not attributed to serde), read excluded (NES parity).
- **Message**: on Flink too, (de)serialization is 82-99% of the pipeline's CPU across all five queries;
  output-heavy queries are serialization-bound (50-70%), the selective filter and YSB flip to
  deserialization-bound (86% / 81%). Query processing is ≤18% everywhere (≤2% on q0/q10). Flink's split
  leans more to deserialization than NES's naive arm (41 vs 27% on q0) because Jackson's CSV decoder is
  slower relative to its JSON encoder than NES's stod/fmt pair — the STRUCTURE (serde dominates, work
  is a sliver) is identical.

## Figure 2 — rows/s vs MB/s, Flink
`fig2_rowss_vs_mbps_flink_2026-09-03.{pdf,png}` (Flink alone, laddered scatter like the NES original) +
`fig2_rowss_vs_mbps_nes_vs_flink_2026-09-03.{pdf,png}` (two panels vs N: (a) Mrows/s log, (b) MB/s; both
engines) + `_scratch/fig2_flink_data.csv` (medians), `fig2_flink_raw.csv` (all 30 runs).

- **Vehicle**: same Flink csv→json arm as Fig1, parallelism 1. Queries `multicol/allf_n{1..10}` with the
  added `flink_sql` (`SELECT c0*CAST(1 AS DOUBLE) AS c0, …` — symmetry only, Flink has no passthrough
  elision). Datasets = the Fig2 `nf{N}.csv` files concatenated 10× (`nf{N}_x10.csv`, 2.0 GB each,
  identical bytes/row 10.9→108.9; catalog entry `xlarge`), so a run is 27-59 s of job time instead of
  ~5 s (JIT-dominated). 3 reps, median. NES comparison = the 2026-08-19 fast compiled SequentialCSV arm.
- **Data (median n=3)**:
  | N | bytes/row | Flink MB/s | Flink Mrows/s | NES MB/s | NES Mrows/s |
  |--:|----------:|-----------:|--------------:|---------:|------------:|
  | 1 | 10.9 | 33.8 | 3.10 | 321.6 | 29.5 |
  | 2 | 21.8 | 47.1 | 2.16 | 326.6 | 15.0 |
  | 3 | 32.7 | 54.2 | 1.66 | 318.1 | 9.7 |
  | 4 | 43.6 | 57.8 | 1.33 | 308.1 | 7.1 |
  | 5 | 54.4 | 60.0 | 1.10 | 318.5 | 5.8 |
  | 6 | 65.3 | 65.1 | 1.00 | 302.2 | 4.6 |
  | 7 | 76.2 | 67.0 | 0.88 | 307.9 | 4.0 |
  | 8 | 87.1 | 71.9 | 0.83 | 301.0 | 3.5 |
  | 9 | 98.0 | 73.7 | 0.75 | 300.8 | 3.1 |
  | 10 | 108.9 | 74.7 | 0.69 | 302.6 | 2.8 |
  Flink: rows/s falls 4.5× (3.10→0.69), MB/s RISES 2.2× (33.8→74.7). NES: rows/s falls 10.5×, MB/s flat ±4%.
- **Cost law** (ns/row = a + b·N from the N=1 and N=10 points): Flink a ≈ 196 ns/row fixed + b ≈ 126 ns/field;
  NES a ≈ 0 + b ≈ 36 ns/field. Flink's fixed per-row cost (StreamRecord/RowData/ObjectNode + generator per
  row, mailbox loop) is ~1.5 fields' worth, so at low N it dominates and MB/s only approaches a plateau
  (~75 MB/s, the per-field Jackson bound) once N ≳ 8. Prediction stated before the run held.
- **Message**: the paper's specific "MB/s flat while rows/s spans 10×" sentence is NES-specific (an engine
  whose per-row overhead is ~0). Flink supports the weaker, still-useful claim: rows/s — the metric a
  stream processor is judged by — falls monotonically with field count in both engines (4.5× / 10.5×),
  while MB/s stays within a narrow band or even rises; MB/s hides the per-row cost. Use the two-panel
  figure if Flink is shown; the Flink-only scatter has no flat band to annotate.
