# Handover: chunk-parallel (gang / chunker) vs buffer-parallel (DPP) parsing under many concurrent queries

Written 2026-09-21. Supersedes `HANDOVER_2026-09-08_SPECULATIVE_PARALLELISM_EXPERIMENT.md` (the plan) — this is the result.

## 1. Purpose and status

The paper's old LF-vs-LOCKING SequenceShredder buffer sweep compared our design against a strawman of itself. It is
replaced by one motivation figure showing that the resource-intensive SotA way of parallelising text parsing — several
threads cooperating on ONE buffer (speculative/enumerative FSM parsers, fork-join chunking, a per-query cutter thread) —
scales worse with the number of concurrently running queries than DPP (one task per buffer, any pooled worker, lock-free
SequenceShredder), on both a 24-core Threadripper and a 4-core Raspberry Pi 5, at up to 512 concurrent text-bound queries.

**Status: experiment DONE, figure delivered, rig UNCOMMITTED.** The figure is `core_story_ws.{png,pdf}`; its raw data is
`sweep_{tr,pi}_ws_D64_C1000.csv` (combined: `core_story_ws_combined.csv`). Everything else in the fig/ directory is the
history that led there (superseded windows and CSVs are marked as such in `FIGURE_SPEC.md`).

Open decisions for the user are in §8.

## 2. Where everything is

Experiment directory: `~/Notes/nebulastream/benchmark/1_isolated_to_engine/gang_vs_dpp_2026-09-08/`

| Path | What |
|---|---|
| `DESIGN.md` | design v6: arms, load model, §2b fairness model, metrics |
| `fig/FIGURE_SPEC.md` | window set (main = engine admission; D=1 companion; D=64 uncapped appendix) + the 2026-09-10 supersession note |
| `fig/run_fig.sh` | THE sweep driver (MACHINE=tr\|pi, DW, CAP, TAG, ARMS, CUT, WS, W, STREAMS) |
| `fig/plot_core.py` | THE figure: `plot_core.py <tr.csv> <pi.csv> <out_basename>` → 2×2 p99 (linear, clipped) over CPU s/GB |
| `fig/plot_fig.py` | older 2×2 p99 + GB/s figure (`--linear-y`, `--linear`, `--exclude=arm:k`) |
| `fig/merge_sweeps.py` | layering of the earlier partial sweeps (historic) |
| `fig/sweep_tr_ws_D64_C1000.csv`, `fig/sweep_pi_ws_D64_C1000.csv` | **FINAL main-window data** (5 arms × 3 reps, WS=2048) |
| `fig/core_story_ws_combined.csv`, `fig/core_story_ws_throughput.csv` | the same, stacked with a `machine` column / throughput columns only |
| `fig/core_story_ws.{png,pdf}` | **THE FIGURE** |
| `fig/core_story.{png,pdf}`, `fig/sweep_*_D64_C1000.csv` | previous main figure — SUPERSEDED (TR working-set trough, §6.1) |
| `fig/sweep_{tr,pi}.csv` | D=1 companion window — still carries the trough at N=64-128 on TR, NOT re-run |
| `fig/sweep_{tr,pi}_D64m.csv` | D=64 uncapped appendix window — same caveat |
| `fig/RESULTS_tr.md`, `fig/RESULTS_pi.md` | per-machine findings incl. chunker cost decomposition and the trough investigation |
| `fig/probe_trough*.sh`, `probe_trough*_tr.csv`, `summarize_trough.py` | the trough probes (§6.1) |
| `fig/probe_admission*.csv`, `probe_chunker_decomp_tr.csv` | earlier probes (window definition, chunker decomposition) |
| `fig/logs/` | consoles per (machine, arm, k, spin), `run_{tr,pi}.meta` (start/finish stamps), perf data of the probes |
| `probe/` | the first N-scan probe (RESULTS.md) that confirmed the expectations before the full runs |

Rig (repo `~/work/nebulastream-public`, branch `benchmark-piparse-lazyparse-fast-csv`, **all uncommitted**):

| File | State |
|---|---|
| `nes-input-formatters/tests/Benchmark/FormatterLatencyBenchmark.cpp` | NEW, 1868 lines, the whole rig |
| `nes-input-formatters/tests/Benchmark/CMakeLists.txt` | + target `formatter-latency-benchmark` (EXCLUDE_FROM_ALL) |
| `nes-query-engine/ShardedTaskQueue.hpp` | `<immintrin.h>` guarded by `__x86_64__`, `spinPause()` (x86 pause / aarch64 yield) — needed for the Pi build |

Binaries: TR `cmake-build-release/nes-input-formatters/tests/Benchmark/formatter-latency-benchmark` (host build, NOT the
docker helper); Pi `/home/pi/data/repos/nebulastream/cmake-build-release-piparse/...` (same source, rsync'd; build recipe
in memory `raspberry-pi5-benchmark-box.md`). Both binaries are current as of 2026-09-10 (quote cut + WS floor included).

## 3. The experiment as run

**Rig** = isolated micro-rig (option A of the plan; user: no engine changes). N query contexts, each with its own
compiled SIMDCSV stage (JIT, formatter captured at trace time, ~4.5 MB each), its own private data ring of 128 KiB raw
buffers (zero-copy views via `BufferManager::wrapExternalMemory`, control blocks recycled over `ring × gens` virtual
slots), a `CountingPec` sink that drops output and counts tuples. Dataset `bench_5xUINT64_512m.csv` (5 UINT64 columns,
512 MiB, 14.3 M rows), projection of one column, FNATTR invoke mode, FastUINT64 parser, quote-free kernel
(`allow_commas_in_strings=false`, as in 418/420 e2e configs).

**Arms** (env `NES_LAT_ARM`, `NES_LAT_K`, `NES_LAT_CUT`):

| arm | threads | what happens per buffer |
|---|---|---|
| `dpp` | W pooled workers | one task per buffer, any worker, real SequenceShredder resolves spanning rows |
| `gprivate k=4` ("gang") | N×4 dedicated | fork: 4 members run the same compiled stage on 4 sub-chunks; atomic join; leader completes. SotA fork-join / speculative parser dropped into a thread-per-source SPE, with speculation FREE and always correct (best case for them) |
| `gprivate k=1` | N dedicated | = thread-per-query, the SotA SPE model, sequential per buffer |
| `chunker k=4` | N cutters + W pooled | the cutter makes ONE sequential SIMD newline scan over every byte, cuts 4 record-aligned chunks, pooled workers parse them with per-worker sequential stages (no shredder, no join) |
| `chunker_quote k=4` | as above | same pass but quote-aware (prefix-XOR quote parity per 64-byte block, carried across buffers; newlines inside quotes are not boundaries) — the general-CSV cutter |
| `gshared` | W pooled | fork-join on the shared pool (ablation, not in the figure) |

**Fairness model** (DESIGN §2b): identical per-byte work (same compiled stage on chunks); sync = atomic join + spin-
then-futex, no mutex anywhere; design-best envelope = per N the better of spin 50 µs / spin 0 (spin 50 only run at N ≤ 32);
pooled designs get every core (W = 24 on TR, 4 on Pi; no producer thread in the closed loop); resources reported as
CPU-seconds per GB (getrusage) so the gang's low-N latency win is priced.

**Load model = closed loop, full load, the engine's admission rule**: every query always has data; at most 64 buffers in
flight per query AND at most 1000 in flight in total, FIFO admission (this is `NES_LAT_D=64 NES_LAT_CAP=1000`). Latency
clock starts at admission (= the e2e read-start stamp). Under full load p50 = in-flight ÷ throughput (Little), so the
p99 shape after the cap binds is the throughput curve plus the tail. This is the ONLY window that reproduces the earlier
e2e (DPP flat ~3-4 ms p99 to 1000 sources; thread-per-query collapsing). D=1 (one buffer per query at a time) and D=64
uncapped are companion/appendix windows.

**Working set floor** `NES_LAT_WS_MIB=2048` (run_fig.sh `WS=2048`, default): the per-query ring grows (wrapping the file)
so N × ring × 128 KiB ≥ 2 GiB at every N — every N-cell streams from DRAM like a real source (§6.1 explains why this
matters).

**Machines**: Threadripper PRO 5965WX (24 cores, `taskset -c 0-23`, 4 CCDs × 32 MiB L3); Raspberry Pi 5 (4× A76,
16 GiB, 2 MiB L3, docker `--cpuset-cpus 0-3`, governor ondemand). N = 1,2,4,…,512; 3 reps × 5 s windows, 1 s warm-up.

## 4. Results (design-best medians, main window, final data)

Threadripper, p99 latency per buffer in ms / CPU s per GB / aggregate GB/s:

| N | DPP | gang k=4 | chunker | quote-aware chunker | thread-per-query |
|---|---|---|---|---|---|
| 1 | 0.2 / 0.52 / 45.9 | 1.4 / 0.62 / 6.4 | 1.2 / 1.09 / 8.1 | 1.2 / 1.01 / 7.5 | 3.9 / 0.46 / 2.2 |
| 8 | 1.5 / 0.52 / 46.0 | 3.9 / 0.78 / 21.4 | 6.5 / 0.85 / 25.7 | 6.6 / 0.88 / 23.7 | 4.0 / 0.47 / 17.0 |
| 32 | 3.0 / 0.53 / 45.1 | 7.3 / 0.85 / 27.0 | 7.6 / 0.85 / 28.1 | 7.8 / 0.88 / 27.1 | 15.6 / 0.50 / 43.5 |
| 128 | 2.9 / 0.52 / 46.2 | 14.2 / 0.84 / 28.3 | 6.9 / 0.87 / 27.5 | 7.1 / 0.92 / 26.2 | 21.9 / 0.52 / 45.0 |
| 512 | 2.9 / 0.52 / 46.5 | 22.6 / 0.88 / 27.1 | 6.2 / 0.97 / 24.7 | 6.5 / 0.99 / 23.8 | 38.5 / 0.54 / 44.4 |

Raspberry Pi 5, same columns:

| N | DPP | gang k=4 | chunker | quote-aware chunker | thread-per-query |
|---|---|---|---|---|---|
| 1 | 5.6 / 2.57 / 1.6 | 6.8 / 2.99 / 1.3 | 7.6 / 3.38 / 1.2 | 7.6 / 3.43 / 1.2 | 21.3 / 2.54 / 0.4 |
| 8 | 44.1 / 2.59 / 1.5 | 57.8 / 3.09 / 1.3 | 59.3 / 3.35 / 1.2 | 61.8 / 3.46 / 1.2 | 48.1 / 2.60 / 1.5 |
| 32 | 86.8 / 2.62 / 1.5 | 119.0 / 3.35 / 1.2 | 114.0 / 3.39 / 1.2 | 118.5 / 3.52 / 1.1 | 112.3 / 2.61 / 1.5 |
| 128 | 91.3 / 2.73 / 1.5 | 231.9 / 3.52 / 1.1 | 114.0 / 3.42 / 1.2 | 119.1 / 3.57 / 1.1 | 492.1 / 2.62 / 1.5 |
| 512 | 90.0 / 2.71 / 1.5 | 389.3 / 3.53 / 1.1 | 113.7 / 3.42 / 1.2 | 118.7 / 3.57 / 1.1 | 765.3 / 2.72 / 1.5 |

Gates: tuples/row 1.0000 in every row, 0 shredder repeats, 0 slot-reuse waits/aborts, 48 rows per arm per machine.

**Findings**

1. **DPP is flat.** Once the 1000-buffer cap binds (N ≥ 16 on TR, N ≥ 16 on Pi) p99 stays at 2.9-3.0 ms (TR) / 86-91 ms
   (Pi) to N = 512, at constant CPU/byte (0.52 / 2.6-2.7 s/GB) and constant aggregate throughput. Matches the e2e.
2. **The gang wins only below the core count.** Below N ≈ cores/k it has the lowest latency of the parallel designs
   (TR: 1.4 ms at N ≤ 4). Its p99 crosses DPP at N ≈ 8 (TR) / N ≈ 2 (Pi) and then grows steadily: 7.8× DPP at N = 512 on
   TR, 4.3× on the Pi. Its CPU/byte is 1.6× DPP (TR) / 1.3× (Pi) from N ≈ 16 on: N×k threads on the cpuset = convoyed
   joins + oversubscription.
3. **The chunker plateaus, at a price.** p99 flat at ~2.1-2.6× DPP (TR) / 1.3× (Pi) from N ≈ 16 on — it does not
   collapse (its parsing is pooled, only the cut is per-query) but it costs 1.65× CPU/byte (TR) / 1.3× (Pi) and loses
   40 % (TR) / 22 % (Pi) of DPP's throughput. Decomposition (RESULTS_tr.md, N = 128): per-query thread hop −15 %
   throughput and 1.5× tail; the extra sequential pass over every byte −25 % (memory traffic ×2); the 4-way split −20 %.
4. **Making the cutter quote-aware changes almost nothing** (TR: −2..7 % throughput, +2..5 % CPU, p99 within 0.3 ms;
   Pi: −4..15 % throughput, +4 % CPU, +5 ms p99). The cut pass is memory-bound; what it computes is not the cost. So the
   chunker's penalty is structural (extra pass + private thread), not a function of the CSV dialect.
5. **Thread-per-query** is the cheapest in CPU/byte (it is sequential) but its tail collapses past the core count:
   38.5 ms at N = 512 on TR (13× DPP), 765 ms on the Pi (8.5×). Off the latency axis in the figure; annotated.

## 5. The figure

`fig/core_story_ws.{png,pdf}`: 2 columns (TR | Pi) × 2 rows (p99 latency per buffer, linear; CPU time per GB), x = N
(log2). Five series in fixed colours: DPP (blue), gang k = 4 (orange), chunker (green), quote-aware chunker (dark green,
dashed), thread-per-query (yellow). The latency axis is scaled to 1.25× the max of DPP/gang/chunker/quote-chunker so
thread-per-query runs off scale; an in-axes note gives its value at N = 512 and from which N it leaves the frame. Right-
hand end labels name each line. Title states the window (≤ 64 per query, ≤ 1000 in flight in total).

Rendering: `~/work/piparse-bench/.venv/bin/python fig/plot_core.py fig/sweep_tr_ws_D64_C1000.csv fig/sweep_pi_ws_D64_C1000.csv fig/core_story_ws`

## 6. What was investigated on the way (so nobody re-investigates it)

### 6.1 The Threadripper "dip after N = 32" — a working-set band of the rig (FIXED, 2026-09-10)

In the first main-window data the chunker's p99 rose to 10 ms at N = 16-32 and fell back to 6 ms; DPP had the same dip
hidden on its scale (38 GB/s vs 46). Cause: the working set N × ring × 128 KiB with the rig's ring forced to 72 at D = 64
(`ring = max(NES_LAT_RING, D+8)` — NES_LAT_RING is silently overridden there). At ~128 MiB-~600 MiB the data straddles the
per-CCD L3s and late DRAM fills per byte double or triple (probed with `ls_any_fills_from_sys.*` counters, varying the
ring at fixed N and vice versa: the trough moves with the working set, not with N). Below the band the data is cache-
served (unrealistic for a source), above ~2 GiB it streams flat. Not scheduling, not pinning, not the window. The Pi
(2 MiB L3) streams from N = 1 and never showed it. Fix = `NES_LAT_WS_MIB` (§3). Full write-up: RESULTS_tr.md.

### 6.2 What the chunker is (three definitions, one chosen)

`memchr` (k local newline searches, ~200 bytes touched) is a quote-free shortcut that does "basically nothing"; `index`
(the full SIMDCSV index pass, fields too) is a full second parse. Agreed middle: `scan` = ONE sequential SIMD newline
pass over every byte (the work a cutter cannot skip: it must consume the stream to find record boundaries), later joined
by `quote` (same pass + parity). All four are still in the rig (`NES_LAT_CUT`); `memchr` and `index` results are historic.

### 6.3 Windows (why "engine admission" is the main one)

D = 1 shows the arms' intrinsic per-buffer costs but its mean is 1/throughput for everyone and the tails are tiny;
D = 64 uncapped makes p50 grow linearly with N for every arm (64 N buffers queued) and was "confusing" (gang/chunker
looked like they improved towards 512 because of a per-N integer window — a rig bug, fixed by the true global FIFO cap).
Only the engine's rule (64/query AND 1000 total, FIFO) reproduces the e2e's flat DPP line and collapsing thread-per-query.

### 6.4 Rig bugs found and fixed (all in the current source)

Zero-copy views re-stamped while the shredder still held them (→ view generations, per-vslot bookkeeping, `ready[v]`
handshake, bounded 2 s wait on a busy slot, re-queue at tail on shredder repeat); gang member missing the fork (baseline
before `ready.count_down()`); libc++ atomic waits polling (→ raw futex + `sem_t` spin-then-block); tuple accounting
across warm-up; per-N window under-filling the cap; per-query drain hang (→ global `totalInFlight`); stray drivers
appending headerless rows to CSVs (→ kill by PID, CSVs rebuilt).

## 7. Naming for the paper (discussed 2026-09-10/21, user's preference still open)

The user did not like "threads-per-query" (confusable with thread-per-query, vague) and found "intra-buffer parallelism"
right but long. Recommendation on the table: **chunk-parallel** (the SotA family: k threads on chunks of ONE buffer —
speculative, enumerative, fork-join, cutter) **vs buffer-parallel** (DPP: one thread per buffer from a fixed pool).
Then thread-per-query is the sequential baseline outside both, the gang arm is "chunk-parallel, fork-join k = 4", and
the chunker is the hybrid "cutter thread + pool" (rename the arm to *cutter* in the paper so "chunk" is not overloaded).
Alternatives considered: sub-buffer parallelism, split(-and-join) parsing, fine- vs coarse-grained. Avoid "speculative
parsing" for the arm: the rig gives speculation for free (its best case) and does not speculate.

## 8. Open decisions / next steps

1. **D = 1 companion re-run** with WS = 2048 on both machines (`sweep_{tr,pi}.csv` still carry the band at N = 64-128 on
   TR). ~25 min per machine. Command in §9. Same for the D = 64 uncapped appendix if it stays in the paper.
2. **DuckDB / Arrow single-stream anchor** (planned, never done): real speculate-and-verify CSV readers on one stream,
   to show the emulated gang is at least as fast per byte as the real thing. `~/work/piparse-bench/.venv` has duckdb
   1.5.4 and pyarrow 16.1.
3. **Caption text**: quote-free kernel assumption (and why the quote-aware chunker answers the obvious objection), the
   window definition, "design-best spin envelope", the 2 GiB working-set footing.
4. **Naming** (§7).
5. **Commit the rig** (3 files, §2) — as a benchmark target, EXCLUDE_FROM_ALL, not run by ctest. The Pi's own stash@{0}
   still holds its earlier local changes; the ShardedTaskQueue guard is identical to it.
6. Optional: gang k ∈ {2, 8} envelope (DESIGN mentions it; only k = 4 was run in the final sweeps).

## 9. How to re-run

```
cd ~/Notes/nebulastream/benchmark/1_isolated_to_engine/gang_vs_dpp_2026-09-08/fig
# main window, all four base arms, then the quote-aware chunker (TR ≈ 30 min, Pi ≈ 35 min); run both in parallel
setsid nohup bash -c 'MACHINE=tr DW=64 CAP=1000 TAG=ws bash run_fig.sh > logs/console_tr_ws.txt 2>&1 && \
  MACHINE=tr DW=64 CAP=1000 TAG=ws CUT=quote ARMS="chunker 4" bash run_fig.sh >> logs/console_tr_ws.txt 2>&1; \
  echo "tr done $(date -Is)" >> logs/driver_ws.log' >/dev/null 2>&1 &
setsid nohup bash -c 'MACHINE=pi DW=64 CAP=1000 TAG=ws bash run_fig.sh > logs/console_pi_ws.txt 2>&1 && \
  MACHINE=pi DW=64 CAP=1000 TAG=ws CUT=quote ARMS="chunker 4" bash run_fig.sh >> logs/console_pi_ws.txt 2>&1; \
  echo "pi done $(date -Is)" >> logs/driver_ws.log' >/dev/null 2>&1 &
# D=1 companion (not yet re-run with the working-set floor):
#   MACHINE=tr DW=1 CAP=0 TAG=ws bash run_fig.sh     /     MACHINE=pi DW=1 CAP=0 TAG=ws bash run_fig.sh
# outputs: sweep_<machine>_<TAG>_D<DW>_C<CAP>.csv (the Pi's CSV is rsync'd back at the end of run_fig.sh)
```

The Pi runs are driven from the TR over ssh (`pi@PI-LINK-LOCAL-ADDRESS`, IPv6 link-local only,
key installed) inside the `nebulastream/nes-development:local-piparse` container. Rebuild after a rig edit: rsync the
.cpp, `touch` it on the Pi (clock skew), then the docker cmake command in memory `raspberry-pi5-benchmark-box.md`.

Single cell by hand (TR):
```
taskset -c 0-23 env NES_LAT_ARM=chunker NES_LAT_K=4 NES_LAT_CUT=quote NES_LAT_SPIN_US=0 NES_LAT_STREAMS=1,32 NES_LAT_WORKERS=24 \
  NES_LAT_D=64 NES_LAT_CAP=1000 NES_LAT_WS_MIB=2048 NES_LAT_RING=16 NES_LAT_GENS=32 NES_LAT_FMT_KIB=32 \
  NES_LAT_REPS=1 NES_LAT_WARMUP_S=1 NES_LAT_WINDOW_S=3 NES_LAT_OUT=/tmp/x.csv \
  cmake-build-release/nes-input-formatters/tests/Benchmark/formatter-latency-benchmark \
  nes-systests/testdata/large/formatter/bench_5xUINT64_512m.csv 128 5 f1 testing/configurations/invokeModeConfGlobalFnAttr.yaml FastUINT64
```

## 10. Gotchas

- Standing rules: state the exact command and ask before any benchmark; never `pkill -f`/`pgrep -f`; `pkill -x` silently
  matches nothing for names > 15 chars (`formatter-latency-benchmark` is one) — kill by PID.
- Killing a driver's `bash run_fig.sh` orphans the running rig binary and the Pi's `docker run` (survives the ssh client):
  kill the rig PID, `docker kill` on the Pi, delete the partial CSV, then relaunch. Launch long sweeps with
  `setsid nohup … &` (the tool's 10-min background limit killed one launch); `$!` of that is not the driver — wait on a
  completion line, and beware stale completion lines from an earlier launch.
- Stray concurrent drivers compete for cores (10+ ms preemptions → 600-buffer queue lags → slot-reuse waits) and append
  headerless rows; the rig prints a stall watchdog + per-worker task dump + SIGSEGV backtrace if that happens.
- `NES_LAT_RING` is a floor: ring = max(RING, D+8); with `NES_LAT_WS_MIB` the ring is derived per N and gens scaled down.
- The TR rig binary is a HOST build (`cmake-build-release`), not the docker helper's default `cmake-build-debug`.
- CSV `arm` column carries `chunker_quote` / `chunker_index` / `chunker_memchr` for non-default cut modes (cfg.label).
- Pi: `rsync` needs the bracketed IPv6 form `pi@[PI-LINK-LOCAL-ADDRESS]:path`; cargo must run offline; `touch` rsync'd sources.
