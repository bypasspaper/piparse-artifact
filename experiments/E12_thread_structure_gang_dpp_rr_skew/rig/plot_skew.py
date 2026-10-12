#!/usr/bin/env python3
"""Skew figure: what happens to each design when the queries are NOT identical.
Row 1: cost skew (10 % of the queries do 4x the work) -- p99 of the worst LIGHT query (the innocent bystander).
Row 2: bursty queries (20 ms on / 20 ms off, random phase) -- pooled p99.
Row 3/4: throughput under the same two skews. Columns: Threadripper | Pi.
Usage: plot_skew.py <tr_heavy.csv> <tr_burst.csv> <pi_heavy.csv> <pi_burst.csv> [out_basename]"""
import csv, statistics, sys
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = Path(__file__).parent
a = sys.argv[1:]
files = {("tr", "heavy"): Path(a[0]), ("tr", "burst"): Path(a[1]), ("pi", "heavy"): Path(a[2]), ("pi", "burst"): Path(a[3])}
out = Path(a[4]) if len(a) > 4 else here / "skew_story"
SERIES = [("dpp", 1, "DPP (ours)", "#2a78d6", "o", "-"),
          ("rr", 1, "round-robin pinning", "#8e5bd6", "p", "-"),
          ("chunker", 4, "chunker k=4", "#1baf7a", "^", "-"),
          ("gprivate", 4, "gang k=4", "#eb6834", "s", "-"),
          ("gprivate", 1, "thread-per-query", "#eda100", "D", "-")]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"

def load(path):
    cells = defaultdict(list)
    if not path.exists():
        print("missing", path); return cells
    for r in csv.DictReader(open(path)):
        cells[(r["arm"], int(r["k"]), int(r["N"]), int(r["spin_us"]))].append(r)
    return cells

def series(cells, arm, k, col):
    """design-best per N = the spin policy with the lower pooled p99; return that policy's median of `col`"""
    byN = defaultdict(dict)
    for (a_, kk, N, spin), rs in cells.items():
        if a_ == arm and kk == k:
            byN[N][spin] = (statistics.median(float(r["p99_us"]) for r in rs), statistics.median(float(r[col]) for r in rs))
    xs = sorted(byN)
    return xs, [min(byN[N].values())[1] for N in xs]

ROWS = [("heavy", "light_strm_p99_max_us", 1e3, "cost skew: p99 of the worst\nunaffected query (ms)"),
        ("burst", "p99_us", 1e3, "bursty queries: p99 (ms)"),
        ("heavy", "GBps", 1.0, "cost skew: throughput (GB/s)"),
        ("burst", "GBps", 1.0, "bursty queries: throughput (GB/s)")]
data = {k: load(v) for k, v in files.items()}
fig, axes = plt.subplots(4, 2, figsize=(7.2, 8.6), sharex="col", dpi=150)
for c, (m, title) in enumerate((("tr", "Threadripper PRO 5965WX, 24 cores"), ("pi", "Raspberry Pi 5, 4 cores"))):
    for rI, (skew, col, div, ylabel) in enumerate(ROWS):
        ax = axes[rI][c]
        cells = data[(m, skew)]
        tops = []
        for arm, k, label, colour, marker, ls in SERIES:
            xs, ys = series(cells, arm, k, col)
            if not xs:
                continue
            ys = [y / div for y in ys]
            ax.plot(xs, ys, color=colour, marker=marker, ms=4, lw=1.5, ls=ls, mec="white", mew=0.6, label=label)
            if (arm, k) != ("gprivate", 1) or "GBps" in col:
                tops.append(max(ys))
        if "p99" in col and tops:
            top = max(tops) * 1.2
            ax.set_ylim(0, top)
            xs, ys = series(cells, "gprivate", 1, col)
            if xs and max(ys) / div > top:
                ax.text(0.03, 0.96, f"thread-per-query: {max(ys)/div:.0f} ms max (off scale)", transform=ax.transAxes, fontsize=6.5, color="#eda100", va="top")
        else:
            ax.set_ylim(bottom=0)
        ax.set_xscale("log", base=2)
        ax.set_xticks([2 ** i for i in range(0, 10, 2)]); ax.set_xticks([], minor=True)
        ax.grid(True, which="major", color=GRID, lw=0.6)
        ax.tick_params(labelsize=7, colors=INK2)
        for sp in ax.spines.values():
            sp.set_color(GRID)
        if c == 0:
            ax.set_ylabel(ylabel, fontsize=7.5, color=INK2)
        if rI == 0:
            ax.set_title(title, fontsize=9, color=INK)
        if rI == 3:
            ax.set_xlabel("concurrent text-bound queries N", fontsize=8, color=INK2)
handles, labels = axes[0][0].get_legend_handles_labels()
fig.legend(handles, labels, fontsize=7, frameon=False, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.01))
fig.suptitle("Non-identical queries under the engine's admission rule: 10 % of the queries at 4x cost (rows 1, 3);\n20 ms on / 20 ms off bursts with random phase (rows 2, 4)", fontsize=8, color=INK2, y=0.995)
fig.tight_layout(rect=(0, 0.03, 1, 0.97))
fig.savefig(str(out) + ".png", bbox_inches="tight"); fig.savefig(str(out) + ".pdf", bbox_inches="tight")
print("wrote", out)
