#!/usr/bin/env python3
"""Derive per-thread CPU time INSIDE the MonitoringSink window for every run of an experiment, from the persisted
artifacts (results/artifacts/<exp>/<run_id>/{threadcpu.csv, query_*_monitoring.csv}) + the DuckDB row (rows, variant...).
Window = [first read start us, last arrival us] of the sink CSV (epoch us); threadcpu.csv wall_s is epoch s (same clock).
Per thread: CPU ticks are linearly interpolated at the window edges (0.5 s sampling, 10 ms tick resolution).
Output CSV per run: run_id, variant, series, query_ref, N (if parseable), repetition, window_s, rows, wall_ns_per_row,
cpu_s_<thread-group>..., cpu_total_s, busy_threads (cpu>=0.5*window), cpu_ns_per_row_total, cpu_ns_per_row_busy.
usage: cpu_from_artifacts.py <experiment> [out.csv]"""
import csv, os, re, sys, glob, duckdb, statistics
args = [a for a in sys.argv[1:] if not a.startswith("--")]
EXP = args[0]; OUT = args[1] if len(args) > 1 else f"{EXP}_cpu.csv"
RG = args[2] if len(args) > 2 else ("LATEST" if "--latest" in sys.argv else None)
ROOT = os.path.expanduser("~/work/piparse-bench")
con = duckdb.connect(f"{ROOT}/results/piparse_bench.duckdb", read_only=True)
if RG == "LATEST":
    RG = con.sql(f"select max(run_group) from runs where experiment='{EXP}'").fetchone()[0]
rg_clause = f" and run_group='{RG}'" if RG else ""
rows = con.sql(f"""select run_id, variant, series, query_ref, repetition, input_rows, processing_time_s, throughput_mrows_s
                   from runs where experiment='{EXP}'{rg_clause} order by variant, series, query_ref, repetition""").fetchall()
print(f"experiment={EXP} run_group={RG or 'ALL'}  ({len(rows)} rows)")
def group(comm):
    for g in ("DataSrc", "WorkerThread", "IOThread", "grpc"):
        if comm.startswith(g): return g
    return "other"
def interp(samples, t):
    """samples: sorted [(wall, ticks)] -> ticks at t (linear; clamp to ends)."""
    if t <= samples[0][0]: return samples[0][1]
    if t >= samples[-1][0]: return samples[-1][1]
    for (t0, v0), (t1, v1) in zip(samples, samples[1:]):
        if t0 <= t <= t1:
            return v0 if t1 == t0 else v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return samples[-1][1]
out = []; groups_seen = set()
for run_id, variant, series, q, rep, nrows, win, mr in rows:
    d = f"{ROOT}/results/artifacts/{EXP}/{run_id}"
    tc = f"{d}/threadcpu.csv"; mons = sorted(glob.glob(f"{d}/query_*_monitoring.csv"))
    if not (os.path.exists(tc) and mons): continue
    hdr = open(tc).readline(); clk = float(re.search(r"clk_tck=(\d+)", hdr).group(1))
    per_tid = {}
    for r in csv.DictReader((l for l in open(tc) if not l.startswith("#"))):
        per_tid.setdefault((r["tid"], r["comm"]), []).append((float(r["wall_s"]), (int(r["utime_ticks"]) + int(r["stime_ticks"])) / clk))
    last = list(csv.DictReader(open(mons[0])))[-1]
    t0 = float(last["first read start us"]) / 1e6; t1 = float(last["last arrival us"]) / 1e6
    cpu = {}
    for (tid, comm), s in per_tid.items():
        s.sort(); c = max(0.0, interp(s, t1) - interp(s, t0)); g = group(comm); cpu[g] = cpu.get(g, 0.0) + c
    groups_seen |= set(cpu)
    total = sum(cpu.values()); wlen = t1 - t0
    busy = sum(1 for (tid, comm), s in per_tid.items() if (interp(sorted(s), t1) - interp(sorted(s), t0)) >= 0.5 * wlen)
    N = re.search(r"_n(\d+)$", q); N = int(N.group(1)) if N else ""
    out.append({"run_id": run_id, "variant": variant, "series": series, "query_ref": q, "N": N, "repetition": rep,
                "window_s": round(wlen, 3), "sink_processing_time_s": win, "rows": nrows,
                "wall_ns_per_row": round(1e9 * wlen / nrows, 2) if nrows else "",
                **{f"cpu_s_{g}": round(cpu.get(g, 0.0), 3) for g in sorted(groups_seen)},
                "cpu_total_s": round(total, 3), "busy_threads": busy,
                "cpu_ns_per_row_total": round(1e9 * total / nrows, 2) if nrows else "",
                "cpu_ns_per_row_busy": round(1e9 * sum(v for v in cpu.values() if v >= 0.5 * wlen) / nrows, 2) if nrows else ""})
if not out: sys.exit(f"no artifacts for experiment {EXP}")
cols = list(out[0].keys())
for o in out:   # pad group columns discovered later
    for g in sorted(groups_seen):
        o.setdefault(f"cpu_s_{g}", 0.0)
cols = [c for c in cols if not c.startswith("cpu_s_")] + sorted(f"cpu_s_{g}" for g in groups_seen)
cols = cols[:cols.index("cpu_total_s")] + [c for c in cols if c.startswith("cpu_s_")] + cols[cols.index("cpu_total_s"):]
seen = set(); cols = [c for c in cols if not (c in seen or seen.add(c))]
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(out)
print(f"{'variant':12} {'series':15} {'query':22} {'win s':>6} {'wall ns/row':>11} {'cpu DataSrc':>11} {'cpu Worker':>10} {'busy':>4} {'cpu ns/row(busy)':>16}")
for o in out:
    print(f"{o['variant']:12} {o['series']:15} {o['query_ref']:22} {o['window_s']:6.2f} {o['wall_ns_per_row']:>11} {o.get('cpu_s_DataSrc',0):11.2f} {o.get('cpu_s_WorkerThread',0):10.2f} {o['busy_threads']:>4} {o['cpu_ns_per_row_busy']:>16}")
print(f"wrote {OUT} ({len(out)} runs)")
