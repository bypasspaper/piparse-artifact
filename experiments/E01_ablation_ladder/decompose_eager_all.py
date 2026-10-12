#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Decompose the v7 compile bar with the parse-all rungs (ablation_eager_all_bidstr, 2026-10-05).
Portable copy of ~/Notes/nebulastream/benchmark/2_engine_to_e2e/ablation_eager_irdump_2026-10-05/scripts/decompose_eager_all.py
(logic unchanged; paths made relative, run_group defaulted, --db/PBENCH_DB override).
Rungs (same session, W1 InMemory): r2_uncompiled, r3_compiled, r3_eager, r3_eager_fast, r3_eager_all.
Factors (today's medians): compilation = r3_eager_all / r2 (work-equal) ; strings pushdown = r3_eager_fast /
r3_eager_all ; numeric pushdown = r3_eager / r3_eager_fast ; laziness+passthrough = r3 / r3_eager.
Anchors: today's r2 and r3 vs v7 (data/ablation_ladder_v7_bidstr.csv); v7-footing projection = r3_v7 x ratio.
Usage: decompose_eager_all.py [--run-group 20261005T182825-4660e569] [--db <duckdb>] [--out out/]"""
import argparse, csv, math, os
from pathlib import Path
import duckdb

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--run-group", default="20261005T182825-4660e569")
ap.add_argument("--db", default=os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results" / "tr" / "piparse_bench.duckdb")))
ap.add_argument("--out", default=str(HERE / "out"))
A = ap.parse_args()
DB, V7, RG, OUT = A.db, HERE / "data" / "ablation_ladder_v7_bidstr.csv", A.run_group, Path(A.out)
OUT.mkdir(parents=True, exist_ok=True)
Q = ["q0", "qproject", "qroute", "q1", "q2og", "q2mod", "q10", "q14", "q22", "qex"]
R = ["r2_uncompiled", "r3_compiled", "r3_eager", "r3_eager_fast", "r3_eager_all"]
BPR = 114.87

con = duckdb.connect(DB, read_only=True)
rows = con.execute("""select variant, series, median(throughput_mbps), count(*), min(throughput_mbps), max(throughput_mbps)
 from runs where run_group=? group by 1,2""", [RG]).fetchall()
med = {(v, s): (m, n, lo, hi) for v, s, m, n, lo, hi in rows}
v7 = {r["variant"]: r for r in csv.DictReader(open(V7))}

def g(q, r): return med.get((q, r), (None,))[0]
def ratio(a, b): return None if a is None or b is None or b == 0 else a / b
def f(x, d=2): return "–" if x is None else f"{x:.{d}f}"
def gm(xs):
    xs = [x for x in xs if x]; return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None

print("## Today's medians (MB/s, W1, n=3) and rep spread")
print("| query | " + " | ".join(R) + " | spread max % |"); print("|---|" + "---|" * (len(R) + 1))
for q in Q:
    sp = max((med[(q, r)][3] - med[(q, r)][2]) / med[(q, r)][0] * 100 for r in R if (q, r) in med)
    print(f"| {q} | " + " | ".join(f(g(q, r), 0) for r in R) + f" | {sp:.1f} |")
print()
print("## Anchors vs v7 (today / v7)")
print("| query | r2 | r3 | r3_eager (v7 split, projected) |"); print("|---|---|---|---|")
for q in Q:
    print(f"| {q} | {f(ratio(g(q,'r2_uncompiled'), float(v7[q]['r2'])))} | {f(ratio(g(q,'r3_compiled'), float(v7[q]['r3'])))} | – |")
print()
print("## Factor decomposition of the compile bar (today's same-session ratios)")
print("| query | r3/r2 (old compile bar) | **compilation** r3_eager_all/r2 | strings r3_eager_fast/r3_eager_all | numerics r3_eager/r3_eager_fast | **pushdown total** r3_eager/r3_eager_all | lazy+passthrough r3/r3_eager | ns/row r2 | ns/row r3_eager_all |")
print("|---|---|---|---|---|---|---|---|---|")
acc = {k: [] for k in ["old", "comp", "str", "num", "push", "lazy"]}
tidy = []
for q in Q:
    r2, r3, re, rf, ra = (g(q, r) for r in R)
    vals = dict(old=ratio(r3, r2), comp=ratio(ra, r2), str=ratio(rf, ra), num=ratio(re, rf), push=ratio(re, ra), lazy=ratio(r3, re))
    for k, v in vals.items(): acc[k].append(v)
    ns2 = None if r2 is None else BPR / r2 * 1e3; nsa = None if ra is None else BPR / ra * 1e3
    print(f"| {q} | {f(vals['old'])} | **{f(vals['comp'])}** | {f(vals['str'])} | {f(vals['num'])} | **{f(vals['push'])}** | {f(vals['lazy'])} | {f(ns2, 0)} | {f(nsa, 0)} |")
    tidy.append([q, r2, r3, re, rf, ra] + [vals[k] for k in ["old", "comp", "str", "num", "push", "lazy"]])
print(f"| **geomean** | {f(gm(acc['old']))} | **{f(gm(acc['comp']))}** | {f(gm(acc['str']))} | {f(gm(acc['num']))} | **{f(gm(acc['push']))}** | {f(gm(acc['lazy']))} | | |")
print()
print("## v7-footing projection (r3_v7 × today's ratios): the parse-all rung as it would sit in the published ladder")
print("| query | r2_v7 | r3_eager_all_v7 | r3_eager_fast_v7 | r3_eager_v7 | r3_v7 |"); print("|---|---|---|---|---|---|")
for q in Q:
    r3v = float(v7[q]["r3"]); r3t = g(q, "r3_compiled")
    k = lambda r: f(None if r3t is None or g(q, r) is None else r3v * g(q, r) / r3t, 0)
    print(f"| {q} | {float(v7[q]['r2']):.0f} | {k('r3_eager_all')} | {k('r3_eager_fast')} | {k('r3_eager')} | {r3v:.0f} |")
with open(OUT / "eager_all_decomposition.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["query"] + R + ["old_compile", "compilation", "strings", "numerics", "pushdown", "lazy"]); w.writerows(tidy)
print(f"\nwrote {OUT}/eager_all_decomposition.csv")
