#!/usr/bin/env python3
# Artifact copy of fig1_fig2_teaser_2026-09-25_scratch/plot_fig2_v2.py (2026-09-25). Changes: Flink medians read from
# ../data/fig2_flink_data.csv (the 2026-09-03 Flink field sweep, fig2_flink_fieldsweep run_group 20260903T155730-7d699aad);
# defaults = ../data/fig2_v2_rowss_mbps_2026-09-25_data.csv -> ../out/fig2_v2_rowss_mbps_3rung (or _teaser with --teaser).
"""Fig2 v2 (2026-09-25): rows/s and MB/s vs fields-per-row N, three NES rungs + Flink.
usage: plot_fig2_v2.py <exp_data.csv> <out_stem> [--teaser]
  --teaser  omit the compiled_eager rung (Sec.2 version: baselines + fully optimised); default = all four (evaluation).
Input CSV columns: rung,N,input_MBps,throughput_Mrows_s,ns_per_row,reps (from extract_fig2_v2.py).
Flink medians read from the 2026-09-03 scratch CSV. Palette validated 2026-09-25 (dataviz validator):
NES rungs = ordinal Blues ramp #6BAED6/#3182BD/#08519C (light->dark = naive->lazy); Flink = #D55E00.
Identity is never colour-alone: distinct markers + direct labels at the right end of every line."""
import csv, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
FLINK_CSV = str(HERE / "data/fig2_flink_data.csv")
SERIES = [  # key, label, colour, marker, linestyle
    ("naive",          "NES naive (interpreted, stod/stringstream)", "#6BAED6", "s", "-"),
    ("compiled_eager", "NES compiled, eager parse (no passthrough)", "#3182BD", "^", "--"),
    ("compiled_lazy",  "NES compiled, lazy passthrough",            "#08519C", "o", "-"),
    ("flink",          "Apache Flink 2.1 (csv→json)",              "#D55E00", "D", "-"),
]
SHORT = {"naive": "NES naive", "compiled_eager": "NES eager", "compiled_lazy": "NES lazy", "flink": "Flink"}
plt.rcParams.update({"font.size": 11, "font.family": "sans-serif", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#444444", "axes.linewidth": 0.8})

def load_nes(path):
    d = {}
    for r in csv.DictReader(open(path)):
        d.setdefault(r["rung"], {})[int(r["N"])] = (float(r["input_MBps"]), float(r["throughput_Mrows_s"]))
    return d

def load_flink(path):
    return {int(r["N_fields"]): (float(r["input_MBps"]), float(r["throughput_Mrows_s"])) for r in csv.DictReader(open(path))}

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; teaser = "--teaser" in sys.argv
    _in = args[0] if args else str(HERE / "data/fig2_v2_rowss_mbps_2026-09-25_data.csv")
    stem = args[1] if len(args) > 1 else str(HERE / ("out/fig2_v2_rowss_mbps_teaser" if teaser else "out/fig2_v2_rowss_mbps_3rung"))
    Path(stem).parent.mkdir(parents=True, exist_ok=True)
    data = load_nes(_in); data["flink"] = load_flink(FLINK_CSV)
    series = [s for s in SERIES if s[0] in data and not (teaser and s[0] == "compiled_eager")]
    fig, (a, b) = plt.subplots(1, 2, figsize=(11.0, 4.1))
    for key, label, col, mk, ls in series:
        pts = sorted(data[key].items()); N = [p[0] for p in pts]
        rows = [p[1][1] for p in pts]; mb = [p[1][0] for p in pts]
        for ax, y in ((a, rows), (b, mb)):
            ax.plot(N, y, ls, color=col, linewidth=2, marker=mk, markersize=6.5, markeredgecolor="white", markeredgewidth=1.0, label=label)
            ax.annotate(SHORT[key], (N[-1], y[-1]), textcoords="offset points", xytext=(7, 0), va="center", ha="left", fontsize=9, color="#222222")
    a.set_yscale("log"); a.set_ylabel("Throughput  (million rows/s)")
    a.set_title("(a) rows/s falls with N on every engine and rung", loc="left", fontsize=11)
    b.set_yscale("log"); b.set_ylabel("Input throughput  (MB/s, log)")
    b.set_title("(b) input MB/s of the same runs", loc="left", fontsize=11)
    for ax in (a, b):
        ax.set_xlabel("Fields per row  N"); ax.set_xticks(range(1, 11)); ax.set_xlim(0.6, 12.4)
        ax.set_axisbelow(True); ax.grid(axis="both", color="#E4E4E4", linewidth=0.7)
    h, l = a.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, 0.86), ncol=2, frameon=False, fontsize=9.2)
    fig.subplots_adjust(top=0.77, bottom=0.15, left=0.07, right=0.99, wspace=0.26)
    fig.savefig(stem + ".pdf", bbox_inches="tight"); fig.savefig(stem + ".png", dpi=170, bbox_inches="tight"); print("wrote", stem + ".{pdf,png}")

if __name__ == "__main__":
    main()
