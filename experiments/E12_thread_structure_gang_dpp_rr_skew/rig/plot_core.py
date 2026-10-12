#!/usr/bin/env python3
"""The one figure: engine-admission window, DPP vs gang vs chunker, p99 latency (linear) over CPU-seconds per GB,
Threadripper | Pi. Usage: plot_core.py [sweep_tr_D64_C1000.csv] [sweep_pi_D64_C1000.csv] [out_basename]"""
import csv, statistics, sys
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = Path(__file__).parent
args = [a for a in sys.argv[1:] if not a.startswith("--")]
## a machine argument may be a '+'-joined list of CSVs (e.g. the rr rows of the TR live in sweep_tr_ws_rr_D64_C1000.csv)
tr = [Path(p) for p in (args[0] if len(args) > 0 else "sweep_tr_D64_C1000.csv").split("+")]
pi = [Path(p) for p in (args[1] if len(args) > 1 else "sweep_pi_D64_C1000.csv").split("+")]
out = Path(args[2]) if len(args) > 2 else here / "core_story"

SERIES = [("dpp", 1, "DPP (ours)", "#2a78d6", "o", "-"),
          ("gprivate", 4, "gang: 4 threads per query", "#eb6834", "s", "-"),
          ("chunker", 4, "chunker: 1 thread per query + pool", "#1baf7a", "^", "-"),
          ("chunker_quote", 4, "quote-aware chunker: cut tracks quote parity", "#0d7a58", "v", "--"),
          ("gprivate", 1, "thread-per-query (SotA SPE)", "#eda100", "D", "-"),
          ("rr", 1, "round-robin pinning (partitioned SPE)", "#8e5bd6", "p", "-")]
CLIP_REF = {("dpp", 1), ("gprivate", 4), ("chunker", 4), ("chunker_quote", 4), ("rr", 1)}   ## the latency axis is scaled to these; thread-per-query may run off
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e6e5e1"

def load(paths):
    cells = defaultdict(list)
    for path in ([paths] if isinstance(paths, Path) else paths):
        if not path.exists():
            print("missing", path); continue
        for r in csv.DictReader(open(path)):
            cells[(r["arm"], int(r["k"]), int(r["N"]), int(r["spin_us"]))].append(r)
    return cells

def series(cells, arm, k):
    """design-best per N: the spin policy with the lower median p99; CPU s/GB of that same policy"""
    byN = defaultdict(dict)
    for (a, kk, N, spin), rs in cells.items():
        if a == arm and kk == k:
            byN[N][spin] = (statistics.median(float(r["p99_us"]) for r in rs) / 1e3,
                            statistics.median(float(r["cpu_s_per_GB"]) for r in rs))
    xs = sorted(byN)
    best = [min(byN[N].values()) for N in xs]
    return xs, [b[0] for b in best], [b[1] for b in best]

cols = [("Threadripper PRO 5965WX, 24 cores", load(tr)), ("Raspberry Pi 5, 4 cores", load(pi))]
fig, axes = plt.subplots(2, 2, figsize=(7.2, 4.9), sharex="col", dpi=150)
for c, (title, cells) in enumerate(cols):
    axL, axC = axes[0][c], axes[1][c]
    endsL, endsC = [], []
    ref_top = 0.0
    clipped = None
    for arm, k, label, colour, marker, ls in SERIES:
        xs, p99, cpu = series(cells, arm, k)
        if not xs:
            continue
        axL.plot(xs, p99, color=colour, marker=marker, ms=4, lw=1.5, ls=ls, mec="white", mew=0.6, label=label, clip_on=True)
        axC.plot(xs, cpu, color=colour, marker=marker, ms=4, lw=1.5, ls=ls, mec="white", mew=0.6, label=label)
        short = label.split(":")[0].split(" (")[0]
        endsC.append((cpu[-1], xs[-1], short))
        if (arm, k) in CLIP_REF:
            ref_top = max(ref_top, max(p99))
            endsL.append((p99[-1], xs[-1], short))
        else:
            clipped = (xs, p99, short, colour)
    top = ref_top * 1.25
    axL.set_ylim(0, top)
    if clipped is not None:
        xs, p99, short, colour = clipped
        if p99[-1] <= top:
            endsL.append((p99[-1], xs[-1], short))
        else:
            ## the line leaves the frame: say where it goes (inside the axes, so the panel widths stay equal)
            exit_i = next(i for i, v in enumerate(p99) if v > top)
            note = f"{short}: {p99[-1]:.0f} ms at N={xs[-1]}" + (f"\n(off scale from N={xs[exit_i]})" if exit_i < len(xs) - 1 else "")
            axL.text(0.03, 0.96, note, transform=axL.transAxes, fontsize=7, color=colour, va="top", ha="left")
    ## right-hand end labels (series name at the last point), pushed apart by >= 7 % of the axis height
    axC.set_ylim(bottom=0)
    xr = max(x for x, _, _ in [(e[1], 0, 0) for e in endsC])
    for ax, ends, ymax in ((axL, endsL, top), (axC, endsC, axC.get_ylim()[1])):
        ax.set_xlim(0.7, xr * 3.2)
        ys = []
        for y, x, short in sorted(ends):
            ys.append(max(y, ys[-1] + 0.07 * ymax) if ys else y)
        for (y0, x, short), y in zip(sorted(ends), ys):
            ax.text(xr * 1.22, y, short, fontsize=7, color=INK2, va="center", ha="left")
    axL.set_title(title, fontsize=9, color=INK)
    axL.set_xscale("log", base=2); axC.set_xscale("log", base=2)
    for ax in (axL, axC):
        ax.set_xticks([2 ** i for i in range(0, 10, 2)])
        ax.set_xticks([], minor=True)
    axC.set_ylim(bottom=0)
    axC.set_xlabel("concurrent text-bound queries N", fontsize=8, color=INK2)
    for ax in (axL, axC):
        ax.grid(True, which="major", color=GRID, lw=0.6)
        ax.tick_params(labelsize=7, colors=INK2)
        for sp in ax.spines.values():
            sp.set_color(GRID)
    if c == 0:
        axL.set_ylabel("p99 latency per buffer (ms)", fontsize=8, color=INK2)
        axC.set_ylabel("CPU time per GB parsed (s)", fontsize=8, color=INK2)
handles, labels = axes[0][0].get_legend_handles_labels()
fig.legend(handles, labels, fontsize=7, frameon=False, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.05))
fig.suptitle("Full load under the engine's admission rule (≤64 buffers per query, ≤1000 in flight in total)", fontsize=8, color=INK2, y=0.995)
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(str(out) + ".png", bbox_inches="tight"); fig.savefig(str(out) + ".pdf", bbox_inches="tight")
print("wrote", out)
