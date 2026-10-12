# Paper Section 2 (Background & Motivation) figures — method + data (2026-08-19)

Both figures use the **naive NebulaStream baseline** from the Flink/Spark head-to-head where noted.
All-numeric `bid_star` dataset (u64 ts, i32 auctionId, i32 bidder, f64 price — NO varsized, so the
numeric (de)serialization cost is not diluted by cheap string passthrough). bid_1GB.csv (`medium`,
4-field aligned; NB bid_653M/`small` has 5 columns and the uncompiled path rejects it).

## Figure 1 — per-query (de)serialization breakdown
`fig1_parsing_overhead_2026-08-19.{pdf,png}` + `_data.csv`

- Vehicle: naive arm = `SequentialUncompiledOldCSV` (scalar indexer, interpreted) + `JSONUncompiled`
  + `NES_INPUT_CODEC=original` (stod / from_chars_with_exception) + `NES_OUTPUT_CODEC=original`
  (fmt/stringstream JSON writer, `JSONFormat::formatOriginalStringstream`). W1, InMemory prefill
  (**read nulled**, so the bars are pure compute: deserialize / process / serialize). csv->json.
- Method: `perf` self-time on the running worker (nes-profile skill), 20 s @ 4 kHz. The naive
  pipeline splits cleanly by thread: **DataSrc thread = index+parse = deserialize**; **WorkerThread
  = query ops (process) + naive JSON writer (serialize)**, sub-split by symbol. Normalized over the
  three engine stages; kernel + idle-spin excluded. q10 CASTFROMUNIXTS (datetime->ISO text, 2%)
  counted as serialization; q10 "process" (4.6%) is varsized-write mechanics (conservative).
- Data (normalized %, + naive throughput):
  | query | deserialize | process | serialize | Mrows/s |
  |-------|------------:|--------:|----------:|--------:|
  | q0 SELECT *         | 26.9 | 1.0 | 72.1 | 2.3 |
  | q1 currency conv.   | 25.8 | 1.0 | 73.2 | 1.8 |
  | q10 datetime fmt    | 23.0 | 4.6 | 72.4 | 1.7 |
  | q2 filter (0.8% sel)| 97.0 | 1.5 |  1.5 | 6.6 |
  | YSB windowed count  | 93.2 | 6.8 |  0.0 | 2.0 |
- YSB (Yahoo Streaming Benchmark, `ysb_1k_varsized`): stateful, tumble-30s COUNT/campaign, filter
  event_type='view'. Naive arm on **InMemory single-pass** (repeat=1 -> window-safe, NOT replay;
  read nulled) over xlarge (80M rows). deser = 93% (varsized string-copy `getBasicStringParseFunction`
  33% + event_time parse + varsized child-buffer handling); process = 7% (the real windowed
  aggregation: `hashBytes` GROUP BY, `loadValue`, JIT window/count code); serialize ~0 (68k
  output rows). WorkerThread was mostly kernel idle-spin (source-starved) -> excluded from the norm.
- Message: output-heavy queries are **serialization-bound (~72%)**; the selective filter **inverts
  to 97% deserialization** (parses every row, serializes 0.8%). Query processing is <7% everywhere
  => >=93% of engine work is (de)serialization. q2 is ~3x faster precisely because it skips
  serialization for 99.2% of rows. **Even the canonical streaming benchmark (YSB) spends 93% of CPU
  deserializing input; its windowed COUNT — the "actual query" — is 7%.**

## Figure 2 — rows/s vs MB/s
`fig2_rowss_vs_mbps_2026-08-19.{pdf,png}` + `_data.csv`

- Vehicle: **fast COMPILED** `SequentialCSV` csv->json, InMemory W1. 10 datasets `nf1..nf10.csv`
  (constant ~200 MB, N=1..10 equi-width .6f FLOAT64 columns; bytes/row 10.9 -> 108.9). Query
  `allf_nN` = `SELECT c0*FLOAT64(1) ... cN-1*FLOAT64(1)` — forces full parse+serialize of all N
  (defeats passthrough elision). Metric: measured rows/s; input MB/s = rows/s x input bytes/row
  (== pbench throughput_mbps).
- Data (median n=3): MB/s 322/327/318/308/319/302/308/301/301/303 (N=1..10, +/-4%, ~311 mean);
  Mrows/s 29.5/15.0/9.7/7.1/5.8/4.6/4.0/3.5/3.1/2.8 (**10.5x span**).
- Message: identical MB/s (~311) hides a **10.5x** difference in rows/s — MB/s is the wrong metric
  for a stream processor; rows/s (tuples/s) is what matters.

## Reproduce
Experiments (scratchpad -> keep if wanted): fig1_prof_{q0,q1,q10,q2mod}.yaml (profiling windows),
fig1_thru.yaml (throughput), fig2_fieldsweep.yaml. New query yamls in piparse-bench (UNCOMMITTED):
queries/multicol/allf_n{1..10}.yaml; queries/nexmark/q2_filter.yaml gained a `medium` entry.
