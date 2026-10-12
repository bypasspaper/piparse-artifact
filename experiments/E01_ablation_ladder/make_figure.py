#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Ablation ladder figure, v8 = the v7 ladder (r1..r6b W1 InMemory, r7 W23) with the two new compile-rung
splits spliced between r2 and r3: r3_eager_all (compiled, parse-all = work-equal to r2) and r3_lazy_nopass
(compiled, lazy values, no passthrough). No v8 figure script existed before the artifact; styling follows
~/Notes/nebulastream/benchmark/2_engine_to_e2e/figures/make_ablation_ladder_v5.py.

Inputs (relative to this file)
  data/ablation_ladder_v8_bidstr.csv        r1,r2,r3_eager_all,r3_eager_fast,r3_eager,r3_lazy_nopass,r3,r4,r5,r6,r6b
                                            (MB/s medians on the v7 footing; new rungs = r3_v7 x same-session ratio)
  data/ablation_ladder_v7_bidstr.csv        r7_true (W23 parallel rung, NES_INMEM_REPEAT x20 already applied);
                                            the v8 CSV carries NO r7 column, so r7 is taken from v7.
  --mrows: the *_mrows twins (Mrows/s; 114.87 B/row), r7 from v7's r7_mrows column.
Outputs: out/ablation_ladder_v8[_all][_mrows].{png,svg}, out/lever_geomeans[_all][_mrows].csv (+ a printed table
with the handover's reference geomeans next to the recomputed ones).
"""
import argparse, csv, math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator, ScalarFormatter

HERE = Path(__file__).resolve().parent
PAPER = ["r1", "r2", "r3_eager_all", "r3_lazy_nopass", "r3", "r4", "r5", "r6", "r6b", "r7"]
ALL = ["r1", "r2", "r3_eager_all", "r3_eager_fast", "r3_eager", "r3_lazy_nopass", "r3", "r4", "r5", "r6", "r6b", "r7"]
# v9 (2026-10-12 re-measurement, paper policy "overloads ON on the top two rungs"): r6b_ovl replaces the pre-fix r6b and
# r7_ovl replaces the overload-OFF r7. Used automatically when data/ablation_ladder_v9_bidstr.csv exists (--v8 forces v8).
PAPER_V9 = ["r1", "r2", "r3_eager_all", "r3_lazy_nopass", "r3", "r4", "r5", "r6", "r6b_ovl", "r7_ovl"]
ALL_V9 = ["r1", "r2", "r3_eager_all", "r3_eager_fast", "r3_eager", "r3_lazy_nopass", "r3", "r4", "r5", "r6", "r6b", "r6b_ovl", "r7", "r7_ovl"]
LABEL = {
    "r1": "r1 interpreted, scalar index",
    "r2": "r2 interpreted, SIMD index",
    "r3_eager_all": "r3a compiled, parse-all (work-equal)",
    "r3_eager_fast": "r3b compiled, eager numerics (Fast twins)",
    "r3_eager": "r3c compiled, eager (paper parsers)",
    "r3_lazy_nopass": "r3d compiled, lazy, no passthrough",
    "r3": "r3 compiled, lazy + passthrough",
    "r4": "r4 +fnattr (GVN parse dedup)",
    "r5": "r5 +inline",
    "r6": "r6 +output fast path (+tcb)",
    "r6b": "r6b +overload (2026-08-24, pre-fix path)",
    "r6b_ovl": "r6b +lazy overloads (ON, re-measured 2026-10-12)",
    "r7": "r7 parallel W23 (overloads OFF, 2026-08-24)",
    "r7_ovl": "r7 parallel W23 (overloads ON, re-measured 2026-10-12)",
}
# reference geomeans from ABLATION_LADDER_V7_HANDOVER.md §3 and ablation_eager_irdump RESULT.md step 3
REF = {("r1", "r2"): 1.08, ("r2", "r3"): 3.56, ("r2", "r3_eager_all"): 1.88, ("r3_eager_all", "r3_lazy_nopass"): 1.50,
       ("r3_lazy_nopass", "r3"): 1.26, ("r3", "r4"): 1.12, ("r4", "r5"): 1.18, ("r5", "r6"): 1.25, ("r6", "r6b"): 1.08,
       ("r6b", "r7"): 9.73}
QUERIES = ["q0", "qproject", "qroute", "q1", "q2og", "q2mod", "q10", "q14", "q22", "qex"]


def load(mrows: bool, force_v8: bool = False):
    v9 = HERE / "data" / ("ablation_ladder_v9_bidstr_mrows.csv" if mrows else "ablation_ladder_v9_bidstr.csv")
    if v9.exists() and not force_v8:
        # v9 carries every column incl. r6b_ovl, r7 (OFF, = v7 r7_true) and r7_ovl -> no v7 lookup needed
        return {r["variant"]: {k: float(v) for k, v in r.items() if k != "variant"} for r in csv.DictReader(open(v9))}, "v9"
    v8 = HERE / "data" / ("ablation_ladder_v8_bidstr_mrows.csv" if mrows else "ablation_ladder_v8_bidstr.csv")
    v7 = HERE / "data" / ("ablation_ladder_v7_bidstr_mrows.csv" if mrows else "ablation_ladder_v7_bidstr.csv")
    data = {r["variant"]: {k: float(v) for k, v in r.items() if k != "variant"} for r in csv.DictReader(open(v8))}
    r7col = "r7_mrows" if mrows else "r7_true"
    for r in csv.DictReader(open(v7)):
        data[r["variant"]]["r7"] = float(r[r7col])
    return data, "v8"


def gm(xs):
    return math.exp(sum(math.log(x) for x in xs) / len(xs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="show every column (adds r3_eager_fast, r3_eager)")
    ap.add_argument("--mrows", action="store_true", help="plot Mrows/s instead of MB/s")
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--v8", action="store_true", help="force the v8 ladder (pre-fix r6b, overload-OFF r7) even if v9 data exists")
    a = ap.parse_args()
    data, version = load(a.mrows, a.v8)
    if version == "v9":
        rungs = ALL_V9 if a.all else PAPER_V9
    else:
        rungs = ALL if a.all else PAPER
    variants = [q for q in QUERIES if q in data]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    suffix = ("_all" if a.all else "") + ("_mrows" if a.mrows else "")

    # ---- per-lever geomeans (ratio of adjacent rungs, geomean over the 10 queries) ----
    rows = []
    print(f"{'lever':<36s} {'geomean':>8s} {'min':>6s} {'max':>6s}  {'(min q, max q)':<20s} {'ref':>6s}")
    for lo, hi in zip(rungs[:-1], rungs[1:]):
        ratios = {q: data[q][hi] / data[q][lo] for q in variants}
        g = gm(ratios.values()); qmin = min(ratios, key=ratios.get); qmax = max(ratios, key=ratios.get)
        ref = REF.get((lo, hi))
        rows.append([f"{lo}->{hi}", lo, hi, f"{g:.3f}", f"{ratios[qmin]:.3f}", f"{ratios[qmax]:.3f}", qmin, qmax, ref if ref else ""])
        print(f"{lo+'->'+hi:<36s} {g:8.3f} {ratios[qmin]:6.2f} {ratios[qmax]:6.2f}  ({qmin}, {qmax}){'':<8s} {ref if ref else '':>6}")
    # the old compile bar and its chain, cumulative
    old = gm([data[q]["r3"] / data[q]["r2"] for q in variants])
    comp = gm([data[q]["r3_eager_all"] / data[q]["r2"] for q in variants])
    lazy = gm([data[q]["r3_lazy_nopass"] / data[q]["r3_eager_all"] for q in variants])
    pth = gm([data[q]["r3"] / data[q]["r3_lazy_nopass"] for q in variants])
    top = rungs[-1]
    cum = gm([data[q][top] / data[q]["r1"] for q in variants])
    print(f"\nold compile bar r2->r3 geomean {old:.3f} (ref 3.55/3.56) = compilation {comp:.3f} (ref 1.88) x lazy code gen "
          f"{lazy:.3f} (ref 1.50) x passthrough {pth:.3f} (ref 1.26); product {comp*lazy*pth:.3f}")
    print(f"cumulative r1->r7 geomean {cum:.1f}x (ref 68x); per query: " +
          ", ".join(f"{q} {data[q][top]/data[q]['r1']:.0f}x" for q in variants))
    rows.append(["r2->r3 (old compile bar)", "r2", "r3", f"{old:.3f}", "", "", "", "", 3.56])
    rows.append([f"r1->{top} (cumulative)", "r1", top, f"{cum:.3f}", "", "", "", "", 68])
    with open(out / f"lever_geomeans{suffix}.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["lever", "from", "to", "geomean", "min", "max", "min_query", "max_query", "reference"]); w.writerows(rows)

    # ---- grouped-bar ladder ----
    nq, nr = len(variants), len(rungs)
    colors = [plt.cm.viridis(t) for t in np.linspace(0.90, 0.12, nr)]
    plt.rcParams.update({"font.size": 11, "axes.edgecolor": "#888", "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(18 if not a.all else 20, 8))
    x = np.arange(nq); width = 0.84 / nr
    for i, r in enumerate(rungs):
        vals = [data[q][r] for q in variants]
        ax.bar(x + (i - (nr - 1) / 2) * width, vals, width, label=LABEL[r], color=colors[i], edgecolor="white", linewidth=0.4, zorder=3)
    ax.set_yscale("log")
    vmin = min(data[q][r] for q in variants for r in rungs); vmax = max(data[q][r] for q in variants for r in rungs)
    ax.set_ylim(10 ** math.floor(math.log10(vmin)), vmax * 1.8)
    ax.yaxis.set_major_locator(LogLocator(base=10)); ax.yaxis.set_major_formatter(ScalarFormatter())
    ax.set_ylabel(("Throughput (Mrows/s, median)" if a.mrows else "Throughput (MB/s of input, median; r7 x20-corrected)") + " — log scale")
    ax.set_xticks(x); ax.set_xticklabels(variants, rotation=30, ha="right")
    ax.set_title("CSV→JSON ablation ladder, bid_strings_3GB (31.3 M rows) — r1…r6b: 1 worker, InMemory; r7: 23 workers (Threadripper PRO 5965WX)", fontsize=13, pad=14)
    ax.grid(axis="y", which="both", color="#ddd", linewidth=0.6, zorder=0); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(ncol=5 if not a.all else 6, loc="upper center", bbox_to_anchor=(0.5, -0.16), frameon=False, fontsize=10, columnspacing=1.0, handlelength=1.2)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(out / f"ablation_ladder_{version}{suffix}.{ext}", dpi=140, bbox_inches="tight", facecolor="white")
    print("wrote", out / f"ablation_ladder_{version}{suffix}.{{png,svg}}", "and", out / f"lever_geomeans{suffix}.csv")


if __name__ == "__main__":
    main()
