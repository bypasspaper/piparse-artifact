#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""E05 orchestrator: regenerate the paper-structure 5-arm CSVs (stateless 10 queries, stateful 3 queries) from the
pbench results DB + the Aug-14 CORRECTED per-rep raw CSV, then draw the head-to-head bar figure from them.

  python3 make_figure.py            # out/stateless_5arm_paper_regen.csv, out/stateful_5arm_paper_regen.csv,
                                    # out/native_native_w23_regen.csv, out/simd_csvnative_w23_regen.csv,
                                    # out/head_to_head_5arm.{png,pdf}
  python3 make_figure.py --verify   # ... and diff the four regenerated CSVs against the shipped data/ copies
  python3 make_figure.py --db PATH  # another pbench DuckDB (default ../../results/tr/piparse_bench.duckdb or $PBENCH_DB)

NOTE on the figure: the submission's `expected/nes_vs_flink_vs_spark_5arm_2026-08-14_CORRECTED.{png,pdf}` was drawn
by an ad-hoc script that was not preserved in the Notes tree. `plot_5arm()` below is a minimal re-implementation
(grouped bars, log-y records/s, med with lo/hi whiskers = med-min / max-med over reps) drawn from the regenerated
paper CSVs, i.e. from the ONE-CODE-STATE columns (tip naive/simd/native->native + Aug-14 Flink/Spark) rather than
the Aug-14 CORRECTED 5-arm run the expected PNG shows (see README §Caveats for the column provenance).
"""
import csv
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
dbargs = []
if "--db" in sys.argv:
    i = sys.argv.index("--db"); dbargs = ["--db", sys.argv[i + 1]]
verify = "--verify" in sys.argv


def run_to(script, outname):
    """The original scripts print their CSV to stdout; capture it into out/<outname>."""
    cmd = [sys.executable, str(HERE / script), *dbargs]
    print("$", script, ">", f"out/{outname}", flush=True)
    res = subprocess.run(cmd, check=True, cwd=HERE, capture_output=True, text=True)
    (OUT / outname).write_text(res.stdout)


run_to("make_paper_csv.py", "stateless_5arm_paper_regen.csv")
run_to("make_stateful_csv.py", "stateful_5arm_paper_regen.csv")
run_to("extract_native_regen.py", "native_native_w23_regen.csv")
run_to("extract_simd_csvnative_regen.py", "simd_csvnative_w23_regen.csv")


def plot_5arm(stateless_csv, stateful_csv, outstem):
    arms = [  # (csv prefix, label, color)
        ("naive", "NES naive (interpreted, W1)", "#9ca3af"),
        ("flink", "Flink (p=23)", "#e76f51"),
        ("spark", "Spark (local[23])", "#f4a261"),
        ("simd", "NES optimised (csv→JSON, W23)", "#1f6fb2"),
        ("native", "NES native→native (no serde, W23)", "#111111"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [10, 3.4]}, sharey=True)
    for ax, path, title in ((axes[0], stateless_csv, "stateless tier (bid_strings, 31.3 M rows)"),
                            (axes[1], stateful_csv, "stateful tier")):
        rows = list(csv.DictReader(open(path)))
        x = np.arange(len(rows)); width = 0.16
        for k, (pfx, label, col) in enumerate(arms):
            med = np.array([float(r[f"{pfx}_med"]) for r in rows])
            lo = np.array([float(r[f"{pfx}_lo"]) for r in rows])
            hi = np.array([float(r[f"{pfx}_hi"]) for r in rows])
            ax.bar(x + (k - 2) * width, med, width, yerr=[lo, hi], color=col, edgecolor="white", linewidth=0.4,
                   error_kw=dict(lw=0.8, capsize=1.5, ecolor="#444"), label=label if ax is axes[0] else None, zorder=3)
        ax.set_xticks(x)
        ax.set_xticklabels([r["query"] for r in rows], rotation=0 if len(rows) > 5 else 15, fontsize=9)
        ax.set_yscale("log")
        ax.grid(True, axis="y", which="both", alpha=0.22)
        ax.set_title(title, fontsize=10)
    axes[0].set_ylabel("throughput  [M records/s, log]")
    axes[0].legend(frameon=False, fontsize=8.5, loc="upper left", ncol=2)
    fig.suptitle("Head-to-head records/s on the Threadripper PRO 5965WX — median of 10 reps, whiskers = min/max", fontsize=10.5)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(f"{outstem}.{ext}", dpi=150, bbox_inches="tight")
    print(f"wrote {outstem}.png / .pdf")


plot_5arm(OUT / "stateless_5arm_paper_regen.csv", OUT / "stateful_5arm_paper_regen.csv", OUT / "head_to_head_5arm")


def compare_csv(a: Path, b: Path, rel=1e-6):
    ra, rb = list(csv.reader(open(a))), list(csv.reader(open(b)))
    if ra[0] != rb[0]:
        return False, f"header differs: {ra[0]} vs {rb[0]}"
    if len(ra) != len(rb):
        return False, f"row count {len(ra) - 1} vs {len(rb) - 1}"
    worst, bad = 0.0, []
    for i, (x, y) in enumerate(zip(ra[1:], rb[1:]), start=2):
        for j, (u, v) in enumerate(zip(x, y)):
            if u == v:
                continue
            try:
                fu, fv = float(u), float(v)
            except ValueError:
                bad.append(f"row {i} col {ra[0][j]}: {u!r} vs {v!r}"); continue
            d = abs(fu - fv) / max(abs(fv), 1e-12)
            worst = max(worst, d)
            if d > rel:
                bad.append(f"row {i} col {ra[0][j]}: {u} vs {v} (rel {d:.2e})")
    return (not bad), (f"{len(ra) - 1} rows, max rel dev {worst:.1e}" + (f"; {len(bad)} cells differ: " + "; ".join(bad[:5]) if bad else ""))


if verify:
    print("\n== verification: out/ vs shipped data/ ==")
    allok = True
    for name in ("stateless_5arm_paper_regen.csv", "stateful_5arm_paper_regen.csv",
                 "native_native_w23_regen.csv", "simd_csvnative_w23_regen.csv"):
        ok, msg = compare_csv(OUT / name, HERE / "data" / name)
        allok &= ok
        print(f"  {'MATCH   ' if ok else 'MISMATCH'} {name}: {msg}")
    sys.exit(0 if allok else 1)
