# SPDX-License-Identifier: Apache-2.0
"""Merge isolated_tidy.csv (reps=15 steady) + e2e_tidy.csv into span_tidy.csv (both buffer sizes).
Isolated gbps := gbps_median; e2e gbps := throughput_mbps/1000. Both W24."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/span_figure/scripts/merge_span.py) ----
## Every path is resolved relative to this file. The pbench results DB defaults to
## <artifact>/results/tr/piparse_bench.duckdb; override with `--db PATH` or env PBENCH_DB. Outputs go to ./out/.
import os as _os, sys as _sys
from pathlib import Path as _Path
HERE = _Path(__file__).resolve().parent
ART_DB = _os.environ.get("PBENCH_DB") or str(HERE.parent.parent / "results" / "tr" / "piparse_bench.duckdb")
if "--db" in _sys.argv:
    _i = _sys.argv.index("--db"); ART_DB = _sys.argv[_i + 1]; del _sys.argv[_i:_i + 2]
(HERE / "out").mkdir(exist_ok=True)
## ---------------------------------------------------------------------------------------------------------
import csv

## artifact: merge the freshly parsed tidy files in out/ (fall back to the shipped data/ copies)
import sys
ISO = sys.argv[1] if len(sys.argv) > 1 else str((HERE / "out/isolated_tidy.csv") if (HERE / "out/isolated_tidy.csv").exists() else HERE / "data/isolated_tidy.csv")
E2E = sys.argv[2] if len(sys.argv) > 2 else str((HERE / "out/e2e_tidy.csv") if (HERE / "out/e2e_tidy.csv").exists() else HERE / "data/e2e_tidy.csv")
OUT = sys.argv[3] if len(sys.argv) > 3 else str(HERE / "out/span_tidy.csv")
ISO_METRIC = "gbps_median"  # or gbps_max for the ramp-free ceiling

out = []
for r in csv.DictReader(open(ISO)):
    if int(r["threads"]) != 24:
        continue
    out.append(dict(harness="isolated", buffer_kb=int(r["buffer_kb"]), row_kb=int(r["row_kb"]),
                    span_buffers=int(r["span_buffers"]), mode=r["mode"], threads=24, gbps=float(r[ISO_METRIC])))
for r in csv.DictReader(open(E2E)):
    out.append(dict(harness="e2e", buffer_kb=int(r["buffer_kb"]), row_kb=int(r["row_kb"]),
                    span_buffers=int(r["span_buffers"]), mode=r["mode"], threads=24, gbps=float(r["gbps"])))

with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["harness", "buffer_kb", "row_kb", "span_buffers", "mode", "threads", "gbps"])
    w.writeheader(); w.writerows(out)
print(f"wrote {OUT} ({len(out)} rows)")
