# SPDX-License-Identifier: Apache-2.0
"""Pull the e2e span-sweep results (row size x buffer size x mode) from the pbench DuckDB aggregated view.
Emits: harness,buffer_kb,row_kb,span_buffers,mode,threads,gbps,throughput_mbps,mrows_s,p50_ms,p99_ms,
       p999_ms,processing_time_s,reps  (gbps = throughput_mbps/1000)."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/span_figure/scripts/parse_e2e.py) ----
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
import sys

import duckdb

## artifact: the DB comes from --db / PBENCH_DB (see header); the only positional arg is the output CSV
DB = ART_DB
OUT = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "out/e2e_tidy.csv")

ROW = {"row_004k": 4, "row_016k": 16, "row_040k": 40, "row_080k": 80,
       "row_160k": 160, "row_320k": 320, "row_640k": 640}
MODE = {"lock_free": "LOCK_FREE", "locking": "LOCKING"}

con = duckdb.connect(DB, read_only=True)
q = """
SELECT variant, series, x_value, throughput_mbps, processing_time_s, throughput_mrows_s,
       p50_latency_us, p99_latency_us, p999_latency_us, num_repetitions
FROM aggregated WHERE experiment = 'shredder_span_sweep'
ORDER BY variant, x_value, series
"""
rows = []
for var, ser, xv, mbps, ptime, mrows, p50, p99, p999, nrep in con.execute(q).fetchall():
    if var not in ROW:
        continue
    row_kb = ROW[var]; buf_kb = int(round(int(xv) / 1024))
    span = round(row_kb * 1000 / (int(xv)))
    rows.append(dict(harness="e2e", buffer_kb=buf_kb, row_kb=row_kb, span_buffers=span,
                     mode=MODE.get(ser, ser), threads=24, gbps=round(mbps / 1000, 4),
                     throughput_mbps=round(mbps, 1), mrows_s=round(mrows, 3) if mrows else "",
                     p50_ms=round(p50 / 1000, 3) if p50 else "", p99_ms=round(p99 / 1000, 3) if p99 else "",
                     p999_ms=round(p999 / 1000, 3) if p999 else "",
                     processing_time_s=round(ptime, 3) if ptime else "", reps=nrep))

with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["harness", "buffer_kb", "row_kb", "span_buffers", "mode", "threads",
                                      "gbps", "throughput_mbps", "mrows_s", "p50_ms", "p99_ms", "p999_ms",
                                      "processing_time_s", "reps"])
    w.writeheader(); w.writerows(rows)
print(f"wrote {OUT} ({len(rows)} rows)")
for bk in sorted(set(r["buffer_kb"] for r in rows)):
    print(f"--- buffer={bk}KB:  row | LF GB/s | LK GB/s | LF/LK | LF p99ms | LK p99ms | LF ptime ---")
    byk = {(r["row_kb"], r["mode"]): r for r in rows if r["buffer_kb"] == bk}
    for rk in sorted(ROW.values()):
        lf, lk = byk.get((rk, "LOCK_FREE")), byk.get((rk, "LOCKING"))
        if lf and lk:
            pt = lf["processing_time_s"]; flag = "" if (pt and float(pt) > 1.4) else " !short"
            print(f"  {rk:>4}KB | {lf['gbps']:6.2f}  | {lk['gbps']:6.2f}  | {lf['gbps']/lk['gbps']:.2f}x | "
                  f"{lf['p99_ms']:>7} | {lk['p99_ms']:>7} | {pt}{flag}")
