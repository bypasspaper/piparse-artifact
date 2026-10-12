#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Artifact copy of ~/Notes/.../figures/make_serde_micro_2panel.py. Change: reads the tidy ../data/serde_micro_2panel_raw.csv
# (type,K,arm,...,mrows_s_true) instead of re-parsing the two run logs with os.path.getsize() on the build tree; the
# log->tidy step is scripts/emit_2panel_csv.py. Output ../out/serde_micro_2panel.
"""Two-panel serde-overhead figure: float64 | int64, shared log-y. Parses the two run logs'
summary lines, converts input-MB/s -> true rows/s (per-arm bytes/row x per-arm REPEAT)."""
import re, os
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

import csv, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
(HERE / "out").mkdir(exist_ok=True)
TIDY = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "data/serde_micro_2panel_raw.csv")
OUT = str(HERE / "out/serde_micro_2panel")
ARMS = [
    ("no_serde",    "no-serde (raw-row passthrough)", "#1b7837", "o", "-"),
    ("only_deser",  "only-deserialize (parse)",       "#2166ac", "s", "-"),
    ("only_ser",    "only-serialize (format)",        "#d6604d", "^", "-"),
    ("serde",       "serde (parse + format)",         "#b2182b", "D", "-"),
    ("serde_naive", "serde, naive serializer",        "#762a83", "v", "--"),
]
def load(path):
    out = {}
    for r in csv.DictReader(open(path)):
        out.setdefault(r["type"], {}).setdefault(r["arm"], {})[int(r["K"])] = float(r["mrows_s_true"])
    return out
_t = load(TIDY); fdat, idat = _t["float64"], _t["int64"]

plt.rcParams.update({"font.size": 12, "axes.edgecolor": "#888", "svg.fonttype": "none"})
fig, (axf, axi) = plt.subplots(1, 2, figsize=(14, 6), sharey=True)

for ax, dat, title in [(axf, fdat, "float64"), (axi, idat, "int64")]:
    for arm, lab, cl, mk, ls in ARMS:
        if arm not in dat: continue
        Ks = sorted(dat[arm]); ax.plot(Ks, [dat[arm][k] for k in Ks],
                                       marker=mk, color=cl, linestyle=ls, linewidth=2, markersize=5, label=lab)
    ax.set_yscale("log")
    ax.set_xlabel("number of projected fields  K")
    ax.set_xticks(range(2, 21, 4)); ax.set_xlim(0.5, 20.5)
    ax.grid(True, which="both", axis="y", color="#eee", linewidth=0.6, zorder=0)
    ax.grid(True, which="major", axis="y", color="#ccc", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title(title, fontsize=13, fontweight="bold")

axf.set_ylabel("throughput  (M rows / s)")
axf.legend(loc="lower left", fontsize=9.5, framealpha=0.95)
fig.suptitle("Cost of (de)serialization vs. passthrough  —  float64 vs int64, single core",
             fontsize=13, y=0.98)
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig(OUT + ".png", dpi=150, bbox_inches="tight")
fig.savefig(OUT + ".svg", bbox_inches="tight")
print(f"wrote {OUT}.png")
# quick sanity: no-serde should match across panels (both 8B native rows)
for K in [1,10,20]:
    print(f"K={K}: no-serde float {fdat['no_serde'].get(K):.1f} vs int {idat.get('no_serde',{}).get(K,float('nan')):.1f} Mrows/s")
