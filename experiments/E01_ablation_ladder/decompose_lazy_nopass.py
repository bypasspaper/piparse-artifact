#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Split the laziness factor with the lazy-without-passthrough rung (ablation_lazy_nopass_bidstr, 2026-10-05).
Portable copy of ~/Notes/nebulastream/benchmark/2_engine_to_e2e/ablation_eager_irdump_2026-10-05/scripts/decompose_lazy_nopass.py
(logic unchanged; paths made relative, run_groups defaulted, --db/PBENCH_DB override).
Same-session rungs: r3_eager_all (compiled parse-all, work-equal) | r3_lazy_nopass (lazy, no overload, no passthrough)
| r3_compiled (lazy + passthrough = v7 r3). Factors: lazy code generation = nopass / eager_all ; passthrough = r3 / nopass.
Also chains with the afternoon session (--run-group-prev: r2 -> r3_eager_all compilation) into the full compile-bar split
and checks the anchors (today's r3_eager_all, r3 vs the afternoon session; r3 vs v7).
Usage: decompose_lazy_nopass.py [--run-group 20261005T191325-76194e52] [--run-group-prev 20261005T182825-4660e569] [--db] [--out]"""
import argparse, csv, math, os
from pathlib import Path
import duckdb

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--run-group", default="20261005T191325-76194e52")
ap.add_argument("--run-group-prev", default="20261005T182825-4660e569")
ap.add_argument("--db", default=os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results" / "tr" / "piparse_bench.duckdb")))
ap.add_argument("--out", default=str(HERE / "out"))
A = ap.parse_args()
DB, V7, RG, RG_PREV, OUT = A.db, HERE / "data" / "ablation_ladder_v7_bidstr.csv", A.run_group, A.run_group_prev, Path(A.out)
OUT.mkdir(parents=True, exist_ok=True)
Q = ["q0", "qproject", "qroute", "q1", "q2og", "q2mod", "q10", "q14", "q22", "qex"]
R = ["r3_eager_all", "r3_lazy_nopass", "r3_compiled"]
BPR = 114.87
con = duckdb.connect(DB, read_only=True)
def meds(rg):
    return {(v, s): (m, n, lo, hi) for v, s, m, n, lo, hi in con.execute(
        "select variant, series, median(throughput_mbps), count(*), min(throughput_mbps), max(throughput_mbps) from runs where run_group=? group by 1,2", [rg]).fetchall()}
now, prev = meds(RG), meds(RG_PREV)
v7 = {r["variant"]: r for r in csv.DictReader(open(V7))}
g = lambda d, q, r: d.get((q, r), (None,))[0]
ratio = lambda a, b: None if a is None or b is None or b == 0 else a / b
f = lambda x, d=2: "–" if x is None else f"{x:.{d}f}"
def gm(xs):
    xs = [x for x in xs if x]; return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None

print("## Medians (MB/s, W1, n=3) + rep spread; anchors vs the afternoon session and v7")
print("| query | r3_eager_all | r3_lazy_nopass | r3_compiled | spread max % | eager_all now/prev | r3 now/prev | r3 now/v7 |")
print("|---|---|---|---|---|---|---|---|")
for q in Q:
    sp = max((now[(q, r)][3] - now[(q, r)][2]) / now[(q, r)][0] * 100 for r in R if (q, r) in now)
    print(f"| {q} | {f(g(now,q,'r3_eager_all'),0)} | {f(g(now,q,'r3_lazy_nopass'),0)} | {f(g(now,q,'r3_compiled'),0)} | {sp:.1f} | "
          f"{f(ratio(g(now,q,'r3_eager_all'), g(prev,q,'r3_eager_all')))} | {f(ratio(g(now,q,'r3_compiled'), g(prev,q,'r3_compiled')))} | {f(ratio(g(now,q,'r3_compiled'), float(v7[q]['r3'])))} |")
print()
print("## Laziness split (same session) and the full compile-bar chain")
print("| query | **lazy code gen** nopass/eager_all | **passthrough** r3/nopass | product r3/eager_all | compilation r2→eager_all (afternoon) | old bar r3/r2 (afternoon) | chain product | ns/row eager_all | ns/row nopass | ns/row r3 |")
print("|---|---|---|---|---|---|---|---|---|---|")
acc = {k: [] for k in ["lazy", "pass", "prod", "comp", "old", "chain"]}
tidy = []
for q in Q:
    ea, np_, r3 = (g(now, q, r) for r in R)
    comp = ratio(g(prev, q, "r3_eager_all"), g(prev, q, "r2_uncompiled"))
    old = ratio(g(prev, q, "r3_compiled"), g(prev, q, "r2_uncompiled"))
    vals = dict(lazy=ratio(np_, ea), pass_=ratio(r3, np_), prod=ratio(r3, ea), comp=comp, old=old)
    chain = None if None in (comp, vals["lazy"], vals["pass_"]) else comp * vals["lazy"] * vals["pass_"]
    for k, v in zip(["lazy", "pass", "prod", "comp", "old", "chain"], [vals["lazy"], vals["pass_"], vals["prod"], comp, old, chain]): acc[k].append(v)
    ns = lambda x: None if x is None else BPR / x * 1e3
    print(f"| {q} | **{f(vals['lazy'])}** | **{f(vals['pass_'])}** | {f(vals['prod'])} | {f(comp)} | {f(old)} | {f(chain)} | {f(ns(ea),0)} | {f(ns(np_),0)} | {f(ns(r3),0)} |")
    tidy.append([q, ea, np_, r3, vals["lazy"], vals["pass_"], vals["prod"], comp, old, chain])
print(f"| **geomean** | **{f(gm(acc['lazy']))}** | **{f(gm(acc['pass']))}** | {f(gm(acc['prod']))} | {f(gm(acc['comp']))} | {f(gm(acc['old']))} | {f(gm(acc['chain']))} | | | |")
print()
print("## v7-footing projection of the new rung (r3_v7 × nopass/r3 today)")
print("| query | r2_v7 | r3_eager_all_v7 (afternoon proj.) | r3_lazy_nopass_v7 | r3_v7 |"); print("|---|---|---|---|---|")
for q in Q:
    r3v = float(v7[q]["r3"]); r3p = g(prev, q, "r3_compiled")
    ea_v7 = None if r3p is None or g(prev, q, "r3_eager_all") is None else r3v * g(prev, q, "r3_eager_all") / r3p
    np_v7 = None if g(now, q, "r3_compiled") is None or g(now, q, "r3_lazy_nopass") is None else r3v * g(now, q, "r3_lazy_nopass") / g(now, q, "r3_compiled")
    print(f"| {q} | {float(v7[q]['r2']):.0f} | {f(ea_v7,0)} | {f(np_v7,0)} | {r3v:.0f} |")
with open(OUT / "lazy_nopass_decomposition.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["query", "r3_eager_all", "r3_lazy_nopass", "r3_compiled", "lazy_codegen", "passthrough", "product", "compilation_prev", "old_bar_prev", "chain"]); w.writerows(tidy)
print(f"\nwrote {OUT}/lazy_nopass_decomposition.csv")
