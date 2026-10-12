#!/usr/bin/env python3
"""Motivation figure: p99 latency and throughput vs #concurrent queries, Threadripper | Pi 5.
Usage: plot_fig.py [sweep_tr.csv] [sweep_pi.csv] [out_basename]
Series are the design-best envelope: per (arm,k,N) the spin policy with the lower median p99."""
import csv, statistics, sys
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = Path(__file__).parent
flags = [a for a in sys.argv[1:] if a.startswith("--")]
args = [a for a in sys.argv[1:] if not a.startswith("--")]
LINEAR_Y = "--linear-y" in flags or "--linear" in flags   ## p99 axis linear (default log)
LINEAR_X = "--linear-x" in flags or "--linear" in flags   ## query axis linear (default log2)
EXCLUDE = {a.split("=", 1)[1] for a in flags if a.startswith("--exclude=")}   ## e.g. --exclude=gprivate:1 (thread-per-query)
tr = Path(args[0]) if len(args) > 0 else here / "sweep_tr.csv"
pi = Path(args[1]) if len(args) > 1 else here / "sweep_pi.csv"
out = Path(args[2]) if len(args) > 2 else here / "motivation_latency_vs_queries"

SERIES = [  # (arm, k, label, colour slot, marker) -- fixed order, fixed colours (validated palette)
    ("dpp", 1, "DPP (ours)", "#2a78d6", "o"),
    ("gprivate", 4, "gang, 4 threads/query", "#eb6834", "s"),
    ("chunker", 4, "chunker, 1 thread/query + pool", "#1baf7a", "^"),
    ("gprivate", 1, "thread-per-query (SotA SPE)", "#eda100", "D"),
]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"

def load(path):
    cells = defaultdict(list)
    if not path.exists():
        return cells
    for r in csv.DictReader(open(path)):
        cells[(r["arm"], int(r["k"]), int(r["N"]), int(r["spin_us"]))].append(r)
    return cells

def envelope(cells, arm, k):
    """per N: (p99 us, GB/s) of the spin policy with the lower median p99"""
    byN = defaultdict(dict)
    for (a, kk, N, spin), rs in cells.items():
        if a == arm and kk == k:
            byN[N][spin] = (statistics.median(float(r["p99_us"]) for r in rs), statistics.median(float(r["GBps"]) for r in rs))
    xs = sorted(byN)
    best = [min(byN[N].values()) for N in xs]
    return xs, [b[0] for b in best], [b[1] for b in best]

data = {"Threadripper PRO 5965WX, 24 cores": load(tr), "Raspberry Pi 5, 4 cores": load(pi)}
## in-flight window D from the CSV (column D; absent = 1) for the subtitle
def windows_of(cells):
    return {int(r.get("D", 1) or 1) for rs in cells.values() for r in rs}
D_set = set().union(*(windows_of(c) for c in data.values())) or {1}
D_window = max(D_set)
D_varies = len(D_set) > 1
def caps_of(cells):
    return {int(r.get("cap", 0) or 0) for rs in cells.values() for r in rs}
CAP = max(set().union(*(caps_of(c) for c in data.values())) or {0})
fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.2), sharex="col", dpi=150)
for col, (title, cells) in enumerate(data.items()):
    axL, axT = axes[0][col], axes[1][col]
    ends = []
    for arm, k, label, colour, marker in SERIES:
        if f"{arm}:{k}" in EXCLUDE:
            continue
        xs, p99, gbps = envelope(cells, arm, k)
        if not xs:
            continue
        axL.plot(xs, [v / 1e3 for v in p99], color=colour, marker=marker, ms=4, lw=1.4, mec="white", mew=0.6, label=label)
        axT.plot(xs, gbps, color=colour, marker=marker, ms=4, lw=1.4, mec="white", mew=0.6, label=label)
        ends.append((p99[-1] / 1e3, xs[-1], label.split(",")[0], colour))
    ## direct labels at the right end, pushed apart by >= 0.16 decades so they never collide
    import math
    ends.sort()
    if LINEAR_Y:
        top = max(e[0] for e in ends) if ends else 1.0
        ys = [e[0] for e in ends]
        for i in range(1, len(ys)):
            ys[i] = max(ys[i], ys[i - 1] + 0.045 * top)
        for (y0, x, text, colour), y in zip(ends, ys):
            axL.annotate(text, (x, y), xytext=(5, 0), textcoords="offset points", fontsize=7, color=INK2, va="center")
    else:
        ys = [math.log10(e[0]) for e in ends]
        for i in range(1, len(ys)):
            ys[i] = max(ys[i], ys[i - 1] + 0.16)
        for (y0, x, text, colour), y in zip(ends, ys):
            axL.annotate(text, (x, 10 ** y), xytext=(5, 0), textcoords="offset points", fontsize=7, color=INK2, va="center")
    axL.set_title(title, fontsize=9, color=INK)
    if not LINEAR_X:
        axL.set_xscale("log", base=2); axT.set_xscale("log", base=2)
    if not LINEAR_Y:
        axL.set_yscale("log")
    else:
        axL.set_ylim(bottom=0)
    axT.set_ylim(bottom=0)
    axT.set_xlabel("concurrent text-bound queries N", fontsize=8, color=INK2)
    for ax in (axL, axT):
        ax.grid(True, which="major", color=GRID, lw=0.6); ax.grid(True, which="minor", color=GRID, lw=0.3, alpha=0.6)
        ax.tick_params(labelsize=7, colors=INK2); [s.set_color(GRID) for s in ax.spines.values()]
    if col == 0:
        axL.set_ylabel("p99 latency per buffer (ms)", fontsize=8, color=INK2)
        axT.set_ylabel("throughput (GB/s)", fontsize=8, color=INK2)
handles, labels = axes[0][0].get_legend_handles_labels()
fig.legend(handles, labels, fontsize=7, frameon=False, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.02))
fig.suptitle((f"Full load, engine admission: ≤{D_window} buffers/query, ≤{CAP} in total (FIFO)" if CAP > 0 else "Full load, engine admission window (≤64 buffers/query, ≤1000 in total)" if D_varies else ("Full load, one 128 KiB buffer in flight per query" if D_window == 1 else f"Full load, {D_window} x 128 KiB buffers in flight per query (backlog)")) + "; futex spin-then-block, design-best policy per N", fontsize=8, color=INK2, y=0.995)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(str(out) + ".png", bbox_inches="tight"); fig.savefig(str(out) + ".pdf", bbox_inches="tight")
print("wrote", out)
