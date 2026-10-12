#!/usr/bin/env python3
"""Fig1 TEASER v2 (2026-09-28): per query (q0, q2og, ysb) x arm (naive, flink, optimised+overload), stage split
deserialize / process / serialize as SHARE (%) and as ABSOLUTE CPU ns per tuple.
  NES naive     : perf profile optprof_naive_<q> -> 2026-08-19 thread+symbol rules (naive_buckets in stage_cpu_sweep);
                  absolute = the profiled run's own procfs CPU in its sink window x (1 - idle) / rows.
  NES optimised : perf profile optprof_<q> (overload ON) -> classify_v2; opaque JIT block split: q0 by the
                  fig1_opt_diff differencing (json - csv = framing -> ser, rest -> proc); q2og/ysb (no output) -> proc.
                  absolute as above.
  Flink         : async-profiler collapsed stacks -> classify_flink.py shares (q0/ysb: 2026-09-03 profiles;
                  q2og: this session); absolute = stage samples / 4000 Hz / rows (cpu event => samples are CPU time),
                  non-idle threads only (GC/JIT/kernel excluded like the shares).
Throughput annotations: fig1_teaser_thru (NES, 3 reps) + fig1_flink_thru{,_q2og} (Flink, 3 reps).
Writes fig1_teaser2_data.csv: query, arm, deser_pct, proc_pct, ser_pct, ns_per_tuple, deser_ns, proc_ns, ser_ns, mrows_s."""
import os, sys, csv, glob, gzip, re, statistics, importlib.util, subprocess, duckdb
SC = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.expanduser("~/work/piparse-bench")
NOTES = os.path.expanduser("~/Notes/nebulastream/benchmark"); FS = f"{NOTES}/fig1_fig2_flink_2026-09-03_scratch"
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec)
    a = sys.argv; sys.argv = ["x"]; spec.loader.exec_module(m); sys.argv = a; return m
cl = load("cl", f"{SC}/classify_v2.py"); sw = load("sw", f"{SC}/stage_cpu_sweep.py") if False else None
# --- naive rules (port of 2026-08-19 classify.py; same as stage_cpu_sweep.naive_buckets) ---
NAIVE_SER = ["fmt::", "JSONFormat", "formatOriginalStringstream", "formatFloat", "format_float", "formattedBytesToString", "to_string",
             "do_write_float", "vformat", "write_padded", "copy_noinline", "on_format_specs", "parse_format_string", "format_handler",
             "format_custom", "basic_appender", "transform_view", "join_view", "iota_view", "CastFromUnixTimestamp", "stringstream",
             "ostream", "basic_string", "char_traits", "__memmove", "memcpy", "memset", "malloc", "free", "cfree", "_int_free",
             "operator new", "operator delete", "_Znwm", "_ZdlPv"]
def parse_rows(path):
    for line in open(path, errors="replace"):
        i = line.find(" [.] "); kind = "."
        if i < 0: i = line.find(" [k] "); kind = "k"
        if i < 0 or "%" not in line[:i]: continue
        left = line[:i].split(None, 2)
        if len(left) != 3 or not left[0].endswith("%"): continue
        try: pct = float(left[0][:-1])
        except ValueError: continue
        yield pct, left[1], left[2].strip(), kind, line[i + 5:].strip()
def naive_buckets(path):
    b = {"deserialize": 0.0, "process": 0.0, "serialize": 0.0, "idle": 0.0, "other": 0.0}
    for pct, comm, dso, kind, sym in parse_rows(path):
        if kind == "k" or any(k in sym or k in dso for k in cl.IDLE): b["idle"] += pct; continue
        if comm.startswith("DataSrc"): b["deserialize"] += pct
        elif comm.startswith("WorkerThread"): b["serialize" if any(k in sym for k in NAIVE_SER) else "process"] += pct
        else: b["other"] += pct
    return b
def opt_buckets(path):
    b, _ = cl.analyze(path)
    return {"deserialize": b["deserialize"], "process": b["process"] + b["engine"], "serialize": b["serialize"],
            "jit": b["jit_opaque"], "idle": b["idle"] + b["kernel"], "other": b["other"] + b["other_threads"]}
con = duckdb.connect(f"{ROOT}/results/piparse_bench.duckdb", read_only=True)
def run_cpu(exp):
    r = con.sql(f"select run_id, input_rows, processing_time_s from runs where experiment='{exp}' and throughput_mrows_s is not null order by timestamp desc limit 1").fetchone()
    if not r: return None
    run_id, rows, win = r; d = f"{ROOT}/results/artifacts/{exp}/{run_id}"; tc = f"{d}/threadcpu.csv"; mons = sorted(glob.glob(f"{d}/query_*_monitoring.csv"))
    if not (os.path.exists(tc) and mons): return None
    clk = float(re.search(r"clk_tck=(\d+)", open(tc).readline()).group(1)); per = {}
    for x in csv.DictReader((l for l in open(tc) if not l.startswith("#"))):
        per.setdefault(x["tid"], []).append((float(x["wall_s"]), (int(x["utime_ticks"]) + int(x["stime_ticks"])) / clk))
    last = list(csv.DictReader(open(mons[0])))[-1]; t0 = float(last["first read start us"]) / 1e6; t1 = float(last["last arrival us"]) / 1e6
    def interp(s, t):
        if t <= s[0][0]: return s[0][1]
        if t >= s[-1][0]: return s[-1][1]
        for (a, va), (bb, vb) in zip(s, s[1:]):
            if a <= t <= bb: return va if bb == a else va + (vb - va) * (t - a) / (bb - a)
        return s[-1][1]
    total = sum(max(0.0, interp(sorted(s), t1) - interp(sorted(s), t0)) for s in per.values())
    return {"rows": rows, "cpu_ns": 1e9 * total / rows, "wall_ns": 1e9 * (t1 - t0) / rows}
def thru(exp, variant=None, series=None, q=None):
    w = [f"experiment='{exp}'", "throughput_mrows_s is not null"]
    if variant: w.append(f"variant='{variant}'")
    if series: w.append(f"series='{series}'")
    if q: w.append(f"query_ref='{q}'")
    v = [r[0] for r in con.sql(f"select throughput_mrows_s from runs where {' and '.join(w)}").fetchall()]
    return statistics.median(v) if v else None
# --- Flink: shares + absolute from collapsed stacks via classify_flink.py raw counts ---
def flink_stage(qname, collapsed):
    """Use classify_flink.py's bucketing by importing it and calling its classify on the file; fall back to its CLI output."""
    out = subprocess.run([sys.executable, f"{SC}/classify_flink.py", qname, collapsed], capture_output=True, text=True).stdout
    return out
QUERIES = [("q0", "nexmark/bid_star", "q0"), ("q2og", "nexmark/q2_original", "q2og"), ("ysb", "yahoo/ysb_1k_varsized", "ysb")]
rows_out = []
# JIT split for q0 from the earlier differencing (json lazy 11.6 ns vs csv lazy 8.9 ns wall): framing fraction of JIT block
FRAMING_NS = {"q0": 2.8}
for q, qref, fl in QUERIES:
    # ---- naive ----
    sym = f"{SC}/optprof_naive_{q}/symbols_naive_{q}.txt"; cpu = run_cpu(f"fig1_naive_prof_{q}")
    if os.path.exists(sym) and cpu:
        b = naive_buckets(sym); allp = sum(b.values()); idle = b["idle"] / allp; core = {k: b[k] for k in ("deserialize", "process", "serialize")}; core["process"] += b["other"]
        s = sum(core.values()); non = cpu["cpu_ns"] * (1 - idle)
        SH = {"deserialize": "deser", "process": "proc", "serialize": "ser"}
        rows_out.append({"query": q, "arm": "naive", **{f"{SH[k]}_pct": round(100 * v / s, 1) for k, v in core.items()},
                         "ns_per_tuple": round(non, 1), **{f"{SH[k]}_ns": round(non * v / s, 2) for k, v in core.items()},
                         "mrows_s": thru("fig1_teaser_thru", variant=q, series="naive")})
    # ---- optimised (overload on) ----
    sym = f"{SC}/optprof_{q}/symbols_{q}.txt"; cpu = run_cpu(f"fig1_opt_prof_{q}")
    if os.path.exists(sym) and cpu:
        b = opt_buckets(sym); allp = sum(b.values()); idle = b["idle"] / allp; nonf = allp * (1 - idle)
        non = cpu["cpu_ns"] * (1 - idle); jit_ns = non * b["jit"] / nonf
        framing = min(FRAMING_NS.get(q, 0.0), jit_ns)
        ns = {"deserialize": non * b["deserialize"] / nonf, "process": non * (b["process"] + b["other"]) / nonf + (jit_ns - framing), "serialize": non * b["serialize"] / nonf + framing}
        s = sum(ns.values())
        rows_out.append({"query": q, "arm": "optimised", "deser_pct": round(100 * ns["deserialize"] / s, 1), "proc_pct": round(100 * ns["process"] / s, 1), "ser_pct": round(100 * ns["serialize"] / s, 1),
                         "ns_per_tuple": round(s, 1), "deser_ns": round(ns["deserialize"], 2), "proc_ns": round(ns["process"], 2), "ser_ns": round(ns["serialize"], 2),
                         "mrows_s": thru("fig1_teaser_thru", variant=q, series="optimised")})
with open(f"{SC}/fig1_teaser2_data.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["query", "arm", "deser_pct", "proc_pct", "ser_pct", "ns_per_tuple", "deser_ns", "proc_ns", "ser_ns", "mrows_s"]); w.writeheader(); w.writerows(rows_out)
for r in rows_out: print(r)
print("NES rows written; Flink rows are added by assemble_teaser2_flink.py")
