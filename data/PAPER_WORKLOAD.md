# Paper evaluation workload (FROZEN 2026-08-04)

The definitive query workload for the paper's evaluation, fixed with the user across the
2026-08-01..04 sessions. Two tiers: **10 stateless cross-format queries** (the generality
figure: compilation + parallelization work for arbitrary formats) and **3 stateful queries**
(general working set only — NOT in the ablation figure; they carry the boundary-of-
applicability story). Every query has two identities: a citable benchmark identity
(NEXMark/YSB/CM number where one exists) and a HOSP reading (the hospital cooperation that
motivates the paper; one query IS the working example, modeled on NEXMark data so it is
reproducible without hospital data — say that sentence in the paper).

## 1. The headline figure (the "4x4")

- **Rows** = formats: CSV, JSON (SchemaJSON), HL7, XML (HL7-indexer config).
- **Columns** = absolute baseline anchor (Mrows/s) + three relative cells.
- **Cell layout** (user's design): total gain on top (bold), the two factors below:
  ```
  +---------------------------------+
  |           Total Gain            |
  +---------------------------------+
  |  Compilation | Parallelization  |
  +---------------------------------+
  ```
  Rungs are cumulative, so Total = Compilation x Parallelization by construction (say so in
  the caption; the cell is self-checking).
- **Cell values = geomean of regime-level geomeans** (regime-stratified, because the query
  set is not regime-balanced: output x1, projection x1, filter/route x4, compute x3, string
  x1, mixed x1). A flat geomean would tilt toward the filter/compute regimes.
- **Wall-clipped cells get a dagger = lower bound** (even with InMemory, CSV passthrough at
  W16 wants ~48 GB/s; some ceiling will bind).
- **Companion figure**: per-query small multiples (one panel per query; x = format; 3 bars
  baseline=1 -> +compilation -> +parallelization; log-y, normalized within format). The
  spread across panels is presented as a LAW, not noise: compilation's multiplier scales
  with the query's (de-)serialization share (Amdahl — the structural-indexing share is fixed
  C++ in every rung); parallelization's is roughly query/format-independent until an ingest
  ceiling binds.
- Ranges live in the companion figure; cells stay three clean numbers.

## 2. Rung definitions (3-rung coarse ladder; indexer held at SIMD in ALL rungs)

| rung | formatter (per format) | config |
| --- | --- | --- |
| r-base: interpreted | SequentialUncompiledCSV / SequentialUncompiledSchemaJSON / SequentialUncompiledHL7 / SequentialUncompiledHL7+XML-config | W1 (`number_of_worker_threads: 1`), BlockingFile + THREADING_MODE SEQUENTIAL |
| r-comp: +compilation | SequentialCSV / SequentialSchemaJSON / SequentialHL7 / SequentialHL7+XML-config | W1, full-opt JIT (fnattr + inline_invoke_calls + trace_constant_bytes + output-serialization fastpath + overload — everything folds into "compilation" at this granularity) |
| r-par: +parallelization | SIMDCSV / SchemaJSON / SIMDHL7 / SIMDHL7+XML-config | W23 (23 workers + 1 source thread = 24 physical cores, nothing oversubscribed; AMENDED from W16 2026-08-04 after the worker-count sweep -- ~90% incremental scaling to 24 cores, W23==W24 within noise, SMT unused by convention), ccx_aware_task_queues=FALSE + pin_threads=FALSE (AMENDED 2026-08-06: the ccx+pin combination is a ~2x PATHOLOGY for single-source runs — one source's sequence-ordered buffers round-robin across CCX cell queues while pinned workers cannot migrate; ccx+pin remains the MULTI-source production config), shredder path, **InMemorySource** |

- Scalar->SIMD indexing is a SEPARATE contribution (effort table / indexer section), NOT one
  of the two levers here — hence SIMD indexer in every rung.
- **InMemory only matters for r-par**: the two W1 rungs sit far below the ~11.3 GB/s file
  wall, so file-vs-InMemory is noise there; the W23 cells are exactly where the file wall is
  an artifact (clips at wall/bytes-per-row, i.e. differently per format). Setup-section
  sentence: "ablation experiments serve preloaded in-memory buffers to isolate proce  ssing
  from I/O; end-to-end and latency experiments use real sources."
- XML config on the HL7 formatters: message_delimiter '\n', segment '<', field '>',
  component '' , subcomponent '' (all four variants take it — proven by SequentialXML.test).

## 3. Stateless tier — 10 queries (cross-format, all three rungs)

All on `bid_strings` (ts UINT64, auctionId, bidder, price FLOAT64, channel VARSIZED,
url VARSIZED) unless noted. SQL below is shape-accurate; exact DSL spelling (CONCAT nesting,
modulo operator, function names) is fixed at yaml/systest time.

| # | id | query (shape) | hot-path regime | HOSP label |
| --- | --- | --- | --- | --- |
| 1 | q0 | `SELECT * FROM bid` | output serialization | full-stream forwarding (integration engine) |
| 2 | q_project | `SELECT price FROM bid` | projection, k=1 (parse-minimal + float codec) | minimal-data-set / de-identified export (extract just the measurement) |
| 3 | q_route | `SELECT * FROM bid WHERE channel == VARSIZED("Google")` | filter -> full-record output | ward-based full-message routing |
| 4 | q1 | `SELECT ts, auctionId, bidder, price*0.908 FROM bid` (og NEXMark currency conversion) | compute + codec | unit conversion (mg/dL -> mmol/L) |
| 5 | q2-og | `SELECT auctionId, price WHERE auctionId==A OR ==B OR ==C OR ==D OR ==E` (og NEXMark q2, 5-way OR) | filter, repeated-identical parse (GVN/overload territory) | test-code routing |
- ellision: comparison on raw string
- ellision: forward values
- dead code elimination: parse only: auctionId, price
- reordering: parse only if condition matches
- deduplictation: parse auctionId only once (instead of 5/6 times)
| 6 | q2-mod | `SELECT auctionId, price WHERE auctionId % 123 == 0` (Flink-nexmark q2) | filter, single parse + arithmetic | id-range partitioning |
| 7 | q10 | datetime-formatted export (CASTFROMUNIXTS-class function on ts) | compute/codec (datetime) | audit-trail export with human-readable timestamps |
| 8 | q14 | calculation (og-extended NEXMark bid arithmetic) | compute | derived values |
| 9 | q22 | concat over all rows (suite's q22_concat / concat_alert shape) | varsized/string output | alert-text generation (unconditioned) |
| 10 | **Q_ex** | see below | mixed-predicate filter, rare output | **THE WORKING EXAMPLE** |

**Q_ex — the HOSP working example** (modeled on the real a university hospital query: 2 string-eq +
threshold + nested-CONCAT alert; the second string match `Bez == "CALCIUM(BG)"` is a test
CODE, i.e. an identifier, rendered here as the numeric-id equality — bid has only one good
categorical string. UnixTimestampToDatetime STRIPPED per user (that lever lives in q10)):

```sql
SELECT CONCAT(CONCAT(CONCAT(
         VARSIZED("Detected low price ("), price),
         VARSIZED(") [Google] for auction ")), auctionId) AS alert,
       ts AS rowcount
FROM bid
WHERE channel == VARSIZED("Google")            -- string exact match   (Gruppe)
  AND (auctionId == A OR auctionId == B)       -- id exact matches     (Bez as test-code)
  AND price < FLOAT64(3.5)                     -- threshold            (Wert < 0.8)
```

- Selectivity knob: pick {A,B} + threshold for ~0.1-1% matched rows (clinically faithful —
  alerts are rare — and keeps the hot path the FILTER, not the concat; that is why q22
  stays in the set as the string-OUTPUT representative).
- Q_ex exercises int-eq (overload), string-eq (the varsized-literal compare the v4 ladder
  flagged as missing coverage — tcb territory), float-threshold parse, and CONCAT-of-numeric.
- The original HOSP query for the paper's motivation section (a university hospital-specific casts and
  all) is in the 2026-08-03 session transcript; general structure = filters(2-3 id-eq +
  1-2 string-eq) + nested CONCAT alert + a second scalar column.

**Excluded, stated in the paper**: q13 (needs bounded side-input join), q21 (needs
CASE/LIKE) — engine features, not formatter limitations. **Appendix/companion only** (self-
added variants, near-duplicates in the coarse view): q2_filter_proj, bid_filter_eq,
bid_ts_projection, person_projection, person_star.

## 4. Stateful tier — 3 queries (general working set; NOT in the ablation figure)

Chosen from the PROVEN 14-variant stateful suite of the Flink head-to-head (2_engine_to_e2e/
all_queries_benchmark_first_session.md §6, 84/84 clean) to span the state-cost axis:

| query | shape | role | HOSP label |
| --- | --- | --- | --- |
| YSB `ysb_1k_varsized` | string filter -> tumbling count per campaign | the "stateless-like" pole (few keys, cheap state, input-bound; 36-49x vs Flink, 8-10 GB/s — the "super fast" one the user remembered) | per-ward event/alarm rate per window |
| nexmark q8 (window join) | new persons JOIN their auctions per window | the state-dominated pole (1.4x vs Flink; format nearly irrelevant) | new admissions JOIN first lab results (ADT-ORU enrichment) |
| cm_q2 (windowed avg per group) | rolling per-group average | the middle (4.1x) | rolling per-ward baseline of a measurement |

(Alternative for slot 3 if preferred flavor: mfg_multi_agg = per-window min/max/avg summary
stats, "lab panel summary" reading — also proven.)

Operational constraints (from the stateful sessions — real mines):
- **Event-time windows over file sources = the proven path** (how all 14 ran). AVOID:
  replay into event-time windows (OPEN heap-corruption engine bug) and ingestion-time
  windows (segfault on this branch without the dropped count-loop patch).
- nexmark joins need the **stateful-pool** config from the head-to-head yamls.
- Avoid high-slice sliding configs (lrb_q1/sg3 territory = trigger contention; the sg1
  rolling-avg lock fix 95b575b93b is in, but slices/row is still the cost driver).
- No sequential/uncompiled arms, no cross-format twins needed — compiled, W16, native
  datasets. Sidesteps all uncompiled-path unknowns.

## 5. Datasets + validity

- Cross-format spine: `bid_strings` in all 4 formats, checksum anchor
  **31300000,269477267979** reproduced through every indexer (the byte-identical-semantics
  sentence no other cross-format ablation can write). Every workload query gets a per-format
  checksum gate before benchmarking.
- Robustness (text/appendix, passthrough only): ysb XML/HL7/JSON twins (arity 49, anchor
  5000000,25115005162), person (varsized-heavy, anchor 4000000,83746084707).
- ysb XML MB/s is meaningless vs CSV (glue 2.2x payload) — rows/s only; within-format
  ratios are metric-invariant anyway.

## 6. Open verification items (the NEXT session — validation systests)

1. **CONCAT-of-numeric on the uncompiled rung** (Q_ex, q22): rope forwards raw text for
   LAZY values; materialized values need the serialize-into-concat fallback. Systest Q_ex +
   q22 shapes through SequentialUncompiled{CSV,SchemaJSON,HL7,+XML-config}.
2. String-eq on materialized varsized (uncompiled rung) — Q_ex/q_route predicate.
3. `%` in the SQL parser (ModuloLogicalFunction EXISTS in nes-logical-operators; spelling
   `%` vs MOD() unverified) — q2-mod.
4. q10 datetime function name + whether the civil_from_days fix (uncommitted in ladder-v5
   session) is in the tree; paper must state which datetime codec was active.
5. InMemorySource: repeat/loop knob (runs must last seconds, 5.66GB @ 30GB/s = 190ms) +
   whether one source thread feeds 16 workers or becomes the new wall (probe: CSV q0,
   InMemory, W16 — query-dependent result = fine, flat pin = new wall).
6. Stateful stability probe: the 3 stateful queries on current branch tip (they ran on the
   head-to-head-era branch; re-verify on this tip).
