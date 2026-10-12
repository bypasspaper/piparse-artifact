#!/usr/bin/env python3
# Artifact copy of ~/Notes/nebulastream/benchmark/fig1_fig2_teaser_2026-09-25_scratch/teaser_v2/plot_teaser2.py
# (2026-09-28). Only the I/O defaults changed: input = ../data/fig1_teaser2_naive_flink_optimised_2026-09-28_data.csv,
# output stem = ../out/fig1_teaser2_naive_flink_optimised. Pass <data.csv> <out_stem> to override.
"""Fig1 TEASER v2 (2026-09-28): per query (q0, Q2-original, YSB) three bars (naive NES, Flink, optimised NES with
overloading), stage split deserialize / process / serialize.
(a) share of engine CPU (%), 100%-stacked, Mrows/s annotated above each bar (staggered);
(b) absolute CPU ns per tuple, stacked on a LOG axis (segments not to scale on log -- totals annotated; read the split
    from (a)); optimised bars carry the naive/optimised speed-up.
Colours as Fig1: deser #0072B2, process #999999, serialize #D55E00. usage: plot_teaser2.py <data.csv> <out_stem>"""
import csv, sys
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
C = {"deser": "#0072B2", "proc": "#999999", "ser": "#D55E00"}
LAB = {"deser": "Deserialization (index + parse)", "proc": "Query processing (incl. raw passthrough copy)", "ser": "Serialization (format + JSON framing)"}
QL = {"q0": "q0\nSELECT *", "q2og": "Q2 (NEXMark)\n5-way point filter", "ysb": "YSB\nwindowed count"}
ARMS = [("naive", "naive"), ("flink", "Flink"), ("optimised", "optimised")]
plt.rcParams.update({"font.size": 11, "font.family": "sans-serif", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#444444", "axes.linewidth": 0.8})
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
_in = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "data/fig1_teaser2_naive_flink_optimised_2026-09-28_data.csv")
stem = sys.argv[2] if len(sys.argv) > 2 else str(HERE / "out/fig1_teaser2_naive_flink_optimised")
Path(stem).parent.mkdir(parents=True, exist_ok=True)
rows = list(csv.DictReader(open(_in)))
def get(q, arm): return next((r for r in rows if r["query"] == q and r["arm"] == arm), None)
queries = [q for q in ("q0", "q2og", "ysb") if any(r["query"] == q for r in rows)]
fig, (a, b) = plt.subplots(1, 2, figsize=(13.0, 4.6), gridspec_kw={"width_ratios": [1.15, 1]})
W = 0.25; G = 0.03; FLOOR = 0.5
for qi, q in enumerate(queries):
    for ai, (arm, alab) in enumerate(ARMS):
        r = get(q, arm)
        if r is None: continue
        x = qi + (ai - 1) * (W + G)
        # (a) share
        bottom = 0.0
        for k in ("deser", "proc", "ser"):
            v = float(r[f"{k}_pct"])
            a.bar(x, v, W, bottom=bottom, color=C[k], edgecolor="white", linewidth=1.0, label=LAB[k] if (qi == 0 and ai == 0) else None)
            if v >= 9: a.text(x, bottom + v / 2, f"{v:.0f}", ha="center", va="center", fontsize=8, color="white" if k != "proc" else "#222", fontweight="bold")
            bottom += v
        mr = r.get("mrows_s")
        if mr not in (None, ""): a.text(x, 101.5 + 7 * (ai % 2), f"{float(mr):.1f}", ha="center", va="bottom", fontsize=7.5, color="#222")
        a.text(x + 0.04, -3.5, alab, ha="right", va="top", fontsize=7.5, color="#444", rotation=30)
        # (b) ns per tuple, log-stacked
        bottom = FLOOR
        for k in ("deser", "proc", "ser"):
            v = float(r[f"{k}_ns"])
            if v <= 0: continue
            b.bar(x, v, W, bottom=bottom, color=C[k], edgecolor="white", linewidth=0.8); bottom += v
        tot = bottom - FLOOR
        b.text(x, bottom * 1.1, f"{tot:.0f}", ha="center", va="bottom", fontsize=7.5, color="#222")
        b.text(x + 0.04, FLOOR * 0.7, alab, ha="right", va="top", fontsize=7.5, color="#444", rotation=30)
        if arm == "optimised":
            rn = get(q, "naive")
            if rn: b.text(x, bottom * 2.1, f"{float(rn['ns_per_tuple']) / tot:.0f}x", ha="center", va="bottom", fontsize=9, color="#08519C", fontweight="bold")
a.set_xticks(range(len(queries))); a.set_xticklabels([QL[q] for q in queries]); a.tick_params(axis="x", pad=26)
a.set_ylim(0, 118); a.set_yticks([0, 25, 50, 75, 100]); a.set_ylabel("Share of engine CPU time (%)")
a.set_title("(a) where the CPU time goes  (Mrows/s above bars)", loc="left", fontsize=10.5)
b.set_xticks(range(len(queries))); b.set_xticklabels([QL[q] for q in queries]); b.tick_params(axis="x", pad=26)
b.set_yscale("log"); b.set_ylim(FLOOR * 0.4, 20000); b.set_ylabel("CPU time per tuple (ns, log)")
b.set_title("(b) the same CPU per tuple; log axis, segments not to scale", loc="left", fontsize=10.5)
for ax in (a, b): ax.set_axisbelow(True); ax.grid(axis="y", color="#E4E4E4", linewidth=0.7)
h, l = a.get_legend_handles_labels()
fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, 0.92), ncol=3, frameon=False, fontsize=9.2)
fig.subplots_adjust(top=0.82, bottom=0.2, left=0.06, right=0.99, wspace=0.22)
fig.savefig(stem + ".pdf", bbox_inches="tight"); fig.savefig(stem + ".png", dpi=170, bbox_inches="tight"); print("wrote", stem)
