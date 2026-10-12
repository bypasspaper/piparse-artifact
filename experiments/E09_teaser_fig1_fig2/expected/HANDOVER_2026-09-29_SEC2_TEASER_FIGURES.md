<!-- SPDX-License-Identifier: Apache-2.0 -->
# HANDOVER 2026-09-29 — Paper §2 motivation/teaser figures (Fig1 CPU split, Fig2 field sweeps)

Session 2026-09-25 → 2026-09-29. ENTRY POINT for this thread. Detailed method + numbers per experiment live in
`fig1_fig2_teaser_2026-09-25.md` (same dir, 8 sections, keep it as the reference); this file is the map, the state,
the decisions and the open items. Earlier context: `fig1_fig2_motivation_2026-08-19.md` (NES naive originals),
`fig1_fig2_flink_2026-09-03.md` (Flink repeat). Memory: `fig1-fig2-teaser-probes.md` (+ `fig1-fig2-motivation-flink-repeat.md`).

## 0. TL;DR — what exists and what to use
| Paper slot | USE THIS | Status | Notes |
|---|---|---|---|
| Fig1 (§2 teaser, CPU by stage) | `fig1_teaser2_naive_flink_optimised_2026-09-28.{pdf,png}` + `_data.csv` | DONE | q0 / NEXMark Q2-original (5-way OR, overload ON) / YSB; naive, Flink, optimised; (a) share %, (b) ns/tuple log |
| Fig2 (§2 teaser, rows/s vs MB/s over N fields) | `fig2_pred_rowss_mbps_4arm_2026-09-28.{pdf,png}` + `_data.csv` + `_raw.csv` | DONE, recommended | PREDICATE sweep `SELECT * WHERE c0 < 8000` over mixed INT32+FLOAT64 rows; naive / bypass±overload / Flink; most prominent design |
| Fig2 alternatives (evaluation / appendix) | `fig2_v2_rowss_mbps_{3rung,teaser}_2026-09-25.*` (all fields output), `fig2_proj1_rowss_mbps_3arm_2026-09-26.*` (one field projected) | DONE | see §2 for the cost laws of all three designs |
| Fig2 stage-CPU vs N (eval) | `fig2_v2_stage_cpu_naive_vs_lazy_2026-09-25.*`, `fig2_v2_stage_cpu_per_tuple_log_2026-09-26.*` | DONE | deser/proc/ser per N, naive vs lazy, 20 perf profiles |
| NOT for the paper | `fig2_v2_cpu_per_row_2026-09-25.*`, `fig2_v2_cpu_utilisation_2026-09-25.*` | superseded | per-THREAD CPU views; author: threads are irrelevant, stages are what matters |
| Fig1 v1 | `fig1_teaser_naive_vs_optimised_2026-09-25.*` | superseded | overload OFF, q2 = MOD-123 variant |

**Decisions taken with the author (do not re-litigate):** (1) §2 figures are SIGMOD-style TEASERS (naive + Flink +
fully optimised), evaluation carries the rigorous versions. (2) Stage taxonomy: deserialize = index + parse; serialize =
formatting + JSON framing; **process = operator work incl. the raw passthrough copy** (caption sentence: a native
engine would copy too) + engine glue (disclosed); no separate index segment. (3) Fig1 filter bar = ORIGINAL NEXMark Q2
(equality chain) with overloading ON, not the MOD rewrite (overload cannot apply to MOD). (4) Fig2 = predicate sweep on
MIXED rows (INT32 predicate column, FLOAT64 payload) because the FLOAT lazy rep overloads only ==/!= vs int constants
(rounding) while the INT rep overloads <,<=,>,>=. (5) Author wants results collected so the visualisation can be chosen
AFTERWARDS: per-run artifacts (sink CSV + per-thread CPU series) are now persisted (§4). (6) 10 reps for NES sweeps,
3 for Flink. (7) The paper claim on Fig2 must be phrased as per-field slope / fitted law a+bN, NOT "rows/s falls x
times" (relative span rewards big fixed costs — Flink looked "flattest" in the projection sweep for that reason).

## 1. Fig1 teaser v2 — numbers (share deser/proc/ser %, CPU ns/tuple, Mrows/s)
| query | naive | Flink 2.1.3 | optimised (fnattr + inline + tcb + overload) |
|---|---|---|---|
| q0 SELECT * | 25/3/72, 613 ns, 2.2 | 41/1/58, 978 ns, 1.8 | 27/49/24, 12.6 ns, 86.2 (49x CPU) |
| Q2 original, 5-way OR on auctionId | 98/1/0, 162 ns, 6.3 | 88/12/0, 364 ns, 3.8 | 70/28/2, 4.8 ns, 232 (34x) |
| YSB windowed count | 91/9/0, 559 ns, 1.8 | 82/18/0, 1351 ns, 1.4 | 56/44/0, 22 ns, 34.5 (25x) |
Reading Q2 optimised: the 70% "deserialization" IS the SIMD index alone (3.3 ns; no parse symbol in the profile —
five raw-digit word-compares), i.e. a large share of a tiny number; put the absolute next to the share in the caption.
Residual lever (future work): the index touches every delimiter incl. fields the predicate never reads.
Method: NES shares from perf (flat 20 s @4 kHz; YSB whole-life + windowed to the 2-3 s query burst), naive by the
2026-08-19 thread+symbol rules, optimised by `classify_v2.py` + JIT split (q0: json−csv differencing 2.8 ns → ser;
no-output queries: JIT → process). NES absolute = own procfs CPU in the sink window × (1−idle)/rows over ALL busy
threads (naive uses ~1.5 cores → CPU/tuple > wall/tuple; optimised ≈ 1 real core + a spinning worker excluded).
Flink: async-profiler cpu@4 kHz whole job, `classify_flink.py`, absolute = stage samples/4000/rows, GC/JIT excluded.
Caveat: panel (b) stacks on a LOG axis (segments not to scale; read the split from (a)).

## 2. Fig2 field sweeps — cost laws ns/row = a + b·N (10 points, R² ≥ 0.998 unless noted)
| Design (query over N cols, ~200 MB/file) | naive | compiled eager | bypass (lazy) | Flink 2.1.3 | slope ratio naive/Flink : bypass |
|---|---|---|---|---|---|
| A. all fields out `SELECT *` (`pass_nN`, FLOAT64) | 58.7 + 134N | −3 + 36N | 1.0 + 2.7N | 196 + 126N (09-03) | 50x / 47x |
| B. one field out `SELECT c0` (`proj1_nN`) | 46 + 76N (N=1 degenerate) | — | 2.8 + 1.17N | 273 + 24N, flat to N=5 (R² 0.79) | 65x / 20-38x |
| C. predicate `SELECT * WHERE c0<8000` (`pred_nN`, INT32 + FLOAT64) | −38 + 82.6N | — | ovl 1.1 + 1.24N; no-ovl 7.9 + 1.42N | 20 + 90.6N | 67x / 73x |
Why C: Flink has no escape (eager conversion of every payload float before the Calc drops 99.2%), the int predicate
column gives no arm a large fixed cost (rows/s panel ranks bypass flattest on its own: spans ovl 5.7x, Flink 9.2x,
naive 21x), and the overload ON/OFF pair is a one-knob ablation (−6.8 ns fixed = the FastINT32 parse; same slope).
A shows bypass at 2.7 ns/field = index + copy + JSON key (byte-bound, 0.49 CPU ns/byte flat vs eager 4.3); B shows
index-only 1.17 ns/field; the "linear in N" of ns/row is bytes/row growing, not per-field serde.
Datasets: `nf{N}.csv` (all FLOAT64, 2026-08-12) and NEW `nm{N}.csv` + `nm{N}_x10.csv` (INT32 + FLOAT64, numpy seed
1000+N, 2026-09-27/28, 22 GB) under `cmake-build-release/nes-systests/testdata/large/multicol/`. Flink uses the x10
files (2 GB, JVM-length jobs; N≥7 still only 10-17 s — warm-up share caveat).
Stage-CPU vs N (naive vs lazy, design A): naive ~36/2/62 flat, lazy settles ~35/42/22 from N≥4 (index +1.0, copy+glue
+0.95, JSON framing +0.8 ns/field); `stage_cpu_sweep.py`, 20 profiles in `_scratch/optprof_sweep/`.

## 3. Flink facts established (all verified, scripts in `_scratch/flink_explain/`)
- Projection pushdown EXISTS at the planner (EXPLAIN: `TableSourceScan(..., project=[c0])` for `format=csv` AND
  `json`; `CsvFileFormatFactory$CsvBulkDecodingFormat`, `CsvFormatFactory$1`, `JsonFormatFactory$1` implement
  ProjectableDecodingFormat) but reaches only the CONVERTER: csv = Jackson MappingIterator<JsonNode> tokenises EVERY
  column (nextChar scan, TextBuffer copy, String + TextNode alloc, ObjectNode map put) then converts projected ones;
  json = readTree of the whole document (numeric literals parsed into DoubleNodes for ALL fields). Worth ~5-10 ns/field.
- Predicate pushdown: `FileSystemTableSource` implements SupportsFilterPushDown and the scan digest shows
  `filter=[...]`, but the Calc keeps `where=[...]` and the scan reads all predicate columns — the source only records
  the filter (partition pruning/statistics). There is NO filterable decoding format in the table API.
- `SELECT *` + predicate converts EVERYTHING eagerly: q2 vs q0 whole-job fetcher samples FloatingDecimal 20.4k vs
  21.6k, int parse 28.6k vs 31.5k, CsvToRowDataConverters 104k vs 116k (same per-row conversion, 99.2% dropped).
  Only VARSIZED strings are lazy (BinaryStringData materialised in the first Calc that touches them).
- The "~300 ns fixed cost" in sweep B was the float c0 parse+serialise per row, not framework: with a lone int
  column Flink's N=1 is 100 ns (sweep C).

## 4. Infrastructure changes — ALL UNCOMMITTED in ~/work/piparse-bench (git status: 191 untracked, several modified)
- `piparse_bench/runners/worker_cli.py`: `_ThreadCpuSampler` (reads /proc/<pid>/task/*/stat every 0.25 s for the
  worker's life → `threadcpu.csv`; samples the pid that LISTENS on the worker port via `_pid_on_port`, warns if it is
  not the launched worker), `_persist_artifacts` (→ `results/artifacts/<experiment>/<run_id>/{query_*_monitoring.csv,
  threadcpu.csv, worker.log}`; run row `config._artifacts`), run_id generated up front. Disable with
  PBENCH_NO_THREADCPU / PBENCH_NO_ARTIFACTS. `cpu_from_artifacts.py` derives per-thread CPU inside any window.
- `configs/parameters.yaml`: `overload: true` rule now accepts branch benchmark-piparse-lazyparse-fast-csv (stale rule;
  the predicate sweep only validated because overload sat in a series override, which the validator ignores).
- Queries: `queries/multicol/{pass,proj1,pred}_n{1..10}.yaml` (30 files; sink_schema MUST be qualified `t.cN`, an
  unqualified name fails nes-cli submission SILENTLY). Experiments: `fig2_fieldsweep_v2{,_smoke}`, `fig2_lazy_csvout`,
  `fig2_proj1_{nes,flink}{,_smoke}`, `fig2_pred_{nes,flink}{,_probe}`, `fig1_opt_{prof_q0,prof_q2mod,prof_ysb,diff}`,
  `fig1_teaser_thru`, `fig1_flink_{prof,thru}_q2og`. `results/artifacts/` 81 MB (34 experiments).
- Scripts (copies in `fig1_fig2_teaser_2026-09-25_scratch/` + subdirs `teaser_v2/`, `pred_sweep/`, `pred_probe/`,
  `optprof_sweep/`, `flink_explain/`): profiling `profile_opt_one.sh` (attach-and-wait), `profile_ysb_full.sh NAME`
  (whole-life + `window_report.sh`, needed when the query burst is <20 s), `profile_flink_one.sh`; classification
  `classify_v2.py` (optimised), `stage_cpu_sweep.py` (naive rules + sweep assembly), `classify_flink.py`; assembly
  `assemble_teaser2.py` + `assemble_teaser2_flink.py`; extraction `extract_fig2_v2.py`, `proj1_extract_plot.py`
  (`--nes-exp/--flink-exp/--tag`), `extract_diff.py`; plots `plot_teaser2.py`, `plot_fig2_v2.py`, `plot_fig2_stage*.py`,
  `plot_pred_sketch.py`.

## 5. Gotchas learned (expensive ones first)
1. GHOST WORKERS: crashed/deadlocked `main` workers survive, get reparented to systemd and keep :9099; the next
   worker fails to bind SILENTLY, the ghost serves the queries, any pid-based sampler reads an idle process (CPU≈0).
   Pre-flight `pkill -9 -x main` + `ss -ltnHp 'sport = :9099'` empty; the sampler now follows the port-holder.
2. YSB optimised SINGLE PASS segfaults ~30% of runs: `ChainedHashMap::updateTimestamp` ← JIT ←
   `CompiledExecutablePipelineStage::execute` on the source thread, repeat=1, with or without perf (also one exit-8
   death). New manifestation of the replay heap-corruption bug. Use the retry loop (`run_teaser2.sh: ysb_retry`).
3. NEVER `pkill -x main` while a pbench experiment is still running — it killed run 400/400 of the first sweep.
4. The optimised sequential arm runs the WHOLE fused pipeline on the SOURCE thread; WorkerThread-0 is ~50% of
   samples but pure idle spin (sched_yield/semaphore backoff/vdso) — classify BOTH threads by symbol, exclude idle.
   Naive is the opposite (parse on source, interpreted JSON writer on worker, both real work).
5. JIT code is opaque to perf (`[JIT] tid N`), libc memcpy ~0% (copies inlined) → split the block by knob differencing
   (csv-out vs json-out; eager_parse) — `fig1_opt_diff`, `fig2_lazy_csvout`.
6. `strings` finds NO descriptor keys in the release worker (not even sequence_shredder_mode) → verify knobs by
   behaviour. `inline_invoke_calls` and `trace_constant_bytes` DEFAULT TRUE (QueryEngineConfiguration.hpp) → every
   optimised arm here = ablation r6 "context" layer; FastINT32 = NAUTILUS_TAGGED_INVOKE native call (~6.7 ns/row).
7. `perf script` prints comm BEFORE time whatever -F order; `perf stat --per-thread` folds threads spawned after
   attach into their creator (useless for pipeline threads); DuckDB is write-locked while pbench runs.
8. generator.repeat MUST equal worker_env.NES_INMEM_REPEAT (input_rows = catalog rows × generator.repeat).
9. naive N=1 on a 1-column row is degenerate (no field delimiter, old scalar indexer +75 ns) — read naive slopes from N≥2.
10. Eager perf-stat/uProf were evaluated and rejected for the sweep sampler (perf stat: late threads; uProf: no time
    series, session overhead); uProf works without sudo and lists late threads — use it for deep profiles.

## 6. Open items / next steps
- Paper: adopt Fig1 v2 and Fig2 C; captions: copy-counts-as-processing sentence, absolute next to share (Q2 70% =
  index), log-axis note for panel (b), Flink 3 reps + JVM warm-up share; phrase Fig2 as per-field slopes.
- Abstract: "pay for serde three times" is fine (no "over"); the LLM-smell was the matched "a X per Y" tricolon —
  name what each cost is paid IN (threads / CPU / engineering) and vary the clause shapes (2026-09-28 discussion).
- Evaluation extras already measured or cheap: eager rung (design A), overload ON/OFF series (design C), stage-CPU vs
  N (design A only — repeat for C if wanted: 20 profiles ≈ 15 min via `run_teaser2.sh`-style chain), q1/q10 optimised
  profiles (mixed-case bars), N=16 out-of-sample check of the cost laws (`parse_k16` row exists).
- Bugs to file: YSB single-pass SIGSEGV (§5.2); the silent-bind-failure of the worker when the port is taken.
- Commit the pbench changes (runner sampler/artifacts, parameters.yaml rule, queries, experiments) — currently
  uncommitted together with older uncommitted work; nothing in the nebulastream repo changed this thread.
- Future-work note for the paper: a lazier index that stops at the last field a query needs (Q2's residual 3.3 ns).

## 7. Reproduce (from ~/work/piparse-bench; binary cmake-build-release worker+nes-cli mtime 2026-09-03 10:50)
```
pkill -9 -x main; ss -ltnHp 'sport = :9099'          # must be empty
PBENCH_KEEP_LOGS=1 uv run python bench.py run experiments/fig2_pred_nes.yaml --build-dir ~/work/nebulastream-public/cmake-build-release --worker-port 9099
uv run python bench.py run experiments/fig2_pred_flink.yaml --build-dir ~/work/nebulastream-public/cmake-build-release
uv run python <scratch>/proj1_extract_plot.py --nes-exp fig2_pred_nes --flink-exp fig2_pred_flink --tag fig2_pred <outdir>
<scratch>/teaser_v2/run_teaser2.sh                   # Fig1 v2 chain (6 NES profiles, throughput, Flink q2og)
uv run python <scratch>/teaser_v2/assemble_teaser2.py && uv run python <scratch>/teaser_v2/assemble_teaser2_flink.py
python3 <scratch>/teaser_v2/plot_teaser2.py fig1_teaser2_data.csv <stem>
```
(`<scratch>` = `fig1_fig2_teaser_2026-09-25_scratch`; the YAML templates for profiling windows are in `teaser_v2/`.)
