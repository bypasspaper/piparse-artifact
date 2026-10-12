# SPDX-License-Identifier: Apache-2.0
"""Consolidate every span-sweep + worker-sweep data point (isolated + e2e) into one tidy CSV.
Columns: sweep,harness,drain,buffer_kb,row_kb,span_buffers,workers,mode,gbps,gbps_max,
         mrows_s,mrows_s_max,p50_ms,p99_ms,repeats_pct,spread_pct
rows/s = gbps * 1e9 / bytes_per_row / 1e6 (bytes_per_row = row_kb*1000 + 3 = id,comma,filler,newline).
isolated: gbps=median, gbps_max=steady ceiling, +repeats/spread; e2e: gbps=throughput/1000, +p50/p99."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/span_figure/scripts/build_all_data_csv.py) ----
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

import duckdb

BASE = str(HERE)
DB = ART_DB


def bpr(row_kb):
    return row_kb * 1000 + 3


def mrows(gbps, row_kb):
    return round(gbps * 1e9 / bpr(row_kb) / 1e6, 4) if gbps not in (None, "") else ""


def span_at(row_kb, buf_kb):
    return round(row_kb * 1000 / (buf_kb * 1024))


rows = []


def parse_iso(log, sweep, buf_of, row_of, drain):
    """buf_of/row_of: callables mapping the two header tags -> (buffer_kb, row_kb)."""
    buf_kb = row_kb = mode = None
    for line in open(log):
        h = re.search(r"#+ BUF (\w+) SPAN (\w+) #+", line)
        if h:
            buf_kb, row_kb = buf_of(h.group(1)), row_of(h.group(2)); continue
        m = re.search(r"sequence_shredder_mode = (LOCK_FREE|LOCKING)", line)
        if m:
            mode = m.group(1); continue
        r = re.match(r"\s*(\d+)\s*\|\s*([\d.]+)\s*\|.*min\.\.max\s*([\d.]+)\.\.\s*([\d.]+).*spread\s+(\d+)%.*pass=\s*(\d+)\s*\(\s*([\d.]+)%", line)
        if r and row_kb is not None and mode:
            w = int(r.group(1)); med = float(r.group(2)); mx = float(r.group(4)); spr = int(r.group(5)); rep = float(r.group(7))
            rows.append(dict(sweep=sweep, harness="isolated", drain=drain, buffer_kb=buf_kb, row_kb=row_kb,
                             span_buffers=span_at(row_kb, buf_kb), workers=w, mode=mode,
                             gbps=med, gbps_max=mx, mrows_s=mrows(med, row_kb), mrows_s_max=mrows(mx, row_kb),
                             p50_ms="", p99_ms="", repeats_pct=rep, spread_pct=spr))


def parse_iso_worker(log, row_kb, drain):
    """single-span worker sweep log: header 'BUF 4k SPAN 12k' style OR plain (uses fixed row_kb)."""
    mode = None
    for line in open(log):
        m = re.search(r"sequence_shredder_mode = (LOCK_FREE|LOCKING)", line)
        if m:
            mode = m.group(1); continue
        r = re.match(r"\s*(\d+)\s*\|\s*([\d.]+)\s*\|.*min\.\.max\s*([\d.]+)\.\.\s*([\d.]+).*spread\s+(\d+)%.*pass=\s*(\d+)\s*\(\s*([\d.]+)%", line)
        if r and mode:
            w = int(r.group(1)); med = float(r.group(2)); mx = float(r.group(4)); spr = int(r.group(5)); rep = float(r.group(7))
            rows.append(dict(sweep="worker", harness="isolated", drain=drain, buffer_kb=4, row_kb=row_kb,
                             span_buffers=span_at(row_kb, 4), workers=w, mode=mode,
                             gbps=med, gbps_max=mx, mrows_s=mrows(med, row_kb), mrows_s_max=mrows(mx, row_kb),
                             p50_ms="", p99_ms="", repeats_pct=rep, spread_pct=spr))


# --- isolated span sweep (4K+8K buffer) ---
tag_kb = lambda t: int(t.rstrip("k"))
parse_iso(f"{BASE}/data/logs/isolated_span_sweep_4k8k.log", "span", tag_kb, tag_kb, "lean")
# --- isolated worker sweeps ---
parse_iso_worker(f"{BASE}/data/logs/isolated_worker_probe_12k_leanprod.log", 12, "leanprod")
parse_iso_worker(f"{BASE}/data/logs/isolated_worker_probe_80k_lean.log", 80, "lean")

# --- e2e (DuckDB) ---
con = duckdb.connect(DB, read_only=True)
# span sweep: variant=row size, x_value=buffer bytes, W24
SPANVAR = {"row_004k": 4, "row_016k": 16, "row_040k": 40, "row_080k": 80, "row_160k": 160, "row_320k": 320, "row_640k": 640}
for var, xv, ser, mbps, p50, p99 in con.execute(
        "SELECT variant,x_value,series,throughput_mbps,p50_latency_us,p99_latency_us FROM aggregated "
        "WHERE experiment='shredder_span_sweep'").fetchall():
    if var not in SPANVAR:
        continue
    row_kb = SPANVAR[var]; buf_kb = round(int(xv) / 1024); g = mbps / 1000
    rows.append(dict(sweep="span", harness="e2e", drain="engine", buffer_kb=buf_kb, row_kb=row_kb,
                     span_buffers=span_at(row_kb, buf_kb), workers=24, mode={"lock_free": "LOCK_FREE", "locking": "LOCKING"}[ser],
                     gbps=round(g, 4), gbps_max="", mrows_s=mrows(g, row_kb), mrows_s_max="",
                     p50_ms=round(p50 / 1000, 3) if p50 else "", p99_ms=round(p99 / 1000, 3) if p99 else "",
                     repeats_pct="", spread_pct=""))
# worker sweep: variant=span, x_value=worker count
WKVAR = {"workers_12k_span3": 12, "workers_80k_span20": 80}
for var, xv, ser, mbps, p50, p99 in con.execute(
        "SELECT variant,x_value,series,throughput_mbps,p50_latency_us,p99_latency_us FROM aggregated "
        "WHERE experiment='shredder_worker_probe'").fetchall():
    if var not in WKVAR:
        continue
    row_kb = WKVAR[var]; g = mbps / 1000
    rows.append(dict(sweep="worker", harness="e2e", drain="engine", buffer_kb=4, row_kb=row_kb,
                     span_buffers=span_at(row_kb, 4), workers=int(xv), mode={"lock_free": "LOCK_FREE", "locking": "LOCKING"}[ser],
                     gbps=round(g, 4), gbps_max="", mrows_s=mrows(g, row_kb), mrows_s_max="",
                     p50_ms=round(p50 / 1000, 3) if p50 else "", p99_ms=round(p99 / 1000, 3) if p99 else "",
                     repeats_pct="", spread_pct=""))

FIELDS = ["sweep", "harness", "drain", "buffer_kb", "row_kb", "span_buffers", "workers", "mode",
          "gbps", "gbps_max", "mrows_s", "mrows_s_max", "p50_ms", "p99_ms", "repeats_pct", "spread_pct"]
rows.sort(key=lambda r: (r["sweep"], r["harness"], r["buffer_kb"], r["row_kb"], r["workers"], r["mode"]))
OUT = f"{BASE}/out/shredder_all_data.csv"
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
print(f"wrote {OUT} ({len(rows)} rows)")
from collections import Counter
c = Counter((r["sweep"], r["harness"]) for r in rows)
for k, v in sorted(c.items()):
    print(f"  {k}: {v}")
