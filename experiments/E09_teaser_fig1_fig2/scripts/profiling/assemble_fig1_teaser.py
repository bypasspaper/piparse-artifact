#!/usr/bin/env python3
"""Assemble the Fig1 TEASER table: per query, naive (2026-08-19 profile) vs optimised (2026-09-25 profile) shares in the
3-segment taxonomy (deserialize / process incl. raw copy + engine / serialize) + absolute ns/row per stage.
Optimised attribution: classify_v2 raw buckets on the busy thread(s); the opaque JIT block is split with the knob
differencing: serialize_jit = (ns_json_lazy - ns_csv_lazy) [JSON per-field framing over a whole-row copy], the JIT
remainder (scan glue + raw span copies + operator code) -> process. For YSB (tiny output) the JIT block -> process.
usage: assemble_fig1_teaser.py  (reads optprof_*/symbols_*.txt, fig1_opt_diff medians from DuckDB, Notes naive CSVs)"""
import os, sys, csv, duckdb, statistics, importlib.util
SC = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("cl", f"{SC}/classify_v2.py"); cl = importlib.util.module_from_spec(spec)
sys.argv = ["x"]; spec.loader.exec_module(cl)
NOTES = os.path.expanduser("~/Notes/nebulastream/benchmark")
naive = {r["query"].split()[0]: r for r in csv.DictReader(open(f"{NOTES}/fig1_parsing_overhead_2026-08-19_data.csv"))}
naive_thr = {}
for r in csv.DictReader(open(f"{NOTES}/fig1_throughput_reps.csv")):
    naive_thr.setdefault(r["query_ref"], []).append(float(r["throughput_mrows_s"]))
NAIVE_KEY = {"q0": ("q0", "nexmark/bid_star"), "q2mod": ("q2", "nexmark/q2_filter"), "ysb": ("YSB", "yahoo/ysb_1k_varsized")}
con = duckdb.connect(os.path.expanduser("~/work/piparse-bench/results/piparse_bench.duckdb"), read_only=True)
d = {}
for v, s, mr in con.sql("select variant, series, throughput_mrows_s from runs where experiment='fig1_opt_diff' and throughput_mrows_s is not null").fetchall():
    d.setdefault(v, {}).setdefault(s, []).append(mr)
ns = {(v, s): 1000 / statistics.median(x) for v in d for s, x in d[v].items()}
print(f"{'query':6} {'arm':10} {'deser%':>7} {'proc%':>6} {'ser%':>6} | {'ns/row':>7} {'deser':>6} {'proc':>6} {'ser':>6}  notes")
out = []
for q in ["q0", "q2mod", "ysb"]:
    nk, nref = NAIVE_KEY[q]; nr = naive[nk]; nthr = statistics.median(naive_thr[nref]); nns = 1000 / nthr
    dn, pn, sn = float(nr["deserialize_pct"]), float(nr["process_pct"]), float(nr["serialize_pct"])
    print(f"{q:6} {'naive':10} {dn:7.1f} {pn:6.1f} {sn:6.1f} | {nns:7.1f} {nns*dn/100:6.1f} {nns*pn/100:6.1f} {nns*sn/100:6.1f}  2026-08-19 profile, 1 busy thread each side")
    out.append([q, "naive", dn, pn, sn, nns])
    path = f"{SC}/optprof_{q}/symbols_{q}.txt"
    if not os.path.exists(path) or (q, "lazy") not in ns: print(f"{q:6} optimised  (missing profile or diff data)"); continue
    b, _ = cl.analyze(path)
    core = {k: b[k] for k in ["deserialize", "process", "serialize", "jit_opaque", "engine"]}; tot = sum(core.values())
    lazy = ns[(q, "lazy")]
    # JIT split by differencing (json framing = json_lazy - csv_lazy), capped to the JIT block
    jit_ns = lazy * core["jit_opaque"] / tot
    framing = max(0.0, ns[(q, "lazy")] - ns.get((q, "lazy_csvout"), ns[(q, "lazy")])) if q != "ysb" else 0.0
    framing = min(framing, jit_ns)
    deser = lazy * core["deserialize"] / tot
    ser = lazy * core["serialize"] / tot + framing
    proc = lazy * (core["process"] + core["engine"]) / tot + (jit_ns - framing)
    s = deser + proc + ser
    note = f"JIT {100*core['jit_opaque']/tot:.0f}% split: framing {framing:.1f} ns (json-csv diff) -> ser, rest -> proc; engine {100*core['engine']/tot:.0f}% folded into proc"
    print(f"{q:6} {'optimised':10} {100*deser/s:7.1f} {100*proc/s:6.1f} {100*ser/s:6.1f} | {lazy:7.1f} {deser:6.1f} {proc:6.1f} {ser:6.1f}  {note}")
    out.append([q, "optimised", 100*deser/s, 100*proc/s, 100*ser/s, lazy])
    if (q, "eager") in ns:
        print(f"{'':6} {'(eager)':10} {'':7} {'':6} {'':6} | {ns[(q,'eager')]:7.1f}  -> removable serde by differencing = {ns[(q,'eager')]-lazy:.1f} ns/row ({ns[(q,'eager')]/lazy:.2f}x)")
with open(f"{SC}/fig1_teaser_data.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["query", "arm", "deserialize_pct", "process_pct", "serialize_pct", "ns_per_row"]); w.writerows(out)
print(f"\nwrote {SC}/fig1_teaser_data.csv")
