#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Artifact copy of /home/user/Notes/nebulastream/benchmark/2_engine_to_e2e/figures/make_serde_micro.py. Paths only: input ../data/serde_micro_decomposition.csv, output ../out/serde_micro.
"""Serde-overhead micro figure: throughput (rows/s) vs #fields K, 5 arms.
Data: scratchpad/serde_micro/serde_decomposition.csv (run_group 20260827T192919, K=1..20)."""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
(HERE / "out").mkdir(exist_ok=True)
CSV = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "data/serde_micro_decomposition.csv")
OUT = str(HERE / "out/serde_micro")

rows = list(csv.DictReader(open(CSV)))
K = [int(r["K"]) for r in rows]
def col(name): return [float(r[name]) for r in rows]

# arm -> (column, label, color, marker, linestyle)
ARMS = [
    ("no_serde_Mrows",    "no-serde (raw-row passthrough)",   "#1b7837", "o", "-"),
    ("only_deser_Mrows",  "only-deserialize (parse)",         "#2166ac", "s", "-"),
    ("only_ser_Mrows",    "only-serialize (format)",          "#d6604d", "^", "-"),
    ("serde_Mrows",       "serde (parse + format)",           "#b2182b", "D", "-"),
    ("serde_naive_Mrows", "serde, naive serializer",          "#762a83", "v", "--"),
]

plt.rcParams.update({"font.size": 12, "axes.edgecolor": "#888", "svg.fonttype": "none"})
fig, ax = plt.subplots(figsize=(9, 6))

for c, lab, col_, mk, ls in ARMS:
    ax.plot(K, col(c), marker=mk, color=col_, linestyle=ls, linewidth=2, markersize=6, label=lab)

ax.set_yscale("log")
ax.set_xlabel("number of projected fields  K")
ax.set_ylabel("throughput  (M rows / s)")
ax.set_xticks(range(2, 21, 2))
ax.set_xlim(0.5, 20.5)
ax.grid(True, which="both", axis="y", color="#ddd", linewidth=0.6, zorder=0)
ax.set_axisbelow(True)
ax.set_title("Cost of (de)serialization vs. passthrough  —  CSV/native $\\rightarrow$ JSON/native, "
             "$K$ float fields, single core", fontsize=12)

# annotate the per-field law + naive factor (stable across K)
txt = ("per-field:  parse $\\approx$ 13 ns   serialize $\\approx$ 22 ns\n"
       "serde $\\approx$ parse + serialize  (slightly sub-additive)\n"
       "naive serializer  $\\approx$ 4.3$\\times$  the fast serde")
ax.text(0.98, 0.97, txt, transform=ax.transAxes, ha="right", va="top", fontsize=10.5,
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#f7f7f7", edgecolor="#bbb"))

ax.legend(loc="lower left", fontsize=10.5, framealpha=0.95)
fig.tight_layout()
fig.savefig(OUT + ".png", dpi=150, bbox_inches="tight")
fig.savefig(OUT + ".svg", bbox_inches="tight")
print(f"wrote {OUT}.png / .svg")
