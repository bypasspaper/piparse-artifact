#!/usr/bin/env python3
"""fig1_opt_diff: medians per variant x series, ratios.  usage: extract_diff.py [experiment]"""
import duckdb, os, sys, statistics
EXP = sys.argv[1] if len(sys.argv) > 1 else "fig1_opt_diff"
con = duckdb.connect(os.path.expanduser("~/work/piparse-bench/results/piparse_bench.duckdb"), read_only=True)
rows = con.sql(f"select variant, series, repetition, throughput_mbps, throughput_mrows_s, processing_time_s from runs where experiment='{EXP}' order by 1,2,3").fetchall()
d = {}
for v, s, r, mb, mr, t in rows:
    if mr is not None: d.setdefault(v, {}).setdefault(s, []).append((mb, mr, t))
print(f"{'variant':7} {'series':12} {'MB/s':>8} {'Mrows/s':>8} {'ns/row':>7} {'win s':>6} {'n':>2}")
med = {}
for v in d:
    for s in d[v]:
        mb = statistics.median(x[0] for x in d[v][s]); mr = statistics.median(x[1] for x in d[v][s]); t = statistics.median(x[2] for x in d[v][s])
        med[(v, s)] = mr; print(f"{v:7} {s:12} {mb:8.1f} {mr:8.2f} {1000/mr:7.1f} {t:6.1f} {len(d[v][s]):>2}")
print("\nratios (rows/s):")
for v in d:
    L = med.get((v, "lazy")); E = med.get((v, "eager")); C = med.get((v, "lazy_csvout"))
    parts = []
    if L and E: parts.append(f"lazy/eager = {L/E:.2f}x  (eager adds {1000/E-1000/L:.1f} ns/row of parse+format)")
    if L and C: parts.append(f"csvout/json = {C/L:.2f}x  (JSON framing costs {1000/L-1000/C:.1f} ns/row over whole-row copy)")
    if parts: print(f"  {v}: " + " | ".join(parts))
