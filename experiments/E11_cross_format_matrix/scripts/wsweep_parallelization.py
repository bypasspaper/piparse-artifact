# SPDX-License-Identifier: Apache-2.0
# Artifact copy of ~/Notes/nebulastream/benchmark/matrix_2026-08-05/wsweep_parallelization_2026-08-06.py. Changes: the 2-rep
# medians are read from ../data/wsweep_output_plateau_raw.csv (DB export, scripts/extract_wsweep_from_db.py) and asserted
# against the values hardcoded in the original (kept below as *_ORIG); output ../out/wsweep_parallelization.
"""Parallelization W-sweep figure: q0 passthrough, csv->csv vs csv->json, W1->W23.

Data = wsweep_output_plateau (2026-08-06c, 2-rep medians, healthy r-par config:
ccx_aware=false, pin_threads=false, InMemory prefill, NES_INMEM_REPEAT=20 -> true = x20).
Machine = TR PRO 5965WX, 23 workers + 1 source thread = 24 physical cores (locked W23
convention; SMT unused). Mechanism behind the csv->json plateau: store-queue-full dispatch
stalls in the field-wise serializer -> OUTPUT_PLATEAU_PROBE_RESULTS.md.

Palette = dataviz reference categorical slots 1-2 (validated: all checks pass; tritan
dE 7.6 in the 6-8 band -> secondary encoding via distinct markers + direct labels).
"""
import matplotlib.pyplot as plt
import csv, statistics, pathlib
HERE = pathlib.Path(__file__).resolve().parent.parent

W = [1, 2, 4, 8, 12, 16, 20, 23]
CSV_MBPS_ORIG = [263.8, 475.8, 897.4, 1693.4, 2358.8, 2905.0, 3244.9, 3404.1]  # reported, x20=true (2026-08-06 script)
JSON_MBPS_ORIG = [130.9, 240.2, 429.7, 692.8, 792.0, 811.0, 830.5, 829.3]
_rows = list(csv.DictReader(open(HERE / "data/wsweep_output_plateau_raw.csv")))
def _med(variant):
    return [statistics.median(float(r["throughput_mbps_reported"]) for r in _rows if r["variant"] == variant and int(r["worker_threads"]) == w) for w in W]
CSV_MBPS, JSON_MBPS = _med("csvcsv_q0"), _med("csvjson_q0")
for a, b in zip(CSV_MBPS + JSON_MBPS, CSV_MBPS_ORIG + JSON_MBPS_ORIG):
    assert abs(a / b - 1) < 0.002, (a, b)
print("DB medians match the 2026-08-06 hardcoded values within 0.2 %")

csv_gbs = [m * 20 / 1000 for m in CSV_MBPS]
json_gbs = [m * 20 / 1000 for m in JSON_MBPS]
csv_su = [m / CSV_MBPS[0] for m in CSV_MBPS]
json_su = [m / JSON_MBPS[0] for m in JSON_MBPS]

BLUE, GREEN = "#2a78d6", "#008300"       # categorical slots 1-2 (light)
SURFACE, INK, INK2 = "#fcfcfb", "#0b0b0b", "#52514e"
GRID, IDEAL = "#e8e7e4", "#b9b8b4"

fig, (axL, axR) = plt.subplots(1, 2, figsize=(9.2, 3.7), dpi=200)
fig.patch.set_facecolor(SURFACE)
fig.subplots_adjust(left=0.075, right=0.945, top=0.80, bottom=0.145, wspace=0.30)

for ax in (axL, axR):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.grid(axis="y", color=GRID, lw=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.set_xticks(W)
    ax.set_xlim(0, 24.4)
    ax.set_xlabel("worker threads", fontsize=8.5, color=INK2)

MK = dict(markeredgecolor=SURFACE, markeredgewidth=1.0, clip_on=False)

# ---- left: absolute true throughput --------------------------------------
axL.plot(W, csv_gbs, "-o", color=BLUE, lw=1.8, ms=5, **MK)
axL.plot(W, json_gbs, "-s", color=GREEN, lw=1.8, ms=4.6, **MK)
axL.set_ylim(0, 74)
axL.set_ylabel("true throughput (GB/s, input wire)", fontsize=8.5, color=INK2)
axL.text(23.7, csv_gbs[-1], f"{csv_gbs[-1]:.0f}", fontsize=8.5, color=INK,
         fontweight="bold", ha="left", va="center")
axL.text(23.7, json_gbs[-1], f"{json_gbs[-1]:.1f}", fontsize=8.5, color=INK,
         fontweight="bold", ha="left", va="center")
axL.annotate("flat from W12 —\nstore-queue stall ceiling", xy=(14, 16.2), xytext=(11.3, 27.5),
             fontsize=7.3, color=INK2, ha="center",
             arrowprops=dict(arrowstyle="-", color=INK2, lw=0.6, shrinkB=2))
axL.set_title("throughput", fontsize=9.5, color=INK, pad=6)

# ---- right: speedup over W1 ----------------------------------------------
axR.plot([0, 24.4], [0, 24.4], "--", color=IDEAL, lw=1.1)
axR.text(13.35, 15.0, "ideal ×W", fontsize=7.3, color=INK2, rotation=63,
         ha="center", va="center")
axR.plot(W, csv_su, "-o", color=BLUE, lw=1.8, ms=5, **MK)
axR.plot(W, json_su, "-s", color=GREEN, lw=1.8, ms=4.6, **MK)
axR.set_ylim(0, 16.4)
axR.set_yticks([0, 4, 8, 12, 16])
axR.set_ylabel("speedup over W1", fontsize=8.5, color=INK2)
axR.text(23.7, csv_su[-1], f"{csv_su[-1]:.1f}×", fontsize=8.5, color=INK,
         fontweight="bold", ha="left", va="center")
axR.text(23.7, json_su[-1], f"{json_su[-1]:.1f}×", fontsize=8.5, color=INK,
         fontweight="bold", ha="left", va="center")
axR.set_title("scaling", fontsize=9.5, color=INK, pad=6)

# ---- legend + titles ------------------------------------------------------
handles = [plt.Line2D([], [], color=BLUE, lw=1.8, marker="o", ms=5,
                      markeredgecolor=SURFACE, label="csv→csv  (coalesced output)"),
           plt.Line2D([], [], color=GREEN, lw=1.8, marker="s", ms=4.6,
                      markeredgecolor=SURFACE, label="csv→json  (field-wise output)")]
axL.legend(handles=handles, loc="upper left", fontsize=7.6, frameon=False,
           handlelength=1.8, borderaxespad=0.1, labelcolor=INK)

fig.text(0.075, 0.945, "Parallelization: q0 passthrough (csv input), W1 → W23",
         fontsize=11.5, fontweight="bold", color=INK)
fig.text(0.075, 0.875, "healthy r-par config (ccx off, pin off) · InMemory ×20 · 2-rep medians · "
                       "TR PRO 5965WX: 23 workers + 1 source thread = 24 physical cores",
         fontsize=7.6, color=INK2)

out = HERE / "out" / "wsweep_parallelization"; out.parent.mkdir(exist_ok=True)
fig.savefig(f"{out}.png", facecolor=SURFACE)
fig.savefig(f"{out}.pdf", facecolor=SURFACE)
print(f"wrote {out}.png / .pdf")
