<!-- SPDX-License-Identifier: Apache-2.0 -->
# Ablation ladder v7 — VARSIZED / paper-workload retake (2026-08-24)

**One-off session. Status: DONE, publishable, binary restored & clean.**
Supersedes v6 (`SESSION_HANDOVER_2026-08-24.md` / `ablation_ladder_v6_inmem.csv`).
Next session resumes the **micro-experiments** family (see `[[microbench-rerun-x86]]`,
`MICROBENCH_RERUN_HANDOVER_2026-08-21.md`) — this handover CLOSES the ablation retake.

---

## 0. Why we retook it (the trigger)

The v6 InMemory ladder was internally clean but **not comparable to the rest of the paper**
(the cross-format matrix / `PAPER_WORKLOAD.md`). User flagged three problems; a fourth surfaced
on inspection. All four confirmed against the actual experiment YAMLs:

| axis | v6 ladder (was) | paper/matrix frame (target) |
| --- | --- | --- |
| **parallelism** | W16 | **W23** |
| **ccx/pin** (compounds #1) | `ccx_aware=true` + `pin_threads=true` (the ~2× single-source **pathology**) | `ccx=false` + `pin=false` (healthy) |
| **dataset** | `medium` = `bid_1GB.csv` (numeric-only, 1.09 GB) | `csv` = `bid_strings_3GB.csv` (**varsized**, 3.6 GB, same 31.3M rows) |
| **queries** | old nexmark set (person_*, bid_star, q1_price, q2_original…) | 10 **frozen paper** queries (`bidstr_q0…qex`) |

The ccx/pin item is the same pathology documented in `MATRIX_RESULTS_2026-08-05.md` V2 note
(ccxON+pinON round-robins one source's ordered buffers across 4 CCX cells → understates Par ~2×).

---

## 1. The anchor (do this FIRST on any ablation retake)

Before rebuilding the fine ladder, we validated the config end-to-end by re-running **rung 7 only**
= the matrix's `r_par` rung, and checking it reproduces the paper. rung 7 (full-opt compiled,
parallel) IS the matrix `r_par`, and the frozen experiment already existed:
`experiments/matrix/cell_csv_json_rparfix.yaml` (W23 / ccx-off / pin-off / InMemory REPEAT=20 /
bidstr / paper queries).

**Result: rung 7 on HEAD reproduces matrix V2 r_par within ±2%, geomean HEAD/V2 = 0.993** (every
query 0.98–1.00). ⇒ config validated; the **parallel rung is drift-stable** `cbf156f20c` → HEAD
(`8217cce465`, only 2 commits: MmapFile source + codec-baseline bench flags). So we did NOT have to
re-measure the whole matrix on HEAD — the top of the ladder still lines up with the paper.

### ⚠️ TRAP that cost ~10 min (record it):
`MATRIX_RESULTS_2026-08-05.json`'s `raw` block still holds the **V1 PATHOLOGICAL** r_par
(ccx+pin on, ~2× understated) — it was **never updated** after the 08-06 ccx fix. Comparing against
it showed a fake 1.1–2.1× "drift" whose pattern (filter-class ~2×, passthrough ~1.14×) is exactly
the documented V1→V2 ccx-fix signature. **The live r_par is `matrix_2026-08-05/matrix_rpar_fixed_480.{csv,parquet}`**
(git `cbf156f20c`, run_group `20260806T200312-99b55b69`; also queryable in the pbench duckdb as
`cell_*_rparfix` at that commit). Use THAT for any r_par comparison, never the JSON `raw`.

---

## 2. Methodology (identical to v6, repointed)

- **Every rung InMemory** (prefill, zero-copy hand-out) → removes the ~11 GB/s page-cache read wall
  that BlockingFile serializes with parse on the single W1 thread. This is the v6 choice, KEPT.
  Consequence for anchoring: fine `r2` ≈ matrix `r_base` **+2–5%** (read negligible at 300–900 MB/s
  interpreted speed) and fine `r6` ≈ matrix `r_comp` **+12–45%** (InMemory read-wall removal, and the
  ordering is perfectly **inverse to per-row compute weight** — qproject/qroute +41–45% lightest,
  q10/q0 +12–15% heaviest; reproduces the source probe `ablation_src_probe_w1`). The clean shared
  anchor is r7 (both r7 and matrix r_par are InMemory).
- **W1** for sequential rungs r1–r6b, **W23 + ccx-off + pin-off** for r7.
- **Two-binary r5**: r5 (general inline only) runs on a **FASTPATH-OFF** binary so the JSON
  output-serialization 2× lands at r5→r6, not buried in general inline. Build steps in §5.
- **Throughput correction**: seq/r5 use `NES_INMEM_REPEAT=1` (reported == true); r7 uses
  `REPEAT=20` → **×20** (`r7_true` in the CSV is already corrected).
- Fast parsers in (Traced*/FastINT32/EiselFloat), ZMIJ out. csv→JSON. bid_strings_3GB, 31.3M rows.

### Rung map (fine ladder ↔ matrix coarse rungs)
```
r1  SequentialUncompiledOldCSV -> JSONUncompiled   (scalar find indexer, interpreted)
r2  SequentialUncompiledCSV    -> JSONUncompiled   == matrix r_base
r3  SequentialCSV -> JSON, default invoke          (compilation, no fnattr/inline/tcb)
r4  + fnattr
r5  + inline_invoke_calls        [FASTPATH-OFF binary]   (general proxy/accessor inline only)
r6  + trace_constant_bytes + output fast path  == matrix r_comp
r6b + overload
r7  Parallel W23 (ccx-off/pin-off)                 == matrix r_par  (anchored ±2%)
```

---

## 3. RESULTS — the v7 ladder

CSVs (canonical): `figures/ablation_ladder_v7_bidstr.csv` (MB/s, r7 ×20-corrected) and
`figures/ablation_ladder_v7_bidstr_mrows.csv` (Mrows/s; 114.87 bytes/row, Mrows/s = MB/s×0.0087059).

### Per-lever multipliers (geomean over 10 queries; and where each fires)
| lever | rung | geomean | min–max | fires on |
| --- | --- | --: | --- | --- |
| SIMD-band indexer | r2/r1 | 1.08× | 1.05–1.11 | uniform, small (interpreted, output-bound) |
| **compilation** | r3/r2 | **3.56×** | 2.56–6.04 | everywhere — dominant lever |
| fnattr (GVN parse-dedup) | r4/r3 | 1.12× | 1.00–1.90 | **only** q2og 1.65×, qex 1.90× (multi-OR); flat on 8 |
| general inline | r5/r4 | 1.18× | 1.02–1.55 | passthrough/accessor: q0 1.55×, q22 1.45×, qroute 1.35× |
| **output fast path** | r6/r5 | 1.25× | 1.00–1.81 | output-bound: q22 1.81×, q1 1.62×, qproject 1.51×, q0 1.31× |
| overload (lazy constantEq) | r6b/r6 | 1.08× | 1.00–1.93 | **only** q2og 1.93×, qex 1.14×; flat on 8 |
| **parallelization** W23 | r7/r6b | **9.73×** | 6.14–16.89 | inverse to W1 headroom (q14 16.9× slow@W1, q0 6.1× fast@W1) |

**Cumulative r1→r7: 48× (q1) … 89× (qex), geomean 68×.**

### The r5 SPLIT — the whole point of the fastpath-OFF binary
The bundled r4→r6 jump splits into two levers hitting **different query classes**:
- **general inline (r5)** → accessor-bound *passthrough* (q0 1.55, q22 1.45, qroute 1.35, q10 1.24)
- **output fast path (r6)** → serialization-bound *output* (q22 CONCAT 1.81, q1 float 1.62 = ZMIJ
  serializer splice via `output_parse`, qproject 1.51, q0 1.31)
- Examples: q0 2.02 = 1.55×1.31; q22 2.63 = 1.45×1.81; q1 1.64 = 1.02×1.62 (**almost all** output).
- Flat on filter queries (q2og/q2mod/qex) — their output is negligible; their wins are fnattr+overload.

### Anchor confirmation (all three matrix rungs)
- r2/r_base **1.02–1.05** (parity, read-negligible interpreted) ✓
- r6/r_comp **1.12–1.45** (documented InMemory read-wall removal, inverse to compute weight) ✓
- r7/r_par **0.98–1.00** (geomean 0.993) ✓

---

## 4. Provenance (pbench duckdb `results/piparse_bench.duckdb`, all @ git `8217cce465`)
| experiment | run_group | rungs | n |
| --- | --- | --- | --- |
| `cell_csv_json_rparfix` | `20260824T163459-fa906b40` | r7 (r_par) | 30 |
| `ablation_suite_json_inmem_seq_bidstr` | `20260824T165156-908bd862` | r1,r2,r3,r4,r6,r6b | 180 |
| `ablation_r5_inmem_fpoff_bidstr` | `20260824T171809-9e392631` | r5 (fastpath-OFF) | 30 |
| (V2 r_par reference) `cell_csv_json_rparfix` | `20260806T200312-99b55b69` @ `cbf156f20c` | r_par | 30 |

**474 runs total this session, 0 failures**, all rep-spreads tight (≤3%). Assembly script:
`scratchpad/assemble_v7.py` (pulls medians from duckdb, writes both CSVs). Raw run logs in
`/tmp/pbench_mon_*` (PBENCH_KEEP_LOGS=1) and scratchpad `ladderA/B/anchor*.log`.

### Experiment files (in `~/work/piparse-bench/experiments/`, embed their own gotchas)
- `ablation_suite_json_inmem_seq_bidstr.yaml` — r1–r4, r6, r6b (W1, FULL binary)
- `ablation_r5_inmem_fpoff_bidstr.yaml` — r5 (W1, FASTPATH-OFF binary; §5)
- `ablation_r1_smoke_bidstr.yaml` — r1-only 1-shot smoke (the NEW combo: InMemory + OldCSV + varsized)
- r7 reuses the existing `experiments/matrix/cell_csv_json_rparfix.yaml`

---

## 5. Binary state & the fastpath-OFF dance (RESTORED — do not skip restore)

`cmake-build-release` is a **host/native vcpkg build** (`/usr/bin/c++`); nes-build helper is `--paths`
= host mode, `exec`s directly. Build target list: `nes-single-node-worker nes-cli`.

**To reproduce the r5 fastpath-OFF binary** (only if re-running r5):
1. comment `nes-plugins/OutputFormatters/JSONOutputFormatter/CMakeLists.txt:34`
   (`nautilus_inline(json_output_formatter_plugin)`)
2. **move** `output_parse` from `enable:` to `disable:` in
   `testing/configurations/InlineTagConfig.yaml` — NOT just comment line 12! The config errors on
   any in-code tag listed in neither section ("Tags used in code but not listed here cause a compile
   error"); line 16 `#  - output_parse` under `disable:` is the prepared toggle — uncomment it.
3. **RECONFIGURE** — `NES_BUILD_DIR=cmake-build-release .claude/skills/nes-build/in-docker.sh cmake {build}`
   (InlineTagConfig is read at CONFIGURE time; a plain `--build` leaves a STALE generated header →
   the tag silently stays ON. VERIFY `cmake-build-release/generated/inline/InlineTagConfig.generated.hpp`
   → `#define NES_INLINE_TAG_output_parse 0`).
4. build the 2 targets.

**Restore (DONE this session):** `git checkout` both files → reconfigure → rebuild → verified
`NES_INLINE_TAG_output_parse 1`, toggle files git-clean, worker relinked 17:21. The current
`cmake-build-release` is the **FULL fastpath-ON binary @HEAD** — the canonical benchmark binary.

Other gotchas hit: `pkill -x main` pre-flight (NEVER `pkill -f` — self-kill); `--worker-port 9099`
(root worker squats on :8080); Monitoring sink is VOID (throughput only — r1-on-varsized output
correctness rests on the existing checksum systest gates, not the bench).

---

## 6. Open / deferred (NOT blockers for v7 being done)
- **fnattr on HEAD**: q2og r4/r3 = 1.65× here (varsized). v6 flagged the GVN-parse-dedup lever
  WEAKENED between `3d23dbc526`→HEAD on numeric q2_original (2.68→2.0×). Different data/query so not
  directly comparable, but fnattr is clearly alive-but-modest on HEAD. Not investigated; not needed.
- **Plot** not made — a stacked per-lever bar (like `ablation_ladder_v5.png`) from
  `ablation_ladder_v7_bidstr.csv` is the obvious figure. Deferred.
- **Paper consistency question for the author**: the matrix's W1 rungs (r_base/r_comp) used
  BlockingFile; this ladder uses InMemory. If the ablation figure sits next to the matrix, decide
  whether to note the +2–45% offset or re-measure the matrix W1 rungs on InMemory. r7 is unaffected.
- The person_* queries were dropped (paper workload is bid-based only). If the ablation wants a
  varsized-column *materialization* stress (old person_star role), add one — none of the 10 paper
  queries is a full-varsized SELECT *.

---

## NEXT SESSION → micro-experiments
Per user: resume the one-optimization-each micro-benchmark family. Entry:
`[[microbench-rerun-x86]]` + `1_isolated_to_engine/MICROBENCH_RERUN_HANDOVER_2026-08-21.md`
(6 families, user picks a subset in-session). The ablation retake is closed.
