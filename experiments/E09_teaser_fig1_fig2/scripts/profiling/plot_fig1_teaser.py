#!/usr/bin/env python3
"""Fig1 TEASER (2026-09-25): per query, naive vs optimised NebulaStream, share of engine CPU time in three segments
(deserialize / process incl. raw passthrough copy / serialize), Mrows/s annotated above each bar; second panel = the
same split in absolute ns per row (log). usage: plot_fig1_teaser.py <fig1_teaser_data.csv> <out_stem>
Colours: deserialize #0072B2, process #999999, serialize #D55E00 (the 2026-08-19 Fig1 palette, kept for continuity)."""
import csv, sys, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
C = {"deserialize": "#0072B2", "process": "#999999", "serialize": "#D55E00"}
LABEL = {"q0": "q0\nSELECT *", "q2mod": "q2\nfilter (0.8%)", "ysb": "YSB\nwindowed count"}
ARM = {"naive": "naive", "optimised": "optimised"}
ARMC = {"naive": "#6BAED6", "optimised": "#08519C"}   # Fig2 v2 rung colours (validated ordinal Blues ramp)
plt.rcParams.update({"font.size": 11, "font.family": "sans-serif", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#444444", "axes.linewidth": 0.8})
rows = list(csv.DictReader(open(sys.argv[1]))); stem = sys.argv[2]
queries = [q for q in ["q0", "q2mod", "ysb"] if any(r["query"] == q for r in rows)]
fig, (a, b) = plt.subplots(1, 2, figsize=(11.0, 4.0), gridspec_kw={"width_ratios": [1.15, 1]})
W = 0.36
for qi, q in enumerate(queries):
    for ai, arm in enumerate(["naive", "optimised"]):
        r = next((r for r in rows if r["query"] == q and r["arm"] == arm), None)
        if r is None: continue
        x = qi + (ai - 0.5) * (W + 0.04)
        ns = float(r["ns_per_row"]); shares = {k: float(r[f"{k}_pct"]) for k in C}
        bottom = 0.0
        for k in ["deserialize", "process", "serialize"]:
            v = shares[k]
            a.bar(x, v, W, bottom=bottom, color=C[k], edgecolor="white", linewidth=1.2, label=k if (qi == 0 and ai == 0) else None)
            if v >= 8: a.text(x, bottom + v / 2, f"{v:.0f}%", ha="center", va="center", fontsize=9, color="white" if k != "process" else "#222222", fontweight="bold")
            bottom += v
        a.text(x, 102 + 7 * ai, f"{1000/ns:.1f} Mrows/s", ha="center", va="bottom", fontsize=8.5, color="#222222")   # staggered: naive low, optimised high
        a.text(x, -6, ARM[arm], ha="center", va="top", fontsize=9, color="#444444")
        # (b): TOTAL ns/row per arm, unstacked (stacking on a log axis distorts proportions; the split is panel (a))
        b.bar(x, ns, W, color=ARMC[arm], edgecolor="white", linewidth=1.2)
        b.text(x, ns * 1.08, f"{ns:.0f} ns", ha="center", va="bottom", fontsize=8.5, color="#222222")
        b.text(x, 0.55, ARM[arm], ha="center", va="top", fontsize=9, color="#444444")
        if arm == "optimised":
            rn = next((float(r2["ns_per_row"]) for r2 in rows if r2["query"] == q and r2["arm"] == "naive"), None)
            if rn: b.annotate(f"{rn/ns:.0f}x", xy=(x, ns * 1.9), ha="center", va="bottom", fontsize=9.5, color="#08519C", fontweight="bold")
a.set_xticks(range(len(queries))); a.set_xticklabels([LABEL[q] for q in queries]); a.tick_params(axis="x", pad=18)
a.set_ylim(0, 118); a.set_yticks([0, 25, 50, 75, 100]); a.set_ylabel("Share of engine CPU time (%)")
a.set_title("(a) where the CPU time goes", loc="left", fontsize=11)
b.set_xticks(range(len(queries))); b.set_xticklabels([LABEL[q] for q in queries]); b.tick_params(axis="x", pad=18)
b.set_yscale("log"); b.set_ylim(0.7, 3000); b.set_ylabel("CPU time per row (ns, log)")
b.set_title("(b) total CPU time per row", loc="left", fontsize=11)
for ax in (a, b): ax.set_axisbelow(True); ax.grid(axis="y", color="#E4E4E4", linewidth=0.7)
h, l = a.get_legend_handles_labels()
fig.legend(h, ["Deserialization (index + parse)", "Query processing (incl. raw passthrough copy)", "Serialization (format + JSON framing)"],
           loc="lower center", bbox_to_anchor=(0.5, 0.90), ncol=3, frameon=False, fontsize=9.2)
fig.subplots_adjust(top=0.80, bottom=0.2, left=0.07, right=0.99, wspace=0.25)
fig.savefig(stem + ".pdf", bbox_inches="tight"); fig.savefig(stem + ".png", dpi=170, bbox_inches="tight"); print("wrote", stem)
