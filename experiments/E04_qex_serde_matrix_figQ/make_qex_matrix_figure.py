# SPDX-License-Identifier: Apache-2.0
"""q-ex worker-scaling figure, 2x2 serde matrix (128 KiB, no spanning, tip code state).
x = worker threads, y = M records/s. Neutral inks = the no-parse pair (native->native, native->JSON);
colors = the csv pair (simd csv->JSON, csv->NATIVE). Expected: pairs coincide, gap = input deser only.
Usage (from ~/work/piparse-bench): uv run python make_qex_matrix_figure.py [outstem]"""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/ideal_scaling/scripts/make_qex_matrix_figure.py) ----
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

DB = ART_DB
EXP, VARIANT = "qex_serde_matrix_scaling", "qex_matrix"
OUT = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "out/figQ_qex_serde_matrix")
WORKERS = [1, 2, 4, 8, 12, 16, 20, 23]

con = duckdb.connect(DB, read_only=True)
data = {}
for exp in (EXP, "qex_locking_scaling"):
    for xv, ser, val in con.execute(
            "SELECT x_value, series, throughput_mrows_s FROM aggregated WHERE experiment=? AND variant=?",
            [exp, VARIANT]).fetchall():
        if val is not None:
            data[(ser, int(xv))] = float(val)

STYLE = {  # color, ls, marker, mfc, lw, label
    "native_native":  ("#111111", "-.", "s", "#111111", 2.0, "native→native (no serde)"),
    "native_json":    ("#6b7280", "--", "s", "white",   1.8, "native→JSON (serialize only)"),
    "simd":           ("#1f6fb2", "-",  "o", "#1f6fb2", 2.4, "bypass — csv→JSON (full serde)"),
    "csv_native":     ("#2a9d8f", "--", "^", "white",   2.0, "csv→native (deserialize only)"),
    "bypass_locking": ("#c0392b", "--", "v", "white",   1.8, "bypass — locking shredder"),
}


def xy(arm):
    xs = [w for w in WORKERS if (arm, w) in data]
    return xs, [data[(arm, w)] for w in xs]


fig, ax = plt.subplots(figsize=(8.6, 5.4))
for arm in ("native_native", "native_json", "simd", "csv_native", "bypass_locking"):
    col, ls, mk, mfc, lw, lab = STYLE[arm]
    xs, yv = xy(arm)
    ax.plot(xs, yv, color=col, ls=ls, marker=mk, ms=7, lw=lw, mfc=mfc, label=lab, zorder=3)

nn, sm = data.get(("native_native", 23)), data.get(("simd", 23))
if nn and sm:
    ax.annotate(f"bypass = {sm/nn:.0%} of no-serde @23", (23, sm), color="#1f6fb2", fontsize=9,
                fontweight="bold", ha="right", va="top", xytext=(-8, -26), textcoords="offset points")

ax.set_xticks(WORKERS)
ax.set_xlabel("worker threads")
ax.set_ylabel("throughput  [M records/s]")
ax.set_title("Worker scaling — NEXMark bidstr q-ex, full serde matrix (~115 B rows, 128 KiB buffers)\n"
             "output serde is free (pairs coincide); the residual gap is input deserialization, closing with threads",
             fontsize=10)
ax.grid(True, alpha=0.22)
ax.set_ylim(bottom=0)
leg = ax.legend(frameon=True, fontsize=9, loc="upper left")
leg.get_frame().set_facecolor("white")
leg.get_frame().set_edgecolor("none")
leg.get_frame().set_alpha(0.92)
fig.tight_layout()
for ext in ("png", "svg"):
    fig.savefig(f"{OUT}.{ext}", dpi=140)
print(f"wrote {OUT}.png / .svg")

csv_path = OUT + "_medians.csv"  ## artifact: CSV lands next to the figure
with open(csv_path, "w") as f:
    f.write("arm,workers,mrows_s\n")
    for arm in STYLE:
        for w in WORKERS:
            if (arm, w) in data:
                f.write(f"{arm},{w},{data[(arm, w)]:.2f}\n")
print(f"wrote {csv_path}")

print(f"\n{'W':>3} {'natnat':>8} {'natjson':>8} {'simd':>8} {'csvnat':>8} {'locking':>8} {'simd/nn':>8} {'LF/LK':>6}")
for w in WORKERS:
    n, j = data.get(("native_native", w)), data.get(("native_json", w))
    s, c = data.get(("simd", w)), data.get(("csv_native", w))
    lk = data.get(("bypass_locking", w))
    if None in (n, j, s, c, lk):
        continue
    print(f"{w:>3} {n:>8.1f} {j:>8.1f} {s:>8.1f} {c:>8.1f} {lk:>8.1f} {s/n:>8.2f} {s/lk:>6.2f}")
