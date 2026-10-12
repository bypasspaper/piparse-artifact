#!/usr/bin/env python3
"""Fig2 CPU UTILISATION (2026-09-25): cores busy = CPU-seconds / wall-seconds, in the sink window, vs fields N.
From cpu_from_artifacts output (per-run per-thread CPU + window_s). Median over 10 reps.
Panel (a): total CPU utilisation (cores) per rung -- how many cores each rung burns (flat in N => utilisation is
N-independent; the WORK per row scales but so does wall time, so cores stay put). Panel (b): per-thread cores for
each rung, DataSrc (real fused-pipeline work) vs WorkerThread (idle spin at W1) vs other -- shows lazy burns ~2
cores of which ~1 is spin. usage: plot_fig2_util.py <exp_cpu.csv> <out_stem>"""
import csv, sys, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
RUNGS = [("naive", "NES naive", "#6BAED6", "s"),
         ("compiled_eager", "NES eager", "#3182BD", "^"),
         ("compiled_lazy", "NES lazy", "#08519C", "o")]
rows = list(csv.DictReader(open(sys.argv[1]))); stem = sys.argv[2]
def med(rung, N, c):
    v = [float(r[c]) for r in rows if r["series"] == rung and str(r["N"]) == str(N) and r.get(c) not in (None, "")]
    return statistics.median(v) if v else None
Ns = sorted({int(r["N"]) for r in rows if r["N"] not in ("", None) and r["series"] in dict((k, 1) for k, *_ in RUNGS)})
plt.rcParams.update({"font.size": 11, "font.family": "sans-serif", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#444444", "axes.linewidth": 0.8})
fig, (a, b) = plt.subplots(1, 2, figsize=(11.0, 4.1))
# (a) total cores per rung
for rung, label, col, mk in RUNGS:
    xs, ys = [], []
    for N in Ns:
        w = med(rung, N, "window_s"); ct = med(rung, N, "cpu_total_s")
        if w and ct: xs.append(N); ys.append(ct / w)
    if ys:
        a.plot(xs, ys, "-", color=col, marker=mk, markersize=6.5, markeredgecolor="white", linewidth=2, label=label)
        a.annotate(label.split()[-1], (xs[-1], ys[-1]), textcoords="offset points", xytext=(7, 0), va="center", fontsize=9, color="#222")
a.axhline(1.0, color="#999", linewidth=1, linestyle=":")
a.text(Ns[-1], 1.02, "1 core", ha="right", va="bottom", fontsize=8, color="#777")
a.set_xlabel("Fields per row  N"); a.set_ylabel("CPU utilisation  (cores busy = CPU-s / wall-s)")
a.set_ylim(0, 2.3); a.set_title("(a) cores burned per rung (flat in N)", loc="left", fontsize=10.5)
# (b) per-thread cores, grouped bars per rung at a representative N (=10, plateau), split DataSrc/Worker/other
import numpy as np
Nrep = 10
groups = ["cpu_s_DataSrc", "cpu_s_WorkerThread"]
extra = sorted(c for c in rows[0] if c.startswith("cpu_s_") and c not in groups)
GC = {"cpu_s_DataSrc": "#0072B2", "cpu_s_WorkerThread": "#D55E00"}
for gc in extra: GC[gc] = "#BBBBBB"
allcols = groups + extra
xr = np.arange(len(RUNGS)); W = 0.6
for i, (rung, label, col, mk) in enumerate(RUNGS):
    w = med(rung, Nrep, "window_s"); bottom = 0.0
    for gc in allcols:
        cs = med(rung, Nrep, gc)
        if not cs or not w: continue
        cores = cs / w
        lab = gc.replace("cpu_s_", "") if i == 0 else None
        b.bar(i, cores, W, bottom=bottom, color=GC.get(gc, "#BBB"), edgecolor="white", linewidth=1, label=lab)
        if cores >= 0.15:
            b.text(i, bottom + cores / 2, f"{cores:.2f}", ha="center", va="center", fontsize=8.5,
                   color="white" if gc in ("cpu_s_DataSrc", "cpu_s_WorkerThread") else "#333", fontweight="bold")
        bottom += cores
b.axhline(1.0, color="#999", linewidth=1, linestyle=":"); b.text(len(RUNGS)-0.5, 1.02, "1 core", ha="right", va="bottom", fontsize=8, color="#777")
b.set_xticks(xr); b.set_xticklabels([l for _, l, *_ in RUNGS]); b.set_ylabel("CPU utilisation  (cores)")
b.set_ylim(0, 2.2); b.set_title(f"(b) per-thread cores at N={Nrep}: naive splits parse/serialise, compiled fuses onto DataSrc", loc="left", fontsize=9.6)
for ax in (a, b): ax.set_axisbelow(True); ax.grid(axis="y", color="#E4E4E4", linewidth=0.7)
a.set_xticks(Ns); a.legend(frameon=False, fontsize=9, loc="center right")
b.legend(frameon=False, fontsize=9, loc="upper left", title="thread")
fig.subplots_adjust(top=0.9, bottom=0.14, left=0.08, right=0.99, wspace=0.24)
fig.savefig(stem + ".pdf", bbox_inches="tight"); fig.savefig(stem + ".png", dpi=170, bbox_inches="tight"); print("wrote", stem)
