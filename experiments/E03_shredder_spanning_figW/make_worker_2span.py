# SPDX-License-Identifier: Apache-2.0
"""e2e worker-scaling, two spans overlaid (3-buffer vs 20-buffer). x=workers, y=GB/s.
4 lines = {3span,20span} x {LF,LK}. If the two spans overlap, the worker-scaling gap is span-robust."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/span_figure/scripts/make_worker_2span.py) ----
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
import sys

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "out/figW_2span_e2e")
WORKERS = [1, 2, 4, 8, 12, 16, 20, 24]
con = duckdb.connect(ART_DB, read_only=True)
d = {}
for var, xv, ser, mbps in con.execute(
        "SELECT variant,x_value,series,throughput_mbps FROM aggregated WHERE experiment='shredder_worker_probe'").fetchall():
    d[(var, ser, int(xv))] = mbps / 1000
BLUE, RED = "#1f6fb2", "#c0392b"
SPEC = [
    ("workers_12k_span3", "lock_free", BLUE, "-", "o", "LOCK-FREE  3-span (12 KB)"),
    ("workers_12k_span3", "locking", RED, "-", "o", "naive-LOCKING  3-span"),
    ("workers_80k_span20", "lock_free", BLUE, "--", "s", "LOCK-FREE  20-span (80 KB)"),
    ("workers_80k_span20", "locking", RED, "--", "s", "naive-LOCKING  20-span"),
]
fig, ax = plt.subplots(figsize=(8.6, 5.6))
for var, ser, col, ls, mk, lab in SPEC:
    ys = [d.get((var, ser, w)) for w in WORKERS]
    ax.plot(WORKERS, ys, color=col, ls=ls, marker=mk, ms=6.5, lw=2.1,
            mfc=col if ls == "-" else "white", label=lab)
for var, tag, dy in (("workers_12k_span3", "3-span", 8), ("workers_80k_span20", "20-span", -14)):
    lf, lk = d.get((var, "lock_free", 24)), d.get((var, "locking", 24))
    if lf and lk:
        ax.annotate(f"{tag}: {lf/lk:.2f}× @24", (24, lf), color="#555", fontsize=8.5, fontweight="bold",
                    ha="right", va="bottom", xytext=(-4, dy), textcoords="offset points")
ax.set_xticks(WORKERS)
ax.set_xlabel("worker threads")
ax.set_ylabel("throughput  [GB/s input]  (e2e, W-swept)")
ax.set_title("e2e worker scaling is SPAN-ROBUST: 3-buffer vs 20-buffer spans nearly coincide\n"
             "LF/LK gap grows with workers to ~1.3× either way (fewer/bigger tuples at 20-span offset the\n"
             "longer critical section) — deep queue, 4 KiB buffer, reps 6", fontsize=10)
ax.grid(True, alpha=0.22)
ax.legend(frameon=False, fontsize=9, loc="upper left")
ax.set_ylim(bottom=0)
fig.tight_layout()
for ext in ("png", "svg"):
    fig.savefig(f"{OUT}.{ext}", dpi=140)
print(f"wrote {OUT}.png / .svg")
