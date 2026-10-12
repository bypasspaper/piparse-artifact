#!/usr/bin/env python3
"""Fig2 STAGE CPU per row vs N (2026-09-25): deserialize / process / serialize, naive vs lazy, from the 20 perf
profiles (optprof_sweep_{naive,lazy}_n{1..10}/symbols_*.txt) + each profiled run's OWN thread-CPU artifacts
(results/artifacts/fig2_prof_sweep_*/<run_id>/) for the absolute CPU, + fig2_lazy_csvout medians for the JIT split.

Stage rules (same taxonomy as the Fig1 teaser, caption sentence: raw passthrough copy counts as PROCESSING):
  NAIVE (2026-08-19 Fig1 classify.py rules, thread-based): DataSrc thread = index+parse = DESERIALIZE; WorkerThread
        = naive JSON writer (fmt/stringstream/memmove/malloc...) = SERIALIZE, arithmetic/predicates = PROCESS,
        unlabeled = process (conservative). Kernel/idle excluded.
  LAZY  (classify_v2 rules, both threads by symbol): index kernels + parse codecs = DESERIALIZE; ZMIJ/JSON writer
        symbols = SERIALIZE; memcpy/operators/engine glue = PROCESS; the opaque [JIT] block is split by differencing:
        framing_ns = ns(json lazy) - ns(csv lazy)  -> SERIALIZE (JSON per-field keys), remainder -> PROCESS
        (scan glue + raw span copies). Idle spin (worker) / kernel excluded.
Absolute: stage_ns_per_row = stage_fraction_of_nonidle_samples x nonidle_CPU_ns_per_row, where nonidle CPU/row =
  total CPU in the sink window (procfs, all threads) x (1 - idle_fraction) / rows.  usage: stage_cpu_sweep.py [out.csv]"""
import csv, os, re, sys, glob, statistics, importlib.util, duckdb
SC = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.expanduser("~/work/piparse-bench")
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{SC}/fig2_stage_cpu.csv"
spec = importlib.util.spec_from_file_location("cl", f"{SC}/classify_v2.py"); cl = importlib.util.module_from_spec(spec)
_argv = sys.argv; sys.argv = ["x"]; spec.loader.exec_module(cl); sys.argv = _argv

# ---- naive rules (port of the 2026-08-19 classify.py) ----
NAIVE_SER = ["fmt::", "JSONFormat", "formatOriginalStringstream", "formatFloat", "format_float", "formattedBytesToString",
             "to_string", "do_write_float", "vformat", "write_padded", "copy_noinline", "on_format_specs", "parse_format_string",
             "format_handler", "format_custom", "basic_appender", "transform_view", "join_view", "iota_view",
             "CastFromUnixTimestamp", "stringstream", "ostream", "basic_string", "char_traits", "__memmove", "memcpy",
             "memset", "malloc", "free", "cfree", "_int_free", "operator new", "operator delete", "_Znwm", "_ZdlPv"]
NAIVE_PROC = ["Modulo", "Multiply", "Divide", "Addition", "Subtract", "Arithmetic", "Selection", "Equals", "LessThan",
              "GreaterThan", "Comparison", "Predicate", "Filter", "evaluate", "ScanPhysical", "EmitPhysical", "MapPhysical"]
IDLE = cl.IDLE
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
        if kind == "k": b["idle"] += pct; continue
        if any(k in sym or k in dso for k in IDLE): b["idle"] += pct; continue
        if comm.startswith("DataSrc"): b["deserialize"] += pct
        elif comm.startswith("WorkerThread"):
            if any(k in sym for k in NAIVE_SER): b["serialize"] += pct
            else: b["process"] += pct                      # named ops + unlabeled JIT glue -> process (conservative, as 2026-08-19)
        else: b["other"] += pct
    return b
def lazy_buckets(path):
    b, _ = cl.analyze(path)   # deserialize/process/serialize/jit_opaque/engine/idle/kernel/other/other_threads
    return {"deserialize": b["deserialize"], "process": b["process"] + b["engine"], "serialize": b["serialize"],
            "jit_opaque": b["jit_opaque"], "idle": b["idle"] + b["kernel"], "other": b["other"] + b["other_threads"]}
# ---- absolute CPU per row from the profiled run's own artifacts ----
con = duckdb.connect(f"{ROOT}/results/piparse_bench.duckdb", read_only=True)
def run_cpu(exp):
    r = con.sql(f"select run_id, input_rows, throughput_mrows_s, processing_time_s from runs where experiment='{exp}' order by timestamp desc limit 1").fetchone()
    if not r: return None
    run_id, rows, mr, win = r; d = f"{ROOT}/results/artifacts/{exp}/{run_id}"
    tc = f"{d}/threadcpu.csv"; mons = sorted(glob.glob(f"{d}/query_*_monitoring.csv"))
    if not (os.path.exists(tc) and mons): return {"rows": rows, "wall_ns": 1e9 * win / rows, "cpu_ns": None}
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
    return {"rows": rows, "wall_ns": 1e9 * (t1 - t0) / rows, "cpu_ns": 1e9 * total / rows, "window_s": t1 - t0}
# ---- csv-out differencing for the lazy JIT split ----
csvout = {}
for q, mr in con.sql("select query_ref, throughput_mrows_s from runs where experiment='fig2_lazy_csvout' and throughput_mrows_s is not null").fetchall():
    csvout.setdefault(int(re.search(r"_n(\d+)$", q).group(1)), []).append(1000 / mr)
csvout = {n: statistics.median(v) for n, v in csvout.items()}
out = []
print(f"{'rung':6} {'N':>2} {'wall':>7} {'cpu_tot':>8} {'idle%':>5} | {'deser':>7} {'proc':>7} {'ser':>7}  ns/row | {'deser%':>6} {'proc%':>5} {'ser%':>5}  notes")
for rung in ("naive", "lazy"):
    for n in range(1, 11):
        name = f"sweep_{rung}_n{n}"; sym = f"{SC}/optprof_{name}/symbols_{name}.txt"
        if not os.path.exists(sym): continue
        b = naive_buckets(sym) if rung == "naive" else lazy_buckets(sym)
        allp = sum(b.values()); idle = b["idle"] / allp if allp else 0
        cpu = run_cpu(f"fig2_prof_{name}")
        if not cpu or cpu["cpu_ns"] is None: print(f"{rung:6} {n:>2}  (no cpu artifacts)"); continue
        nonidle_ns = cpu["cpu_ns"] * (1 - idle)
        st = {k: b[k] for k in ("deserialize", "process", "serialize")}; jit = b.get("jit_opaque", 0.0); other = b["other"]
        note = ""
        if rung == "lazy":
            # JIT split by differencing (wall ns): framing = json - csv, capped to the JIT block's ns
            jit_ns = nonidle_ns * jit / (allp * (1 - idle)) if allp else 0
            framing = max(0.0, cpu["wall_ns"] - csvout[n]) if n in csvout else 0.0
            framing = min(framing, jit_ns); note = f"JIT {100*jit/(allp*(1-idle)):.0f}% of nonidle: framing {framing:.1f} ns -> ser, {jit_ns-framing:.1f} -> proc"
            frac = {k: v / (allp * (1 - idle)) for k, v in st.items()}
            ns = {k: nonidle_ns * frac[k] for k in st}; ns["serialize"] += framing; ns["process"] += (jit_ns - framing)
            ns["process"] += nonidle_ns * other / (allp * (1 - idle))   # unlabeled -> process (conservative)
        else:
            frac = {k: v / (allp * (1 - idle)) for k, v in st.items()}
            ns = {k: nonidle_ns * frac[k] for k in st}; ns["process"] += nonidle_ns * other / (allp * (1 - idle))
        s = sum(ns.values())
        print(f"{rung:6} {n:>2} {cpu['wall_ns']:7.1f} {cpu['cpu_ns']:8.1f} {100*idle:5.1f} | {ns['deserialize']:7.1f} {ns['process']:7.1f} {ns['serialize']:7.1f}         | {100*ns['deserialize']/s:6.1f} {100*ns['process']/s:5.1f} {100*ns['serialize']/s:5.1f}  {note}")
        out.append({"rung": rung, "N": n, "wall_ns_per_row": round(cpu["wall_ns"], 2), "cpu_ns_per_row_total": round(cpu["cpu_ns"], 2),
                    "idle_frac": round(idle, 4), "deser_ns": round(ns["deserialize"], 2), "proc_ns": round(ns["process"], 2),
                    "ser_ns": round(ns["serialize"], 2), "deser_pct": round(100*ns["deserialize"]/s, 1), "proc_pct": round(100*ns["process"]/s, 1),
                    "ser_pct": round(100*ns["serialize"]/s, 1), "jit_frac_nonidle": round(jit/(allp*(1-idle)), 4) if rung == "lazy" and allp else "",
                    "csvout_wall_ns": round(csvout.get(n, float("nan")), 2)})
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
print("wrote", OUT)
