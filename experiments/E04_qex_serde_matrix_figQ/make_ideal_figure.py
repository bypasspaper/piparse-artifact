# SPDX-License-Identifier: Apache-2.0
"""Ideal-conditions worker-scaling figure (128 KiB buffers, bidstr q2_mod, no spanning).

x = worker threads, y = M records/s (format-invariant). 4 arms:
  no_serde  SystemNative -> NATIVE (native->native reference ceiling, neutral ink)
  bypass    SIMDCSV lazy elision + LOCK_FREE (all contributions), csv -> JSON
  lockfree  eager_parse=true (real per-field parse), LOCK_FREE shredder
  locking   eager_parse=true, LOCKING shredder
Reads the pbench DuckDB aggregated view; falls back to converting throughput_mbps
with per-arm bytes/row when throughput_mrows_s is absent. Also dumps a tidy CSV
and prints the per-W table with LF/LK and bypass/no-serde ratios.

Usage: uv run python make_ideal_figure.py [outstem]   (run from ~/work/piparse-bench)
"""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/ideal_scaling/scripts/make_ideal_figure.py) ----
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
EXP, VARIANT = "shredder_ideal_scaling_q2mod", "ideal_q2mod"
OUT = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "out/figI_ideal_workers_q2mod")
WORKERS = [1, 2, 4, 8, 12, 16, 20, 23]
BYTES_PER_ROW = {"no_serde": 110.0, "bypass": 114.865, "lockfree": 114.865, "locking": 114.865}

con = duckdb.connect(DB, read_only=True)
cols = {r[0] for r in con.execute("DESCRIBE aggregated").fetchall()}
have_mrows = "throughput_mrows_s" in cols
sel = "throughput_mrows_s" if have_mrows else "throughput_mbps"
data = {}
for xv, ser, val in con.execute(
        f"SELECT x_value, series, {sel} FROM aggregated WHERE experiment=? AND variant=?",
        [EXP, VARIANT]).fetchall():
    if val is None:
        continue
    data[(ser, int(xv))] = float(val) if have_mrows else float(val) / BYTES_PER_ROW[ser]

STYLE = {  # color, linestyle, marker, mfc(open/filled), lw, label
    "no_serde": ("#111111", "-.", "s", "white", 1.9, "no-serde (native→native)"),
    "bypass":   ("#1f6fb2", "-",  "o", "#1f6fb2", 2.4, "bypass (lazy elision, lock-free)"),
    "lockfree": ("#2a9d8f", "--", "^", "white", 2.0, "eager parse — lock-free"),
    "locking":  ("#c0392b", "--", "v", "white", 2.0, "eager parse — locking"),
}


def xy(arm):
    xs = [w for w in WORKERS if (arm, w) in data]
    return xs, [data[(arm, w)] for w in xs]


fig, ax = plt.subplots(figsize=(8.6, 5.4))
for arm in ("no_serde", "bypass", "lockfree", "locking"):
    col, ls, mk, mfc, lw, lab = STYLE[arm]
    xs, yv = xy(arm)
    ax.plot(xs, yv, color=col, ls=ls, marker=mk, ms=7, lw=lw, mfc=mfc, label=lab, zorder=3)

# input-bandwidth parity: the rows/s bypass would reach at the native arm's GB/s
ns23 = data.get(("no_serde", 23))
if ns23:
    parity = ns23 * BYTES_PER_ROW["no_serde"] / BYTES_PER_ROW["bypass"]
    ax.axhline(parity, color="#8a8a8a", ls=":", lw=1.3, zorder=1)
    ax.annotate("byte-parity with no-serde (same GB/s)", (23, parity), fontsize=8,
                color="#8a8a8a", ha="right", va="bottom", xytext=(-2, 3), textcoords="offset points")
bp23, lf23, lk23 = data.get(("bypass", 23)), data.get(("lockfree", 23)), data.get(("locking", 23))
if bp23 and ns23:
    ax.annotate(f"bypass = {bp23/ns23:.0%} of no-serde @23", (23, bp23), color="#1f6fb2",
                fontsize=9, fontweight="bold", ha="right", va="top", xytext=(-4, -10),
                textcoords="offset points")
if lf23 and lk23:
    ax.annotate(f"LF/LK = {lf23/lk23:.2f}× @23", (23, lk23), color="#8a8a8a", fontsize=9,
                ha="right", va="top", xytext=(-4, -12), textcoords="offset points")

ax.set_xticks(WORKERS)
ax.set_xlabel("worker threads")
ax.set_ylabel("throughput  [M records/s]")
ax.set_title("Ideal-conditions worker scaling — NEXMark bidstr q2-mod (~115 B rows, 128 KiB buffers, no spanning)\n"
             "bypass closes on the native→native bound as threads grow; lock-free ≈ locking (shredder off the critical path)",
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
print(f"wrote {OUT}.png / .svg  (metric={'mrows' if have_mrows else 'mbps/bpr'})")

csv_path = OUT + "_medians.csv"  ## artifact: CSV lands next to the figure
with open(csv_path, "w") as f:
    f.write("arm,workers,mrows_s\n")
    for arm in STYLE:
        for w in WORKERS:
            if (arm, w) in data:
                f.write(f"{arm},{w},{data[(arm, w)]:.2f}\n")
print(f"wrote {csv_path}")

print(f"\n{'W':>3} {'no_serde':>9} {'bypass':>9} {'lockfree':>9} {'locking':>9} {'byp/ns':>7} {'LF/LK':>6}")
for w in WORKERS:
    ns, bp = data.get(("no_serde", w)), data.get(("bypass", w))
    lf, lk = data.get(("lockfree", w)), data.get(("locking", w))
    if None in (ns, bp, lf, lk):
        continue
    print(f"{w:>3} {ns:>9.1f} {bp:>9.1f} {lf:>9.1f} {lk:>9.1f} {bp/ns:>7.2f} {lf/lk:>6.2f}")
