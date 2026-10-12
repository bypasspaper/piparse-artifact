#!/usr/bin/env python3
# Artifact copy of fig1_fig2_teaser_2026-09-25_scratch/extract_fig2_v2.py. Changes: DB = ../../../results/tr/piparse_bench.duckdb
# (override: --db PATH or env PBENCH_DB), output dir default ../out. usage: extract_fig2_v2.py [experiment] [out_dir] [--db PATH]
"""Pull fig2_fieldsweep_v2 (or _smoke) runs from pbench's DuckDB -> per-rung medians, a+bN fit, anchor gates.
usage: extract_fig2_v2.py [experiment_name] [out_dir]"""
import duckdb, csv, re, os, sys, statistics
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
DB = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results/tr/piparse_bench.duckdb"))
_args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] != "--db"]
EXP = _args[0] if len(_args) > 0 else "fig2_fieldsweep_v2"
OUT = _args[1] if len(_args) > 1 else str(HERE / "out")
Path(OUT).mkdir(parents=True, exist_ok=True)
con = duckdb.connect(DB, read_only=True)
rows = con.sql(f"""select variant, series, query_ref, repetition, throughput_mbps, throughput_mrows_s,
                          processing_time_s, input_rows
                   from runs where experiment='{EXP}' order by 1,2,3,4""").fetchall()
OLD = {1:(321.6,29.5),2:(326.6,15.0),3:(318.1,9.7),4:(308.1,7.1),5:(318.5,5.8),
       6:(302.2,4.6),7:(307.9,4.0),8:(301.0,3.5),9:(300.8,3.1),10:(302.6,2.8)}   # 2026-08-19 compiled allf
BPR = {1:10.9,2:21.8,3:32.7,4:43.6,5:54.4,6:65.3,7:76.2,8:87.1,9:98.0,10:108.9}
by = {}
with open(f"{OUT}/{EXP}_raw.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["rung","N","rep","MBps","Mrows_s","window_s","input_rows"])
    for var, ser, q, rep, mb, mr, t, n in rows:
        N = int(re.search(r"_n(\d+)$", q).group(1))
        rung = "anchor_allf" if var == "anchor_allf" else ser
        w.writerow([rung, N, rep, mb, mr, t, n])
        if mb is not None and mr is not None:
            by.setdefault(rung, {}).setdefault(N, []).append((mb, mr, t))
med = {}
with open(f"{OUT}/{EXP}_data.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["rung","N","input_MBps","throughput_Mrows_s","ns_per_row","reps"])
    for rung in ["naive","compiled_eager","compiled_lazy","anchor_allf"]:
        if rung not in by: continue
        print(f"\n== {rung} ==\n{'N':>2} {'MB/s':>8} {'Mrows/s':>8} {'ns/row':>7} {'win s':>6} {'reps':>4}")
        for N in sorted(by[rung]):
            v = by[rung][N]
            mb = statistics.median(x[0] for x in v); mr = statistics.median(x[1] for x in v); t = statistics.median(x[2] for x in v)
            med[(rung, N)] = (mb, mr)
            print(f"{N:>2} {mb:8.1f} {mr:8.2f} {1000/mr:7.1f} {t:6.1f} {len(v):>4}")
            w.writerow([rung, N, f"{mb:.1f}", f"{mr:.3f}", f"{1000/mr:.1f}", len(v)])
# a + b*N least-squares fit on ns/row
print("\n== cost law ns/row = a + b*N ==")
for rung in ["naive","compiled_eager","compiled_lazy","anchor_allf"]:
    pts = [(N, 1000/med[(rung,N)][1]) for N in range(1,11) if (rung,N) in med]
    if len(pts) < 2: continue
    n = len(pts); sx = sum(p[0] for p in pts); sy = sum(p[1] for p in pts)
    sxx = sum(p[0]**2 for p in pts); sxy = sum(p[0]*p[1] for p in pts)
    b = (n*sxy - sx*sy)/(n*sxx - sx*sx); a = (sy - b*sx)/n
    ss_res = sum((p[1]-(a+b*p[0]))**2 for p in pts); ss_tot = sum((p[1]-sy/n)**2 for p in pts)
    print(f"{rung:>15}: a = {a:6.1f} ns/row  b = {b:6.1f} ns/field  R2 = {1-ss_res/ss_tot:.4f}  (n={n})")
# gates
print("\n== gates ==")
for N in range(1,11):
    parts = []
    if ("anchor_allf",N) in med:
        mb, mr = med[("anchor_allf",N)]; parts.append(f"anchor vs 2026-08-19: {100*(mr/OLD[N][1]-1):+5.1f}% rows/s {100*(mb/OLD[N][0]-1):+5.1f}% MB/s")
    if ("anchor_allf",N) in med and ("compiled_eager",N) in med:
        parts.append(f"eager/anchor: {med[('compiled_eager',N)][1]/med[('anchor_allf',N)][1]:.3f}")
    if ("compiled_lazy",N) in med and ("compiled_eager",N) in med:
        parts.append(f"lazy/eager: {med[('compiled_lazy',N)][1]/med[('compiled_eager',N)][1]:.2f}x")
    if ("compiled_eager",N) in med and ("naive",N) in med:
        parts.append(f"eager/naive: {med[('compiled_eager',N)][1]/med[('naive',N)][1]:.2f}x")
    if parts: print(f"N={N:>2}: " + " | ".join(parts))
print(f"\nwrote {OUT}/{EXP}_data.csv and _raw.csv")
