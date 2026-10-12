#!/usr/bin/env python3
"""Append the Flink rows to fig1_teaser2_data.csv. Shares: classify_flink.analyze (2026-09-03 rules) on the collapsed
async-profiler stacks (cpu event @4 kHz, whole job): 3-stage NES footing = deser | process(+residual+internal) | ser,
excluding read / kernel / other threads (GC, JIT, coordinator). Absolute CPU ns per tuple = stage samples / 4000 / rows
(the cpu event samples each thread's CPU time, so samples/4000 = CPU-seconds; non-idle threads only, like the shares).
q0 + ysb: the 2026-09-03 profiles (flink_prof_q0 / flink_prof_ysb, gz); q2og: this session's flink_prof_q2og.
Throughput: fig1_flink_thru (q0/ysb, 2026-09-03 clean medians) + fig1_flink_thru_q2og (DB)."""
import os, sys, csv, glob, gzip, shutil, tempfile, statistics, importlib.util, duckdb
SC = os.path.dirname(os.path.abspath(__file__)); FS = os.path.expanduser("~/Notes/nebulastream/benchmark/fig1_fig2_flink_2026-09-03_scratch")
spec = importlib.util.spec_from_file_location("cf", f"{SC}/classify_flink.py"); cf = importlib.util.module_from_spec(spec)
a = sys.argv; sys.argv = ["x"]; spec.loader.exec_module(cf); sys.argv = a
HZ = 4000.0
ROWS = {"q0": 183991721, "q2og": 183991721, "ysb": 80000000}   # bid_6GB (large) / ysb xlarge
SRC = {"q0": f"{FS}/flink_prof_q0", "ysb": f"{FS}/flink_prof_ysb", "q2og": f"{SC}/flink_prof_q2og"}
con = duckdb.connect(os.path.expanduser("~/work/piparse-bench/results/piparse_bench.duckdb"), read_only=True)
def thru(exp, variant):
    v = [r[0] for r in con.sql(f"select throughput_mrows_s from runs where experiment='{exp}' and variant='{variant}' and throughput_mrows_s is not null").fetchall()]
    return statistics.median(v) if v else None
THRU = {"q0": thru("fig1_flink_thru", "q0"), "ysb": thru("fig1_flink_thru", "ysb"), "q2og": thru("fig1_flink_thru_q2og", "q2og")}
out_rows = []
for q in ("q0", "q2og", "ysb"):
    files = sorted(glob.glob(f"{SRC[q]}/prof_*.collapsed*"))
    if not files: print(f"{q}: no collapsed profile in {SRC[q]}"); continue
    paths = []
    for f in files:
        if f.endswith(".gz"):
            t = tempfile.NamedTemporaryFile(delete=False, suffix=".collapsed"); shutil.copyfileobj(gzip.open(f, "rb"), t); t.close(); paths.append(t.name)
        else: paths.append(f)
    total, b, per_thread, resid, proc_top, ser_top = cf.analyze(paths)
    deser = b["deserialize"]; proc = b["process"] + b["residual"] + b["internal"]; ser = b["serialize"]
    s = deser + proc + ser; rows = ROWS[q]
    ns = {k: 1e9 * v / HZ / rows for k, v in (("deser", deser), ("proc", proc), ("ser", ser))}
    out_rows.append({"query": q, "arm": "flink", "deser_pct": round(100 * deser / s, 1), "proc_pct": round(100 * proc / s, 1), "ser_pct": round(100 * ser / s, 1),
                     "ns_per_tuple": round(sum(ns.values()), 1), "deser_ns": round(ns["deser"], 2), "proc_ns": round(ns["proc"], 2), "ser_ns": round(ns["ser"], 2),
                     "mrows_s": round(THRU[q], 3) if THRU[q] else ""})
    print(f"{q}: samples {total} (stages {s}, excluded read {b['read']} kernel {b['kernel']} other {b['other_threads']}); "
          f"shares {100*deser/s:.1f}/{100*proc/s:.1f}/{100*ser/s:.1f}; ns/tuple {sum(ns.values()):.0f} (wall {1000/THRU[q]:.0f} at {THRU[q]:.2f} Mrows/s)" if THRU[q] else f"{q}: no throughput")
p = f"{SC}/fig1_teaser2_data.csv"; existing = [r for r in csv.DictReader(open(p))] if os.path.exists(p) else []
existing = [r for r in existing if r["arm"] != "flink"] + out_rows
with open(p, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["query", "arm", "deser_pct", "proc_pct", "ser_pct", "ns_per_tuple", "deser_ns", "proc_ns", "ser_ns", "mrows_s"]); w.writeheader(); w.writerows(existing)
print("flink rows merged into", p)
