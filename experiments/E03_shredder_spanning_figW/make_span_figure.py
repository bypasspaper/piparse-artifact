# SPDX-License-Identifier: Apache-2.0
"""Isolated-vs-e2e spanning figure for one buffer size. x = row size (span count); 4 lines =
{iso,e2e} x {LF,LK}; y = GB/s; W24. Shaded band between the LF lines = per-task machinery cost."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/span_figure/scripts/make_span_figure.py) ----
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
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

TIDY = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "data/span_tidy.csv")
OUT = sys.argv[2] if len(sys.argv) > 2 else str(HERE / "out/figS_span")
W = int(sys.argv[3]) if len(sys.argv) > 3 else 24
BUF = int(sys.argv[4]) if len(sys.argv) > 4 else 4

rows = [r for r in csv.DictReader(open(TIDY)) if int(r["threads"]) == W and int(r["buffer_kb"]) == BUF]
series = defaultdict(dict)
span_of = {}
for r in rows:
    rk = int(r["row_kb"])
    series[(r["harness"], r["mode"])][rk] = float(r["gbps"])
    span_of[rk] = int(r["span_buffers"])
xs_all = sorted(span_of)
BLUE, RED = "#1f6fb2", "#c0392b"
STYLE = {
    ("isolated", "LOCK_FREE"): dict(color=BLUE, ls="-", marker="o", label="isolated  LOCK-FREE"),
    ("isolated", "LOCKING"):   dict(color=RED, ls="-", marker="o", label="isolated  naive-LOCKING"),
    ("e2e", "LOCK_FREE"):      dict(color=BLUE, ls="--", marker="s", mfc="white", label="e2e  LOCK-FREE"),
    ("e2e", "LOCKING"):        dict(color=RED, ls="--", marker="s", mfc="white", label="e2e  naive-LOCKING"),
}


def ys(key):
    d = series.get(key, {})
    return [d.get(x) for x in xs_all]


fig, ax = plt.subplots(figsize=(8.8, 5.6))
iso_lf, e2e_lf = ys(("isolated", "LOCK_FREE")), ys(("e2e", "LOCK_FREE"))
if all(v is not None for v in iso_lf + e2e_lf):
    ax.fill_between(xs_all, iso_lf, e2e_lf, color=BLUE, alpha=0.08, zorder=0)

for key in [("isolated", "LOCK_FREE"), ("isolated", "LOCKING"), ("e2e", "LOCK_FREE"), ("e2e", "LOCKING")]:
    st = STYLE[key]
    ax.plot(xs_all, ys(key), color=st["color"], ls=st["ls"], marker=st["marker"],
            mfc=st.get("mfc", st["color"]), ms=7, lw=2.1, label=st["label"], zorder=3)

for harness, ref_key, dy, col in (
        ("isolated", ("isolated", "LOCK_FREE"), 11, BLUE),
        ("e2e", ("e2e", "LOCKING"), -15, "#8a8a8a")):
    lf = series.get((harness, "LOCK_FREE"), {})
    lk = series.get((harness, "LOCKING"), {})
    refd = series.get(ref_key, {})
    for x in xs_all:
        if x in lf and x in lk and lk[x] > 0:
            ax.annotate(f"{lf[x]/lk[x]:.2f}×", (x, refd[x]), fontsize=8.5, color=col, ha="center",
                        va="center", fontweight="bold", xytext=(0, dy), textcoords="offset points", zorder=4)

ax.set_xscale("log", base=2)
ax.set_xticks(xs_all)
ax.set_xticklabels([f"{x}KB\n(span {span_of[x]})" for x in xs_all])
ax.set_xlabel(f"spanning tuple size — row size  (span count @ {BUF} KiB buffer)")
ax.set_ylabel(f"throughput  [GB/s input]   (W{W})")
ax.set_title(f"LOCK-FREE SequenceShredder beats naive-LOCKING at every span  ({BUF} KiB buffer)\n"
             "per-task engine machinery halves LOCK-FREE (shaded) but leaves LOCKING untouched\n"
             "isolated (compiled Scan→Emit)  vs  e2e (full engine)", fontsize=11)
ax.grid(True, which="both", alpha=0.22)
ax.legend(frameon=False, fontsize=9, loc="upper left")
ax.set_ylim(bottom=0)
fig.tight_layout()
for ext in ("png", "svg"):
    fig.savefig(f"{OUT}.{ext}", dpi=140)
print(f"wrote {OUT}.png / .svg  (buffer={BUF}KB, W={W}, rows={xs_all})")
