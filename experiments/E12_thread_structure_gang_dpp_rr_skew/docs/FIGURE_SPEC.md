# Motivation figure — thousands of text-bound queries on restricted hardware (spec, 2026-09-09)

**Purpose (user):** one figure that motivates a main section: the chunker and the gang approach scale less well
with a large number of concurrently running queries because they use more of the available resources; the
goal is thousands of text-bound queries on restricted hardware (Threadripper 24 cores and Raspberry Pi 5,
4 cores) at low latency.

## The figure (one figure, 2 columns × 2 rows)
- Columns: **Threadripper PRO 5965WX, 24 cores** (taskset 0-23, SMT siblings excluded) | **Raspberry Pi 5, 4 cores**.
- Row (a): **p99 per-buffer latency vs number of concurrent queries N**, log-log, N = 1 … 512 (user, 2026-09-09; the rig was validated to 1024 on the Threadripper).
- Row (b): **sustained throughput (GB/s) vs N** on the same x — the "resources" axis: a design that burns its
  cores on threads and joins delivers fewer bytes per second for the same hardware. (CPU-seconds per GB is in
  the CSV as an alternative for row b.)
- Lines (same 4 in both columns):
  - **DPP** (ours): one task per 128 KiB buffer, any pooled worker, lock-free SequenceShredder.
  - **gang k=4**: SotA speculative parallel parsing with a dedicated 4-thread gang per query (fork/join).
  - **chunker k=4**: one cutter thread per query finds the record boundaries and hands record-aligned chunks to
    the shared pool, which parses them independently (no shredder, no join). The figure runs every design with
    the quote-free kernel (the paper's setting), so the cutter uses the quote-free method: a local newline search
    at each of the k cut points (`NES_LAT_CUT=memchr`). The general-CSV cutter — a full structural scan with the
    real SIMDCSV indexer on the query's thread (`NES_LAT_CUT=index`) — is appendix data: pairing it with quote-free
    DPP would be unfair (2026-09-10). With the scan the chunker's cost roughly doubles (TR: 2.9× DPP p99 at N=512,
    −52 % throughput; Pi: 1.6×, −35 %).
  - **thread-per-query** (gang k=1): sequential parsing on a dedicated thread — the SotA SPE model.
  Excluded from the figure (appendix data): gang-on-shared-pool, k ∈ {2, 8}, D=64 backlog regime.

## Load model — full load, one buffer at a time per query (D = 1)
Every query is always active: the moment its buffer completes, its next buffer is available and offered to
the design's front-end (queue / gang leader / cutter). Latency = completion − availability, so it includes
queueing, thread wake-ups and scheduling waits; the mean per query is 1/throughput-per-query for every design
(Little), the distribution shape differs → plot p99. The knee of each curve is the N at which that design
stops keeping up with its queries.

## Wait policy (fairness, DESIGN §2b)
All waits are spin-then-futex (no locks anywhere). Spinning is the gang's/chunker's best policy only below the
knee (N ≤ 8) and catastrophic above it; blocking is their best above. Runs: spin 0 at every N; spin 50 µs
additionally at N ≤ 32; the plotted line is the per-N minimum p99 ("design-best"). DPP is policy-insensitive.

## Common parameters
Numeric quote-free CSV `bench_5xUINT64_512m.csv` (5×UINT64 rows, ~37 B), 128 KiB raw buffers, project f1 +
fnattr (SELECT-key workload), FastUINT64, SIMDCSV compiled stage per query (own shredder). Per-query private
data ring 16 × 128 KiB = 2 MiB (N=4096 → 8 GiB, ≫ L3 from N ≈ 16 up), 8 view generations, 32 KiB output
buffers, output dropped after counting tuples (tuples/row gate = 1.0000). 1 s warm-up discarded, 5 s window,
3 reps (median), pooled p50/p99/p999. N ∈ {1, 2, 4, 8, 16, 32, 64, 128, 256, 512} (both machines; buffer size 128 KiB kept — knee of the per-buffer-overhead curve, the size of every e2e run).

| | Threadripper | Pi 5 |
|---|---|---|
| cores used | 24 (taskset 0-23) | 4 |
| pooled workers W | **24** pinned (first pass 23; +2-3 %, noise) | **4** pinned (first pass 3: −25 % throughput, unfair — pooled designs get every core, there is no producer thread in the closed loop) |
| governor | performance | ondemand (no sudo; full load pins 2.4 GHz) |
| gang threads at N=4096, k=4 | 16384 (ulimit -u 256k, threads-max 512k ✓) | 16384 (ulimit -u 64k, threads-max 129k ✓) |
| memory (measured N=1024: 7.4 GB dpp / 7.9 GB gang) | N=4096 ≈ 28 GB of 62 ✓ | **N capped at 2048** (≈ 13 GB of 16): each compiled per-query stage costs ≈ 4.5 MB of JIT memory (1024 stages = 4.6 GB) — a real per-query cost of compiled pipelines |
| run time (4 arms, 10 N ≤ 512, envelope, 3 × 6 s) | ≈ 25 min | ≈ 40 min (compiles ~0.15 s × Σ N) |
| binary | host build `cmake-build-release` | `cmake-build-release-piparse` run inside `nes-development:local-piparse` |

## Commands
```
# Threadripper (from the repo root)
MACHINE=tr ~/Notes/nebulastream/benchmark/1_isolated_to_engine/gang_vs_dpp_2026-09-08/fig/run_fig.sh
# Pi (driven from the Threadripper over ssh; runs inside the Pi's dev container)
MACHINE=pi ~/Notes/nebulastream/benchmark/1_isolated_to_engine/gang_vs_dpp_2026-09-08/fig/run_fig.sh
```
Outputs: `fig/sweep_tr.csv`, `fig/sweep_pi.csv`, logs in `fig/logs/`, then `fig/plot_fig.py` → `fig/motivation_latency_vs_queries.{pdf,png}`.

## Threadripper smoke at N=1024 (2026-09-09, ring 16, gens 8, fmt 32 KiB, spin 0, 3 s window)
| arm | GB/s | p50 ms | p99 ms | max ms | CPU s/GB | maxrss | setup |
|---|---:|---:|---:|---:|---:|---:|---:|
| dpp | 46.4 | 2.88 | 3.14 | 3.7 | 0.50 | 7.4 GB | 25 s (1024 stage compiles) |
| gang k=4 (4096 threads) | 27.0 | 5.06 | 6.66 | 27.7 | 0.89 | 7.9 GB | 25 s |
| chunker k=4 (1024 cutters) | 32.6 | 4.11 | 4.62 | 9.4 | 0.73 | 2.8 GB | 1 s |
DPP p50 = 1024/23 × 65 µs = 2.9 ms (Little, exactly); gang 2.1× DPP p99 and −42 % throughput; chunker 1.5× / −30 %.
tuples/row = 1.0000 in all three. So at N in the thousands the gap is a stable factor + tail, not a cliff (spin 0).

## Expected shapes (from the probes; to be confirmed at N ≥ 512)
Threadripper: DPP p99 flat ~65-90 µs to N=23 then ∝ N (queueing), tight; gang k=4 wins ×2.7 at N ≤ 4, crosses
DPP at N ≈ 8 = cores/k, 2-2.4× above; chunker 1.5× above DPP from N=16; thread-per-query flat p50 but p99
17-27 ms at N ≥ 128 (CFS time-slicing), and at N in the thousands the thread-bound designs should degrade
further (context-switch + wake storms), which is the claim. Pi: the same with knees at N ≈ 1-4.

## Risks / gotchas
- Setup per N cell compiles one stage per query (≈30 ms TR, ≈150 ms Pi) → minutes at N=4096; outside windows.
- Pi memory at N=4096 for gang k=4; the driver stops at the first cell that fails and the CSV keeps the rest.
- Pi clock is ~1 h behind → rsync'd files are "future"; `touch` before ninja (else "manifest still dirty").
- Pi has no internet: cargo runs offline from the copied registry (`CARGO_HOME=/cargo-home`).

## FINAL WINDOW SET (2026-09-10 evening)
1. **MAIN: engine admission** — ≤64 buffers per query AND ≤1000 in flight in total, FIFO admission, clock starts at admission
   (`DW=64 CAP=1000 run_fig.sh`; `sweep_{tr,pi}_D64_C1000.csv`; figure `motivation_latency_vs_queries_cap.{png,pdf}`, `_linY`).
   Reproduces the e2e regime: DPP flat (3 ms TR / 86 ms Pi) to 512 queries; gang tail 1.8→7.9× (TR) / 1.3→3.9× (Pi);
   chunker flat 2.1-2.8× (TR) / 1.3× (Pi); thread-per-query 13× (TR) / 8.6× (Pi) at 512, p999 56 ms / 1.2 s.
2. Companion: **D=1** (one buffer per query; where each design stops keeping up; gang wins below cores/k).
3. Appendix: **D=64 uncapped** (backlog without admission control). The per-N-window "adm" run is superseded (integer window
   under-filled the cap at N ≥ 256).

## 2026-09-10 (evening): MAIN FIGURE INPUTS SUPERSEDED — `sweep_{tr,pi}_ws_D64_C1000.csv` → `core_story_ws.{png,pdf}`
The earlier main-window CSVs (`sweep_*_D64_C1000.csv`) carry a rig artefact at N=16-64 on the Threadripper: a working-set band
of the private per-query data rings (see RESULTS_tr.md "Trough investigation"). The re-run adds `NES_LAT_WS_MIB=2048`
(`WS=2048` in run_fig.sh: the ring grows, wrapping the file, so N × ring × 128 KiB ≥ 2 GiB at every N = streaming regime
everywhere) and a fifth arm, `chunker_quote` (NES_LAT_CUT=quote: the sequential cut pass also tracks quote parity).
Both machines, 5 arms, 3 reps, spin 50 at N ≤ 32 (design-best envelope), all gates clean (tuples/row 1.0000, 0 repeats).
