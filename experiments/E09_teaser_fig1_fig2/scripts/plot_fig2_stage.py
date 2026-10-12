#!/usr/bin/env python3
"""Fig2 STAGE CPU vs N (2026-09-25): deserialize / process / serialize CPU ns per row, naive vs lazy, N=1..10.
Panels: (a) naive stacked ns/row (linear), (b) lazy stacked ns/row (linear, own scale), (c) share of CPU per stage
(100%-stacked) for both rungs side by side per N. Same three colours as Fig1 (deser #0072B2, process #999999,
serialize #D55E00). Idle spin / kernel excluded (stated). usage: plot_fig2_stage.py <fig2_stage_cpu.csv> <out_stem>"""
import csv, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
C = {"deser": "#0072B2", "proc": "#999999", "ser": "#D55E00"}
LAB = {"deser": "Deserialization (index + parse)", "proc": "Query processing (incl. raw passthrough copy)", "ser": "Serialization (format + JSON framing)"}
plt.rcParams.update({"font.size": 11, "font.family": "sans-serif", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#444444", "axes.linewidth": 0.8})
rows = list(csv.DictReader(open(sys.argv[1]))); stem = sys.argv[2]
def get(rung): return sorted(((int(r["N"]), r) for r in rows if r["rung"] == rung), key=lambda x: x[0])
fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.2), gridspec_kw={"width_ratios": [1, 1, 1.25]})
for ax, rung, title in ((axes[0], "naive", "(a) naive: CPU ns/row by stage"), (axes[1], "lazy", "(b) lazy passthrough: CPU ns/row by stage")):
    for N, r in get(rung):
        bottom = 0.0
        for k in ("deser", "proc", "ser"):
            v = float(r[f"{k}_ns"])
            ax.bar(N, v, 0.75, bottom=bottom, color=C[k], edgecolor="white", linewidth=0.8, label=LAB[k] if (N == 1 and rung == "naive") else None)
            bottom += v
        ax.text(N, bottom, f"{bottom:.0f}", ha="center", va="bottom", fontsize=7.5, color="#333")
    ax.set_title(title, loc="left", fontsize=10.5); ax.set_xlabel("Fields per row  N"); ax.set_ylabel("CPU time per row (ns)")
    ax.set_xticks(range(1, 11)); ax.set_axisbelow(True); ax.grid(axis="y", color="#E4E4E4", linewidth=0.7)
# (c) shares, naive and lazy bars side by side per N
ax = axes[2]; W = 0.38
for i, rung in enumerate(("naive", "lazy")):
    for N, r in get(rung):
        x = N + (i - 0.5) * (W + 0.03); bottom = 0.0
        for k in ("deser", "proc", "ser"):
            v = float(r[f"{k}_pct"])
            ax.bar(x, v, W, bottom=bottom, color=C[k], edgecolor="white", linewidth=0.6, alpha=1.0 if rung == "lazy" else 0.55)
            bottom += v
ax.set_title("(c) share of CPU per stage (left bar naive, right bar lazy)", loc="left", fontsize=10.5)
ax.set_xlabel("Fields per row  N"); ax.set_ylabel("Share of engine CPU (%)"); ax.set_xticks(range(1, 11)); ax.set_ylim(0, 100)
ax.set_axisbelow(True); ax.grid(axis="y", color="#E4E4E4", linewidth=0.7)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, 0.91), ncol=3, frameon=False, fontsize=9.2)
fig.subplots_adjust(top=0.80, bottom=0.15, left=0.05, right=0.99, wspace=0.28)
fig.savefig(stem + ".pdf", bbox_inches="tight"); fig.savefig(stem + ".png", dpi=170, bbox_inches="tight"); print("wrote", stem)
