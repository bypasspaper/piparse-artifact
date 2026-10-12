#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Artifact copy of /home/user/Notes/nebulastream/benchmark/2_engine_to_e2e/figures/make_serde_micro_linear.py. Paths only: input ../data/serde_micro_decomposition.csv, output ../out/serde_micro_linear.
"""Serde-overhead micro figure, LINEAR y (equi-distant y gridlines). Same data as make_serde_micro.py."""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
(HERE / "out").mkdir(exist_ok=True)
CSV = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "data/serde_micro_decomposition.csv")
OUT = str(HERE / "out/serde_micro_linear")

rows = list(csv.DictReader(open(CSV)))
K = [int(r["K"]) for r in rows]
def col(n): return [float(r[n]) for r in rows]

ARMS = [
    ("no_serde_Mrows",    "no-serde (raw-row passthrough)",   "#1b7837", "o", "-"),
    ("only_deser_Mrows",  "only-deserialize (parse)",         "#2166ac", "s", "-"),
    ("only_ser_Mrows",    "only-serialize (format)",          "#d6604d", "^", "-"),
    ("serde_Mrows",       "serde (parse + format)",           "#b2182b", "D", "-"),
    ("serde_naive_Mrows", "serde, naive serializer",          "#762a83", "v", "--"),
]

plt.rcParams.update({"font.size": 12, "axes.edgecolor": "#888", "svg.fonttype": "none"})
fig, ax = plt.subplots(figsize=(9, 6))
for c, lab, cl, mk, ls in ARMS:
    ax.plot(K, col(c), marker=mk, color=cl, linestyle=ls, linewidth=2, markersize=6, label=lab)

ax.set_ylim(0, 150)
ax.yaxis.set_major_locator(MultipleLocator(20))   # equi-distant y gridlines every 20 Mrows/s
ax.set_xlabel("number of projected fields  K")
ax.set_ylabel("throughput  (M rows / s)")
ax.set_xticks(range(2, 21, 2)); ax.set_xlim(0.5, 20.5)
ax.grid(True, axis="y", color="#ddd", linewidth=0.8, zorder=0)
ax.set_axisbelow(True)
ax.set_title("Cost of (de)serialization vs. passthrough  —  $K$ float fields, single core (linear y)",
             fontsize=12)
txt = ("per-field:  parse $\\approx$ 13 ns   serialize $\\approx$ 22 ns\n"
       "serde $\\approx$ parse + serialize  (slightly sub-additive)\n"
       "naive serializer  $\\approx$ 4.3$\\times$  the fast serde")
ax.text(0.975, 0.60, txt, transform=ax.transAxes, ha="right", va="top", fontsize=10.5,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f7f7f7", edgecolor="#bbb"))
ax.legend(loc="upper right", fontsize=10.5, framealpha=0.95)
fig.tight_layout()
fig.savefig(OUT + ".png", dpi=150, bbox_inches="tight")
fig.savefig(OUT + ".svg", bbox_inches="tight")
print(f"wrote {OUT}.png / .svg")
