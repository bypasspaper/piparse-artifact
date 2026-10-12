<!-- SPDX-License-Identifier: Apache-2.0 -->
# Why no-serde flattens on figQ (q_ex) and why the optimised arm catches up — analysis + probe plan (2026-10-05)

Source: Opus subagent analysis of existing data + code (no runs). Experiment under study: figQ =
`qex_serde_matrix_scaling` (run_group 20260902T220312-52fa4604) + `qex_locking_scaling` (20260903T084122-767c3984),
commit b5d757c9f6 (+17 uncommitted knob files + the eqImpl fix), `nexmark/matrix/bidstr_qex` on bid_strings_3GB
(CSV 114.865 B/row, native 110.000 B/row), MmapFile + NES_MMAP_POPULATE=1, repeat 8, 128 KiB buffers, pool 16384
(2 GiB), io=1, fnattr, pin/ccx off, Monitoring sink, 6 reps. q_ex emits 220 of 250.4 M rows → output bytes ≈ 0.
Data: `bypass_scaling_2026-08-28/ideal_scaling/data/figQ_qex_serde_matrix_medians.csv`.

## 0. Central methodological finding
**No hardware counter was ever taken on any figQ/figI arm.** The "DRAM-bound" label in IDEAL_SCALING_RESULTS.md is a
level comparison. Because `operator_buffer_size` = 131072 in EVERY run in the DB (no native-arm run at any other size),
GB/s = 131072 × buffers/s exactly → a byte (DRAM) wall and a per-buffer serialized-cost wall are numerically
indistinguishable in all existing data. Probe A below breaks that degeneracy.

## 1. Data (input bytes only; %peak vs the 83 GB/s all-core streaming-read peak; kbuf/s = GB/s ÷ 131072)
| W | nat_nat Mr/s | GB/s | %peak | kbuf/s | p50 µs | simd Mr/s | GB/s | %peak | kbuf/s | p50 µs | simd/nat rows | bytes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 96.07 | 10.57 | 12.7 | 80.6 | 860 | 44.59 | 5.12 | 6.2 | 39.1 | 1655 | 0.464 | 0.485 |
| 2 | 159.24 | 17.52 | 21.1 | 133.6 | 494 | 81.74 | 9.39 | 11.3 | 71.6 | 900 | 0.513 | 0.536 |
| 4 | 285.37 | 31.39 | 37.8 | 239.5 | 270 | 156.62 | 17.99 | 21.7 | 137.3 | 467 | 0.549 | 0.573 |
| 8 | 481.86 | 53.00 | 63.9 | 404.4 | 156 | 293.67 | 33.73 | 40.6 | 257.4 | 245 | 0.609 | 0.636 |
| 12 | 579.11 | 63.70 | 76.7 | 486.0 | 127 | 413.10 | 47.45 | 57.2 | 362.0 | 172 | 0.713 | 0.745 |
| 16 | 622.71 | 68.50 | 82.5 | 522.6 | 116 | 506.89 | 58.22 | 70.1 | 444.2 | 138 | 0.814 | 0.850 |
| 20 | 643.65 | 70.80 | 85.3 | 540.2 | 111 | 563.16 | 64.69 | 77.9 | 493.5 | 123 | 0.875 | 0.913 |
| 23 | 656.62 | 72.23 | 87.0 | 551.1 | 107 | 585.46 | 67.25 | 81.0 | 513.1 | 116 | 0.892 | 0.931 |

native_json ≡ native_native within 0.25 % at every W; csv_native 579.36 @W23; bypass_locking 544.47 (= 0.93 × simd).
**Row gap at W23: 1.122 = 1.044 (CSV file 4.4 % bigger per row) × 1.074 (byte-rate deficit)** → ~40 % of the published
gap is file size, not parser speed. Nothing in the whole DB exceeds 83.5 GB/s of input or ~637 kbuf/s (the two candidate
ceilings = the same measurement).

Cross-check M1 (`shredder_scaling_pass128r40`, InMemory, 4-int rows, csv 34.8 B / native 24 B): no_serde plateaus at
24.3 GB/s in = 29 % of read peak — but NATIVE output materialises the full row into a cold FIFO-recycled 2 GiB pool
(RowTupleBufferRef::writeRecord; BufferManager availableBuffers = folly::MPMCQueue FIFO → RFO per line): 24.34 rd +
24.34 RFO + 24.34 wr = 73 GB/s = 88 % of peak = the measured `copy_rfo` ceiling (25.6 GB/s useful). ⚠️ The M1 bypass
points at W16–24 imply 88.7–109.8 GB/s of in+out bytes on an 83 GB/s machine with 0.8–1.0 s windows → ramp-contaminated;
re-run ≥ 3 s before citing "bypass 1.56× above no-serde".

## 2. Engine facts at b5d757c9f6 (code-verified; all in the figQ binary)
- SystemNative DOES go through the SequenceShredder, twice per buffer (NativeInputFormatIndexer IsSequential=false; the
  delimiter predicate at InputFormatter.hpp:345 is always true; early-out at :521-525 compares uint32 vs UINT64_MAX).
- ⚠️ `nes-input-formatters/src/SequenceShredder.cpp:44-76`: diagnostic `g_shredNs`/`g_shredCalls` atomics (one shared
  .bss line) + `ShredScopeTimer` (steady_clock::now on entry, 2 fetch_add on exit) at :109/:115/:122/:128, ungated,
  "REVERT before merge" — present at the measurement commit → 4 clock reads + 4 RMWs on one cross-CCX line per raw buffer.
- `output_format: NATIVE` is NOT a passthrough: PipeliningPhase.cpp:351-360 tests `sourceFormat == "NATIVE"` but the
  formatter registers as "SystemNative" → dead branch → 3 pipelines, 2 engine tasks per raw buffer.
- q_ex emits ~551 k essentially-EMPTY output buffers/s: EmitPhysicalOperator::open allocates a buffer per task
  unconditionally, close emits even with 0 rows → per buffer: EmitOperatorHandler::sequenceStates folly::Synchronized
  map WRITE lock (insert + erase) AND the process-wide MonitoringSink::mutex held across clock_gettime + unordered_map
  emplace (unbounded growth, in-lock rehash) + global-pool pop/push with unconditional steady_clock::now (BufferManager.cpp:206).
- 131072 % 110 = 62 → the native spanning-tuple path fires on EVERY buffer (vector<StagedBuffer> malloc, an Arena acquire of
  a whole pooled buffer for 110 B, a copy, a second indexRawBuffer). Disappears if buffer size % 110 == 0.
- 2 std::function heap allocs per task (DefaultPEC, QueryEngine.cpp:211-212) = 4 malloc + 4 free per raw buffer.
- `NES_SOURCE_EMIT_BATCH` defaults to 1 (RunningSource.cpp:150-158) and the qex worker_env sets only NES_MMAP_POPULATE →
  98ab8e3cb3's admission batching was INERT in figQ.
- LogContext likely live: NesLogger.hpp:131-153 gates on >= LOG_DEBUG and SingleNodeWorkerStarter.cpp:71 defaults to
  LOG_DEBUG unless NES_LOG_LEVEL is set (pbench did not) → per task fmt::format + std::string malloc + 2 spdlog::mdc ops.
- No zeroing on buffer acquire; q_ex never writes output payload → output DRAM traffic ≈ 0 (figQ byte accounting is clean).

## 3. Hypotheses, ranked
1. **H1 DRAM bandwidth at the asymptote + H2 loaded-fabric/MC latency under low MLP shaping W1→W12** — MOST LIKELY.
   For: 87 % of peak at W23; best native run ever = 83.51 GB/s (99.4 %); marginal gain per thread 2.68→1.20→0.58→0.48
   GB/s over W8→12→16→20→23; independent paths converge on ~74–80 GB/s engine-achievable (TCP N=12 76, async-File 77.6,
   InMemory blob 78, mlp_probe 80, 4-CCX pinned ~74); per-thread 3.14 GB/s @W23 within 10 % of the pure-read probe's 3.46.
   H2 (source-scaling-union-handover §12): IPC 2.36→1.62 at held 4.33 GHz, L3-miss latency 429→1179 clk, MAB 0.38→1.85/core
   → latency exposed → ~45 % stall cycles. Against: no counter on this arm (amplification unknown: amp 1.08 would be 100 %);
   the W1→W12 shape is not bandwidth (probe hits 82 GB/s with 8 threads; this arm is at 53 @W8); W23 windows are 0.38 s.
2. **H3 per-buffer engine serialization** (sink mutex, emit-handler wlock, pool acquire + clock, SHRED_TIMER globals,
   4 mallocs, semaphore) — CO-EQUAL, perfectly degenerate with H1 at fixed 128 KiB. For: 551 kbuf/s = 1.81 µs serialized
   budget; `bidtiny_buf{4k,8k,16k}` @W24 = 751/700/693 kbuf/s FLAT while bytes/s doubles (~1.3–1.45 µs per-buffer
   ceiling; figQ is at 73–80 % of it); the same arm rose +25 % (522.4→655.0 Mr/s on q_ex) from per-task machinery
   commits alone (Aug-14 → Sep-2) → REFUTES IDEAL_SCALING_RESULTS.md's "NATIVE-vs-JSON output lifted 516→705" (native_json
   ≡ native_native to 0.25 %). Against: OUTPUT_PLATEAU_PROBE saw spinlock 0.03 % — different sink/buffer size, non-transferable.
3. H5 cross-CCX coherence — real (840× ext_cache fills at 2 KiB) but a sub-mechanism of H3 at 128 KiB (shared lines are
   the mutexes, the timer globals, taskIdCounter, pendingTasks, the BufferManager shared_ptr control block, the semaphore).
4. H4 residual: the 64-buffer in-flight window (8 MiB WIP = 2.8 tasks/worker @W23) was never swept UPWARD.
5. **H4 single mmap source thread — REFUTED**: zero-copy source (no per-byte term); 6.84× rise W1→23; Little's law
   L = p50 × buf/s = 69.3…59.2 (native) / 64.7…59.5 (simd) at every W ≈ the 64-buffer cap → source throttled, not
   starving; RunningSource.cpp:286-305 yield-spins on pendingTasks >= inflightLimit ("large buffers" regime).
6. Ruled out: H6 store queue (220 output rows; native_json ≡ native_native), H7 pool/allocator (65536→128 flat; 128K→1M
   flat), H8 frequency/thermal (4.46→4.33 GHz; steady across 71→87 °C), shredder lock (LF/LK 0.99–1.08).

## 4. Why the simd arm keeps climbing (and where the wall is)
Per-thread demand @W1: native 10.57 GB/s (10.41 ns/row) vs simd 5.12 (22.43 ns/row) → N* ≈ 83/10.57 = 7.9 vs 83/5.12 = 16.2
threads (ordering of the knees matches). Per-row service time per thread: native 10.41→35.03 ns, simd 22.43→39.29 ns →
the formatter's extra cost is 12.02 ns @W1 but 4.26 ns @W23: **~65 % of the CSV formatter's per-row work is absorbed into
the memory-stall shadow the native arm pays anyway.** USL fit (λN/(1+σ(N−1)+κN(N−1))): native λ85.8 σ0.0486 κ1.90e-3
N_peak 22.4 asymptote 71.6 GB/s; simd λ39.2 σ−0.0012 κ1.11e-3 N_peak 30.1 asymptote 69.9 GB/s → both converge on the SAME
~70–72 GB/s ceiling (2 % apart); simd is at 96 % of its own asymptote at W23; its peak lies at W≈30 > 24 cores, and SMT
does not help (memory_ceiling_poc: DRAM efficiency 86→58 % at 25 threads). Paper-safe phrasing: at 23 workers the optimised
CSV arm sustains 93 % of the no-serde byte rate / 89 % of its row rate; row gap = 1.044× (bigger input) × 1.074×
(byte-rate deficit); both arms' fitted curves converge to the same ~70–72 GB/s ceiling (native ~W22, CSV ~W30). Do NOT
write "both hit the DRAM wall" until Probe D returns the DRAM number.

## 5. Probe plan (~22 min, Threadripper; NOT launched — needs the owner's go)
Preconditions: `pkill -x main` pre-flight; `perf_event_paranoid` ≤ 1 (box −1); DRAM via AMDuProfPcm (perf undercounts
on this Zen3 part); governor performance. Known confounds in the published binary: SHRED_TIMER (needs a rebuild to
remove → NOT in budget; measure in aggregate first), NES_LOG_LEVEL unset (Probe B A/Bs it).

**Probe A — THE discriminator: buffer-size sweep at constant 2 GiB pool bytes** (~6 min).
native_native @W23 and @W8, simd @W23 as control; `operator_buffer_size` ∈ {65536, 131072, 262144, 524288} with
`number_of_buffers_in_global_buffer_manager` ∈ {32768, 16384, 8192, 4096} (pool bytes constant → FIFO reuse distance
constant); `NES_FILE_REPEAT=4` (W23 window 0.38 → ~1.5 s; METRIC TRAP: reported mbps/mrows = per staged pass → ×4);
5 reps. Read: byte-bound ⇒ GB/s flat, buf/s halves per doubling; buffer-bound ⇒ buf/s flat, GB/s doubles; mixed ⇒ fit
rate = B/(a + b·B): a = serialized per-buffer cost (H3; prior 1.3–1.8 µs), 1/b = asymptotic byte rate (H1; prior 72–83 GB/s).
W8 is the control (64 % of bus): equal gains at W8 and W23 ⇒ per-buffer. Gotchas: buffer size also sets the mmap WINDOW
size (source-side cost moves too → Probe D separates); wrapExternalMemory leaks a segment + control block per window
into an unbounded vector (fine at repeat 4; never > 32); none of the 4 sizes is a multiple of 110 (spanning cost present
at every point, does not bias the slope). pbench must vary both knobs per point (two-parameter axis or 4 single-point
variants).
YAML skeleton: defaults = figQ's (W23, io1, fnattr, pin/ccx off, admission 1024, 131072, COMPILER, pool 16384, MmapFile,
Monitoring, SystemNative string_length "13,73", NATIVE out, repeat 8, NES_MMAP_POPULATE=1, NES_FILE_REPEAT=4);
variants bufsize_natnat_w23 / bufsize_natnat_w8 (override W=8) / bufsize_simd_w23 (data_size csv, SIMDCSV LOCK_FREE,
JSON out, the fast parsers); x = worker.default_query_execution.operator_buffer_size.
**Probe B — hygiene A/B** (~3 min): native_native @W23, 128 KiB, 5 reps × {baseline, +NES_LOG_LEVEL=WARNING,
+NES_SOURCE_EMIT_BATCH=32, both}. Any arm > 3 % = removable artifact in the published figure.
**Probe C — 110-divisibility A/B** (~3 min): native_native @W23 and W8, operator_buffer_size ∈ {131072, 131010 (=110×1191)},
5 reps → removes the per-buffer spanning tuple (vector malloc + Arena pooled-buffer acquire + copy + 2nd index) at 0.05 %
byte-rate change; simd = null control. (UIntOption with NumberValidation, no power-of-two constraint — smoke 1 run first.)
**Probe D — counters** (~8 min): NES_FILE_REPEAT=32 (W23 ~12 s, W8 ~17 s), native_native + simd @W23 and W8, alongside:
`AMDuProfPcm -m memory -I 1000 -d 10 -A system` and `-m l3`; `perf stat -p $PID -a --timeout 10000 -e cycles,instructions,
task-clock,ls_dmnd_fills_from_sys.{lcl_l2,int_cache,ext_cache_local,mem_io_local},ls_alloc_mab_count,
de_dis_dispatch_token_stalls1.{store_queue_rsrc_stall,load_queue_rsrc_stall}`; source-thread CPU% from
/proc/$PID/task/<DataSrc tid>/stat over 10 s; `nes-profile.sh --port 9099 --secs 10 --stat`. Decision table: DRAM ≥ 78 GB/s
with mem_io_local dominating → H1 (report amp = DRAM/72.23); DRAM ≈ 72, amp ≈ 1 → H1-adjacent, rest H2/H3; DRAM 50–60 with
L3-miss latency 1100–1300 clk and MAB ~1.8–2 → H2; ext_cache_local ≈ mem_io_local → H5; source thread < 70 % → H4 excluded;
source ~100 % with sched_yield hot → yield-spin burning a core; store_queue stalls ≳ 0.1/cycle → unexpected; profile with
MonitoringSink::execute / EmitOperatorHandler::setChunkNumber / __lll_lock_wait / native_queued_spin_lock_slowpath → H3 localised.
**Probe E — in-flight window A/B** (~2 min): native_native @W23, default_max_inflight_buffers ∈ {64, 256}, 5 reps.
Little's law predicts p50 ×4 with throughput unchanged if consumer-bound; a rise means the 8 MiB WIP window co-limits.
**Probe F (optional)** — L3-resident input: `head -c 14417920 bid_strings_3GB.nes > bid_strings_L3.nes` (110 × 131072 B =
131072 rows, exactly 110 windows), ~10 s window: byte rate ≫ 78 GB/s ⇒ H1 by removal; pinned ~600 kbuf/s ⇒ H3 by removal.
Direction only (wrapExternalMemory's unbounded vector grows ~600 k/s here).

## 6. Corrections for existing writeups (independent of the probe)
- IDEAL_SCALING_RESULTS.md "native out lifts the ceiling 516 → 705" is wrong: native_json ≡ native_native at every W in
  the matrix; the jump was the Aug-14 → Sep-2 per-task machinery commits.
- bypass-scaling memory "no-serde saturates ~1015 Mrows/s (bandwidth)" for M1 is right only as the 3×-traffic copy_rfo
  ceiling (24.34 vs 25.6 GB/s useful); the M1 bypass W16–24 points are physically impossible as stated (ramp) → re-run ≥ 3 s.
