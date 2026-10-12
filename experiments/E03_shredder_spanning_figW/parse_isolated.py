# SPDX-License-Identifier: Apache-2.0
"""Parse the isolated formatter-scaling-benchmark span-sweep log (4K + 8K buffer) into tidy rows.
Emits: harness,buffer_kb,row_kb,span_buffers,mode,threads,gbps_median,gbps_max
Log markers: '########## BUF <b>k SPAN <r>k ##########' then per-mode 'threads | GB/s | ... min..max'.
span_buffers = round(row_bytes / buffer_bytes)."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/span_figure/scripts/parse_isolated.py) ----
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
import re
import sys

LOG = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "data/logs/isolated_span_sweep_4k8k.log")
OUT = sys.argv[2] if len(sys.argv) > 2 else str(HERE / "out/isolated_tidy.csv")

ROW_KB = {"4k": 4, "16k": 16, "40k": 40, "80k": 80, "160k": 160, "320k": 320, "640k": 640}

re_hdr = re.compile(r"#+ BUF (\w+) SPAN (\w+) #+")
re_mode = re.compile(r"sequence_shredder_mode = (LOCK_FREE|LOCKING)")
re_row = re.compile(r"^\s*(\d+)\s*\|\s*([\d.]+)\s*\|\s*[\d.]+x\s*\|\s*min\.\.max\s*([\d.]+)\.\.\s*([\d.]+)")

rows = []
buf_kb = row_kb = mode = None
for line in open(LOG):
    m = re_hdr.search(line)
    if m:
        buf_kb = int(m.group(1).rstrip("k")); row_kb = int(m.group(2).rstrip("k")); continue
    m = re_mode.search(line)
    if m:
        mode = m.group(1); continue
    m = re_row.match(line)
    if m and row_kb and mode:
        threads, med, mn, mx = m.groups()
        span = round(row_kb * 1000 / (buf_kb * 1024))
        rows.append(dict(harness="isolated", buffer_kb=buf_kb, row_kb=row_kb, span_buffers=span,
                         mode=mode, threads=int(threads), gbps_median=float(med), gbps_max=float(mx)))

with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["harness", "buffer_kb", "row_kb", "span_buffers", "mode", "threads", "gbps_median", "gbps_max"])
    w.writeheader(); w.writerows(rows)
print(f"wrote {OUT} ({len(rows)} rows)")
for bk in sorted(set(r["buffer_kb"] for r in rows)):
    print(f"--- W24 buffer={bk}KB (median):  row | LF | LK | LF/LK ---")
    byk = {(r["row_kb"], r["mode"]): r for r in rows if r["threads"] == 24 and r["buffer_kb"] == bk}
    for rk in sorted(ROW_KB.values()):
        lf, lk = byk.get((rk, "LOCK_FREE")), byk.get((rk, "LOCKING"))
        if lf and lk:
            print(f"  {rk:>4}KB | {lf['gbps_median']:5.2f} | {lk['gbps_median']:5.2f} | {lf['gbps_median']/lk['gbps_median']:.2f}x")
