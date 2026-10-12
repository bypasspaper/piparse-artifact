# Gang-parallel (SotA) parsing vs DPP — latency vs #streams — EXPERIMENT DESIGN (DRAFT, 2026-09-08)

Status: **draft v6 (probe DONE both spin policies: expectations hold, see probe/RESULTS.md), nothing implemented, nothing run.** Replaces the LF-vs-LOCKING buffer sweep
(`../shredder_bufsweep_x86_2026-09-03/`) as the paper's SequenceShredder/DPP micro figure. Written from
`~/Notes/nebulastream/benchmark/HANDOVER_2026-09-08_SPECULATIVE_PARALLELISM_EXPERIMENT.md` §2-§4.
Box: Threadripper PRO 5965WX = 24 cores × 2 SMT (cpu i and cpu i+24 share a core; 6 cores per L3, 4 L3s),
governor already `performance`. Branch `benchmark-piparse-lazyparse-fast-csv` @ b5d757c9f6 + uncommitted rig edits.

## 0. Claim and figure

**Claim (C1 micro):** state-of-the-art data-parallel text parsing binds a gang of k threads to each stream
(chunk the input, advance the FSM on every chunk in parallel, join per chunk — ParPaRaw, Ge et al. '19,
path fusion). That is the right design for ONE fast stream and the wrong one for hundreds of streams on a
fixed core budget: once N·k exceeds the cores, the per-chunk join waits for descheduled gang members and the
latency tail collapses, while DPP (one thread per buffer, any thread, shared pool, no join) stays flat until
the cores are genuinely full.

**Load model: CLOSED LOOP, FULL LOAD** (user decision 2026-09-08: "all queries processing data concurrently for
maximum pressure"). Every stream hands over its next buffer the moment its previous one is done, so all N
streams are always active and the engine is always at capacity — the intro figure's method (file sources at
full speed). Open-loop (each stream emits at a fixed rate regardless of engine load, like a real sensor) is an
OPTIONAL appendix only.

**Figure (2 panels, log x):**
- (a) x = concurrent streams N (1 … 256), y = per-buffer residence latency p99 (µs, log); lines DPP /
  gang-shared / gang-private, each gang line = "gang-best" (min over k ∈ {1,2,4,8}); dashed = p50.
  Panel (c): sustained aggregate GB/s and CPU-seconds per GB (the "resources per query" axis).
- (b) same x, gang-private for k ∈ {1, 2, 4, 8} vs DPP — the knee moves with 24/k; k=1 = thread-per-stream
  (the intro figure's SPE model).
- Appendix: DPP at the engine's real backpressure (64 in-flight/source + admission queue 1000): under full
  load a flat ≈ 3 ms backlog line — shows deep queues trade residence for throughput; bigstr dataset;
  16 KiB; J / chunk-granularity sensitivity; open-loop. (S=2 dropped — §2b.)

**What "latency" means here (decides the whole shape).** The clock starts when the parsing stage ACCEPTS the
buffer and stops when every tuple ending in it is emitted (max(done_s, done_{s−1})). Both arms run with ONE
buffer in flight per stream (D = 1): the gang intrinsically (leader takes the next buffer after the join),
DPP by the same rule (the stream's next buffer is enqueued when its previous one completed). Symmetric, no
knob. The engine's real backpressure (64 in-flight buffers per source, global admission queue of 1000 tasks —
`RunningSource.cpp:296`, `worker.query_engine.admission_queue_size`) is an APPENDIX arm: under full load it
keeps ~1000 buffers of backlog, i.e. a flat ≈ 3 ms residence (1000 / 330 K buf/s) that sits ABOVE the gang's
line until N ≈ 700 — deep queues buy throughput smoothing with residence, and the paper must not present that
as the DPP latency. Waiting BEFORE acceptance is throughput's job to report, not latency's.

**Expected shapes under full load — Little's law first.** Past saturation every design's residence is
backlog ÷ throughput, so the p50 lines of DPP and the gang both grow ∝ N once their cores are full. The
figure's signal is therefore (1) WHERE the knee is — DPP at N ≈ cores, the gang at N ≈ cores/k; (2) the
gang's constant p50 offset above DPP from its per-buffer switching overhead (throughput loss, expect 1.3-2×);
(3) the gang's p99 fanning out from its p50 (a buffer completes only when all k members got a scheduling
turn; DPP never has more runnable threads than cores, so p99 ≈ p50). **This rig will NOT show orders of
magnitude** — that came from blocking IO wake/park storms in the intro figure (`tcp-blocking-collapse-
mechanism`), which a compute-only rig does not have; option B (e2e gang formatter in the blocking source
path) would include them.

| arm | N = 1 | knee | past the knee (p50) | p99 / p50 | throughput |
|---|---|---|---|---|---|
| DPP, D=1 | ~75 µs (128 KiB on one thread @ ~1.8 GB/s) | N ≈ 23 (= cores) | ≈ N/23 × 75 µs (queueing only) | ≈ 1-1.5 | max, ~42 GB/s |
| gang-shared k=4 | ~30-50 µs (**wins**: 4×32 KiB in parallel + join) | N ≈ 23 | ≈ DPP + fixed floor (fork/join, k wakes) | ≈ 1.5-2 | slightly below DPP |
| gang-private k=4 | same | **N ≈ 6 (= cores/k)** | ≈ (N·k/24) × (chunk + switch) — same slope as DPP, offset by the switching overhead | **3-5+**, growing with N·k/24 (convoy at the join, preemption of mid-chunk members) | ~8 context switches + ~7 futex wakes per buffer → 0.6-0.8× DPP |
| DPP, engine defaults (appendix) | same as DPP | N ≈ 16 (backlog hits 1000) | flat ≈ 3 ms = backlog/throughput | ≈ 1 | max |

The honest part: gang parallelism WINS at N=1 by up to ~2× (k threads on one buffer; DPP can only parallelise
across buffers, which does not shorten a single buffer's latency). Between N ≈ 6 and N ≈ 23 the gang rises
while DPP is still flat — that window plus the tail fan-out is the qualitative message; the crossover N is
the number.

**Falsifier.** If gang-private residence stays within ~1.5× of DPP to N=256 with p99/p50 < 3, the Linux
scheduler multiplexes 1024 compute threads well enough that "threads per query" is not a latency cost at this
granularity, and the paper's C1 wording must retreat to the throughput loss + the e2e (IO-bound) collapse.

## 1. Decisions (answers to handover §4) — please confirm or overrule

1. **Option A (isolated micro-rig) first.** It isolates the three costs and is the rig the old figure came from.
   B (e2e gang formatter in NES's blocking-source path) stays a follow-up, justified by A's arms.
2. **Emulation = the DPP pipeline on sub-chunks + gang structure on top; speculation is free and always
   correct.** Each gang chunk task runs the SAME compiled Scan(SIMDCSV)->Emit stage DPP runs, so per-byte
   index and parse cost is identical by construction; the gang adds fork, join, and (gang-private) k dedicated
   threads. Both datasets are quote-free, so the chunk-start guess ("outside quotes, scan to the next
   newline") is exactly what DPP pays per buffer — the most favourable case for the gang. The S=2 enumeration
   knob is DROPPED (§2b: it would charge the gang for quoted fields DPP does not handle either).
3. **Gang-best envelope (min over k ∈ {1,2,4,8}) in panel (a); per-k lines in panel (b).** k=1 private =
   thread-per-stream = the intro figure's SPE model.
4. **Closed loop, full load = headline** (user, 2026-09-08). Every stream always has its next buffer ready;
   D = 1 in flight per stream in BOTH arms (symmetric; re-emitted by the done-stamper). Latency = residence
   from acceptance to completion (§0). DPP behind the engine's real backpressure (64/source + admission 1000)
   is an appendix arm only — under full load it is a ~3 ms backlog line, not a latency claim. Open-loop is an
   optional appendix (at moderate load idle gang threads cost nothing; the cost is a full-load phenomenon).
5. **Old LF/LK sweep survives as an appendix** (done, documented, costs nothing).

## 2. Arms — the three costs kept separable

| arm | threads on the 24-core cpuset | per 128 KiB buffer | synchronisation | isolates |
|---|---|---|---|---|
| **DPP** | 23 workers pinned cpu 0-22, producer cpu 23 | 1 task; boundaries via SequenceShredder | shared MPMC + counting semaphore (`leansem` dynamic: workers park when idle, 1 wake/buffer) | baseline |
| **gang-shared** | same 23 workers | first worker to take the buffer forks k chunk tasks (B/k each) into the shared queue, does one itself; last finisher stamps done | per-buffer atomic join counter; chunk boundaries via the shredder (chunk seq numbers) | (b) redundant work + (c) fork/join, WITHOUT oversubscription |
| **gang-private** | N gangs × k threads (unpinned inside the cpuset) + producer | leader takes the buffer, wakes k−1 members (fork), all index+parse their chunk, sense-reversing barrier (join); ONE buffer at a time per gang (SotA parallel-for semantics), later buffers queue at the leader | futex generation counter + barrier | adds (a) threads-per-query oversubscription |
| **chunker** (user, 2026-09-08) | N light cutter threads + the same 23 workers | ONE thread per stream only CUTS the buffer into record-aligned chunks (memchr to the next newline at k cut points + one small memcpy for the boundary row) and hands the self-contained chunks to the pool; workers parse them with per-worker SEQUENTIAL stages | none: no shredder, no join, no speculation (a passive completion counter only) | the cost of ANY per-stream thread (light work, in the critical path) — Arrow-reader-like design point between DPP and the gang |

Fairness notes: same kernel, same parse, same bytes, same cpuset, same producer (1 enqueue + 1 wake per buffer
in every arm — the fork cost sits on the gang, as in real gang systems). The gang pays k wakes/buffer, DPP 1:
inherent to the approach, not a strawman. Boundary stitching inside a gang buffer goes through the shredder
(k−1 calls of ~1 µs per buffer) — slightly MORE than a hand-rolled carry, ≈ 6 % of a 32 KiB chunk's work;
noted, not corrected (it is also what a shredder-less gang would pay in its own stitch step).

## 2b. Fairness model — how the speculative / multi-thread approach is emulated (user question, 2026-09-08)

Five dimensions, each with the honest answer and the strawman it avoids:

1. **Work per byte.** Gang chunk = the SAME compiled Scan(SIMDCSV)->Emit stage DPP runs. Intrinsic
   speculation cost = at each chunk start "assume outside quotes, scan to the next newline" — on quote-free
   data always right, and exactly what DPP pays at every buffer start. So the headline isolates the
   STRUCTURAL cost with speculation free and always correct: the point most favourable to the gang.
   **S=2 enumeration panel DROPPED** (it would charge the gang for quoted fields, which DPP on this branch
   does not handle either → comparing against a capability we lack). Text only: on formats where the
   assumption fails, the gang pays a verify pass / enumeration and DPP its speculative-bit fallback
   (`piparse.tex` l.798-804, not implemented) — neither evaluated.
   Strawman avoided: re-parsing everything on speculation, runtime chunk copies, extra shredder calls beyond
   what DPP pays at the same chunk size.
2. **Synchronisation primitive.** Join = atomic counter; fork/join waits = spin-then-block with a bounded
   spin budget (~50 µs, the OpenMP/TBB policy): best latency while N·k ≤ cores, best behaviour when
   oversubscribed, without per-cell tuning. Strawman avoided: mutex barrier, lock + condvar broadcast.
3. **Thread mapping** (the published parsers are batch tools for ONE input; the N-stream mapping is our
   construction, so show both):
   - **gang-private** — k threads owned by each stream = a SotA parallel parser inside a SotA SPE's
     thread-per-source model; the related-work claim ("dedicated parallel resources per parse job").
     **k=1 private = plain thread-per-stream parsing = the intro figure's SPE model** → anchors the figures.
   - **gang-shared** — fork/join per buffer on the 23 DPP workers = the best adaptation a SotA author would
     propose; it already borrows our resource model → the ABLATION, not the opponent. Be ready: it may
     match/beat DPP on latency below saturation (a buffer's work split k ways, cheap join at 128 KiB) —
     that says the win is the resource model, and DPP could adopt sub-buffer chunking for low-load latency.
4. **Configuration envelope.** The gang gets its best configuration at every N: min over k ∈ {1,2,4,8},
   unpinned (CFS balances; check at the knee that pinning does not change the conclusion). Caption: "gang-best".
   Knobs exposed but not swept by default: **J** = buffers per fork/join (amortises the join, adds batching
   latency, D = J) and **chunk granularity** (B/k sub-chunks = SotA parallel-for = headline; or whole buffers,
   one per thread = DPP-like across-buffer parallelism inside a private gang, the gang's throughput-best).
5. **Metrics.** Latency alone flatters the gang at N=1 (k threads on one buffer). Add **CPU-seconds per GB
   parsed** (`getrusage(RUSAGE_SELF)` user+sys delta over the window ÷ bytes completed) = "resources per
   query" stated directly; the crossover N in latency AND in CPU/GB is the result. Same enqueue path and
   stamp rule in every arm.

**Optional real-system anchor** (½ day, footnote not figure): DuckDB's parallel CSV reader (real
speculate-and-verify at chunk boundaries) or Arrow's multithreaded CSV reader (parallel-for over blocks) on
ONE stream of the same file → our gang emulation at N=1 is ≥ as fast per byte, so it is not a weak stand-in.

## 3. Load model and latency definition

- **Stream context** = one compiled stage (own InputFormatter → own SequenceShredder → own sequence space; the
  compiled scan captures its formatter at trace time, so N contexts = N compiles, ~0.5 s each, done ONCE per
  N-cell outside every timed window and reused across arms × loops × reps) + a ring of R = 64 raw buffers
  (8 MiB/stream, 2 GiB at N=256) pre-loaded from the file's first R buffers, the ring's last buffer trimmed to
  its last '\n' so cycle wrap is a clean record boundary. For gang arms the ring is pre-split into k chunk
  TupleBuffers at setup (no runtime copy). Sequence numbers continue across cycles: DPP seq = c·R + j,
  gang seq = (c·R + j)·k + chunk.
- **Closed loop, D = 1:** at start the producer (cpu 23) emits buffer 0 of every stream (staggered over the
  first ~100 ms so the shredders do not all start in lock-step). Afterwards the done-stamper of buffer j of
  stream i emits buffer j+1 of stream i itself (sets seq, stamps `enq`, enqueues / hands to the gang leader).
  No producer in the loop — no producer bottleneck. Appendix knobs for the DPP arm: `NES_LAT_D` (in-flight
  window per stream, engine default 64) and `NES_LAT_CAP` (global admission-queue capacity, engine default
  1000; 0 = unbounded); the emitter blocks on both BEFORE stamping `enq` (= the source waiting for a pool
  buffer / for `pendingTasks < inflightLimit` in the engine). Gang-private: D = 1 is intrinsic. Gang-shared:
  the buffer's chunks are forked into the same queue.
- **Latency per buffer s of a stream** = max(done_s, done_{s−1}) − enq_s. Rationale: the tuples that END in
  buffer s are its complete tuples (done_s) plus its leading spanning tuple, which is resolved by whichever of
  execute(s−1)/execute(s) runs last. Gang: done = join completion. Repeats (neighbour not yet processed) show
  up naturally as latency.
- **Window:** 2 s warm-up discarded, 10 s measured, then stop re-emitting and drain. Report per cell: pooled
  p50/p99/p999/max over all buffers of all streams (the rig has raw samples), plus median-across-streams p99
  and worst-stream p99 (the e2e harness's statistics, `monitoring.py::aggregate_monitoring_results`), sustained
  buffers/s → GB/s, repeats, context switches (`/proc/self/status` voluntary/involuntary delta over the window)
  as the gang's overhead witness. Reps: 5, medians, min..max spread printed.
- **Correctness gate:** tuples emitted per stream per cycle must be identical across arms (counting pec).

## 4. Sweep grid and budget

| dimension | headline | panels |
|---|---|---|
| dataset | `bench_5xUINT64_512m.csv`, 5 cols, project f1 + fnattr, FastUINT64, no-quote kernel (S=1 honest) | `bigstr_id_4k_500m.csv` varsized=2 (spanning strings, shredder on the path) |
| buffer | 128 KiB (production) | 16 KiB |
| N | 1, 2, 4, 6, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256 | — |
| arms | DPP, gang-shared k∈{2,4,8}, gang-private k∈{1,2,4,8} (→ gang-best) | J∈{4,8}; whole-buffer chunks |
| load | closed loop, D=1 both arms | DPP at engine defaults (D=64, cap 1000); open-loop (optional) |
| reps | 5 (12 s each) | — |

Headline grid: 15 N × 3 arms × 5 reps × 12 s ≈ 45 min + compiles (Σ N ≈ 900 stages × 0.5 s ≈ 8 min).
Full matrix (2 datasets × 2 buffers × 2 backpressure settings × 7 arm-k combos × S) ≈ 10-12 h → run as separate driver
invocations, headline first. Whole process under `taskset -c 0-23` (one SMT sibling per core: the "24 cores"
of the intro figure; otherwise the OS spreads N·k threads over 48 hardware threads and halves the effect).

## 5. Rig — IMPLEMENTED 2026-09-08 as a separate target `formatter-latency-benchmark`
(`nes-input-formatters/tests/Benchmark/FormatterLatencyBenchmark.cpp`, ~1150 lines, uncommitted; header documents
every env knob). Arms dpp / gshared / gprivate / chunker, closed loop D=1, futex spin-then-block waits everywhere
(libc++ `std::atomic::wait`/`counting_semaphore` POLL with timed sleeps and burned ~3 idle cores → replaced by raw
futex + POSIX `sem_t`), zero-copy views via `BufferManager::wrapExternalMemory` at setup, per-stream 8 MiB memory
copies, CountingPec (drops output, counts tuples → `tuples/row` gate), `getrusage` CPU-s/GB + context switches.
Stage compile is ~30 ms (compilation cache) so N=256 contexts cost nothing.

**Smoke 2026-09-08 (N=1, 2 s window, taskset 0-23, numeric 5×UINT64 project f1 + fnattr, FastUINT64):**
| arm | p50 µs | p99 µs | GB/s | CPU s/GB | vcsw/buf | tuples/row |
|---|---|---|---|---|---|---|
| dpp | 59.2 | 65.1 | 2.20 | 0.52 | 1.0 | 1.0000 |
| gshared k=4 | 21.5 | 28.4 | 6.01 | 0.86 | 4.0 | 1.0000 |
| gprivate k=4 | 20.0 | 24.0 | 6.51 | 0.61 | 0.0 (spinning) | 1.0000 |
| chunker k=4 | 21.8 | 30.6 | 5.77 | 1.07 | 5.0 | 1.0000 |
→ gang wins N=1 latency ~3×, DPP lowest CPU/byte: the expected N=1 picture.

**PROBE DONE 2026-09-08 → `probe/RESULTS.md`** (5 arms × N 1..256 × 2 reps × 5 s, spin 50 µs AND spin 0 → envelope).
Expectations HOLD: dpp knee N=23, p50 ∝ N/23, p99/p50 ≤ 1.4, 45 GB/s; gang-best (k=4) 2.7× better at N=1, crosses DPP at
N ≈ 8 = cores/k, then p99 2-2.4×, p50 1.5×, throughput −33%, CPU/GB +60%; spinning gang = ÷4 throughput / ×6 p99 (the
gang's policy dilemma); chunker ≈ gshared + a per-stream hop (1.4-1.5× DPP, −30%); thread-per-stream p50 flat but p99
17-27 ms at N ≥ 128 (CFS time-slicing = the intro figure's cliff on compute alone). ⚠️ Little/D=1: mean latency =
1/per-stream throughput for every arm → figure must plot p99. Spin policy = `NES_LAT_SPIN_US`; driver `probe/run_probe.sh`
(`SPIN=`, `TAG=`), tables `probe/summarize_probe.py`, `probe/compare_spin.py`.

### 5a. Original plan (kept for reference)

New drain mode `lat` (arg 6) driven by env vars (positional args are already 13):

```
NES_LAT_ARM=dpp|gshared|gprivate   NES_LAT_K=1,2,4,8   NES_LAT_STREAMS=1,2,4,...   NES_LAT_D=1   NES_LAT_CAP=0
NES_LAT_J=1   NES_LAT_CHUNK=sub|buffer   NES_LAT_SPIN_US=50   NES_LAT_WARMUP_S=2   NES_LAT_WINDOW_S=10   NES_LAT_RING=64
[NES_LAT_LOOP=closed|open  NES_LAT_RATE=<buf/s/stream>: appendix]
NES_LAT_WORKERS=23   NES_LAT_PRODUCER_CPU=23   NES_LAT_OUT=<csv path>
```

Pieces (≈ 400-500 lines, one file; no formatter-side change):
1. `StreamCtx { stage; ring[R] (whole buffers or k chunks); nextSeq; enq[], done[] (64-bit ns, sized
   rate·window·1.2); join[R] (atomic, cache-line padded); inFlight[R]; tuplesEmitted }`.
2. `Task { streamId, slot, chunk, TupleBuffer }`; the shared queue is the existing folly MPMC + the
   `leansem` counting semaphore; workers `acquire()` (park) instead of spinning.
3. Closed-loop re-emit in the done-stamper (D / cap waits BEFORE the `enq` stamp); the producer only
   seeds buffer 0 of every stream. (Open-loop producer with a next-emit heap + overrun counter: appendix only.)
4. gang-shared fork: the worker that dequeues a whole-buffer task enqueues chunks 1..k−1 and runs chunk 0;
   every chunk finisher decrements `join[slot]`; the one reaching 0 stamps `done` (and in closed-loop re-emits).
5. gang-private: per stream a leader + k−1 members waiting on `std::atomic<uint64_t> generation` (spin
   `NES_LAT_SPIN_US`, then futex wait/notify); leader loop = {pop buffer from private queue (semaphore), gen++, notify_all, do chunk 0, barrier,
   stamp done}; members = {wait gen, do chunk c, barrier}.
6. Latency stamping in the pec or around `eps->execute`; `done_{s−1}` max at post-processing.
7. Report: one CSV row per (arm, k, N, D, cap, rep) incl. CPU-s/GB (`getrusage` delta) + the existing stdout table.
Reuse as-is: `loadRawBuffers`, stage creation (`runOnce`'s `idxParams`/`createInputFormatter`), the
pre-faulted recycled formatted-buffer pool, `DroppingPec`, `g_repeats`.

## 6. Pitfalls to design around (from the memories + this box)

- Under full load residence = backlog/throughput for everyone. Never run the DPP headline with the engine's
  deep backpressure (64/source, 1000 global): that is a ~3 ms backlog line above the gang, not DPP's latency.
  D=1 in both arms; state it in the caption.
- Stamp `enq` AFTER the bounded-queue wait in every arm, or DPP's latency silently includes source-side
  backpressure that the gang arm does not measure (its D=1 wait is before hand-over by construction).
- Compile per N-cell only; never inside a window (`bench-debug-tooling-gotchas`, old rig already does this).
- Pinning: `taskset -c 0-23` + per-thread affinity for DPP workers; gang threads deliberately unpinned.
  The old sweep's 48-53 % small-buffer spread was unpinned-24-thread placement noise — irrelevant at 128 KiB
  but pin anyway.
- Memory: 2 GiB rings at N=256 + formatted pools (recycled, pre-faulted) — fine on 62 GB; watch N=256 × k=8
  chunk pools (same bytes, 8× the TupleBuffer control blocks).
- `NES_BUILD_DIR=cmake-build-release` (`output-codec-seam` gotcha); run via the nes-build skill's
  `in-docker.sh`; `taskset` must wrap the container command (or use `--cpuset-cpus`).
- Isolated varsized (the bigstr panel) needs the `leannoemit`-style dropping pec (`bypass-scaling`: frontier
  hold otherwise) — the `lat` mode uses `DroppingPec` + a tuple counter for all arms.
- The gang at N=1 with k=8 on 16 KiB buffers = 2 KiB chunks — per-chunk overhead dominates; that is a real
  property of gangs on small inputs, report it, do not tune it away.

## 7. Step plan

1. Confirm §1 decisions.
2. Implement §5 (≈ 1-1.5 days), smoke at N=1 for all three arms: expect DPP ≈ 75 µs, gang-4 ≈ 30-50 µs,
   identical tuple counts.
3. Headline grid (§4) → `results.csv`, `plot_latency_vs_streams.py`, `RESULTS.md` in this directory.
4. Panels: DPP at engine defaults; bigstr; 16 KiB; J / whole-buffer chunks; open-loop (optional); DuckDB/Arrow
   single-stream anchor — in that priority.
5. Memory + handover update; decide whether B (e2e gang formatter) is still wanted.

## 8. Pointers
Rig `FormatterScalingBenchmark.cpp` (drain loops l.258-615, arg parsing l.616-700, stage build l.775-870);
shredder ownership `InputFormatter.hpp:120-130`; formatter capture `InputFormatterTupleBufferRef.cpp:30`;
quote kernels `SIMDCSVKernel.cpp:38-47`; e2e latency stats `~/work/piparse-bench/piparse_bench/monitoring.py:204`;
paper `piparse.tex` intro fig l.156-171, C1 l.449-461, DPP l.553-660, related work l.1138-1149
(`parparaw`, `ge2019speculative`, `scalablefsm`; Mytkowicz ASPLOS'14 not yet in bib).
