<!-- SPDX-License-Identifier: Apache-2.0 -->
# Handover 2026-08-31 — NEXT: add NES-Naive + NES-Native(native in+out) to the N=1→1000 scaling sweep

## GOAL (user, this session's close)
Go back to the **many-source scaling experiment** (N = 1 → 1000 concurrent sources/queries, the fan-out
that produced the bounded green curve) and get **throughput + per-batch latency vs N** for **two more NES
configurations**, alongside the existing fully-optimized NES-SIMD curve:
1. **NES-Naive** — the *same* naive config used in the stateless/stateful head-to-head (no-SIMD,
   interpreted, original/naive (de)serializers).
2. **NES-Native (no parsing) — native input AND native output** (SystemNative in, NATIVE out, no
   parse, no serialize).

So the scaling figure gains two NES-internal arms: **Naive → SIMD → Native** across N (the parse/serde
cost axis, now as a function of source count). Flink/Spark are already done (don't re-run unless wanted).

---

## Where everything lives
- **Infra: `~/work/piparse-bench`** (branch `benchmark-piparse-lazyparse-fast-csv`). The many-source
  scaling machinery is BUILT + committed (pushed 2026-08-11) + extended (uncommitted, 2026-08-20).
- **Scaling experiments** (`experiments/`): `nes_vs_flink_vs_spark_scaling_step20.yaml` (the definitive
  51-pt N=1,20,…,1000 sweep), `..._probe.yaml` (N=128/256), `..._probe_n1000.yaml`. These use
  **`query_mix`** = round-robin over the 10 `bidstr_*` matrix queries (each of the N sources runs one of
  the 10 shapes). x-axis = `num_queries` (=N).
- **The naive/native arm configs** are already defined for the FIXED-config 5-arm head-to-head:
  `experiments/nes_vs_flink_vs_spark_stateless_5arm.yaml` (NES-Native, NES-SIMD, NES-Naive, Flink, Spark)
  and `naive_corrected_stateless.yaml` (the genuine-codec naive). **native→native** shape:
  `nes_vs_flink_native_native_stateful.yaml` / `nexmark_native_native_v3.yaml` (`output_formatter: {type: NATIVE}`).
- Memory: **[[many-source-scaling-3way]]** (the scaling infra + the DONE 3-way curve), **[[spark-streaming-arm]]**
  (the 5-arm naive/native taxonomy + exact configs), [[fragment-shredder-landed]], [[nexmark-native-vs-csv]]
  (CCX-cell config), [[ablation-study]] (the rung taxonomy), [[output-codec-seam]] (original codecs).
- Data: workload = **`bid_strings_3GB.csv`** (~3.6 GB) + the 10 `queries/nexmark/matrix/bidstr_*`.
  Native twin `.nes` needed for the Native arm (see §3).

---

## The two arms — EXACT config (copy from the 5-arm, adapt to the scaling query_mix)

### NES-Naive (from `nes_vs_flink_vs_spark_stateless_5arm.yaml` + `naive_corrected_*`)
```yaml
worker.query_engine.number_of_worker_threads: 1        # SEQUENTIAL = single-thread per source
query_config.source_type: BlockingFile
query_config.input_formatter:  { type: SequentialUncompiledOldCSV, threading_mode: sequential }
query_config.output_formatter: { type: JSONUncompiled }
query_config.input_parser: {}      # EMPTY — uncompiled hardcodes codecs (a non-empty override crashes)
query_config.output_parser: {}
worker_env:
  NES_INPUT_CODEC: original         # genuine stod (NOT fast_float) — the TRUE naive baseline
  NES_OUTPUT_CODEC: original        # genuine stringstream (NOT zmij)  ([[output-codec-seam]])
```
- `SequentialUncompiledOldCSV` = the **scalar-find INTERPRETED** indexer (ablation rung **r1**), i.e. no
  SIMD, no compilation. This is exactly the naive column of the stateless/stateful figure.
- ⚠️ The 5-arm's first naive run wrongly used the FAST codecs; the CORRECTED naive uses
  `NES_INPUT_CODEC=original` + `NES_OUTPUT_CODEC=original`. Verify they're applied via the DIAG lines.

### NES-Native — native input AND output (no parse, no serialize)
```yaml
data_size: native                                       # selects the .nes twin
query_config.source_type: MmapFile                      # (or SystemNative reader; MmapFile = zero-copy warm)
query_config.input_formatter:  { type: SystemNative, string_length: "13,73" }   # bidstr arity; see below
query_config.output_formatter: { type: NATIVE }         # raw tuple rows, formatter BYPASSED (no JSON)
sink_type: Monitoring                                    # NoneFormat meter (no serialize)
```
- This is the **native→native** shape (`nexmark_native_native_v3.yaml`) — differs from the 5-arm
  NES-Native, which was SystemNative-in → **JSON**-out. The user wants native OUT too (no serialize).
- ⚠️ **SystemNative REQUIRES `string_length` even for zero-varsized schemas** (dummy ok). For the
  `bidstr` schema it is **`"13,73"`** (per the 5-arm). Each query's native string_length must match its schema.

### NES-SIMD (already the scaling arm — the middle rung)
Fully-optimized many-source production config: **CCX cells + fragment shredder `LOCK_FREE_FRAGMENTS` +
`pin_threads=true` + 16 workers / 8 io + 192×128 KiB shared source pools + File source**, compiled SIMDCSV
→ JSON. This is the existing green curve; keep it as the reference.

---

## KEY DESIGN QUESTIONS to resolve FIRST (don't just run)
1. **Naive threading in the many-source regime.** The naive path is `threading_mode: sequential` (the
   SOURCE thread parses inline; no worker pool). In the N-source fan-out that means **N single-threaded
   pipelines** (each source its own thread) — which is the natural naive scaling model, and different from
   the SIMD arm's shared 16w/CCX-cell pool. DECIDE the fair config: almost certainly *each of the N naive
   sources runs sequential/inline*, so the "scaling" is N independent inline parsers. Confirm the query_mix
   + num_queries loop drives N naive sources correctly (it renders `query_list[i % len]` per instance —
   should be formatter-agnostic, but the CCX-cell/pool config is SIMD-oriented; the naive arm likely needs
   `ccx_aware_task_queues=false` + no shared source pools, just N BlockingFile sources). This is the crux.
2. **Native data twin.** Confirm/generate the `.nes` twin of `bid_strings_3GB.csv` and that the 10
   `bidstr_*` queries have native schema entries + correct `string_length`. The 5-arm added "native data
   entries on all 10 bidstr queries" (uncommitted) — verify they exist for the scaling file, else generate
   (`csv_to_binary.py <csv> <nes> --schema ...`). At N=1000 the source pool = N × per-source buffers ×
   128 KiB — watch RAM (62 GB box).
3. **Metric = records/s + per-batch latency.** Native `.nes` bytes ≠ csv bytes, so **throughput must be
   `throughput_mrows_s` (records/s, format-invariant)**, NOT MB/s (the 5-arm rule). Latency = per-batch
   ingest→sink (the scaling infra already pools ns samples across the N pipelines; NES batch = 128 KiB).
4. **Scope.** This is NES-internal — you can drop Flink/Spark and make a **NES-only 3-arm scaling
   experiment** (Naive / SIMD / Native) × N, which is far cheaper than the 30 h 3-engine sweep. Probe
   N=128/256/1000 first, then the step20 grid (N=1,20,…,1000).

---

## Run recipe (probe → full)
1. Build a NES-only scaling experiment (e.g. `nes_naive_simd_native_scaling.yaml`): 3 explicit series
   (NES-Naive / NES-SIMD / NES-Native configs above), `query_mix` = the 10 bidstr queries, x=`num_queries`.
   Start with probe values `["128","256","1000"]`, `repetitions: 3`.
2. `cd ~/work/piparse-bench && pkill -9 -x main; PBENCH_KEEP_LOGS=1 uv run python bench.py run \`
   `experiments/nes_naive_simd_native_scaling.yaml --build-dir ~/work/nebulastream-public/cmake-build-release --worker-port 9099`
   (capture FULL stdout, no tail; `--dry-run` first to check expansion + arm count).
3. Verify: naive DIAG shows original codecs; native N=1 sane; records/s pulled from DuckDB
   `throughput_mrows_s`; latency from the pooled mon dirs / DB.
4. Then the step20 grid (N=1,20,…,1000, 51 pts) for the two new arms (SIMD curve already exists —
   run_group `20260817T164347-3ec56b98`; you may reuse it or re-run all 3 for consistency).
5. Figure: extend `scripts/plot_nes_flink_spark_scaling.py` (or a new NES-only plotter) — 2-panel
   throughput(records/s) + p99 latency vs N, 3 NES arms.

## GOTCHAS (carry forward)
- **NES N=1 = ramp** (single source under-fills the pool → ~5.6 GB/s, climbs to steady by N~20). The low-N
  ramp is real structure, not a bug.
- **DuckDB is write-locked during a run** → mid-run previews: parse the LOG (throughput) + kept
  `/tmp/pbench_mon_*` dirs (NES latency via `monitoring.aggregate_monitoring_results`).
- **`nes-build` defaults to cmake-build-debug** → benchmarks use `cmake-build-release` (`--build-dir` /
  `NES_BUILD_DIR`).
- **Naive empty parser overrides** (`input_parser: {}`, `output_parser: {}`) — a non-empty override on the
  uncompiled path crashes (it hardcodes codecs; e.g. EiselF64 override → integer-parse crash).
- **`pkill -x main` pre-flight; NEVER `pkill -f`** (self-match). `pgrep -f 'bench.py run'` self-matches too.
- **Fully-optimized many-source config** is the OPPOSITE of the single-source head-to-head: CCX+pin is a
  ~2× *pathology* for a single source but the intended regime here. (The naive arm may not want CCX cells —
  see design Q1.)

---

## Prior session (this one) — SEPARATE thread, for context
Built the **SequenceShredder LOCK_FREE vs LOCKING span/worker figures** (the paper figure). All in
`bypass_scaling_2026-08-28/span_figure/` (SPAN_FIGURE_RESULTS.md, figures/, data/shredder_all_data.csv,
scripts/). Headlines: LOCK-FREE beats naive-LOCKING; the advantage EMERGES WITH PARALLELISM (worker axis
1.0×→3.06× iso / 1.37× e2e); span-robust; W1→W2 anomaly = shredder cache-coherence (per-call 77→285 ns);
isolated high-W LOCKING repeat-storm = a no-backpressure harness artifact (engine's in-flight bound avoids
it). Uncommitted harness change: `FormatterScalingBenchmark.cpp` arg13 `varsized=2` + `wideOutput` output
sizing. Memory: **[[bypass-scaling]]** has the full arc. Not related to the scaling task above.
