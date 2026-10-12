# SPDX-License-Identifier: Apache-2.0
"""Worker-scaling figure at fixed span (12KB/3-span, 4KiB buffer, deep queue).
x = worker threads. METRIC = gbps | mrows | p99.
  gbps/mrows: 4 lines {isolated,e2e} x {LF,LK} (throughput). rows/s = GB/s / bytes_per_row.
  p99: e2e-only (isolated is a prefilled drain -> no arrival process -> no latency), 2 lines, log-y, lower=better.
Reads the isolated log (max=steady) + the e2e DuckDB aggregated view."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/span_figure/scripts/make_worker_figure.py) ----
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
import re
import sys

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ISO_LOG = str(HERE / "data/logs/isolated_worker_probe_12k_leanprod.log")
DB = ART_DB
OUT = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "out/figW_workers_12k")
METRIC = sys.argv[2] if len(sys.argv) > 2 else "gbps"   # gbps | mrows | p99
WORKERS = [1, 2, 4, 8, 12, 16, 20, 24]
BYTES_PER_ROW = 12003.0
BLUE, RED = "#1f6fb2", "#c0392b"
MODEMAP = {"lock_free": "LOCK_FREE", "locking": "LOCKING"}


def to_metric_gbps(gbps):
    return gbps if METRIC == "gbps" else gbps * 1e9 / BYTES_PER_ROW / 1e6  # -> Mrows/s


# isolated (max = ramp-free steady) — throughput only
iso = {}
mode = None
for line in open(ISO_LOG):
    m = re.search(r"sequence_shredder_mode = (LOCK_FREE|LOCKING)", line)
    if m:
        mode = m.group(1); continue
    m = re.match(r"\s*(\d+)\s*\|\s*[\d.]+\s*\|\s*[\d.]+x\s*\|\s*min\.\.max\s*[\d.]+\.\.\s*([\d.]+)", line)
    if m and mode:
        iso[(mode, int(m.group(1)))] = to_metric_gbps(float(m.group(2)))

# e2e
con = duckdb.connect(DB, read_only=True)
e2e = {}
E2E_VARIANT = "workers_12k_span3"  # filter: the DB now holds both 12k & 80k variants
if METRIC == "p99":
    for xv, ser, p99 in con.execute(
            "SELECT x_value, series, p99_latency_us FROM aggregated WHERE experiment='shredder_worker_probe' AND variant=?",
            [E2E_VARIANT]).fetchall():
        if p99 is not None:
            e2e[(MODEMAP[ser], int(xv))] = p99 / 1000.0  # ms
else:
    for xv, ser, mbps in con.execute(
            "SELECT x_value, series, throughput_mbps FROM aggregated WHERE experiment='shredder_worker_probe' AND variant=?",
            [E2E_VARIANT]).fetchall():
        e2e[(MODEMAP[ser], int(xv))] = to_metric_gbps(mbps / 1000.0)


def xy(src, m):
    xs = [w for w in WORKERS if src.get((m, w)) is not None]
    return xs, [src[(m, w)] for w in xs]


fig, ax = plt.subplots(figsize=(8.6, 5.6))

if METRIC == "p99":
    for m, col, mk in (("LOCKING", RED, "s"), ("LOCK_FREE", BLUE, "s")):
        xs, yv = xy(e2e, m)
        ax.plot(xs, yv, color=col, ls="--", marker=mk, ms=7, lw=2.2, mfc="white",
                label=f"e2e  {'naive-LOCKING' if m == 'LOCKING' else 'LOCK-FREE'}  p99")
    lf, lk = e2e.get(("LOCK_FREE", 24)), e2e.get(("LOCKING", 24))
    if lf and lk:
        ax.annotate(f"LK/LF = {lk/lf:.2f}× @24", (24, lk), color="#8a8a8a", fontsize=9, fontweight="bold",
                    ha="right", va="bottom", xytext=(-4, 8), textcoords="offset points")
    ax.set_yscale("log")
    ax.set_ylabel("p99 ingest→sink latency  [ms, log]")
    ax.set_title("Worker scaling — p99 LATENCY at fixed span (12 KB ≈ 3-buffer span, 4 KiB buffer, deep queue)\n"
                 "more workers drain the deep queue faster → latency falls; LOCKING's tail plateaus higher (mutex-capped)\n"
                 "e2e only (isolated harness has no arrival process) — ⚠ absolute ms inflated by the deep queue",
                 fontsize=10)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
else:
    SR = {
        ("iso", "LOCK_FREE"): (iso, BLUE, "-", "o", "isolated  LOCK-FREE"),
        ("iso", "LOCKING"): (iso, RED, "-", "o", "isolated  naive-LOCKING"),
        ("e2e", "LOCK_FREE"): (e2e, BLUE, "--", "s", "e2e  LOCK-FREE"),
        ("e2e", "LOCKING"): (e2e, RED, "--", "s", "e2e  naive-LOCKING"),
    }
    common = [w for w in WORKERS if iso.get(("LOCK_FREE", w)) is not None and e2e.get(("LOCK_FREE", w)) is not None]
    ax.fill_between(common, [iso[("LOCK_FREE", w)] for w in common], [e2e[("LOCK_FREE", w)] for w in common],
                    color=BLUE, alpha=0.08, zorder=0)
    for (h, m), (src, col, ls, mk, lab) in SR.items():
        xs, yv = xy(src, m)
        ax.plot(xs, yv, color=col, ls=ls, marker=mk, ms=7, lw=2.1, mfc=col if ls == "-" else "white",
                label=lab, zorder=3)
    for src, ref, col, dy in ((iso, "iso", BLUE, 10), (e2e, "e2e", "#8a8a8a", -16)):
        lf, lk = src.get(("LOCK_FREE", 24)), src.get(("LOCKING", 24))
        if lf and lk:
            ax.annotate(f"{lf/lk:.2f}× @24", (24, lf if ref == "iso" else lk), color=col, fontsize=9,
                        fontweight="bold", ha="right", va="bottom" if ref == "iso" else "top",
                        xytext=(-4, dy), textcoords="offset points")
    unit = "GB/s input" if METRIC == "gbps" else "M rows/s"
    ax.set_ylabel(f"throughput  [{unit}]")
    ax.set_title(f"Worker scaling — throughput ({unit}) at fixed span (12 KB ≈ 3-buffer span, 4 KiB buffer, deep queue)\n"
                 "LOCK-FREE keeps scaling; naive-LOCKING plateaus as the mutex saturates — the gap grows with workers\n"
                 "isolated (compiled Scan→Emit)  vs  e2e (full engine)", fontsize=10)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.set_ylim(bottom=0)

ax.set_xticks(WORKERS)
ax.set_xlabel("worker threads")
ax.grid(True, which="both", alpha=0.22)
fig.tight_layout()
for ext in ("png", "svg"):
    fig.savefig(f"{OUT}.{ext}", dpi=140)
print(f"wrote {OUT}.png / .svg  (metric={METRIC})")
