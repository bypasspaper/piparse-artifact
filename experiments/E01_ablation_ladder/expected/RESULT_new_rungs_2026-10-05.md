<!-- SPDX-License-Identifier: Apache-2.0 -->
# Is r3_eager a parse-all rung? IR-dump probe on q2og (2026-10-05) — NO

**Question (user):** the v7 ablation's r3_eager (`SequentialCSV` + `eager_parse: true`, default invoke, no fnattr/
inline/tcb, W1 InMemory) was meant to be "compiled serde with eager deserialisation, all fields parsed" so that
r2 → r3_eager isolates compilation with the WORK held equal to the uncompiled rung (which parses all 6 fields).
Does the JIT keep all six parses?

**Answer: no. On q2og the eager module parses 3 of 6 fields per record.** Verified in the post-optimisation LLVM
IR (nautilus `dump.file`: `after_llvm_generation.ll` is printed AFTER `makeOptimizingTransformer` ran on the module
in place — see vcpkg nautilus `LLVMIROptimizer.cpp:46-59`). Proxy callees are bare addresses; resolved against the
worker's `nm` table by PIE page-offset matching (`scripts/resolve_proxies.py`, 31/31 resolved in both modules).

## Per-record hot loop, eager module (`dumps/r3_eager_q2og/after_llvm_generation.ll` blocks 25→52→65→78)
| schema field | parser | in the loop? | why |
| --- | --- | --- | --- |
| timestamp UINT64 | TracedUINT64 (traced, inline IR) | **NO** — no digit loop anywhere (0 `mul …, 10`) | result unused → LLVM DCE |
| auctionId INT32 | FastINT32 → proxy `parseWithFastInt<int>` | yes (1×) | used by the filter |
| bidder INT32 | FastINT32 → proxy `parseWithFastInt<int>` | **yes (1×), although unused** | opaque invoke at default mode → not removable |
| price FLOAT64 | EiselFloatF64 → proxy `parseWithEiselFloat<double>` | yes (1×, hoisted above the switch) | used on survivors; eager hoists it |
| channel, url VARSIZED | lazy view (ptr,len), `parseValue()` = view, no copy | **NO** — no copy/materialise call | dead view → removed |

Then `switch i32 %auctionId` (5 constants) → output path (parseInt32 + parseF64ZMIJ + copyBytesUnchecked ×3 variants).
So r3_eager = "parse every field whose parser is an opaque proxy": which fields survive is an accident of
which parser plugin is traced (Traced* = inline IR, DCE-able) vs invoked (FastINT32, EiselFloat = kept).

## Lazy control (`dumps/r3_lazy_q2og`, blocks 25→49→67)
auctionId parsed **5× per record** (one `parseWithFastInt` per OR term, blocks 49+67; no GVN at default invoke),
bidder/timestamp never, price forwarded RAW (`writeRawBytes` / `copyBounded16/32`, no Eisel, no ZMIJ). Throughput
this probe: eager 2547 MB/s, lazy 2267 (v7: 2583 / 2299) — eager wins on q2og because 1 parse < 5 parses, even
paying the extra bidder + price parses.

## Consequence for the ladder
r2 (uncompiled) materialises all 6 fields incl. both strings via std::function + child-buffer copies. r3_eager
parses 3 numerics. The r2→r3_eager "compilation" bar (q2og 2.92×, q2mod 2.93×) therefore still bundles projection
pushdown (3 fields, incl. both strings, never touched) with compilation/fusion. A true parse-all compiled rung
does not exist yet.

## Options for a parse-all rung (step 2 — DONE below, option A chosen in the 'full' variant: Fast twins + string copy)
A. **`eager_sink` knob**: in eager mode write every materialised value (and a byte-copy of each VARSIZED) into a
   per-pipeline scratch area obtained through an opaque proxy, 1 store per field per record (~1–2 ns/row). LLVM
   cannot DCE stores to escaped memory. Cleanest; the sink cost is small and uniform.
B. **Force usage through the query**: output all fields → changes the query (output-bound) — rejected.
C. **Make eager parses opaque**: route traced parsers through invoke in eager mode and copy VARSIZED through an
   invoke — more code, and changes the parser codegen itself.
Recommended: A, run as rung `r3_eager_all` on the 10 queries (W1, 3 reps, ~20 min), integrate by the same-session
ratio method of PASSTHROUGH_ABLATION_SPLIT_RESULTS.md → compile bar splits into compilation (r2→r3_eager_all),
pushdown (r3_eager_all→r3_eager), laziness/passthrough (r3_eager→r3).

## Files
`dumps/r3_eager_q2og/`, `dumps/r3_lazy_q2og/` (trace, ssa, ir, mlir, ll); `scripts/resolve_proxies.py <ll> <nm-table>`
(nm table: `nm -C --defined-only <worker> | awk '$2 ~ /[TtWw]/'`), `scripts/eager_skeleton.txt` (labels+calls+branches),
`scripts/ablation_r3eager_q2og_irdump.yaml` (pbench, UNCOMMITTED copy), `scripts/irdump.log`. Run group
20261005T180846-db7fdd9e (DB `ablation_r3eager_q2og_irdump`). Worker: cmake-build-release Sep-3, b5d757c9f6.


---

# Step 2 — the parse-all compiled rungs (DONE 2026-10-05 18:28–18:47, run_group 20261005T182825-4660e569)

**Decision (user): full version** = numerics via the invoke-based Fast twins + an opaque byte copy of every VARSIZED
field under eager. Engine knob: `NES_EAGER_COPY_VARSIZED=1` (env, effective only with `eager_parse`), implemented as
`eagerCopyVarsizedProxy` in `nes-input-formatters/src/RawValueParser.cpp` (thread-local 1 MiB ring arena, memcpy per
field, opaque proxy → the JIT must keep it; diff `scripts/rawvalueparser_eager_copy_knob.diff`, UNCOMMITTED, default
off = unchanged behaviour). Worker + nes-cli rebuilt in `cmake-build-release` (18:27; Sep-3 binaries kept as `*.sep03`;
68 ninja steps, no nautilus rebuild). **IR-verified on q2og** (`dumps/r3_eager_fast_q2og`, `dumps/r3_eager_all_q2og`):
r3_eager_fast carries `parseWithFastInt<unsigned long>` (timestamp) ×2 sites + INT32 ×4 + Eisel ×2; r3_eager_all adds
`eagerCopyVarsizedProxy` ×4 sites (channel, url × 2 tuple paths).

**Rungs** (`experiments/ablation_eager_all_bidstr.yaml`, 10 queries × 5 rungs × 3 reps = 150 runs, 0 fail, 19 min; W1
InMemory, csv→JSON, default invoke, no fnattr/inline/tcb, NES_INMEM_REPEAT=1): r2_uncompiled | r3_compiled (v7 r3) |
r3_eager (v7 split rung, paper parser block) | r3_eager_fast (+ Fast twins → every numeric parse survives) |
r3_eager_all (+ string copies) = **the work-equal compiled parse-all rung**.

## Today's medians (MB/s, W1, n=3) and rep spread
| query | r2_uncompiled | r3_compiled | r3_eager | r3_eager_fast | r3_eager_all | spread max % |
|---|---|---|---|---|---|---|
| q0 | 309 | 1323 | 680 | 669 | 625 | 2.6 |
| qproject | 715 | 3950 | 1657 | 1486 | 1289 | 1.0 |
| qroute | 618 | 3713 | 1570 | 1480 | 1318 | 1.0 |
| q1 | 619 | 1569 | 1141 | 1099 | 966 | 3.2 |
| q2og | 903 | 2302 | 2600 | 2190 | 1781 | 4.4 |
| q2mod | 896 | 4815 | 2601 | 2178 | 1783 | 1.0 |
| q10 | 459 | 1296 | 918 | 857 | 779 | 2.2 |
| q14 | 797 | 2168 | 2015 | 1766 | 1478 | 1.0 |
| q22 | 456 | 1304 | 915 | 851 | 807 | 0.7 |
| qex | 842 | 2507 | 2287 | 2113 | 1777 | 0.7 |

## Anchors vs v7 (today / v7)
| query | r2 | r3 | r3_eager (v7 split, projected) |
|---|---|---|---|
| q0 | 0.99 | 1.00 | – |
| qproject | 1.01 | 1.00 | – |
| qroute | 1.01 | 1.01 | – |
| q1 | 1.01 | 1.00 | – |
| q2og | 1.02 | 1.00 | – |
| q2mod | 1.01 | 1.01 | – |
| q10 | 1.01 | 1.01 | – |
| q14 | 1.01 | 0.99 | – |
| q22 | 1.01 | 1.03 | – |
| qex | 1.01 | 1.00 | – |

## Factor decomposition of the compile bar (today's same-session ratios)
| query | r3/r2 (old compile bar) | **compilation** r3_eager_all/r2 | strings r3_eager_fast/r3_eager_all | numerics r3_eager/r3_eager_fast | **pushdown total** r3_eager/r3_eager_all | lazy+passthrough r3/r3_eager | ns/row r2 | ns/row r3_eager_all |
|---|---|---|---|---|---|---|---|---|
| q0 | 4.28 | **2.02** | 1.07 | 1.02 | **1.09** | 1.95 | 371 | 184 |
| qproject | 5.53 | **1.80** | 1.15 | 1.11 | **1.29** | 2.38 | 161 | 89 |
| qroute | 6.00 | **2.13** | 1.12 | 1.06 | **1.19** | 2.37 | 186 | 87 |
| q1 | 2.54 | **1.56** | 1.14 | 1.04 | **1.18** | 1.38 | 186 | 119 |
| q2og | 2.55 | **1.97** | 1.23 | 1.19 | **1.46** | 0.89 | 127 | 65 |
| q2mod | 5.37 | **1.99** | 1.22 | 1.19 | **1.46** | 1.85 | 128 | 64 |
| q10 | 2.83 | **1.70** | 1.10 | 1.07 | **1.18** | 1.41 | 250 | 147 |
| q14 | 2.72 | **1.85** | 1.19 | 1.14 | **1.36** | 1.08 | 144 | 78 |
| q22 | 2.86 | **1.77** | 1.06 | 1.08 | **1.13** | 1.42 | 252 | 142 |
| qex | 2.98 | **2.11** | 1.19 | 1.08 | **1.29** | 1.10 | 136 | 65 |
| **geomean** | 3.55 | **1.88** | 1.15 | 1.10 | **1.26** | 1.50 | | |

## v7-footing projection (r3_v7 × today's ratios): the parse-all rung as it would sit in the published ladder
| query | r2_v7 | r3_eager_all_v7 | r3_eager_fast_v7 | r3_eager_v7 | r3_v7 |
|---|---|---|---|---|---|
| q0 | 314 | 625 | 669 | 680 | 1323 |
| qproject | 707 | 1286 | 1483 | 1653 | 3941 |
| qroute | 611 | 1308 | 1469 | 1559 | 3687 |
| q1 | 611 | 963 | 1095 | 1137 | 1563 |
| q2og | 889 | 1779 | 2187 | 2597 | 2299 |
| q2mod | 885 | 1766 | 2157 | 2575 | 4768 |
| q10 | 455 | 770 | 847 | 907 | 1281 |
| q14 | 790 | 1490 | 1780 | 2031 | 2185 |
| q22 | 453 | 781 | 824 | 886 | 1262 |
| qex | 830 | 1772 | 2107 | 2280 | 2500 |

wrote /home/user/Notes/nebulastream/benchmark/2_engine_to_e2e/ablation_eager_irdump_2026-10-05/data/eager_all_decomposition.csv


## Findings
1. **Work-equal compilation = 1.88× geomean (1.56 q1 … 2.13 qroute)**, not the 3.55× the v7 ladder credits to
   "compilation" (r3/r2). The old bar factors EXACTLY (by construction) into compilation 1.88 × projection pushdown
   1.26 × laziness/passthrough 1.50. On the filters: q2og 2.55 = 1.97 × 1.46 × 0.89, q2mod 5.37 = 1.99 × 1.46 × 1.85.
2. **What the 1.88× is**: both rungs parse 4 numerics and copy 2 strings per row; r2 does it in a separate C++ task on
   the source thread with a per-field type switch, std::function string parsers, a native-row write + child-buffer
   bookkeeping, then a second task reads the row, then a third stage serialises; r3_eager_all does it in one fused JIT
   pass with no intermediate buffer. Per row on q2og: 127 → 65 ns. (The compiled rung still skips r2's native-row
   WRITES for unused fields — parsed values are dropped — so "fusion" includes that; the parse calls themselves are kept.)
3. **Projection pushdown = 1.26× geomean**, 1.46× on the pure filters (q2og/q2mod: strings 1.22–1.23, numerics
   1.19), 1.36 on q14, 1.29 qex/qproject. ⚠️ On queries that USE the strings (q0, qroute, q22, qex) the "strings"
   factor (1.06–1.19) is partly the knob's double copy, and on queries that use timestamp the "numerics" factor
   contains the TracedUINT64-vs-FastUINT64 codegen difference (q0 1.02) — so read the pushdown column as exact on
   q2og/q2mod/q14 and as an upper bound elsewhere.
4. **Laziness/passthrough = 1.50× geomean**, 1.95–2.38 on the output-bound projections (q0, qproject, qroute),
   1.38–1.42 on computed outputs (q1, q10, q22), ~1.1 on filters, **0.89 on q2og** (lazy re-parses auctionId 5× at
   this footing; fnattr at r4 recovers it) — unchanged from the 08-27 split.
5. Anchors: today's r2 and r3 = v7 × 0.99–1.03 on all 10 → the rebuilt binary is drift-stable; the v7-footing
   projection table above is what to splice into the published ladder (insert r3_eager_all, r3_eager_fast, r3_eager
   between r2 and r3).

## Paper-safe phrasing
"Compilation with identical work (every field parsed, strings copied) buys 1.9× over the interpreted formatter; the
remaining 1.9× of the old 3.6× compile bar is parse elision — projection pushdown of unused fields (1.26×) and lazy
parsing with raw passthrough of untouched fields to the output (1.5×)."

## Files (step 2)
`scripts/ablation_eager_all_bidstr.yaml` (+ `_irdump_smoke.yaml`), `scripts/decompose_eager_all.py <run_group> <outdir>`,
`scripts/ablation_eager_all_bidstr_2026-10-05.log`, `data/eager_all_decomposition.csv`, `data/eager_all_tables.md`,
`dumps/r3_eager_fast_q2og`, `dumps/r3_eager_all_q2og`, `scripts/rawvalueparser_eager_copy_knob.diff`.


---

# Step 3 — the lazy-WITHOUT-passthrough rung (DONE 2026-10-05 19:13–19:25, run_group 20261005T191325-76194e52)

**Question (user):** is there a rung with lazy values (on-demand parse = less serde code) but WITHOUT overloading and
WITHOUT passthrough? Not before; now: **r3_lazy_nopass** = compiled + lazy, overload off, paper parser block, default
invoke / no fnattr / inline / tcb, and passthrough off on BOTH sides: `output_formatter: {type: JSON,
disable_passthrough: true}` (lazy numerics parsed at the use site in the writer and ZMIJ re-serialised; whole-record
fast path declined) + `input_formatter: {…, assume_clean_strings: false}` (VARSIZED loses JSON_ESCAPED → escape-scan
path instead of verbatim forwarding; the string gate is separate from the output knob). Config-only (both knobs
pre-existed; the hoisting micro used them on q_route only). **IR-verified on q2og** (`dumps/r3_lazy_nopass_q2og`): no
`writeRawBytes`/`copyBounded*` anywhere; Eisel + ZMIJ at the output inside the survivor branch; FastInt at 22 sites
(5 per OR term × 2 paths + output). Same session anchors: r3_eager_all (parse-all) and r3_compiled (= v7 r3).
`experiments/ablation_lazy_nopass_bidstr.yaml`, 90 runs, 0 fail, 12 min.

## Medians (MB/s, W1, n=3) + rep spread; anchors vs the afternoon session and v7
| query | r3_eager_all | r3_lazy_nopass | r3_compiled | spread max % | eager_all now/prev | r3 now/prev | r3 now/v7 |
|---|---|---|---|---|---|---|---|
| q0 | 619 | 935 | 1320 | 3.6 | 0.99 | 1.00 | 1.00 |
| qproject | 1285 | 2125 | 3933 | 1.8 | 1.00 | 1.00 | 1.00 |
| qroute | 1313 | 3052 | 3693 | 0.5 | 1.00 | 0.99 | 1.00 |
| q1 | 968 | 1129 | 1567 | 1.4 | 1.00 | 1.00 | 1.00 |
| q2og | 1787 | 2295 | 2285 | 0.8 | 1.00 | 0.99 | 0.99 |
| q2mod | 1775 | 4688 | 4818 | 3.5 | 1.00 | 1.00 | 1.01 |
| q10 | 779 | 900 | 1297 | 3.5 | 1.00 | 1.00 | 1.01 |
| q14 | 1477 | 1948 | 2161 | 0.6 | 1.00 | 1.00 | 0.99 |
| q22 | 807 | 898 | 1303 | 0.7 | 1.00 | 1.00 | 1.03 |
| qex | 1764 | 2528 | 2504 | 0.8 | 0.99 | 1.00 | 1.00 |

## Laziness split (same session) and the full compile-bar chain
| query | **lazy code gen** nopass/eager_all | **passthrough** r3/nopass | product r3/eager_all | compilation r2→eager_all (afternoon) | old bar r3/r2 (afternoon) | chain product | ns/row eager_all | ns/row nopass | ns/row r3 |
|---|---|---|---|---|---|---|---|---|---|
| q0 | **1.51** | **1.41** | 2.13 | 2.02 | 4.28 | 4.31 | 186 | 123 | 87 |
| qproject | **1.65** | **1.85** | 3.06 | 1.80 | 5.53 | 5.52 | 89 | 54 | 29 |
| qroute | **2.32** | **1.21** | 2.81 | 2.13 | 6.00 | 5.99 | 87 | 38 | 31 |
| q1 | **1.17** | **1.39** | 1.62 | 1.56 | 2.54 | 2.53 | 119 | 102 | 73 |
| q2og | **1.28** | **1.00** | 1.28 | 1.97 | 2.55 | 2.52 | 64 | 50 | 50 |
| q2mod | **2.64** | **1.03** | 2.71 | 1.99 | 5.37 | 5.40 | 65 | 25 | 24 |
| q10 | **1.15** | **1.44** | 1.66 | 1.70 | 2.83 | 2.83 | 147 | 128 | 89 |
| q14 | **1.32** | **1.11** | 1.46 | 1.85 | 2.72 | 2.71 | 78 | 59 | 53 |
| q22 | **1.11** | **1.45** | 1.62 | 1.77 | 2.86 | 2.85 | 142 | 128 | 88 |
| qex | **1.43** | **0.99** | 1.42 | 2.11 | 2.98 | 3.00 | 65 | 45 | 46 |
| **geomean** | **1.50** | **1.26** | 1.89 | 1.88 | 3.55 | 3.55 | | | |

## v7-footing projection of the new rung (r3_v7 × nopass/r3 today)
| query | r2_v7 | r3_eager_all_v7 (afternoon proj.) | r3_lazy_nopass_v7 | r3_v7 |
|---|---|---|---|---|
| q0 | 314 | 625 | 937 | 1323 |
| qproject | 707 | 1286 | 2129 | 3941 |
| qroute | 611 | 1308 | 3047 | 3687 |
| q1 | 611 | 963 | 1127 | 1563 |
| q2og | 889 | 1779 | 2309 | 2299 |
| q2mod | 885 | 1766 | 4639 | 4768 |
| q10 | 455 | 770 | 888 | 1281 |
| q14 | 790 | 1490 | 1971 | 2185 |
| q22 | 453 | 781 | 870 | 1262 |
| qex | 830 | 1772 | 2524 | 2500 |

wrote /home/user/Notes/nebulastream/benchmark/2_engine_to_e2e/ablation_eager_irdump_2026-10-05/data/lazy_nopass_decomposition.csv


## Findings
1. **The laziness factor (r3 / r3_eager_all = 1.89) splits into lazy code generation 1.50× and passthrough 1.26×**
   (geomeans). Full chain, by construction exact per query: old compile bar 3.55 = compilation (work-equal) 1.88 ×
   lazy code generation 1.50 × passthrough 1.26.
2. **Lazy code generation** = parse only the fields the query uses, at the use site (inside the taken branch), output
   still re-serialising: q2mod 2.64× (auctionId once, price only on the 1/123 survivors), qroute 2.32× (numerics only
   on the 20 % channel matches), qproject 1.65×, q0 1.51× (strings take the escape path once instead of copy + escape),
   qex 1.43, q14 1.32, q2og 1.28 (the 5× re-parse at this footing still beats parse-all + 2 string copies),
   computed-output queries q1/q10/q22 1.11–1.17 (3 of 4 numerics are used anyway).
3. **Passthrough** = raw forwarding of untouched lazy fields to the JSON output: qproject 1.85×, q22/q10/q0/q1
   1.39–1.45 (the non-computed int columns), qroute 1.21, filters ~1.0 (q2og 1.00, q2mod 1.03, qex 0.99).
4. Note the two decompositions of the same 1.89: via the eager rungs it reads pushdown 1.26 × lazy+passthrough 1.50;
   via r3_lazy_nopass it reads lazy code generation 1.50 × passthrough 1.26 — same geomeans by coincidence, different
   per-query splits. The r3_lazy_nopass chain is the one that matches the paper's layer names (lazy value = on-demand
   parse incl. pushdown and branch-local parsing; passthrough = raw forwarding) → use it for the ladder figure.
5. Ladder order caveat (unchanged): at this footing there is no fnattr, so lazy re-parses repeated uses (q2og 5×); r4
   recovers it (v7 q2og r4/r3 = 1.65×). Overloading (lazy constantEq) enters only at r6b.

## Paper-safe sentence (replaces the one in Step 2)
"With identical work, compilation buys 1.9× over the interpreted formatter. Lazy values add 1.5× by generating serde
code only for the fields a query touches, at the point where it touches them, and raw passthrough of untouched fields
to the output adds a further 1.26× — together the 3.6× the ladder credits to the compiled rung."

## Files (step 3)
`scripts/ablation_lazy_nopass_bidstr.yaml` (+ `_irdump_smoke.yaml`), `scripts/decompose_lazy_nopass.py <rg> <rg_prev>
<outdir>`, `scripts/ablation_lazy_nopass_bidstr_2026-10-05.log`, `data/lazy_nopass_decomposition.csv`,
`data/lazy_nopass_tables.md`, `dumps/r3_lazy_nopass_q2og`. v7-footing projection table above: insert
r3_eager_all → r3_lazy_nopass → r3 between r2 and r4 in the published ladder.
