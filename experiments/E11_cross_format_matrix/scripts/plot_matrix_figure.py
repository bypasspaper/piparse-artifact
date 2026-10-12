#!/usr/bin/env python3
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Artifact copy of ~/Notes/nebulastream/benchmark/matrix_2026-08-05/plot_matrix_figure.py. Changes: parquet inputs read
from ../data/ (DATA), outputs to ../out/ (OUT), and the computed 4x4 table is also written to ../out/matrix_table_v2.csv
(in,out,comp,par,total,dagger,base_anchor_mrows) for a numeric check against expected/MATRIX_RESULTS_2026-08-05.md v2.

The paper's main figure: the 4x4 input x output matrix, cell = Total (bold) over
Compilation | Parallelization (the frozen cell anatomy, PAPER_WORKLOAD.md §1).
Data: matrix_runs_all1440.parquet in this directory (per-run rows; medians + regime
geomeans computed here from raw, so the figure is regenerable from first principles).
Cell background = sequential blue ramp (validated dataviz reference palette) encoding
Total; all text in ink tokens. Emits MATRIX_FIGURE_2026-08-05.{pdf,png}.
Run: cd ~/work/piparse-bench && uv run python <this file>
"""
import math
import pathlib
import statistics

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = pathlib.Path(__file__).resolve().parent.parent / "data"   # parquet inputs
OUT = pathlib.Path(__file__).resolve().parent.parent / "out"; OUT.mkdir(exist_ok=True)
REPEAT = 20.0
FORMATS = ["csv", "json", "hl7", "xml"]
LABEL = {"csv": "CSV", "json": "JSON", "hl7": "HL7", "xml": "XML"}
REGIMES = [["q0"], ["qproject"], ["qroute", "q2og", "q2mod"], ["q1", "q10", "q14"], ["q22"], ["qex"]]

## dataviz reference palette: sequential blue steps 100..700 + ink tokens + surface
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
       "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281"]
SURFACE, INK, INK2 = "#fcfcfb", "#0b0b0b", "#52514e"
INK_ON_DARK, INK2_ON_DARK = "#ffffff", "#dbe7f6"

con = duckdb.connect(str(HERE / "matrix_runs_all1440.parquet".replace(".parquet", "")) + ".duckdb" if False else ":memory:")
## r_base/r_comp from the original run; r_par from the FIXED re-run (2026-08-06: the
## ccx_aware+pin combination was a ~2x single-source pathology; r_par convention is now
## W23 + ccx_aware=false + pin_threads=false -- see MATRIX_RESULTS v2 + the handover).
rows = con.execute(f"""
    SELECT experiment, variant, series, median(throughput_mbps) m, geomean(throughput_mrows_s) mr
    FROM read_parquet('{HERE}/matrix_runs_all1440.parquet') WHERE series != 'r_par'
    GROUP BY experiment, variant, series
    UNION ALL
    SELECT replace(experiment, '_rparfix', ''), variant, series, median(throughput_mbps), geomean(throughput_mrows_s)
    FROM read_parquet('{HERE}/matrix_rpar_fixed_480.parquet')
    GROUP BY 1, variant, series
""").fetchall()
med = {}
for exp, var, ser, m, mr in rows:
    med.setdefault(exp.removeprefix("cell_"), {}).setdefault(var, {})[ser] = (m, mr)

## Wall-clip detection (dagger): a cell is a memory-wall-bounded LOWER BOUND when >= half
## its queries run at >= 85% of the measured ~66 GB/s aggregate wire ceiling at W23.
WALL_GBPS = 56.0
clip_rows = con.execute(f"""
    SELECT replace(experiment,'_rparfix',''), count(*) FILTER (g >= {WALL_GBPS}) FROM (
      SELECT experiment, variant, median(throughput_mbps)*{REPEAT}/1000 g
      FROM read_parquet('{HERE}/matrix_rpar_fixed_480.parquet') GROUP BY 1,2)
    GROUP BY 1
""").fetchall()
clipped = {e.removeprefix('cell_'): (n >= 5) for e, n in clip_rows}

gm = lambda v: math.exp(sum(map(math.log, v)) / len(v))
table, base_anchor = {}, {}
for i in FORMATS:
    anchors = []
    for o in FORMATS:
        qs = med[f"{i}_{o}"]
        comp = {q: s["r_comp"][0] / s["r_base"][0] for q, s in qs.items()}
        par = {q: s["r_par"][0] * REPEAT / s["r_comp"][0] for q, s in qs.items()}
        rg = lambda d: gm([gm([d[q] for q in reg]) for reg in REGIMES])
        table[(i, o)] = (rg(comp), rg(par), rg(comp) * rg(par))
        anchors += [s["r_base"][1] for s in qs.values()]
    base_anchor[i] = gm(anchors)

## ---- layout ----
FW, FH = 7.6, 6.35
fig = plt.figure(figsize=(FW, FH), dpi=200)
fig.patch.set_facecolor(SURFACE)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, FW); ax.set_ylim(0, FH); ax.axis("off")

L, T = 1.22, 0.62          # left header column width / top header row height
CW, CH, GAP = 1.44, 0.86, 0.045
gx0, gy0 = L, FH - 0.68 - T  # grid top-left (y measured downward from here)

tmin, tmax = 45.0, 228.0
def cell_color(total):
    t = math.sqrt((total - tmin) / (tmax - tmin))
    return SEQ[min(len(SEQ) - 1, max(0, round(t * (len(SEQ) - 1))))]

fig.text(0.06 / FW, 1 - 0.30 / FH, "Compilation and parallelization gains generalize across formats",
         fontsize=12.5, fontweight="bold", color=INK, ha="left", va="center")
fig.text(0.06 / FW, 1 - 0.56 / FH,
         "Speedup over the fully-interpreted baseline, geomean of regime geomeans over the 10-query workload  ·  bid_strings, 31.3M rows",
         fontsize=8, color=INK2, ha="left", va="center")

## column headers (output formats) + corner
ax.text(gx0 - 0.10, gy0 + 0.30, "input", fontsize=8.5, color=INK2, ha="right", va="center", style="italic")
ax.text(gx0 + (4 * CW + 3 * GAP) / 2, gy0 + 0.52, "output format", fontsize=8.5, color=INK2,
        ha="center", va="center", style="italic")
for c, o in enumerate(FORMATS):
    x = gx0 + c * (CW + GAP)
    ax.text(x + CW / 2, gy0 + 0.28, LABEL[o], fontsize=10.5, fontweight="bold", color=INK, ha="center", va="center")

for r, i in enumerate(FORMATS):
    y = gy0 - r * (CH + GAP) - CH
    ax.text(gx0 - 0.14, y + CH / 2 + 0.10, LABEL[i], fontsize=10.5, fontweight="bold", color=INK, ha="right", va="center")
    ax.text(gx0 - 0.14, y + CH / 2 - 0.13, f"base {base_anchor[i]:.2f} Mrows/s",
            fontsize=6.6, color=INK2, ha="right", va="center")
    for c, o in enumerate(FORMATS):
        x = gx0 + c * (CW + GAP)
        comp, par, total = table[(i, o)]
        bg = cell_color(total)
        dark = SEQ.index(bg) >= 7
        ink, ink2 = (INK_ON_DARK, INK2_ON_DARK) if dark else (INK, INK2)
        ax.add_patch(FancyBboxPatch((x, y), CW, CH, boxstyle="round,pad=0,rounding_size=0.05",
                                    facecolor=bg, edgecolor="none"))
        ## total (bold, top); dagger = memory-wall-clipped lower bound
        dag = "\u2020" if clipped.get(f"{i}_{o}") else ""
        ax.text(x + CW / 2, y + CH - 0.27, f"{total:.0f}×{dag}", fontsize=15.5, fontweight="bold",
                color=ink, ha="center", va="center")
        ## divider + the two factors
        ax.plot([x + 0.13, x + CW - 0.13], [y + 0.335, y + 0.335], color=ink2, lw=0.5, alpha=0.55)
        ax.plot([x + CW / 2, x + CW / 2], [y + 0.075, y + 0.29], color=ink2, lw=0.5, alpha=0.55)
        ax.text(x + CW * 0.27, y + 0.185, f"{comp:.1f}×", fontsize=8.8, color=ink, ha="center", va="center")
        ax.text(x + CW * 0.73, y + 0.185, f"{par:.1f}×", fontsize=8.8, color=ink, ha="center", va="center")

## anatomy key (bottom left) — one schematic cell, labeled
kx, ky, kw, kh = 0.30, 0.46, 1.30, 0.74
ax.add_patch(FancyBboxPatch((kx, ky), kw, kh, boxstyle="round,pad=0,rounding_size=0.05",
                            facecolor="#eef1f4", edgecolor="#c9ccd1", linewidth=0.6))
ax.text(kx + kw / 2, ky + kh - 0.22, "total", fontsize=10.5, fontweight="bold", color=INK, ha="center", va="center")
ax.plot([kx + 0.11, kx + kw - 0.11], [ky + 0.30, ky + 0.30], color=INK2, lw=0.5, alpha=0.55)
ax.plot([kx + kw / 2, kx + kw / 2], [ky + 0.06, ky + 0.26], color=INK2, lw=0.5, alpha=0.55)
ax.text(kx + kw * 0.27, ky + 0.165, "comp.", fontsize=7.4, color=INK2, ha="center", va="center")
ax.text(kx + kw * 0.73, ky + 0.165, "par.", fontsize=7.4, color=INK2, ha="center", va="center")
ax.annotate("gain over interpreted baseline\n(rungs cumulative: total = comp. × par.)",
            xy=(kx + kw + 0.08, ky + kh - 0.20), fontsize=7.2, color=INK2, ha="left", va="center")
ax.annotate("× from compilation (JIT, W1)", xy=(kx + kw + 0.08, ky + 0.34), fontsize=7.2, color=INK2, ha="left", va="center")
ax.annotate("× from parallelization (23 workers)", xy=(kx + kw + 0.08, ky + 0.14), fontsize=7.2, color=INK2, ha="left", va="center")

fig.text(1 - 0.06 / FW, 0.16 / FH,
         "† memory-wall-clipped lower bound: ≥ half the workload runs ≥ 85% of the ~66 GB/s aggregate ceiling at 23 workers\n"
         "(filter-class queries touch the wall in every cell). in-memory sources isolate processing from I/O — the source is never the binder.\n"
         "baselines hand-implement identical codecs; interpreted rung materializes full records.",
         fontsize=6.8, color=INK2, ha="right", va="center")

for ext in ("pdf", "png"):
    fig.savefig(OUT / f"MATRIX_FIGURE_2026-08-05.{ext}", facecolor=SURFACE, bbox_inches="tight")
print("written", OUT / "MATRIX_FIGURE_2026-08-05.pdf")
import csv
with open(OUT / "matrix_table_v2.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["in", "out", "comp", "par", "total", "dagger", "base_anchor_mrows"])
    for i in FORMATS:
        for o in FORMATS:
            comp, par, total = table[(i, o)]
            w.writerow([i, o, f"{comp:.2f}", f"{par:.2f}", f"{total:.2f}", int(bool(clipped.get(f"{i}_{o}"))), f"{base_anchor[i]:.3f}"])
            print(f"{i:>4} -> {o:<4}  total {total:6.1f} = comp {comp:4.1f} x par {par:4.1f}{' †' if clipped.get(f'{i}_{o}') else ''}")
print("written", OUT / "matrix_table_v2.csv")
