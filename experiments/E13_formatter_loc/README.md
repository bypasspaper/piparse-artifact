# E13 — Lines of code to add a formatter (evaluation statement, static analysis)

**Claim in the paper.** A new input format is one indexer class — descriptor, metadata accessor, buffer-indexing routine,
two generated registrars: **329–339 lines (254–264 non-blank non-comment) across three unrelated formats**, of which only
74–154 lines are the format's own scan; a new output format is **338 lines (275 code)**, 93 of them serialisation.
Adding HL7 took **1,292 lines of plugin C++ (+20 CMake) and 0 production lines outside the plugin** (plus a 24-line
fix of a pre-existing multi-byte-delimiter bug in one shared header); 65 % of the 1,292 is an optional SIMD arm.
Packed XML afterwards took **zero** new indexer code (a six-line HL7 configuration) + a 108-line kernel relaxation.
~6,800 (input) / ~1,900 (output) lines of shared machinery are reused unchanged (~20:1).

**Machine.** None — static analysis of the engine tree. Original measurement 2026-10-07 on `b5d757c9f6` + the then
uncommitted overlay; the artifact tag `piparse-artifact-v1` (`184ec91f50`) contains exactly that overlay.

**Measured with.** `scripts/loc.py` (raw / code / nolic per file; `code` == cloc's code column), `scripts/range.py`
(the same for `FILE:START-END` ranges), `scripts/agg.py` + `scripts/split.tsv` (the mandatory / kernel / optional /
benchmark attribution of every line range — the auditable record), `git show --numstat` on four commits.

## Files

| path | what |
| --- | --- |
| `scripts/{loc.py,range.py,agg.py,split.tsv}` | the counters and the line-range attribution table (repo-relative paths) |
| `expected/FORMATTER_LOC_2026-10-07.md` | the full study: method, per-file tables (§2–3), the M/K/O/B split (§4), minimum slices (§5), git ground truth (§6), what a formatter does not implement (§7), paper-safe statement (§8), caveats (§9), consistency with the earlier effort table (§10) |
| `expected/headline.txt`, `expected/min_slices.txt`, `expected/split_table.txt` | the driver's output on the frozen tree (2026-10-12) |
| `run.sh` | reproduces everything above against `$NES_SRC`; writes `out/` |

## Reproduce (seconds)

```
NES_SRC=/path/to/nebulastream-public ./run.sh        # checkout at tag piparse-artifact-v1
cat out/headline.txt; cat out/split_table.txt; cat out/per_file_tables.txt
```

Verified 2026-10-12 on `184ec91f50` (= tag): min input **334 raw / 264 code**, min output **338 / 275**; every `ship`
column of the §4 split (CSV-in 329/254, SIMDCSV 824/637, HL7-in 1187/909, SchemaJSON 536/377, JSON-in 744/612, Native
339/254, CSV-out 557/477, JSON-out 1033/836, HL7-out 343/275) and every per-directory total of §2–3 reproduce exactly;
git truth HL7 input +1292 plugin C++ / 0 core, HL7 output +376, XML +108/−59; cloc cross-check HL7 input dir code = 985.
The only delta: the `CSV (out)` per-file line in `out/per_file_tables.txt` omits the 2 CMake lines (589/477/561 vs the
doc's 591/479/563 which include `src/CMakeLists.txt:21-22`).

## Caveats / provenance notes

- The tables include the benchmark overlay (two ablation knobs, +160/−43 lines in the formatter trees, §9.1); the §5
  minimum slices are unaffected. Subtract ~11 lines per custom FIF and ~28 from JSON-out for a pre-overlay number.
- Quote the `ship` (M+K+O) columns, not `ALL`, for "size of the formatter" claims; the `B` column is self-labelled
  benchmark-only code (`Sequential*` rungs, `TMP DIAGNOSTIC` counters).
- Git insertion counts include the 12–14-line license preamble per file (HL7 input +1292 → +1180 without preambles).
  The earlier effort table (SchemaJSON ≈590, HL7 ≈1300, XML 0+107) is raw git insertions; on one footing use
  raw-minus-preamble (SchemaJSON 537, HL7 1187, XML +108/−59). HL7's ≈1300 is 65 % optional (SIMD kernel + custom FIF +
  second indexer); the format itself is 334 lines.
- Commit hashes in older notes (`e66ce11d95`, `e20689f0ab`, `9c10cbd4b3`) were rewritten by an autosquash; the current
  hashes with byte-identical content are `bd619454d9`, `f804ba27d3`, `e8e34d85cb`.
