#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Put the 2026-10-12 r6/r6b and r7 ctrl-vs-overload re-measurement onto the v7 ladder footing (paper policy:
the two top rungs are overloads-ON rungs).

Reads the two run groups (default: the newest run group of `ablation_r6_overload_rerun_bidstr` and
`ablation_r7_overload_rerun_bidstr` in the results DB), takes per-query medians (r7 reported x20 = true MB/s), and
writes
  out/ablation_overload_rerun_medians.csv   query, r6_ctrl, r6b_ovl, r7_ctrl_true, r7_ovl_true, ovl/ctrl ratios,
                                           drift of the ctrl arms against the v7 ladder (same binary family)
  data/ablation_ladder_v9_bidstr{,_mrows}.csv   = the v8 columns + r6b_ovl (= v7 r6 x r6b_ovl/r6_ctrl)
                                           + r7 (= v7 r7_true, overload OFF) + r7_ovl (= v7 r7_true x r7_ovl/r7_ctrl)
The same-session ratio-onto-footing rule is the one used for the 2026-10-05 new rungs (decompose_*.py).
Usage: splice_overload_rerun.py [--db PATH] [--rg-r6 RG] [--rg-r7 RG] [--no-write]
"""
import argparse, csv, os, statistics
from pathlib import Path
import duckdb

HERE = Path(__file__).resolve().parent
BPR = 114.87                      # bytes per bid_strings_3GB row -> Mrows/s = MB/s / BPR
ORDER = ["q0", "qproject", "qroute", "q1", "q2og", "q2mod", "q10", "q14", "q22", "qex"]
ap = argparse.ArgumentParser()
ap.add_argument("--db", default=os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results" / "tr" / "piparse_bench.duckdb")))
ap.add_argument("--rg-r6"); ap.add_argument("--rg-r7"); ap.add_argument("--no-write", action="store_true")
A = ap.parse_args()
con = duckdb.connect(A.db, read_only=True)

def latest_rg(exp):
    r = con.execute("select run_group from runs where experiment=? group by 1 order by max(timestamp) desc limit 1", [exp]).fetchone()
    if not r: raise SystemExit(f"no runs of {exp} in {A.db}")
    return r[0]
rg6 = A.rg_r6 or latest_rg("ablation_r6_overload_rerun_bidstr")
rg7 = A.rg_r7 or latest_rg("ablation_r7_overload_rerun_bidstr")
print(f"run groups: r6 {rg6}, r7 {rg7}")

def medians(rg, scale):
    rows = con.execute("select variant, series, throughput_mbps from runs where run_group=? and throughput_mbps is not null", [rg]).fetchall()
    d = {}
    for q, s, mb in rows: d.setdefault(q, {}).setdefault(s, []).append(mb * scale)
    return {q: {s: statistics.median(v) for s, v in a.items()} for q, a in d.items()}, {q: {s: len(v) for s, v in a.items()} for q, a in d.items()}
m6, n6 = medians(rg6, 1.0); m7, n7 = medians(rg7, 20.0)   # r7: NES_INMEM_REPEAT=20 -> reported x20 = true
v7 = {r["variant"]: r for r in csv.DictReader(open(HERE / "data" / "ablation_ladder_v7_bidstr.csv"))}
v8 = {r["variant"]: r for r in csv.DictReader(open(HERE / "data" / "ablation_ladder_v8_bidstr.csv"))}

out = HERE / "out"; out.mkdir(exist_ok=True)
hdr = ["query", "n", "r6_ctrl", "r6b_ovl", "ovl_r6_ratio", "r7_ctrl_true", "r7_ovl_true", "ovl_r7_ratio", "r6_ctrl_vs_v7_r6", "r7_ctrl_vs_v7_r7"]
print("| " + " | ".join(hdr) + " |"); print("|" + "---|" * len(hdr))
rows9 = []
with open(out / "ablation_overload_rerun_medians.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(hdr)
    for q in ORDER:
        if q not in m6 or q not in m7: print(f"| {q} | MISSING |"); continue
        r6c, r6o = m6[q]["r6_ctrl"], m6[q]["r6b_ovl"]; r7c, r7o = m7[q]["r7_ctrl"], m7[q]["r7_ovl"]
        v7r6, v7r7 = float(v7[q]["r6"]), float(v7[q]["r7_true"])
        row = [q, f"{n6[q]['r6_ctrl']}/{n7[q]['r7_ctrl']}", f"{r6c:.1f}", f"{r6o:.1f}", f"{r6o/r6c:.3f}", f"{r7c:.1f}", f"{r7o:.1f}", f"{r7o/r7c:.3f}", f"{r6c/v7r6:.3f}", f"{r7c/v7r7:.3f}"]
        w.writerow(row); print("| " + " | ".join(row) + " |")
        rows9.append((q, v7r6 * r6o / r6c, v7r7, v7r7 * r7o / r7c))
import math
gm = lambda xs: math.exp(sum(math.log(x) for x in xs) / len(xs))
print(f"\ngeomean ovl/ctrl: r6 {gm([m6[q]['r6b_ovl']/m6[q]['r6_ctrl'] for q in ORDER if q in m6]):.3f}   r7 {gm([m7[q]['r7_ovl']/m7[q]['r7_ctrl'] for q in ORDER if q in m7]):.3f}")
print(f"geomean drift ctrl vs v7: r6 {gm([m6[q]['r6_ctrl']/float(v7[q]['r6']) for q in ORDER if q in m6]):.3f}   r7 {gm([m7[q]['r7_ctrl']/float(v7[q]['r7_true']) for q in ORDER if q in m7]):.3f}")
if A.no_write: raise SystemExit(0)
for mrows in (False, True):
    src = HERE / "data" / ("ablation_ladder_v8_bidstr_mrows.csv" if mrows else "ablation_ladder_v8_bidstr.csv")
    dst = HERE / "data" / ("ablation_ladder_v9_bidstr_mrows.csv" if mrows else "ablation_ladder_v9_bidstr.csv")
    rd = list(csv.DictReader(open(src))); cols = list(rd[0].keys()) + ["r6b_ovl", "r7", "r7_ovl"]
    extra = {q: (a, b, c) for q, a, b, c in rows9}
    with open(dst, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(cols)
        for r in rd:
            a, b, c = extra[r["variant"]]
            f = (lambda x: f"{x / BPR:.4f}") if mrows else (lambda x: f"{x:.2f}")
            w.writerow([r[k] for k in rd[0].keys()] + [f(a), f(b), f(c)])
    print("wrote", dst.relative_to(HERE))
