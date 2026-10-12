# Flink e2e latency arm + file-source scaling latency comparison — handover

Session 2026-07-15/16. Mission: measure **end-to-end ingest→sink latency in Apache Flink**, the
fair counterpart to NebulaStream's MonitoringSink, and run the **file-source scaling latency
comparison (1→1024 sources)** — nexmark bid-passthrough, the workload behind the existing NES
"green curve" (CCX cells + fragment shredder). All work is in `~/work/piparse-bench`
(uncommitted; NES source untouched this session). Box: Threadripper-class, 24 cores, warm page
cache. PyFlink 2.1.3 MiniCluster.

---

## 0. TL;DR

- Built a **faithful Flink e2e latency arm**: a delegating `csv-latency` source format (wraps
  Flink's OWN CSV parser, stamps `nanoTime()` at `readBatch()` start, carries `__ingest_ns` through
  Flink's own source→task queue) + a `latency-blackhole` sink (computes `now−ingest`, pooled-exact
  percentiles). Overhead ~1.4 % (noise).
- Extended it to **N concurrent pipelines** (StatementSet, N task slots) = the analog of NES's N
  concurrent File-source queries.
- **DID NOT retake NES** — the file-scaling curve already exists (`shredder_fragments_source_scaling`
  / `lock_free_fragments`); reproduced N=1/N=8 to confirm the box, then used the stored curve.
- **Headline result (bid passthrough, e2e latency, 1→1024):** NES holds p99 **bounded ~4 ms** and
  throughput **~40 GB/s FLAT to 1024**; Flink's **tail collapses** past the core count — p99 goes
  3.9→37.8→181.7→**1197.7 ms** (N=16→64→128→1024), throughput pinned at the 24-core parse ceiling
  **~1.4 GB/s**. At N=1024 Flink's p99 is **~290× NES** at **~28× lower throughput**.
- Figure: `results/figures/flink_vs_nes_latency_scaling.png` (2-panel, mirrors the file_scaling
  figure). Regenerator: `scripts/plot_flink_vs_nes_latency_scaling.py` (pulls live from the DuckDB).

---

## 1. What NES measures (the definition mirrored)

`MonitoringSink.cpp` + source runners: **per-TupleBuffer** latency. `sourceCreationTimestamp` is
stamped (µs) at **read-start** when the io thread begins filling a buffer; at the sink
`latency = now_µs − creation`, one sample per buffer; p50/p99/p999 over all retained samples. Under
bulk load this is dominated by **queue-residence** (the buffer waiting in the shared task queue for
a worker) — the decoupling that enables NES's parallel parse. Sampling ≈ one sample per
`operator_buffer_size` (131072 B) of input.

## 2. The Flink latency arm — mechanism (the crux)

**A naive SQL/UDF stamp measures nothing.** Flink parses on a separate **SplitFetcher thread** and
hands records to the task thread across a queue; a `now_ns()` UDF in the SELECT is POST-parse on the
task thread → it measured only the **~21 ns Calc→Sink operator handoff** (parse AND the fetcher queue
excluded). Confirmed empirically (21 ns).

**The faithful arm = a delegating source format** — `flink-ext/CsvLatencyFileFormatFactory`
(`'format' = 'csv-latency'`):
- Wraps Flink's own `CsvFileFormatFactory` `BulkFormat` (the delegate does ALL parsing → still the
  **native** parser). Strips a trailing synthetic `__ingest_ns` column from the type it hands the
  delegate (so the delegate parses only the real CSV fields), re-appends it via `JoinedRowData` +
  `RecordMapperWrapperRecordIterator`.
- Stamps `System.nanoTime()` at the START of every `readBatch()` — **before** the batch's bytes are
  read/parsed. Robust to lazy/eager decode; every row in a batch inherits the batch's stamp =
  NES's per-buffer read-start stamp. Carried unchanged through Flink's own queue+operators to the sink.
- Sink `flink-ext/LatencyBlackHoleTableSinkFactory` (`'connector' = 'latency-blackhole'`): reads
  `__ingest_ns` (last col), computes `nanoTime() − ingest` (valid across fetcher/task threads —
  nanoTime is JVM-global, one MiniCluster process). Retains one sample every `sample-every` rows.
  Prints `PBENCH_LATENCY subtask=… p50/p99/p999=…` (ns) + `PBENCH_LATENCY_SAMPLES <raw ns csv>`.

So the measured latency = **read + native parse + Flink's own source→task queue + projection + sink**
— the true e2e, the fair analog of NES ingest→sink.

## 3. Two fairness fixes (both user-required)

1. **Batch alignment (config-derived, NOT hardcoded).** Latency scales LINEARLY with Flink's per-fetch
   bytes `source.file.stream.io-fetch-size` (128 KiB→p50 1.56 ms, 1 MB[default]→12.2 ms, 8 MB→102 ms;
   throughput INVARIANT). The renderer sets `io-fetch-size = operator_buffer_size` so Flink's
   per-batch stamp granularity == NES's per-TupleBuffer stamp. Template var `FETCH_IO_SIZE`, latency
   mode only.
2. **Negligible overhead.** The sink must call `nanoTime()` ONLY on sampled rows (per-row nanoTime
   ≈ 20 ns × 31 M rows ≈ 0.6 s ≈ 5–7 %). After sampling the clock: **~1.4 %** (none@128k 10.77 s vs
   latency@128k 10.93 s ELAPSED, distributions overlap). Ingest side already cheap (one nanoTime per
   readBatch ≈ per 128 KiB).

Stance chosen (user): **honest same-definition, chained** (Flink's natural max-efficiency mode). The
architecture difference (NES trades latency for parse-parallelism via its queue; Flink chains) IS the
finding, not a measurement error.

## 4. N-pipeline scaling (the "run N times" model)

`num_queries = N` → **N independent source→project→sink pipelines in ONE Flink job** via a
`StatementSet`, each at **parallelism 1** (a single non-splittable CSV = one reader anyway), with
`taskmanager.numberOfTaskSlots = N` so all N run concurrently. Source tables `bid__p{i}`, sinks
`pbench_sink__p{i}`; the SELECT's source-table name is rewritten per pipeline via a `\b`-anchored
regex. `SIZE_BYTES = N × file`. Each sink emits raw samples; the runner **POOLS all samples across
pipelines** for EXACT percentiles (median-of-per-pipeline-p99 would be wrong). Single-source
stateless only (joins/aggs would need a defined ingest semantics → the renderer raises).

Thread policy: Flink = **N single-threaded pipelines** (N slots, ~2N threads incl. fetchers). NES =
N sources multiplexed onto a **fixed 16-worker shared pool**. This asymmetry is the whole story
(§6): Flink can't multiplex N pipelines onto a bounded pool.

## 5. NES baseline — reproduced, NOT retaken

The NES file-scaling latency curve already exists: `shredder_fragments_source_scaling` /
`lock_free_fragments` (CCX cells + fragment shredder + `ccx_shared_source_pools` 192, bid
passthrough, 16w/8io `pin_threads`, warm cache, `generator.repeat 6`, bid_1GB medium).
**Config that matters** (copy verbatim; see `experiments/repro_shredder_scaling_n1_n8.yaml`):
`ccx_aware_task_queues: true`, `ccx_shared_source_pools: true`, `ccx_source_pool_buffers: 192`,
`operator_buffer_size: 131072`, `number_of_buffers_in_global_buffer_manager: 32768`,
`sequence_shredder_mode: LOCK_FREE_FRAGMENTS`.

Reproduced N=1/N=8 on this box (dd bid_1GB first to warm cache): N=1 p50 0.052 / p99 0.145 /
9801 MB/s; N=8 p50 1.46 / p99 2.127 / 38298 MB/s — matches the recorded p50/p99 tightly. **Box is
sound.** (My first NES attempt read p50 10 ms because it was MISCONFIGURED: 1 worker, no CCX cells /
no fragment shredder, q1 arithmetic instead of passthrough. Discarded.)

## 6. RESULTS — full 1→1024 sweep (bid passthrough, e2e latency)

3-rep for N=1/8 (both engines), 1-rep for the sweep (matches the green curve's methodology). ms.

| N | NES p50/p99/p999 | NES GB/s | Flink p50/p99/p999 | Flink GB/s |
|---|---|---|---|---|
| 1 | 0.05 / 0.15 / 1.2 | 9.7 | 1.30 / 2.76 / 10.1 | 0.10 |
| 2 | 0.06 / 0.43 / 0.9 | 15.9 | 1.35 / 3.14 / 13.7 | 0.19 |
| 4 | 0.07 / 0.15 / 1.3 | 29.0 | 1.43 / 3.12 / 19.4 | 0.36 |
| 8 | 1.41 / 2.13 / 3.3 | 38.8 | 1.36 / 3.32 / 22.1 | 0.75 |
| 16 | 2.03 / 3.12 / 4.6 | 39.3 | 1.55 / 3.90 / 41.8 | 1.35 |
| 32 | 2.23 / 3.83 / 5.7 | 40.7 | 2.95 / 6.74 / 32.9 | 1.38 |
| 64 | 2.23 / 4.19 / 5.6 | 41.5 | 4.00 / **37.8** / 94.7 | 1.45 |
| 128 | 2.29 / 3.98 / 5.8 | 39.5 | 5.41 / **181.7** / 296 | 1.14 |
| 256 | 2.29 / 3.94 / 5.5 | 40.6 | 3.78 / **195.5** / 404 | 1.46 |
| 512 | 2.30 / 3.95 / 5.8 | 39.8 | 3.66 / **496.3** / 1263 | 1.44 |
| 1024 | 2.38 / **4.09** / 5.62 | **39.0** | 3.53 / **1197.7** / 3142 | 1.40 |

**Laws:**
- **NES = bounded.** CCX cells + fragment shredder hold p99 in the ~4 ms band and throughput ~40 GB/s
  FLAT from N=8 to N=1024 (Little's law on the fixed 16-worker shared pool). N=1 is sub-ms (parse
  ELIDED byte-copy + parallel workers on one stream); latency rises to the ~4 ms plateau by N≈8 as the
  shared pool saturates, then stays there.
- **Flink = tail collapse past core count (~N=32–64).** p99 3.9→37.8→181.7→1197.7 ms; p999 → 3.1 s.
  Mechanism: N pipelines = ~2N threads (fetcher + task) oversubscribing 24 cores → HOL / scheduling
  jitter — the same collapse as the C10K blocking-file case. Flink's **p50 stays LOW (~3.5 ms even at
  1024)** → purely a TAIL phenomenon. Throughput plateaus at the 24-core parse ceiling ~1.4 GB/s from
  N=16 (Flink always parses; NES elides on passthrough → the ~28× throughput gap).
- Flink plays the role of the file_scaling figure's pre-CCX "q1-parse campaign" blowup (363 ms @1000).

**N=1024 GOTCHA (user caught):** the NES N=1024 point is the CERTIFIED plateau config
= `shredder_fragments_n1024_pool_ladder` (run_group `20260712T223728`, 192×128 KiB pool + timer
wait) → **39.0 GB/s, p99 4.09 ms**. Do NOT median-average `shredder_fragments_n1024_timerwait`/
`_throughput` — they MIX suboptimal-pool rows (256×128K L3-tax, undersized pool, 384×64K detour) at
23–32 GB/s and understate NES (my first figure did this = 27.8 GB/s; NOT an engine regression). The
plot script now takes the MAX-throughput N=1024 row (always the plateau config).

## 7. Ops lessons

- **Port 8080 conflict.** Another session's worker (a different checkout's `nes-repl-embedded`,
  comm=main) can squat :8080 → the NES worker dies "Address already in use". DON'T kill other
  sessions' processes. FIX LANDED: pbench `run --worker-port N` (adds `--grpc=127.0.0.1:N` only when
  N≠8080; threads the port to the yaml host + readiness check). NB the worker parses `--grpc` as YAML,
  so the default `[::]:PORT` form is INVALID on the CLI ("bad conversion", leading `[` = flow seq) →
  use plain `host:port`. Used `--worker-port 8085`.
- **High-N is slow** (aggregate ~1.4 GB/s ÷ N-GB of work): N=1024 ran ~12 min (~1 TB parsed). Added
  `PBENCH_FLINK_TIMEOUT` env to bump the 900 s runner cap (used 2400). MiniCluster handled 1024 slots
  / 1024 chained single-task pipelines fine (no shuffle → minimal network memory).
- `pbench run --detach` for the long runs (survives harness reaping); `dd bid_1GB` to warm cache
  before every NES/Flink file run.
- DuckDB store: use `con.execute(...).fetchall()` (NOT `for … in con.execute`).

## 8. Artifacts

New (uncommitted):
- `flink-ext/src/main/java/dev/pbench/flink/CsvLatencyFileFormatFactory.java` — delegating latency format.
- `flink-ext/src/main/java/dev/pbench/flink/LatencyBlackHoleTableSinkFactory.java` — latency sink.
  (registered in META-INF services; `flink-ext/build.sh` rebuilds the jar, which is gitignored.)
- `experiments/latency_flink_q1_1src.yaml` — q1 1-source (superseded framing; kept for the 21 ns→ms mechanism note).
- `experiments/repro_shredder_scaling_n1_n8.yaml` — NES green-curve reproduction (N=1, N=8).
- `experiments/latency_flink_passthrough_scaling.yaml` — the FULL 1→1024 Flink sweep (curve baked into the description).
- `scripts/plot_flink_vs_nes_latency_scaling.py` — 2-panel figure, live from DuckDB.
- `results/figures/flink_vs_nes_latency_scaling.{png,pdf}`.

Modified (uncommitted): `piparse_bench/renderer.py` (latency mode + N-pipeline + StatementSet template),
`piparse_bench/runners/flink.py` (latency parse + pooling + PBENCH_FLINK_TIMEOUT),
`piparse_bench/runners/worker_cli.py` + `piparse_bench/cli.py` (`--worker-port`/`--grpc`),
`queries/nexmark/bid_passthrough.yaml` (added `flink_sql`),
`flink-ext/.../META-INF/services/…Factory` (registered the two new factories).

Run groups in DuckDB (this session): `latency_flink_passthrough_scaling` (sweep),
`latency_flink_q1_1src`, `repro_shredder_scaling_n1_n8`.

## 9. Open threads / next

1. **Overlay figure is done** — could add NES's p50 line, a PDF/TikZ paper variant, or annotate the
   throughput panel with the parse-elision note.
2. **q1 (parse) sweep** — same infra, `flink_output_format: latency` on `nexmark/q1_price`; would show
   the parse cost on top (Flink q1 1-src was p50 1.5 ms before batch-alignment work).
3. **Commit** the pbench changes (nothing committed yet this session).
4. Thread-policy variants: cap Flink slots at core count (pipelines queue) vs the current N-slots — but
   that serializes pipelines (changes the workload); the current N-slots model is the honest "run N
   concurrently" analog.

Related memory: `flink-latency-measurement.md` (this session), `csv-to-json-output.md` (Flink infra
parent), `scaling-poc-thread-model.md` (latency scaling / C10K collapse laws),
`fragment-shredder-landed.md` (the NES green-curve engine).
