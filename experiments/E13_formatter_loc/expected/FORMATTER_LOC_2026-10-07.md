# Formatter implementation effort (LOC) — NebulaStream, 2026-10-07

**Purpose.** Supply the paper's evaluation section with a defensible "how much code
does it take to add a new input / output format" number, split into the part the
framework forces on you (interface, descriptor, registration) and the part that is
genuinely the new format (the scan / serialisation kernel).

**Repo state.** `/home/user/work/nebulastream-public`, branch
`benchmark-piparse-lazyparse-fast-csv`, HEAD `b5d757c9f6`, plus an uncommitted
benchmark overlay (quantified in *Caveats*). Read-only investigation: nothing was
built, run, or modified.

---

## 1. Method

### Tools

* `cloc` v1.98 (`/usr/bin/cloc`) — used as a cross-check only.
* A purpose-written counter, so that all three metrics come from one pass:
  * `/tmp/claude-1000/-home-user-work-nebulastream-public/c6013374-f819-4ee4-8444-72cb802d2a90/scratchpad/loc.py`
    — per-file `raw / code / nolic`.
  * `.../scratchpad/range.py` — the same two metrics for an explicit `FILE:START-END` range.
  * `.../scratchpad/agg.py` + `.../scratchpad/split.tsv` — the category split
    (`split.tsv` is the machine-readable record of *every* line-range attribution
    in §4; `python3 agg.py split.tsv --detail` reprints it line by line).

> The scratchpad is session-scoped and will be garbage-collected, so all four files
> were copied next to this note:
> **`./formatter_loc_2026-10-07_scripts/{loc.py,range.py,agg.py,split.tsv}`**.
> `range.py` and `agg.py` `import` from `loc.py`, so keep them in one directory and
> run them from the repo root (paths in `split.tsv` are repo-relative).
> Everything else in this document is reproducible from `git` plus `cloc`.

### The three metrics

| metric | definition |
| --- | --- |
| **raw** | every line in the file |
| **code** | non-blank **and** non-comment. C++: strips `//`, `///`, `/* … */` (with string/char-literal awareness). CMake/py: strips `#`. |
| **nolic** | `raw` minus the leading Apache-2.0 preamble block and the one blank line after it (14 lines in `.hpp`/`.cpp`, 12 in `CMakeLists.txt`). This is "lines the author actually typed". |

**`code` is identical to `cloc`'s `code` column.** Cross-check:

```
cloc nes-plugins/InputFormatters/HL7InputFormatter  --quiet   # SUM code = 985
cloc nes-plugins/OutputFormatters/HL7OutputFormatter --quiet  # SUM code = 279
python3 loc.py $(find nes-plugins/InputFormatters/HL7InputFormatter  -type f | sort)  # 985
python3 loc.py $(find nes-plugins/OutputFormatters/HL7OutputFormatter -type f | sort)  # 279
```

### What is counted / excluded

* **Counted:** `.hpp`, `.cpp`, the plugin's own `CMakeLists.txt`, and the single
  `activate_optional_plugin(...)` line each plugin needs in
  `nes-plugins/CMakeLists.txt`.
* **Excluded from the plugin tables:** unit tests (`nes-input-formatters/tests/`),
  systests (`nes-systests/formatter/**/*.test`), test fixtures and fixture
  generators, benchmark harnesses (`nes-input-formatters/{benchmarks,tests/Benchmark}`).
  Test effort is reported separately in the git ground truth (§5).
* **Excluded structurally:** the generated registrar `.inc` files. The registrar
  *bodies* a plugin author writes (`RegisterXInputFormatIndexer`, `RegisterXOutputFormatter`,
  `…ValidationGeneratedRegistrar::RegisterX…`) are counted — they live in the
  plugin's `.cpp`. The dispatch tables that call them are generated at configure
  time by `cmake/PluginRegistrationUtil.cmake` (128 raw / 78 code) from the
  `.inc.in` templates in `*/registry/templates/`, so a new format adds **zero**
  hand-written registry lines.
* The category ranges in §4 skip pure file-level doc-comment blocks that sit
  *between* two attributed sections (e.g. the 27-line class comment in
  `HL7InputFormatIndexer.hpp`). That is why a plugin's `ALL raw` in §4 can be a
  few lines below its `nolic` total in §2; the gap is comments and namespace braces.

### What "a formatter" is, structurally

Everything the `InputFormatIndexerType` concept
(`nes-input-formatters/include/InputFormatters/Concepts.hpp:60-70`) forces on an
input formatter:

* a nested `IndexerMetaData` type satisfying `IndexerMetaDataType`
  (`Concepts.hpp:36-48`): constructible from `(InputFormatterDescriptor, TupleBufferRef)`
  and exposing `getTupleDelimitingBytes / getQuotationType / getFieldDataTypeAt /
  getFieldNameAt / getNumberOfFields / getNullValues`;
* a nested `FieldIndexFunctionType`;
* `static constexpr bool IsSequential`;
* `indexRawBuffer(FieldIndexFunctionType&, RawTupleBuffer&, IndexerMetaData&)`;
* `operator<<`;
* plus (not concept-enforced, but required by the registries)
  `static constexpr std::string_view NAME`, `static validateAndFormat(config)`, and the
  two registrar bodies.

**The `FieldIndexFunction` does not have to be written.** Core ships two reusable
ones — `FieldOffsets<N>` (`include/InputFormatters/FieldOffsets.hpp`, 277/215/263)
and `FieldBand` (`FieldBand.hpp`, 248/161/234). Who reuses what:

| indexer | FieldIndexFunction |
| --- | --- |
| `CSV` | `FieldOffsets<ONE>` (core) |
| `SIMDCSV`, `SequentialCSV` | `FieldBand` (core) |
| `HL7` | `FieldOffsets<ONE>` (core) |
| `SIMDHL7`, `SequentialHL7` | `Hl7FieldIndex` (own) |
| `SchemaJSON`, `SequentialSchemaJSON` | `SchemaJSONFieldIndex` (own) |
| `JSON`, `SequentialJSON` | `SIMDJSONFIF` (own) |
| `SystemNative` | `NativeFIF` (own) |

A custom FIF is therefore an **optimisation**, not part of the mandatory surface.
This is the single most important fact behind the "minimum" number below.

For an output formatter, the mandatory surface
(`nes-output-formatters/include/OutputFormatters/OutputFormatter.hpp`) is two pure
virtuals — `writeFormattedValue(...)` and `toString(...)` — plus the base
constructor, `validateAndFormat`, and the two registrar bodies. The three
performance hooks `supportsRunCoalescing()`, `tryWriteCoalescedRun(...)` and
`tryWriteRecordAllPassthrough(...)` all ship with "decline" defaults
(`OutputFormatter.hpp:91`, `:100-110`, `:124-133`) and are pure opt-in.

### Category legend (used in §4)

| code | meaning |
| --- | --- |
| **M** | mandatory interface: includes, descriptor config parameters + `validateAndFormat`, the `IndexerMetaData` / member block, the indexer-or-formatter class declaration, `indexRawBuffer` / `writeFormattedValue` plumbing, `operator<<`, registrar bodies, CMake glue |
| **K** | format-specific kernel: the actual scan (delimiter logic, escape handling, SIMD) or the actual serialisation dispatch |
| **O** | optional / optimisation: a second SIMD indexer arm, a custom FIF, output fast paths, `nautilus_inline` registration, `assume_clean_strings`-style characteristics |
| **B** | benchmark-only: explicitly-labelled ablation rungs (`Sequential*` indexers) and `TMP DIAGNOSTIC … REVERT before merge` counters |

---

## 2. Input formatters — per file

Every registered compiled input indexer in the tree: `CSV`, `SequentialCSV`,
`SIMDCSV` (in core, `nes-input-formatters`), and the plugins `HL7` + `SIMDHL7` +
`SequentialHL7`, `SchemaJSON` + `SequentialSchemaJSON`, `JSON` + `SequentialJSON`,
`SystemNative`. "XML" is not a formatter — it is a *config* of `SIMDHL7` (§6).

Columns: **raw / code / nolic**.

### CSV family — core library (`nes-input-formatters/`), not a plugin

| file | raw | code | nolic |
| --- | --- | --- | --- |
| `private/CSVInputFormatIndexer.hpp` | 178 | 117 | 164 |
| `src/CSVInputFormatIndexer.cpp` | 205 | 151 | 191 |
| **`CSV` subtotal** | **383** | **268** | **355** |
| `private/SIMDCSVInputFormatIndexer.hpp` | 64 | 29 | 50 |
| `src/SIMDCSVInputFormatIndexer.cpp` | 119 | 85 | 105 |
| `private/SIMDCSVKernel.hpp` | 84 | 32 | 70 |
| `src/SIMDCSVKernel.cpp` | 237 | 178 | 223 |
| `private/SIMDCSVScan.hpp` | 413 | 329 | 399 |
| **`SIMDCSV` subtotal** | **917** | **653** | **847** |
| `private/SequentialCSVInputFormatIndexer.hpp` | 64 | 29 | 50 |
| `src/SequentialCSVInputFormatIndexer.cpp` | 82 | 53 | 68 |
| **`SequentialCSV` subtotal (benchmark rung)** | **146** | **82** | **118** |
| CMake: `src/CMakeLists.txt:31-36` | 6 | 6 | 6 |

`SIMDCSV` and `SequentialCSV` reuse `CSV`'s `ConfigParametersCSVInputFormatIndexer`
and `CSVMetaData` verbatim — they add no descriptor code at all. That is why their
`.hpp`s are 64 lines.

### HL7 + SIMDHL7 + SequentialHL7 — `nes-plugins/InputFormatters/HL7InputFormatter/`

| file | raw | code | nolic | role |
| --- | --- | --- | --- | --- |
| `CMakeLists.txt` | 23 | 9 | 11 | glue for all 3 indexers |
| `HL7InputFormatIndexer.hpp` | 235 | 151 | 221 | config + metadata + scalar class |
| `HL7InputFormatIndexer.cpp` | 77 | 52 | 63 | `indexRawBuffer` + validate + registrars |
| `Hl7Scan.hpp` | 313 | 209 | 299 | scalar walk (62 raw) **+** SIMD band flatten (204 raw) |
| `Hl7SimdKernel.hpp` | 65 | 23 | 51 | SIMD kernel decl |
| `Hl7SimdKernel.cpp` | 234 | 196 | 220 | SSE2/AVX2/NEON/scalar 6-compare kernel |
| `Hl7FieldIndex.hpp` | 185 | 118 | 171 | custom single-band FIF |
| `SIMDHL7InputFormatIndexer.hpp` | 62 | 29 | 48 | SIMD indexer class |
| `SIMDHL7InputFormatIndexer.cpp` | 172 | 128 | 158 | SIMD indexer + registrars |
| `SequentialHL7InputFormatIndexer.hpp` | 63 | 31 | 49 | ablation rung |
| `SequentialHL7InputFormatIndexer.cpp` | 61 | 39 | 47 | ablation rung |
| **total** | **1490** | **985** | **1338** | |

### JSON (simdjson On-Demand) — `nes-plugins/InputFormatters/JSONInputFormatter/`

| file | raw | code | nolic | role |
| --- | --- | --- | --- | --- |
| `CMakeLists.txt` | 25 | 10 | 13 | |
| `SIMDJSONInputFormatIndexer.hpp` | 52 | 29 | 38 | indexer class |
| `SIMDJSONInputFormatIndexer.cpp` | 80 | 48 | 66 | `indexRawBuffer` + validate + registrars |
| `SIMDJSONFIF.hpp` | 450 | 348 | 436 | config + `SIMDJSONMetaData` + On-Demand FIF |
| `SIMDJSONFIF.cpp` | 213 | 182 | 199 | On-Demand value extraction |
| `SequentialSIMDJSONInputFormatIndexer.hpp` | 49 | 26 | 35 | ablation rung |
| `SequentialSIMDJSONInputFormatIndexer.cpp` | 72 | 44 | 58 | ablation rung |
| **total** | **941** | **687** | **845** | |

This plugin is structurally unusual: its config parameters *and* its
`IndexerMetaData` live inside `SIMDJSONFIF.hpp` rather than in the indexer header,
because simdjson's iterator *is* the field index. The FIF is therefore the kernel
here, not an optimisation.

### SchemaJSON (simdjson stage-1 strided gather) — `nes-plugins/InputFormatters/SchemaJSONInputFormatter/`

| file | raw | code | nolic | role |
| --- | --- | --- | --- | --- |
| `CMakeLists.txt` | 23 | 8 | 11 | |
| `SchemaJSONInputFormatIndexer.hpp` | 145 | 87 | 131 | config + metadata + class |
| `SchemaJSONInputFormatIndexer.cpp` | 90 | 58 | 76 | `indexRawBuffer` + validate + registrars |
| `SchemaJSONStage1.cpp` | 139 | 87 | 125 | simdjson stage-1 strided gather |
| `SchemaJSONFieldIndex.hpp` | 214 | 142 | 200 | custom single-band FIF (+8-15 % e2e, `348e7f6831`) |
| `SequentialSchemaJSONInputFormatIndexer.hpp` | 63 | 31 | 49 | ablation rung |
| `SequentialSchemaJSONInputFormatIndexer.cpp` | 54 | 32 | 40 | ablation rung |
| **total** | **728** | **445** | **632** | |

### SystemNative (packed binary) — `nes-plugins/InputFormatters/NativeInputFormatter/`

| file | raw | code | nolic | role |
| --- | --- | --- | --- | --- |
| `CMakeLists.txt` | 16 | 4 | 4 | |
| `NativeInputFormatIndexer.hpp` | 172 | 117 | 158 | config + metadata + class |
| `NativeInputFormatIndexer.cpp` | 107 | 68 | 93 | fixed-stride record walk + registrars |
| `NativeFIF.hpp` | 99 | 65 | 85 | packed-binary FIF |
| **total** | **394** | **254** | **340** | |

**Smallest complete input formatter plugin in the tree.** Four files, one indexer,
no SIMD arm, no ablation rung.

---

## 3. Output formatters — per file

Exactly three output formatters exist. (`OUTPUT_FORMAT=NATIVE` is **not** a
formatter: `nes-sinks/include/Sinks/FileSink.hpp:84-93` routes it to a raw
tuple-buffer dump that bypasses the `OutputFormatter` interface entirely. The
registrar grep `OutputFormatterGeneratedRegistrar::Register` returns exactly
CSV, JSON, HL7.)

| formatter | file | raw | code | nolic |
| --- | --- | --- | --- | --- |
| **CSV** (core, `nes-output-formatters/`) | `private/CSVOutputFormatter.hpp` | 115 | 76 | 101 |
| | `src/CSVOutputFormatter.cpp` | 474 | 401 | 460 |
| | CMake: `src/CMakeLists.txt:21-22` | 2 | 2 | 2 |
| | **total** | **591** | **479** | **563** |
| **JSON** (plugin) | `CMakeLists.txt` | 34 | 12 | 22 |
| | `JSONOutputFormatter.hpp` | 88 | 58 | 74 |
| | `JSONOutputFormatter.cpp` | 953 | 766 | 939 |
| | **total** | **1075** | **836** | **1035** |
| **HL7** (plugin) | `CMakeLists.txt` | 31 | 12 | 19 |
| | `HL7OutputFormatter.hpp` | 143 | 83 | 129 |
| | `HL7OutputFormatter.cpp` | 233 | 184 | 219 |
| | **total** | **407** | **279** | **367** |

---

## 4. The mandatory / kernel / optional / benchmark split

Produced by `python3 agg.py split.tsv`; the exact line ranges are in `split.tsv`.
"ship" = M+K+O, i.e. the plugin with its benchmark-only rungs removed.

| formatter | M raw | M code | K raw | K code | O raw | O code | B raw | B code | ship raw | ship code |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CSV (in) | 208 | 158 | 121 | 96 | 0 | 0 | 16 | 12 | 329 | 254 |
| SIMDCSV (in) | 106 | 75 | 718 | 562 | 0 | 0 | 20 | 16 | 824 | 637 |
| SequentialCSV (in) | 0 | 0 | 0 | 0 | 0 | 0 | 118 | 82 | 0 | 0 |
| HL7 (in, all 3 arms) | 259 | 204 | 74 | 59 | 854 | 646 | 100 | 72 | 1187 | 909 |
| SchemaJSON (in) | 211 | 148 | 125 | 87 | 200 | 142 | 96 | 68 | 536 | 377 |
| JSON (in) | 109 | 82 | 635 | 530 | 0 | 0 | 101 | 75 | 744 | 612 |
| SystemNative (in) | 185 | 140 | 154 | 114 | 0 | 0 | 0 | 0 | 339 | 254 |
| CSV (out) | 241 | 203 | 218 | 193 | 98 | 81 | 0 | 0 | 557 | 477 |
| JSON (out) | 200 | 169 | 570 | 490 | 263 | 177 | 0 | 0 | 1033 | 836 |
| HL7 (out) | 244 | 192 | 93 | 82 | 6 | 1 | 0 | 0 | 343 | 275 |

Reading notes:

* **HL7 (in)** is the whole directory, i.e. three registered indexers. Its `O`
  column (854/646) is the entire SIMD arm: the band flatten in `Hl7Scan.hpp`,
  `Hl7SimdKernel.*`, `Hl7FieldIndex.hpp`, `SIMDHL7InputFormatIndexer.*`. The
  minimum-viable HL7 formatter is `M + K` only.
* **SIMDCSV / JSON (in)** show `K ≫ M` because their kernels are, respectively, a
  hand-written SIMD scan (`SIMDCSVScan.hpp` + `SIMDCSVKernel.cpp`, 650 raw) and
  simdjson's On-Demand FIF (663 raw).
* **CSV (out)** `O` = `supportsRunCoalescing` + `tryWriteCoalescedRun` (98 raw).
  **JSON (out)** `O` = the unchecked-copy / width-table / bounded-store helpers
  (114 raw) + `tryWriteRecordAllPassthrough` (128 raw) + the `nautilus_inline`
  CMake block. Delete all of it and JSON output still works, ~17 % smaller.
* **B** is explicitly self-labelled in the source: the `Sequential*` CMake entry
  says *"Sequential variant (ablation baseline rung)"*, and the CSV diagnostic
  blocks say *"TMP DIAGNOSTIC … REVERT before merge"*.

---

## 5. Minimum to add a formatter

### Minimum new INPUT formatter — **334 lines (264 code), 3 new files + 4 CMake lines**

The exemplar is the scalar `HL7` indexer, taken alone (drop `SIMDHL7`,
`SequentialHL7`, `Hl7FieldIndex`, `Hl7SimdKernel`, and the SIMD half of
`Hl7Scan.hpp`). It is a *complete, registered, systest-gated* formatter that
reuses core's `FieldOffsets<ONE>` as its field index function.

| part | file : lines | raw | code |
| --- | --- | --- | --- |
| **M** includes | `HL7InputFormatIndexer.hpp:15-37` | 23 | 20 |
| **M** descriptor config parameters (6 params) | `HL7InputFormatIndexer.hpp:65-118` | 54 | 38 |
| **M** `IndexerMetaData` (`HL7MetaData`) | `HL7InputFormatIndexer.hpp:119-214` | 96 | 76 |
| **M** indexer class declaration | `HL7InputFormatIndexer.hpp:216-235` | 20 | 15 |
| **M** `.cpp`: includes (19) + `indexRawBuffer` (10) + `validateAndFormat` (15) + 2 registrars + `operator<<` (17) | `HL7InputFormatIndexer.cpp:15-77` | 63 | 52 |
| **M** CMake: `include` + 2 `add_plugin*` + 1 `activate_optional_plugin` | `CMakeLists.txt:13-15`, `nes-plugins/CMakeLists.txt:25` | 4 | 4 |
| **M subtotal** | | **260** | **205** |
| **K** scalar structural walk (`indexHl7ScalarInto` + arity throw) + its 12 includes | `Hl7Scan.hpp:15-26`, `:47-108` | 74 | 59 |
| **TOTAL (M+K)** | | **334** | **264** |

**Two independent corroborations of the same magnitude:**

* `SystemNative`, the smallest complete plugin as it actually ships:
  **339 raw / 254 code**, 4 files (`M` 185/140 + `K` 154/114).
* `CSV` scalar in core: **329 raw / 254 code** (`M` 208/158 + `K` 121/96), after
  removing its 16 lines of `TMP DIAGNOSTIC`.

So three unrelated formats land in a **329–339 line / 254–264 code-line** band.
Of that, ~60-78 % is mandatory interface (descriptor + metadata + class + registration
+ CMake) and only ~22-40 % is the format's own scan.

Within the mandatory block, ~30 lines are pure boilerplate that is *identical* in
every formatter: `getFieldNameAt` / `getFieldDataTypeAt` / `getNumberOfFields` /
`getNullValues` plus the `fieldNames` / `fieldDataTypes` / `nullValues` members
(`HL7InputFormatIndexer.hpp:184-214`).

### Minimum new OUTPUT formatter — **338 lines (275 code), 2 new files + 14 CMake lines**

The exemplar is `HL7OutputFormatter` **as it ships**: it overrides *none* of the
three optional fast paths, so it is already the minimum.

| part | file : lines | raw | code |
| --- | --- | --- | --- |
| **M** includes | `HL7OutputFormatter.hpp:15-35` | 21 | 18 |
| **M** class declaration (ctor, `writeFormattedValue`, `validateAndFormat`, `toString`, `operator<<`, 4 members) | `HL7OutputFormatter.hpp:54-87` | 34 | 22 |
| **M** descriptor config parameters (6 params) + `FMT_OSTREAM` | `HL7OutputFormatter.hpp:89-143` | 55 | 41 |
| **M** `.cpp` includes | `HL7OutputFormatter.cpp:15-46` | 32 | 30 |
| **M** constructor (precomputes the constant HL7 glue per field) | `HL7OutputFormatter.cpp:143-163` | 21 | 18 |
| **M** `writeFormattedValue` | `HL7OutputFormatter.cpp:165-200` | 36 | 27 |
| **M** `validateAndFormat` + `operator<<` + 2 registrars | `HL7OutputFormatter.cpp:202-233` | 32 | 25 |
| **M** CMake (`include`, 2 × `add_plugin_as_library`, 2 × `target_include_directories`, 1 × `activate_optional_plugin`) | `CMakeLists.txt:13-25`, `nes-plugins/CMakeLists.txt:27` | 14 | 12 |
| **M subtotal** | | **245** | **193** |
| **K** `writeRawBytes` + `writeValue` (lazy-varsized rope walk, lazy numeric, materialised varsized, computed-value fallback) | `HL7OutputFormatter.cpp:49-141` | 93 | 82 |
| **TOTAL (M+K)** | | **338** | **275** |
| *(O)* `nautilus_inline(...)` registration so the raw-copy helper splices into the JIT | `CMakeLists.txt:26-31` | 6 | 1 |
| **as shipped** | | **344** | **276** |

Comparison: the CSV output formatter is 557 raw / 477 code with its coalescing
fast path (459/396 without it); the JSON output formatter is 1033 raw / 836 code,
of which 263/177 is the optional whole-record passthrough machinery.

---

## 6. Git ground truth — what "adding HL7" actually cost

⚠️ **Hash note.** The three commits named in earlier notes (`e66ce11d95`,
`e20689f0ab`, `9c10cbd4b3`) were rewritten by a later autosquash. The *current*
branch hashes with byte-identical content and messages are:

| then | now | subject |
| --- | --- | --- |
| `e66ce11d95` | **`bd619454d9`** | `feat(output-formatters): HL7 MLLP output formatter plugin` |
| `e20689f0ab` | **`f804ba27d3`** | `fix(input-formatters): parse ALL records of a reassembled spanning tuple` |
| `9c10cbd4b3` | **`e8e34d85cb`** | `feat(input-formatters): HL7 + SIMDHL7 MLLP input indexer plugin` |

(The old hashes are still reachable in the object store, which is how the
correspondence was verified. The old blobs differ from the new ones by two lines
in `HL7InputFormatIndexer.cpp` / `SIMDHL7InputFormatIndexer.cpp` — a preamble-script
change folded in by the rebase. Cite the **new** hashes.)

Commands:

```bash
git show --numstat --format='' bd619454d9   # HL7 output formatter
git show --numstat --format='' f804ba27d3   # the one core fix HL7 needed
git show --numstat --format='' e8e34d85cb   # HL7 + SIMDHL7 input indexers
git show --numstat --format='' cbf156f20c   # XML as an HL7 config
```

### HL7 **output** formatter — `bd619454d9` (518 insertions, 2 deletions)

| bucket | lines | files |
| --- | --- | --- |
| **plugin code** | **+376** | `HL7OutputFormatter.cpp` +233, `HL7OutputFormatter.hpp` +143 |
| **plugin CMake** | **+32** | plugin `CMakeLists.txt` +31, `nes-plugins/CMakeLists.txt` +1 |
| **core changes** | **+35** | `nes-common/src/Util/Strings.cpp` +35 — `unescapeSpecialCharacters` gains `\xNN`, needed because the SQL parser passes delimiter configs through verbatim |
| **test-harness changes** | **+14 / −2** | `ChecksumSink.hpp` +6/−1 (respect an explicit `OUTPUT_FORMAT`), `SystestBinder.cpp` +8/−1 (inject `quote_strings` only for CSV checksums) |
| **tests** | **+61** | `HL7Output.test` +48 (systest), `StringUtilTest.cpp` +13 (unit) |

### HL7 + SIMDHL7 **input** indexers — `e8e34d85cb` (2044 insertions, 13 deletions)

| bucket | lines | files |
| --- | --- | --- |
| **plugin code** | **+1292** | `HL7InputFormatIndexer.cpp` +77, `.hpp` +235, `Hl7FieldIndex.hpp` +183, `Hl7Scan.hpp` +282, `Hl7SimdKernel.cpp` +234, `.hpp` +65, `SIMDHL7InputFormatIndexer.cpp` +155, `.hpp` +61 |
| **plugin CMake** | **+20** | plugin `CMakeLists.txt` +19, `nes-plugins/CMakeLists.txt` +1 |
| **core changes** | **0** | — no production file outside the plugin directory was touched |
| **unit tests** | **+416 / −9** | `HL7SimdScanTest.cpp` +326 (differential scalar↔SIMD + 3.5 k fuzz cases), `SmallFilesTest.cpp` +87/−9, `tests/UnitTests/CMakeLists.txt` +3 |
| **test utils** | **+5 / −1** | `tests/Util/FileUtil.hpp` (golden loader handles zero-length varsized) |
| **systests + fixtures** | **+307** | `HL7Input.test` +66, `HL7InputSpanning.test` +129, `HL7RoundTrip.test` +25, `HL7Errors.test` +14, `generate_fixtures.py` +69, 3 fixture files +3 |
| **tooling** | **+4 / −3** | `scripts/check_preamble.py`, `scripts/format.sh` |

### The one core change HL7 needed — `f804ba27d3` (24 insertions, 6 deletions)

A single file, `nes-input-formatters/include/InputFormatters/InputFormatter.hpp`:
`parseLeadingRecord` / `parseTrailingRecord` read exactly record 0 of a reassembled
spanning tuple, which silently dropped records when a **multi-byte** tuple delimiter
split across raw buffers and reunited inside the assembly. A latent bug for any
multi-byte-delimiter format; loop-once-equivalent for every single-byte one.

> **Citable sentence.** *Adding the HL7 input format took 1,312 lines of plugin
> code (1,292 C++ + 20 CMake) and 24 changed lines in one shared header — a
> pre-existing multi-byte-delimiter bug in the spanning-tuple reassembly — with no
> other change to the engine. The HL7 output format took 408 lines of plugin code
> plus a 35-line extension of a shared string utility.*

### XML as a *config* of the HL7 indexer — `cbf156f20c` (758 insertions, 131 deletions)

| bucket | lines | files |
| --- | --- | --- |
| **plugin code** | **+108 / −59** (net +49) | `Hl7Scan.hpp` +80/−49, `SIMDHL7InputFormatIndexer.cpp` +24/−7, `.hpp` +4/−3 |
| **core changes** | **0** | — |
| **new indexer** | **0** | XML is a 6-line YAML stanza: `type: HL7`, `message_delimiter: "\n"`, `segment_delimiter: "<"`, `field_delimiter: ">"`, `component_delimiter: ""`, `subcomponent_delimiter: ""` |
| **tests** | **+261 / −72** | `HL7SimdScanTest.cpp` +180/−71, `SmallFilesTest.cpp` +53/−1, `TwoIntegerColumnsXML.xml` +28 |
| **systests + fixtures** | **+389** | `XMLInput.test` +65, `XMLInputSpanning.test` +131, `XMLErrors.test` +40, `generate_fixtures.py` +85, 4 fixture files +68 |

The +108 is a kernel-mode relaxation (a 1-byte-delimiter path for the SIMD block
kernel). The **scalar** `HL7` indexer needed **zero** lines: packed record-per-line
XML indexes as "HL7 with structural class `{<, >}`" out of the box.

---

## 7. What a new formatter does **not** implement

This is the contrast the paper needs. Columns: **raw / code / nolic**.

### Input side — `nes-input-formatters/` (56 production files: 8377 / 5895 / 7603)

| shared concern | files | raw | code | nolic |
| --- | --- | --- | --- | --- |
| **Scan driver** — the JIT'd record loop: projections, lazy-value construction, leading/trailing spanning-record assembly, per-field dispatch into the FIF | `include/InputFormatters/InputFormatter.hpp` (718/551/705), `InputFormatterProvider/InputFormatterTupleBufferRef.{hpp,cpp}`, `InputFormatterTupleBufferRefProvider.{hpp,cpp}`, `InputFormatters/RawTupleBuffer.hpp` | 1158 | 821 | 1076 |
| **Spanning-tuple reassembly** — `SequenceShredder` + `FragmentSequenceShredder` + `LockingSequenceShredder` and their 4 spanning-buffer/state pairs. Lock-free multi-buffer reassembly across worker threads; a formatter only says *what its tuple delimiter is* | 18 files under `include/InputFormatters/` + `private/` + `src/` | 2913 | 2005 | 2661 |
| **Value parsing** — `RawValueParser` + the `InputParser` plugin registry + `DefaultInputParsers` (fast integer/float/bool/char/varsized codecs, lazy representations). Parsing is **not** part of a formatter | `RawValueParser.{hpp,cpp}`, `InputParser.hpp`, `InputParsers/DefaultInputParsers.{hpp,cpp}` | 1385 | 1129 | 1316 |
| **Reusable field index functions** + the CRTP bases + the concepts a formatter is checked against | `FieldOffsets.hpp`, `FieldBand.hpp`, `FieldIndexFunction.hpp`, `InputFormatIndexer.hpp`, `Concepts.hpp` | 729 | 493 | 659 |
| **Descriptor, validation, registries, registrar templates** | `InputFormatterDescriptor.{hpp,cpp}`, `InputFormatterValidationProvider.{hpp,cpp}`, `registry/include/*.hpp` (3), `registry/templates/*.inc.in` (3) | 636 | 388 | 497 |

### Output side — `nes-output-formatters/` (23 files: 2285 / 1594 / 1971)

| shared concern | files | raw | code | nolic |
| --- | --- | --- | --- | --- |
| **Record-emit driver** — walks the output schema, detects all-passthrough records, offers coalesced runs, handles child-buffer spill; it *calls* the formatter | `nes-nautilus/.../OutputFormatterBufferRef.{hpp,cpp}` | 278 | 200 | 251 |
| **Formatter base + write utilities** — `writeBytesToBuffer`, `writeConstantBytes`, `formatAndWriteVal`, child-buffer allocation, the three optional-hook defaults | `OutputFormatter.{hpp,cpp}`, `OutputFormatterUtil.hpp` | 366 | 230 | 324 |
| **Value serialisation** — the `OutputParser` plugin registry + `DefaultOutputParsers` (Eisel-Lemire-class float, ZMIJ integer, bool/char writers) | `OutputParser.hpp`, `OutputParsers/DefaultOutputParsers.{hpp,cpp}` | 714 | 552 | 672 |
| **Descriptor, provider, validation, registries, registrar templates** | `OutputFormatterDescriptor.{hpp,cpp}`, `OutputFormatterProvider.{hpp,cpp}`, `OutputFormatterValidationProvider.{hpp,cpp}`, `registry/include/*.hpp` (3), `registry/templates/*.inc.in` (3) | 538 | 300 | 372 |

**Also free:** threading and task scheduling (`nes-query-engine`), buffer pooling,
the nautilus JIT and its inlining pass, the SQL-side plumbing that turns an
`input_formatter:` / `output_format:` config stanza into a bound descriptor, and
the entire registrar dispatch generation.

So: ~**6,800 lines** of shared input machinery and ~**1,900 lines** of shared output
machinery are reused verbatim by a **~335-line** new formatter — a roughly **20:1**
reuse ratio on the input side.

### A note on the uncompiled twins

`nes-input-formatters-uncompiled/` (49 files, 5355 / 3414 / 4677) carries
interpreted twins of five formats (`UncompiledCSV`, `UncompiledJSON`,
`SequentialUncompiled{CSV,OldCSV,JSON,SchemaJSON,HL7}`). These exist **only** as
ablation baselines for the compilation-benefit ladder; they are a parallel module
with its own registries, FIFs and shredder, not a cost a formatter author pays.
For reference, the HL7 twin is 392 / 260 / 350 across 3 files. **The paper's
"effort to add a formatter" statement is about the compiled plugin surface and
should not include this module.**

---

## 8. Paper-safe statement

> Adding a new input format to NebulaStream requires implementing one indexer
> class: a configuration descriptor, a metadata accessor, and a buffer-indexing
> routine, registered through two generated registrars. Across three unrelated
> formats this is **329–339 lines** (254–264 non-blank, non-comment), of which only
> **74–154 lines** are the format's own scanning logic and the remainder is the fixed
> interface; a new output format is **338 lines** (275 non-comment), of which **93** are
> the format's serialisation. Concretely, adding HL7 took **1,312 lines of plugin code**
> — including an optional hand-written SIMD kernel and a custom field-index
> function that together account for 65 % of it — plus **24 changed lines** in one
> shared header, and no other engine change; supporting packed XML afterwards took
> **zero** new indexer code (a six-line formatter configuration) plus a **108-line**
> relaxation of the existing SIMD kernel. Value parsing, lazy value
> representations, cross-buffer tuple reassembly, threading, buffer management and
> the output fast paths are shared machinery — ~6,800 and ~1,900 lines on the input
> and output sides respectively — that a new formatter inherits unchanged.

---

## 9. Caveats

1. **Uncommitted overlay.** The working tree carries a benchmark overlay on top of
   `b5d757c9f6`. In the formatter trees it is **+160 / −43** lines across 12
   production files (plus +92/−19 in `tests/Benchmark/`), reproducible with
   `git diff --numstat -- nes-input-formatters nes-output-formatters nes-plugins/{Input,Output}Formatters`.
   It is almost entirely two ablation knobs: `InputFormatterDescriptor::EAGER_PARSE`
   (+12, and the `eagerParse` argument threaded through `readSpanningRecord` → +3/+4
   lines in each of the four custom FIFs) and
   `OutputFormatterDescriptor::DISABLE_PASSTHROUGH` (+14, +5 in `OutputFormatter.hpp`,
   +28/−5 in `JSONOutputFormatter.cpp`). Both are self-labelled
   *"Hoisting-study lever"*. **All tables above are measured on the working tree**,
   i.e. they include this overlay; subtract ~11 lines from `HL7-in`/`SchemaJSON-in`/
   `SIMDJSON-in`/`Native-in` custom-FIF rows and ~28 from `JSON-out` for a
   committed-state number. The §5 minimum numbers are unaffected (the overlay
   touches no file in the minimum slice).
2. **Benchmark-only code is marked, not silently dropped.** The `B` column in §4
   isolates it: `Sequential*` ablation rungs (CMake comment: *"Sequential variant
   (ablation baseline rung)"*) and `TMP DIAGNOSTIC … REVERT before merge` index-CPU
   counters in `CSVInputFormatIndexer.cpp:36-51` and
   `SIMDCSVInputFormatIndexer.cpp:38-57` (introduced in `7bd4fc7cf6`). Quote the
   `ship` columns, not `ALL`, for any "size of the formatter" claim.
3. **CMake registrar generation.** A plugin's hand-written CMake is 3-13 lines; the
   dispatch tables that bind `NAME` → registrar are generated at configure time by
   `cmake/PluginRegistrationUtil.cmake` (128/78) from `*/registry/templates/*.inc.in`.
   Those generated files are excluded from every count. A new formatter writes
   **zero** registry lines.
4. **Line attribution is judgement in the grey zone.** `split.tsv` records every
   range so the judgement is auditable. The main debatable calls: (a) the HL7
   `IndexerMetaData` constructor's delimiter `PRECONDITION`s are counted as **M**
   even though their content is format-specific; (b) `assume_clean_strings` /
   `getVarSizedCharacteristics` (≈13 lines in HL7) is an output-passthrough
   optimisation counted as **M** because it sits inside the config/metadata block;
   (c) in `JSONOutputFormatter.cpp` the boundary between JSON escaping (**K**) and
   fast-path store machinery (**O**) was drawn at line 419.
5. **`code` vs `nolic`.** `nolic` is the honest "lines typed" number and is what
   matches the earlier effort table; `code` (= `cloc`) is the conservative one.
   Pick one and state which. The §8 statement quotes `nolic`-equivalent raw-minus-preamble
   figures with the `code` figure in parentheses.
6. **Git insertion counts include the license preamble** (12-14 lines per file).
   §6's +1292 for HL7 plugin C++ becomes **+1180** excluding preambles (8 files × 14).
   The earlier effort table used raw git insertions; §6 keeps that convention for
   comparability and flags it here.

---

## 10. Consistency with the earlier XML effort table

The Aug-01 handover (`2_engine_to_e2e/SESSION_HANDOVER_2026-08-01.md:95-96`) and
`XML_INDEXER_PLAN.md:57-59` state:

> *Effort-table row: SchemaJSON ≈590 LOC, HL7 ≈1300, **XML = 0 (scalar, config) + 107 (SIMD 1-byte mode)***

Re-derived today:

| earlier claim | measured now | verdict |
| --- | --- | --- |
| SchemaJSON ≈ 590 | **605 raw** for the 5 plugin files as of `cbf156f20c` (the state the handover described): 19 + 212 + 90 + 145 + 139 | ✅ consistent (≈590 was a round number; 605 exact). Today's tree is **728 raw** — the +123 is the `SequentialSchemaJSON` ablation rung added later in `66ab110f30`. |
| HL7 ≈ 1300 | **1311 raw** git insertions for the 9 plugin files in `e8e34d85cb` | ✅ exact. Today's tree is **1490 raw** — the +179 is the `SequentialHL7` rung (124) + the XML kernel relaxation (net +49) + preamble-script churn. |
| XML = 0 + 107 | **0** new indexer files; **+108 / −59** insertions in 3 existing plugin files (`Hl7Scan.hpp` +80/−49, `SIMDHL7…cpp` +24/−7, `SIMDHL7….hpp` +4/−3) | ✅ consistent (108 vs 107 — a one-line difference, presumably the handover was written against a slightly earlier state of the diff). **Prefer 108 insertions / net +49** going forward, and say which. |

**Two things to flag before reusing the earlier table:**

1. **Metric drift.** The earlier numbers are *raw git insertions*, which include the
   12-14-line Apache preamble per file. On the same footing HL7 input is 1311; on a
   preamble-free footing it is 1187, and on a `cloc`-code footing 871. If the paper
   puts SchemaJSON, HL7 and XML in one table, all three must use the same footing.
   Recommended: raw-minus-preamble (`nolic`), i.e. SchemaJSON 537, HL7 1187, XML +108/−59.
2. **The table conflates "a formatter" with "a formatter plus its optimisations".**
   HL7's ≈1300 is 65 % optional: a hand-written SIMD kernel (520 raw), a custom
   single-band FIF (183), and a second registered indexer (216). The *format* cost
   334 lines. If the paper's claim is "adding a format is cheap", the ≈1300 number
   argues against it; add a column separating `M+K` from `O`, or state 334 for HL7
   and present the SIMD arm as a separate, optional performance investment. This is
   the one substantive inconsistency found, and it is a framing problem rather than
   a counting error.
3. **No output-formatter row exists in the earlier table.** HL7 output
   (408 raw git insertions / 367 nolic / 279 code, and the minimum at 338) should be
   added so the generality claim covers both directions.

---

## 11. Reproduction

```bash
cd /home/user/work/nebulastream-public
git rev-parse HEAD            # b5d757c9f6…  (plus the overlay in `git status`)
S=~/Notes/nebulastream/benchmark/formatter_loc_2026-10-07_scripts   # loc.py range.py agg.py split.tsv

# §2 / §3 per-file tables
for d in nes-plugins/InputFormatters/*/ nes-plugins/OutputFormatters/*/; do
    echo "=== $d"; python3 $S/loc.py $(find $d -type f | sort); done
python3 $S/loc.py nes-input-formatters/private/CSVInputFormatIndexer.hpp \
                  nes-input-formatters/src/CSVInputFormatIndexer.cpp      # … etc
python3 $S/loc.py nes-output-formatters/private/CSVOutputFormatter.hpp \
                  nes-output-formatters/src/CSVOutputFormatter.cpp

# cross-check against cloc
cloc nes-plugins/InputFormatters/HL7InputFormatter --quiet

# §4 category split (and its full line-range audit trail)
python3 $S/agg.py $S/split.tsv
python3 $S/agg.py $S/split.tsv --detail

# §5 minimum slices -- the ranges MUST match the itemised tables exactly
# (a combined range such as hpp:65-235 picks up the blank separator lines and
#  reports 335 instead of 334)
H=nes-plugins/InputFormatters/HL7InputFormatter
python3 $S/range.py "min input = 334 raw / 264 code" \
  $H/HL7InputFormatIndexer.hpp:15-37  $H/HL7InputFormatIndexer.hpp:65-118 \
  $H/HL7InputFormatIndexer.hpp:119-214 $H/HL7InputFormatIndexer.hpp:216-235 \
  $H/HL7InputFormatIndexer.cpp:15-77  $H/CMakeLists.txt:13-15 \
  nes-plugins/CMakeLists.txt:25-25 \
  $H/Hl7Scan.hpp:15-26 $H/Hl7Scan.hpp:47-108

O=nes-plugins/OutputFormatters/HL7OutputFormatter
python3 $S/range.py "min output = 338 raw / 275 code" \
  $O/HL7OutputFormatter.hpp:15-35 $O/HL7OutputFormatter.hpp:54-87 \
  $O/HL7OutputFormatter.hpp:89-143 $O/HL7OutputFormatter.cpp:15-46 \
  $O/HL7OutputFormatter.cpp:49-141 $O/HL7OutputFormatter.cpp:143-163 \
  $O/HL7OutputFormatter.cpp:165-200 $O/HL7OutputFormatter.cpp:202-233 \
  $O/CMakeLists.txt:13-25 nes-plugins/CMakeLists.txt:27-27

# §6 git ground truth
git show --numstat --format='' bd619454d9 f804ba27d3 e8e34d85cb cbf156f20c

# §9 overlay size
git diff --numstat -- nes-input-formatters nes-output-formatters \
    nes-plugins/InputFormatters nes-plugins/OutputFormatters

# §10 historical states
git ls-tree --name-only cbf156f20c nes-plugins/InputFormatters/SchemaJSONInputFormatter/
git show cbf156f20c:<path>   # pipe each blob through loc.py
```
