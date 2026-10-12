#!/usr/bin/env python3
"""Fig2 CPU per TUPLE (ns, log) with stage attribution, naive vs lazy, N=1..10 (2026-09-26).
(a) per N two stacked bars (naive | lazy) on a LOG axis, deser/proc/ser segments, total annotated. NB: on a log axis a
    segment's drawn height is log(top)-log(bottom), so segment proportions are NOT to scale -- read shares from panel
    (b) or the linear figure (fig2_v2_stage_cpu_naive_vs_lazy). Kept because a log axis is the only way to show both
    rungs (4..2300 ns) on one panel.
(b) per-stage lines on the same log axis: stage colour, naive dashed / lazy solid -- magnitudes read correctly here.
usage: plot_fig2_stage_log.py <fig2_stage_cpu.csv> <out_stem>"""
import csv, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
C = {"deser": "#0072B2", "proc": "#999999", "ser": "#D55E00"}
LAB = {"deser": "Deserialization (index + parse)", "proc": "Query processing (incl. raw passthrough copy)", "ser": "Serialization (format + JSON framing)"}
MK = {"deser": "o", "proc": "s", "ser": "^"}
plt.rcParams.update({"font.size": 11, "font.family": "sans-serif", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#444444", "axes.linewidth": 0.8})
rows = list(csv.DictReader(open(sys.argv[1]))); stem = sys.argv[2]
def get(rung): return sorted(((int(r["N"]), r) for r in rows if r["rung"] == rung), key=lambda x: x[0])
fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.4), gridspec_kw={"width_ratios": [1.25, 1]})
W = 0.38; FLOOR = 0.5
for i, (rung, alpha) in enumerate((("naive", 0.55), ("lazy", 1.0))):
    for N, r in get(rung):
        x = N + (i - 0.5) * (W + 0.04); bottom = FLOOR
        for k in ("deser", "proc", "ser"):
            v = float(r[f"{k}_ns"])
            if v <= 0: continue
            a.bar(x, v, W, bottom=bottom, color=C[k], alpha=alpha, edgecolor="white", linewidth=0.6,
                  label=LAB[k] if (N == 1 and rung == "lazy") else None)
            bottom += v
        a.text(x, bottom * 1.12, f"{bottom - FLOOR:.0f}", ha="center", va="bottom", fontsize=7, color="#333")
a.set_yscale("log"); a.set_ylim(FLOOR * 0.45, 8000); a.set_xticks(range(1, 11)); a.set_xlabel("Fields per row  N")
a.set_ylabel("CPU time per tuple (ns, log)")
a.set_title("(a) CPU per tuple by stage, naive (pale) vs lazy (solid); log axis, segments not to scale", loc="left", fontsize=9.6)
for rung, ls, lw in (("naive", "--", 1.6), ("lazy", "-", 2.0)):
    pts = get(rung); Ns = [n for n, _ in pts]
    for k in ("deser", "proc", "ser"):
        ys = [max(float(r[f"{k}_ns"]), 0.05) for _, r in pts]
        b.plot(Ns, ys, ls, color=C[k], linewidth=lw, marker=MK[k], markersize=5, markeredgecolor="white",
               label=f"{rung} {k}")
        dy = {"lazy": {"deser": -1, "proc": 9, "ser": -11}, "naive": {"deser": 0, "proc": 0, "ser": 0}}[rung][k]
        b.annotate(f"{rung} {k}", (Ns[-1], ys[-1]), textcoords="offset points", xytext=(6, dy), va="center", fontsize=7.5, color="#333")
b.set_yscale("log"); b.set_ylim(0.05, 5000); b.set_xticks(range(1, 11)); b.set_xlim(0.6, 13.2)
b.set_xlabel("Fields per row  N"); b.set_ylabel("CPU time per tuple (ns, log)")
b.set_title("(b) per-stage cost lines (naive dashed, lazy solid)", loc="left", fontsize=10)
for ax in (a, b): ax.set_axisbelow(True); ax.grid(axis="y", color="#E4E4E4", linewidth=0.7)
h, l = a.get_legend_handles_labels()
fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, 0.91), ncol=3, frameon=False, fontsize=9.2)
fig.subplots_adjust(top=0.80, bottom=0.15, left=0.06, right=0.99, wspace=0.22)
fig.savefig(stem + ".pdf", bbox_inches="tight"); fig.savefig(stem + ".png", dpi=170, bbox_inches="tight"); print("wrote", stem)
