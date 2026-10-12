#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Reproduce the formatter LOC study (E13, FORMATTER_LOC_2026-10-07.md) on an engine checkout.
#   NES_SRC  engine source tree (default ~/work/nebulastream-public); use the tag piparse-artifact-v1 for the paper state
# Static analysis only, no build. Runtime: seconds. Writes out/{per_file_tables.txt,split_table.txt,split_detail.txt,
# min_slices.txt,git_truth.txt,headline.txt}.
set -euo pipefail
NES_SRC=${NES_SRC:-$HOME/work/nebulastream-public}
HERE=$(cd "$(dirname "$0")" && pwd); S=$HERE/scripts; OUT=$HERE/out; mkdir -p "$OUT"
cd "$NES_SRC"
echo "engine tree: $NES_SRC @ $(git rev-parse --short HEAD) ($(git describe --tags --always 2>/dev/null))" | tee "$OUT/headline.txt"

{ # §2 / §3 per-file tables (raw / code / nolic)
  for d in nes-plugins/InputFormatters/*/ nes-plugins/OutputFormatters/*/; do echo "=== $d"; python3 "$S/loc.py" $(find "$d" -type f | sort); done
  echo "=== CSV (in, core)"; python3 "$S/loc.py" nes-input-formatters/private/CSVInputFormatIndexer.hpp nes-input-formatters/src/CSVInputFormatIndexer.cpp
  echo "=== SIMDCSV (in, core)"; python3 "$S/loc.py" nes-input-formatters/private/SIMDCSVInputFormatIndexer.hpp nes-input-formatters/src/SIMDCSVInputFormatIndexer.cpp nes-input-formatters/private/SIMDCSVKernel.hpp nes-input-formatters/src/SIMDCSVKernel.cpp nes-input-formatters/private/SIMDCSVScan.hpp
  echo "=== SequentialCSV (in, core, benchmark rung)"; python3 "$S/loc.py" nes-input-formatters/private/SequentialCSVInputFormatIndexer.hpp nes-input-formatters/src/SequentialCSVInputFormatIndexer.cpp
  echo "=== CSV (out, core)  [+ CMake src/CMakeLists.txt:21-22 = 2/2/2 in the doc's 591/479/563]"; python3 "$S/loc.py" nes-output-formatters/private/CSVOutputFormatter.hpp nes-output-formatters/src/CSVOutputFormatter.cpp
} > "$OUT/per_file_tables.txt"

# §4 mandatory / kernel / optional / benchmark split (split.tsv paths are repo-relative -> run from $NES_SRC)
python3 "$S/agg.py" "$S/split.tsv" > "$OUT/split_table.txt"
python3 "$S/agg.py" "$S/split.tsv" --detail > "$OUT/split_detail.txt"

# §5 minimum slices (the ranges MUST match the itemised tables; a merged range picks up blank separator lines)
H=nes-plugins/InputFormatters/HL7InputFormatter; O=nes-plugins/OutputFormatters/HL7OutputFormatter
{
python3 "$S/range.py" "min input = 334 raw / 264 code" \
  $H/HL7InputFormatIndexer.hpp:15-37 $H/HL7InputFormatIndexer.hpp:65-118 $H/HL7InputFormatIndexer.hpp:119-214 $H/HL7InputFormatIndexer.hpp:216-235 \
  $H/HL7InputFormatIndexer.cpp:15-77 $H/CMakeLists.txt:13-15 nes-plugins/CMakeLists.txt:25-25 $H/Hl7Scan.hpp:15-26 $H/Hl7Scan.hpp:47-108
python3 "$S/range.py" "min output = 338 raw / 275 code" \
  $O/HL7OutputFormatter.hpp:15-35 $O/HL7OutputFormatter.hpp:54-87 $O/HL7OutputFormatter.hpp:89-143 $O/HL7OutputFormatter.cpp:15-46 \
  $O/HL7OutputFormatter.cpp:49-141 $O/HL7OutputFormatter.cpp:143-163 $O/HL7OutputFormatter.cpp:165-200 $O/HL7OutputFormatter.cpp:202-233 \
  $O/CMakeLists.txt:13-25 nes-plugins/CMakeLists.txt:27-27
} > "$OUT/min_slices.txt"

# §6 git ground truth (plugin insertions for HL7 in/out, the one core fix, XML-as-config)
{ for c in bd619454d9 f804ba27d3 e8e34d85cb cbf156f20c; do echo "=== $c $(git log -1 --format=%s $c)"; git show --numstat --format='' "$c"; done; } > "$OUT/git_truth.txt" 2>&1 || true
# HL7 input plugin C++ insertions (the +1292) and core changes (0) from e8e34d85cb
git show --numstat --format='' e8e34d85cb | awk '/HL7InputFormatter\/.*\.(hpp|cpp)$/ {s+=$1} END {print "HL7 input plugin C++ insertions (e8e34d85cb):", s, "(doc: 1292)"}' | tee -a "$OUT/headline.txt"
git show --numstat --format='' e8e34d85cb | awk '!/nes-plugins\// && !/tests\// && !/scripts\// && !/testdata\// {s+=$1; print "  core change:", $0} END {print "HL7 input: core production insertions outside the plugin:", s+0, "(doc: 0)"}' | tee -a "$OUT/headline.txt"
git show --numstat --format='' bd619454d9 | awk '/HL7OutputFormatter\/.*\.(hpp|cpp)$/ {s+=$1} END {print "HL7 output plugin C++ insertions (bd619454d9):", s, "(doc: 376)"}' | tee -a "$OUT/headline.txt"
git show --numstat --format='' cbf156f20c | awk '/HL7InputFormatter\/.*\.(hpp|cpp)$/ {s+=$1; d+=$2} END {print "XML-as-config plugin insertions/deletions (cbf156f20c):", s, d, "(doc: +108 / -59)"}' | tee -a "$OUT/headline.txt"
grep -c "" "$OUT/split_table.txt" >/dev/null
{ echo "--- min slices"; cat "$OUT/min_slices.txt" | grep "=="; echo "--- split (ship raw/code = M+K+O)"; cat "$OUT/split_table.txt"; } | tee -a "$OUT/headline.txt"
echo "cloc cross-check (if installed):"; command -v cloc >/dev/null && cloc nes-plugins/InputFormatters/HL7InputFormatter --quiet | grep -E "^SUM" || echo "  cloc not installed"
