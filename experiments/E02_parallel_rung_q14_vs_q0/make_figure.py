#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""W-sweep figure for the par-rung decomposition (PAR_RUNG_Q14_VS_Q0_2026-10-06.md §4): q0 (SELECT *, csv->json) plateaus
from W12 at the field-wise JSON serializer ceiling while q14 (computed-float range filter, 3 numeric output columns) keeps
scaling at 73 % of linear to W23; the NATIVE-output arms show the text serializer costs q0 31 % and q14 6 % at W23.
No figure existed for this element before the artifact (the paper cites the table); this draws two panels from
data/wsweep_q14_vs_q0.csv (written by extract.py): (a) true input GB/s vs workers, (b) per-worker Mrows/s vs workers.
Usage: make_figure.py [--csv data/wsweep_q14_vs_q0.csv] [--out out/]"""
import argparse, csv
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--csv", default=str(HERE / "data" / "wsweep_q14_vs_q0.csv"))
ap.add_argument("--out", default=str(HERE / "out"))
A = ap.parse_args()
rows = list(csv.DictReader(open(A.csv)))
arms = {}
for r in rows:
    arms.setdefault(r["variant"], []).append((int(r["workers"]), float(r["true_mbps"]) / 1000, float(r["per_worker_mrows_s"])))
style = {"q0_json": ("q0 SELECT * → JSON", "#c0392b", "o", "-"), "q14_json": ("q14 range filter → JSON", "#1f618d", "s", "-"),
         "q0_native": ("q0 → NATIVE output", "#c0392b", "o", "--"), "q14_native": ("q14 → NATIVE output", "#1f618d", "s", "--")}
plt.rcParams.update({"font.size": 11, "svg.fonttype": "none"})
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
for arm in ["q0_json", "q14_json", "q0_native", "q14_native"]:
    if arm not in arms:
        continue
    pts = sorted(arms[arm]); lab, col, mk, ls = style[arm]
    ax1.plot([p[0] for p in pts], [p[1] for p in pts], marker=mk, color=col, ls=ls, label=lab)
    ax2.plot([p[0] for p in pts], [p[2] for p in pts], marker=mk, color=col, ls=ls, label=lab)
w = sorted({p[0] for v in arms.values() for p in v})
w1 = {a: sorted(v)[0][1] for a, v in arms.items()}
ax1.plot(w, [w1["q14_json"] * x for x in w], color="#999", ls=":", lw=1, label="linear from q14 W1")
ax1.axhspan(21, 30, color="#f5b7b1", alpha=0.35, lw=0, label="serializer plateau band (output 21–30 GB/s ÷ 1.55 B/B for q0)")
ax1.set_xlabel("worker threads (+1 source, +1 io)"); ax1.set_ylabel("input throughput, true GB/s (reported × 20)")
ax1.set_title("(a) q0 clips at the JSON output ceiling, q14 keeps scaling"); ax1.set_xticks(w); ax1.grid(alpha=0.3); ax1.legend(fontsize=8.5, loc="upper left")
ax2.set_xlabel("worker threads"); ax2.set_ylabel("per-worker Mrows/s (true)"); ax2.set_title("(b) per-worker productivity: q0 collapses 3.7×, q14 −23 %")
ax2.set_xticks(w); ax2.grid(alpha=0.3); ax2.legend(fontsize=8.5)
fig.suptitle("Parallel rung W-sweep at the r7 config (InMemory, SIMDCSV PARALLEL, fnattr+inline+tcb, 128 KiB buffers), Threadripper PRO 5965WX", fontsize=11)
fig.tight_layout()
out = Path(A.out); out.mkdir(parents=True, exist_ok=True)
for ext in ("png", "svg"):
    fig.savefig(out / f"wsweep_q14_vs_q0.{ext}", dpi=140, bbox_inches="tight", facecolor="white")
print("wrote", out / "wsweep_q14_vs_q0.{png,svg}")
