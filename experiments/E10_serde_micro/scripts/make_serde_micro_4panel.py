#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Artifact copy of /home/user/Notes/nebulastream/benchmark/2_engine_to_e2e/figures/make_serde_micro_4panel.py. Paths only: inputs ../data/{serde_micro_2panel_raw,serde_micro_mixed_raw}.csv (or a dir given as argv[1]), output ../out/serde_micro_4panel.
"""Four-panel serde-overhead figure: float64 | int64 | int64->float64 | float64->int64,
shared log-y. Pure panels from the canonical tidy CSV (serde_micro_2panel_raw.csv);
mixed panels from serde_micro_mixed_raw.csv (decompose_mixed.py output).

The mixed panels carry ONE gray reference curve each -- the pure-panel arm of the FLOAT
half of the pipeline (i2f: pure-float only-serialize; f2i: pure-float only-deserialize).
The claim the figure makes: the mixed serde curve sits at/below that reference, i.e. the
float half ALONE already bounds the mixed pipeline (its cost is paid on one side).
Arm colors/markers are the family's fixed assignment (same arm = same color in all panels).
"""
import csv
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
(HERE / "out").mkdir(exist_ok=True)
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data"   # directory holding the two tidy CSVs
PURE = str(DATA / "serde_micro_2panel_raw.csv")
MIXED = str(DATA / "serde_micro_mixed_raw.csv")
OUT = str(HERE / "out/serde_micro_4panel")

ARMS = [
    ("no_serde",    "no-serde (raw-row passthrough)", "#1b7837", "o", "-"),
    ("only_deser",  "only-deserialize (parse)",       "#2166ac", "s", "-"),
    ("only_ser",    "only-serialize (format)",        "#d6604d", "^", "-"),
    ("serde",       "serde (parse + format)",         "#b2182b", "D", "-"),
    ("serde_naive", "serde, naive serializer",        "#762a83", "v", "--"),
]
REF_GRAY = "#777777"


def load(path):
    out = {}
    for row in csv.DictReader(open(path)):
        out.setdefault(row["type"], {}).setdefault(row["arm"], {})[int(row["K"])] = float(row["mrows_s_true"])
    return out


pure = load(PURE)
mixed = load(MIXED)

PANELS = [
    ("float64", pure["float64"], None, None),
    ("int64", pure["int64"], None, None),
    ("int64 → float64", mixed["i2f"], pure["float64"]["only_ser"], "pure-float only-serialize"),
    ("float64 → int64", mixed["f2i"], pure["float64"]["only_deser"], "pure-float only-deserialize"),
]

plt.rcParams.update({"font.size": 12, "axes.edgecolor": "#888", "svg.fonttype": "none"})
fig, axes = plt.subplots(1, 4, figsize=(22, 5.6), sharey=True)

for ax, (title, dat, ref, reflab) in zip(axes, PANELS):
    for arm, lab, cl, mk, ls in ARMS:
        if arm not in dat:
            continue
        Ks = sorted(dat[arm])
        ax.plot(Ks, [dat[arm][k] for k in Ks], marker=mk, color=cl, linestyle=ls,
                linewidth=2, markersize=5, label=lab)
    if ref is not None:
        Ks = sorted(ref)
        ax.plot(Ks, [ref[k] for k in Ks], color=REF_GRAY, linestyle=":", linewidth=2.2,
                label=reflab, zorder=1)
        ax.legend(handles=[ax.lines[-1]], loc="upper right", fontsize=9, framealpha=0.95)
    ax.set_yscale("log")
    ax.set_xlabel("number of projected fields  K")
    ax.set_xticks(range(2, 21, 4))
    ax.set_xlim(0.5, 20.5)
    ax.grid(True, which="both", axis="y", color="#eee", linewidth=0.6, zorder=0)
    ax.grid(True, which="major", axis="y", color="#ccc", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.set_title(title, fontsize=13, fontweight="bold")

axes[0].set_ylabel("throughput  (M rows / s)")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="upper center", ncol=5, fontsize=10.5, framealpha=0.95,
           bbox_to_anchor=(0.5, 0.955))
fig.suptitle("Cost of (de)serialization vs. passthrough — pure and mixed-type pipelines, single core",
             fontsize=13, y=0.995)
fig.tight_layout(rect=[0, 0, 1, 0.90])
fig.savefig(OUT + ".png", dpi=150, bbox_inches="tight")
fig.savefig(OUT + ".svg", bbox_inches="tight")
print(f"wrote {OUT}.png")

# sanity lines: (1) mixed no_serde vs pure no_serde (cast+Map cost); (2) mixed serde vs the float bound
for K in [1, 10, 20]:
    for d, pin in [("i2f", "int64"), ("f2i", "float64")]:
        ns_m = mixed[d]["no_serde"].get(K)
        ns_p = pure[pin]["no_serde"].get(K)
        if ns_m and ns_p:
            print(f"K={K} {d}: no_serde mixed {ns_m:.1f} vs pure {ns_p:.1f} Mrows/s "
                  f"(cast+Map {1e3 / ns_m - 1e3 / ns_p:+.1f} ns/row)")
for K in [1, 10, 20]:
    b_i2f = pure["float64"]["only_ser"].get(K)
    b_f2i = pure["float64"]["only_deser"].get(K)
    print(f"K={K}: serde_i2f {mixed['i2f']['serde'].get(K, float('nan')):.1f} <= float-ser bound {b_i2f:.1f} ; "
          f"serde_f2i {mixed['f2i']['serde'].get(K, float('nan')):.1f} <= float-parse bound {b_f2i:.1f}")
