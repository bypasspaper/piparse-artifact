# Scaling with many sources / queries — results so far

Stage 2, the paper's core axis: **how do throughput and (especially) latency scale as the
number of concurrent queries / sources / connections grows** (1 → 10 → 100 → 1000), and what
source/threading model to use. Machine: Threadripper PRO 5965WX, 24c/48t, **4 CCX × 6 cores,
32 MB L3/CCX**, ~84 GB/s DRAM peak. Host-native `cmake-build-release` (`-O3 -march=native`,
clang-19). Workload: `nexmark/bid_passthrough_1gb` — 4-int-field `SELECT *`, SIMDCSV lazy-elision
passthrough (parse elided, byte-copy) → minimal per-tuple work, so scheduling/thread overhead is
maximally exposed. Warm page-cache reads (CPU-bound; no I/O wait — see the big caveat in §8).

Primary harness: `~/work/piparse-bench/scripts/perccx_latency.py` (+ `profile_blocking.py`).
Sink emits latency percentiles now (engine change, §3). All latency in **microseconds**.

---

## 0. HEADLINE — async vs blocking File, full scaling (corrected steady-state)

Steady-state (`NES_FILE_REPEAT`), fixed sink + wall-span throughput. Async File vs BlockingFile.

| Sources | Async GB/s | Async p50 | Async p99 | Block GB/s | Block p50 | Block p99 | Tput winner | **Latency winner (p99)** |
|--:|--:|--:|--:|--:|--:|--:|:--|:--|
| 1 | 5.7 | 67 µs | 105 µs | 2.8 | 92 µs | 148 µs | async 2.0× | async 1.4× |
| 10 | 13.7 | 138 µs | 1.1 ms | 17.3 | 126 µs | 2.8 ms | blocking 1.3× | async 2.6× |
| 50 | 14.7 | 451 µs | 644 µs | 16.1 | 8.5 ms | 11.6 ms | blocking 1.1× | **async 18×** |
| 100 | 15.2 | 853 µs | 4.4 ms | 15.5 | 9.0 ms | 12.9 ms | ~tie | async 2.9× |
| 250 | 17.6 | 1.7 ms | 31 ms* | 15.7 | 53 ms | 86 ms | async 1.1× | async 2.8× / **15× pinned** |
| 500 | 17.0 | 3.3 ms | 16 ms* | 10.5 | 117 ms | 168 ms | async 1.6× | async 10× / **30× pinned** |

\* async *unpinned* p99 is migration-jittery at scale; **pin1worker** tightens it to a flat **~5.6 ms
at both 250 and 500** (async lead → 15× / 30×). Config note: 1–100 measured at io4/w24 pool32768,
250–500 at io8/w16 pool8192 (pool is inert at scale, §6). Async=unpinned baseline unless noted.

**Two DIFFERENT crossovers:**
- **Latency: async wins at EVERY N** (1.4× → 18× → 30×). No crossover.
- **Throughput: blocking leads only at low fan-out** (10–50, threads still fit cores), ties ~100,
  and LOSES by 250–500 (oversubscription drags ingestion down).

**Pinning is opposite per model:** helps async (p99 31→5.7 ms), HURTS blocking (86→197 ms, tput halved).

**Mechanism (profiled):** blocking collapse = runqueue starvation (source threads wait 64–76% of
wall time for a CPU) + scheduler thrash (1.6M ctx-sw/s, 253K mig/s) + IPC collapse (1.30→0.42).
Async stays under the core count (50 threads, 0% wait, IPC 1.30, DRAM-bound on 17 cores).

⚠️ CPU-bound (warm-file) regime = worst case for blocking (threads always runnable). Network
experiment (threads park in `recv()`) is the open test (§12, async generator built).

---

## 1. Architecture (verified in code)

- **Async sources** (`TCPSource`, `FileSource`): multiplex onto a process-wide singleton
  `IOThread` pool of `number_of_io_threads` (round-robin). N sources share a FIXED pool.
- **Blocking sources** (`BlockingFileSource`, `InMemoryFileSource`, `BlockingTCPSource`): **one
  dedicated OS thread per source**.
- **Workers/queries**: one shared `ThreadPool` (`number_of_worker_threads`) behind a **single
  global MPMC task queue**, shared by all queries. Per-source private buffer pool (64 buffers);
  global pool serves pipeline outputs. Admission queue bounded (default 1000).
- Source-type registry strings = the `Register<Key>Source` infix: `File` (async), `BlockingFile`,
  `InMemory`, `TCP`, `BlockingTCP`, …
- Engine pins io→cores `[offset, offset+io)`, workers→`[offset+io, offset+io+w)`;
  `NES_PIN_CPU_OFFSET` shifts the base. **One worker = one global queue** → a single 24-thread
  worker pinned across CCXs still hands buffers cross-CCX. The per-CCX locality win needs
  SEPARATE worker processes (shared-nothing, one queue each).

## 2. The three placements compared

- **unpinned**: 1 worker, io=8 + w=16, `pin_threads=false` (threads float 48 logical cores).
- **pin1worker**: 1 worker, io=8 + w=16, `pin_threads=true` (pinned cores 0-23, spans 4 CCX).
- **perCCX**: 4 worker processes, each `taskset`'d to one CCX, io=2 + w=4 (= 24 threads total),
  shared-nothing. Sources split evenly.
- **blocking{Unpinned,Pinned}**: BlockingFile (1 thread/source) + 16 workers (io moot).

## 3. Engine + harness changes (METHODOLOGY — the results depend on these)

- **MonitoringSink.cpp**: now emits `p50/p99/p999 latency us` (sorts the retained per-buffer
  latency map — exact, no reservoir) + absolute `first read start` / `last arrival` epoch us.
- **BlockingFileSource.cpp**: added `NES_FILE_REPEAT` support (on EOF, `clear()`+`seekg(0)` and
  re-read N passes) — mirrors the async FileSource; needed so blocking gets a steady-state window
  (it had none → single-pass, ramp-contaminated). *(both engine changes UNCOMMITTED on branch
  benchmark-piparse-lazyparse-fast-csv; built into cmake-build-release.)*
- **pbench `monitoring.py`**: fixed the latency-drop bug (header `average_latency_us` vs the old
  lookup `average_latency` → silently 0); `throughput_mbps` is now the **wall-span aggregate**
  (total bytes / (max last − min first)) not the overcounting sum-of-per-query-rates (which read
  >DRAM peak). `store.py`/`models.py`: `_us` latency + percentile columns via migration.

**Metric hygiene (hard-won):**
- **SUM of per-query throughput OVERCOUNTS** once the sequential `nes-cli` submit staggers the
  windows (hit 84–115 GB/s > DRAM peak). Use **wall-span** (robust) — but it includes the startup
  ramp, so it's a lower bound at high N. Truth is between; both are reported.
- **Single-pass runs are ramp-contaminated** — use `NES_FILE_REPEAT` for a steady window.
  (pin1worker@100 read p99 11.8 ms single-pass vs ~1 ms steady — a ~2.6× ramp inflation.)
- **Tail has ~2–3× run-to-run variance** — use REPS ≥ 3; quote p99 as a range, not a point.

---

## 4. PoC #1 — thread model (async File vs BlockingFile), 1→100 sources

⚠️ **PoC #1 was single-pass (repeat=1) → CORRECTED by the §7b steady re-run.** The single pass
distorted BOTH models oppositely: INFLATED async's tail (startup burst) AND UNDER-measured
blocking (the pass finished before sustained oversubscription developed). Original claim "blocking
wins at 50" was an artifact. See §7b for the corrected steady-state picture.

## 7b. ⭐ STEADY-STATE re-run (repeat=6, fixed sink) — corrects PoC #1

`source_thread_scaling` @ steady window:
| src | n=50 | n=100 |
| async File | p99 644us, p50 451 | p99 4390us, p50 853 |
| BlockingFile | p99 11607us, p50 8500 | p99 12904us, p50 8998 |
Single-pass had inflated async@100 p99 to 15565us (3.5×) and UNDER-measured blocking@50 p50 as
164us (true steady = 8500us, **52× off**). ⇒ **CORRECTION: async wins on LATENCY at essentially
every N (no crossover).** Blocking keeps only a THROUGHPUT edge at low N (17.3 vs 13.7 GB/s @10,
threads still fit cores), shrinking by ~100, collapsing by 250/500 (§8). Honest picture: latency =
async always; throughput = blocking leads only at low fan-out.

`io_worker_split_sweep` @ steady: tails much lower than ramp version (io8_w16@50 p99 2836us not
11144). io4_w20@50 = sweet spot (14.4 GB/s AND 660us tail). @100 all splits ~8-12ms (saturated),
medians low. Queueing tradeoff (§5) holds but tail numbers were ramp-inflated before.

## 5. PoC #2 — io:worker split (fixed 24 threads), async, 50/100 sources

Sweeping the io:worker split relocates the bottleneck through three regimes (a queueing / Little's
law tradeoff, NOT an io-thread-count knob):
- io-starved (io=2/w=22): ingestion-bound ~10 GB/s, queues empty → low+tight tail.
- balanced (io=4-8): DRAM ceiling ~16 GB/s → bursty, great median + catastrophic tail (p99 ~11 ms).
- worker-starved (io=12-16): uniform backlog, high median, tight tail, throughput dropping.
**Peak throughput coincides with the worst tail; tightest tail costs 37% throughput. No split gives
both.** (NOTE: these tails were single-pass ramp-inflated — see §3; steady-state numbers are lower.)

## 6. PoC #3 — pinning + per-CCX

- **perCCX is a FEW-source win**: at 8 sources (2/CCX) it wins BOTH — **43.6 GB/s** (2× single
  worker, validated vs `two_worker_ccx.py` = 45.9) + best tail. By 12–25 sources/CCX both collapse
  (io=2 can't feed 25 sources; per-CCX throughput halves 10.9→5.4 GB/s/CCX; tail becomes worst).
- **Single-worker PINNED wins the many-source tail**: unified io=8 pool load-balances bursts; the
  four isolated 2-thread per-CCX pools can't.
- **Pool is INERT at scale**: within a placement, pool ∈ {256,4096,32768} barely moves tail or
  throughput at 50/100. (The pool×placement interaction was a FEW-source-only effect — at 8 src
  pool 32768 wrecks perCCX locality; by 50/100 perCCX has already lost locality → pool moot.)

## 7. Scale test — single worker, 100 → 500 sources (wall-span, REPEAT 3)

| arm | 100 | 250 | 500 |
|---|---|---|---|
| unpinned p99 | 12 ms | 31 ms | 16–28 ms |
| pin1worker p99 | ~1.2 ms | ~5.7 ms | ~5.6 ms |
| wall throughput | ~17 GB/s (both) | 17 | 17 |

- **Throughput = a HARD single-worker ceiling ~16–17 GB/s, FLAT** — adding sources adds zero.
- **Median latency grows ~LINEARLY with source count** (Little's law: fixed throughput ÷ growing
  load → deeper queues). Pinning doesn't change the median.
- **Pinning persistently wins the tail 2–10×**; async pin1worker p99 stays ~5.6 ms flat 250→500,
  but the sub-ms tail is a ≤100-source luxury.

## 8. ⭐ Async vs Blocking at scale (250/500) — DECISIVE

Same session, REPEAT 3, REPS 3, wall-span:

| arm | src | wall GB/s | p50 | p99 |
|---|---|---|---|---|
| async pin1worker | 250 | 16.1 | **1.9 ms** | **5.7 ms** |
| async unpinned | 250 | 17.6 | 1.7 ms | 31 ms |
| blockUnpinned | 250 | 15.7 | 53 ms | 86 ms |
| blockPinned | 250 | 8.4 | 152 ms | 197 ms |
| async pin1worker | 500 | 16.0 | **3.9 ms** | **5.6 ms** |
| async unpinned | 500 | 17.0 | 3.3 ms | 16 ms |
| blockUnpinned | 500 | 10.5 | 117 ms | 168 ms |
| blockPinned | 500 | 5.3 | 237 ms | 334 ms |

- **Async beats blocking 27–30× on median, 15–30× on p99, at equal-or-better throughput.**
- At 500 blocking loses throughput too (10.5 vs 16 GB/s).
- **Pinning HURTS blocking** (confining 16 workers while 250–500 source threads oversubscribe) —
  opposite of async.
- **Crossover ~100 sources**: 50 (1.5× oversub) blocking wins → 250 (5×) async by 27× → 500 (10×)
  async by 30× + throughput. Thread-per-source works at low fan-out, collapses at high.

## 9. ⭐ Mechanism — profiled (`profile_blocking.py`, 10 s steady window, sudo-free)

| cfg | thr | IPC | ctx-sw/s | mig/s | **runq-wait** | CPUs busy |
|---|---|---|---|---|---|---|
| async250 pin | 50 | 1.30 | 6.5K | 3 | **0%** | 17 |
| blocking250 | 291 | 0.56 | 1.58M | 253K | **64%** | 40 |
| blocking500 | 540 | 0.42 | 1.68M | 147K | **76%** | 46 |

Three compounding layers:
1. **Runqueue starvation = primary latency source.** Blocking source threads spend 64/76% of wall
   time WAITING for a CPU (async 0% — 50 threads fit 48 cores). A buffer's latency IS its source
   thread on the runqueue → the 53–237 ms directly.
2. **Scheduler thrash = overhead.** ctx-sw 6.5K/s → 1.58M/s (243×); migrations 3/s → 253K/s.
3. **IPC collapse = throughput drop.** 1.30 → 0.42 (cold caches from migrations + 250–500 working
   sets evicting) → blocking500 burns 46/48 cores but on scheduling+stalls; async does 16 GB/s on
   17 cores at IPC 1.3 (rest idle = DRAM-bound, not scheduler-bound).

**One line:** async stays under the core count (latency = queue depth); blocking explodes past it
(latency = waiting-for-a-CPU; overhead drags throughput too).

---

## 10. Synthesis (paper story)

- For **many sources**, the async unified io pool is essential; thread-per-source collapses on CPU
  (runqueue starvation + scheduler thrash + IPC collapse, all measured).
- But a single worker is **throughput-capped (~17 GB/s)** → median latency grows linearly with load.
- **Multi-worker per-CCX** adds throughput (to ~43 GB/s) but only for FEW sources/CCX; at many
  sources/CCX it fragments the io pool → worse tail.
- ⇒ **Neither single-worker nor shared-nothing-per-CCX scales BOTH throughput and latency to many
  sources on the current engine.** Motivates the §23 redesign: affinity-routed per-CCX queues
  INSIDE one worker (unified-io-pool tail behavior + per-CCX throughput scaling).

## 11. ⚠️ The load-bearing caveat

**All of this is the CPU-BOUND regime** (warm page-cache reads never block → every source thread
is always runnable → maximal scheduler contention = the WORST case for blocking). On a real
**network**, blocking threads PARK in `recv()` (off-CPU when waiting) → the runqueue-starvation
layer should be much milder (C10K is about memory / context-switch cost, not pure CPU starvation).
The file result and the network result probe **different failure modes** — the network one is what
actually speaks to "scaling connections," and is the open experiment (§12).

## 8b. ⚠️ RETRACTED / CONFOUNDED — NETWORK (TCP) async vs blocking (do NOT trust)

**This result is INVALID and retracted.** The loopback setup is confounded: the async generator
burns ~8 CPUs on-box (send-side TCP copy), and FLOATING placement lets the scheduler preempt the
async engine's latency-critical io threads with generator threads (floating cannot isolate them).
So the numbers measure PRODUCER↔CONSUMER CPU CONTENTION, not source-model scaling — ignoring the
TCP handover's central lesson (producer placement = dominant ~2× lever; recv copy-bound). The
mechanism claims (parking / HOL) were never profiled on the ENGINE (only the generator was), and
"blocking wins C10K at 250 conns" contradicts textbook knowledge = an artifact, not a discovery.
RESOLVED after a rigorous isolated redo (generator taskset CCX3, engine CCX0-2, contained 4-thread
generator, io-thread sweep, pin on/off, ENGINE profiling): with the confound fixed, at 50 conns
async wins (474us vs blocking 5327us, as C10K predicts — the floating "blocking wins" was pure
placement artifact). BUT at 100/250 conns all arms CONVERGE on a ~20/50ms tail, invariant to
source-model + io-count + pinning. Engine profile (async_io8@250): runq_wait=0%, 6.8/18 CPUs busy,
IPC 1.73 → ENGINE UNDERLOADED. The tail is a GENERATOR ARTIFACT — the per-connection service
interval (4 gen threads round-robin N conn-tasks with 512KB chunks → source waits for data). PROVED:
chunk 512->64KB dropped p99 20->5.9ms@100, 50->8.8ms@250.
**FINAL: async-vs-blocking network LATENCY is NOT cleanly measurable on this single loopback box —
IRREDUCIBLE CONFOUND (few gen threads → per-conn service gaps dominate latency; many → CPU
oversubscription). Needs a REAL NIC (producer off-box, DMA/IRQ delivery). The engine's TCP source
(async or blocking) is NOT the loopback constraint (underloaded); the producer is. The clean,
solid contribution is the FILE axis (§0-9). Original untrusted table kept below for the record.

### (untrusted)

`scripts/tcp_latency.py` (async tokio generator `async-tcp-generator`, floating, BLAST/saturation,
REPS 2, wall-span). async `TCP` (asio, 8-io-pool multiplexed) vs `BlockingTCP` (1 thread/conn):

| conns | async GB/s | async p50 | async p99 | block GB/s | block p50 | block p99 |
|--:|--:|--:|--:|--:|--:|--:|
| 50 | 9.6 | 694 µs | 1.4 ms | 10.8 | 160 µs | 5.9 ms |
| 100 | 8.9 | 1.4 ms | 4.7 ms | 10.3 | 1.2 ms | 2.9 ms |
| 250 | 9.0 | 3.2 ms | **105 ms** | 13.3 | 1.9 ms | **3.4 ms** |

**On TCP, BLOCKING WINS at scale** — at 250 conns p99 3.4 ms vs async 105 ms (31×) AND higher
throughput. **Opposite of files** (BlockingFile@250 = 53–86 ms). MECHANISM: TCP recv = CPU-heavy
copy BUT threads PARK in recv() between packets (off-CPU when idle) → 250 blocking threads DON'T
oversubscribe + each dedicated thread parallelizes the recv-copy with NO head-of-line blocking;
async's 8 io threads can't serialize 250 conns' recv-copy → HOL → 105 ms tail. ⇒ **source-model
optimality FLIPS with the workload**: async wins CPU-bound (warm file, always-runnable), BLOCKING
wins I/O-bound (TCP, parks). The C10K nuance: "async always scales better" holds CPU-bound, INVERTS
I/O-bound. Also note async TCP tput 9–10 GB/s < async File 15 (TCP recv-copy CPU cost).

**Confounds addressed:** (1) internal control — same generator fed blocking 13.3 GB/s, so async's
9.0 is engine(io-pool)-limited, not generator-starved; (2) generator profiled (`gen_profile.py`)
at 250 conns = **9 OS threads (fixed), 0% runqueue-wait, ~8 CPUs** → contained, not the bottleneck
(the async-generator design defeats the localhost 1-thread-per-client oversubscription confound).
CAVEATS: loopback (recv-copy is the cost; a real NIC with DMA/less-copy would differ), BLAST only
(controlled sub-saturation not yet), async fixed at 8 io threads (io-sweep would test if more io
rescues the async 250-conn tail); blocking's 13.3 may be gen-capped at 8 gen-threads.

## 12. Open / next

- **(b) Re-run the ramp-inflated pbench sweeps** (`source_thread_scaling`, `io_worker_split_sweep`)
  with a `NES_FILE_REPEAT` steady window + the fixed sink/aggregate — their published tails are
  single-pass ramp-inflated.
- **(a) Network async vs blocking TCP** — the C10K regime. ⚠️ CONFOUND: on localhost the data
  generator runs on the same machine; naive 1-generator-thread-per-source would itself
  oversubscribe and hit the ASYNC path too. Needs a careful generator design (few generator
  threads / epoll producer) or a second host, else the measurement is confounded.
- **1000 sources**: needs faster/batched query submit (sequential `nes-cli` stagger + JIT ramp
  make it unreliable now).
- Profile async's DRAM-bound ~17 GB/s ceiling to characterize its limit.
