#!/usr/bin/env python3
"""Bucket a flat perf report (--sort comm,dso,symbol) of the OPTIMISED arm into
deserialize / process / serialize (+ jit_opaque, engine, kernel, other) per the 2026-09-25 taxonomy:
  deserialize = converting input text into an engine representation: index kernels + parse codecs (+ DataSrc thread)
  serialize   = producing output text: float/int formatting, JSON key/framing writers, output-formatter code
  process     = operator work incl. things that MOVE or INSPECT bytes without converting them:
                raw passthrough memcpy/memmove (caption: a native engine would copy too), overload byte compares,
                hash/aggregate/window code
  engine      = task/buffer/pipeline mechanics (folded into process for the figure, disclosed in the caption)
  jit_opaque  = anonymous JIT blocks on the worker thread -- ambiguous (copy loop + key writes + operator code);
                reported separately so the split can be decided with knob differencing.
usage: classify_v2.py <symbols_X.txt> [...]"""
import re, sys, os
row = re.compile(r'^\s*([0-9.]+)%\s+(\S+)\s+(.+?)\s+\[([.k])\]\s+(.*?)\s*$')   # dso may contain spaces ('[JIT] tid N')
DESER = ["computeBlocks", "indexBand", "indexSequential", "flattenBits", "CSVInputFormatIndexer", "SIMDCSV", "FieldBand", "FieldOffsets",
         "FieldIndexFunction", "InputFormatter", "SequenceShredder", "parseNumber", "parseRawValue", "Eisel", "FastINT",
         "TracedINT", "TracedUINT", "from_chars", "strtod", "stod", "RawValueParser", "fast_float", "parseValue"]
SER   = ["ZMIJ", "zmij", "to_chars", "formatAndWrite", "writeJson", "JSONOutputFormatter", "OutputFormatter", "formatFloat",
         "fmt::", "writeValue", "writeField", "CastFromUnixTimestamp", "writeRawBytes", "tryWriteCoalesced"]
COPY  = ["__memmove", "__memcpy", "memcpy", "memmove"]
PROC  = ["hash", "Hash", "Aggregat", "Window", "Slice", "Selection", "Filter", "Predicate", "Modulo", "Multiply",
         "Comparison", "Equals", "wordEqual", "memcmp", "bcmp", "__memcmp", "Map", "Project", "evaluate"]
IDLE  = ["[vdso]", "sched_yield", "__sched_yield", "poll_with_backoff", "try_acquire", "steady_clock::now", "clock_gettime",
         "__cxx_atomic_wait", "futex", "nanosleep", "usleep", "tryWaitForTurn", "__atomic_semaphore"]
ENGINE= ["printf", "BaseTask", "__variant_detail", "any_invocable", "WorkTask", "RunningQueryPlan", "TupleBuffer", "BufferManager", "BufferProvider", "TaskQueue", "ShardedTaskQueue", "emitWork", "PipelineExecution",
         "ExecutablePipeline", "QueryEngine", "ThreadPool", "malloc", "free", "cfree", "_int_", "operator new",
         "operator delete", "_Znwm", "_ZdlPv", "memset", "__memset", "std::function", "_M_invoke", "folly", "moodycamel",
         "atomic", "pthread", "__GI_", "clock_gettime", "steady_clock", "LogContext", "spdlog", "Statistic", "Monitoring"]
def bucket(sym, dso):
    for k in IDLE:
        if k in sym or k in dso: return "idle"
    if dso.startswith("[JIT]") or dso in ("//anon", "[unknown]") or sym.startswith("0x") or "[unknown]" in sym: return "jit_opaque"
    for k in DESER:
        if k in sym: return "deserialize"
    for k in SER:
        if k in sym: return "serialize"
    for k in COPY:
        if k in sym: return "process"          # raw passthrough copy -> process (see taxonomy)
    for k in PROC:
        if k in sym: return "process"
    for k in ENGINE:
        if k in sym: return "engine"
    return "other"
def analyze(path):
    b = {k: 0.0 for k in ["deserialize","process","serialize","jit_opaque","engine","idle","kernel","other","other_threads"]}
    top = {}
    for line in open(path, errors="replace"):
        # fast marker split (regex backtracks quadratically on 2000-char lambda names)
        i = line.find(" [.] "); kind = "."
        if i < 0:
            i = line.find(" [k] "); kind = "k"
        if i < 0 or "%" not in line[:i]: continue
        left = line[:i].split(None, 2)
        if len(left) != 3 or not left[0].endswith("%"): continue
        try: pct = float(left[0][:-1])
        except ValueError: continue
        comm, dso, sym = left[1], left[2].strip(), line[i + 5:].strip()
        if kind == "k": b["kernel"] += pct; continue
        if comm.startswith("DataSrc") or comm.startswith("WorkerThread"):
            k = bucket(sym, dso)          # 2026-09-25: the fused sequential pipeline runs ON the source thread;
        else:                              # the worker thread mostly idle-spins -> classify BOTH by symbol
            b["other_threads"] += pct; continue
        b[k] += pct; key = (comm, k, sym[:80]); top[key] = top.get(key, 0) + pct
    return b, top
for path in sys.argv[1:]:
    b, top = analyze(path); tot = sum(b.values())
    print(f"\n##### {os.path.basename(path)}  (sum of parsed rows {tot:.1f}%)")
    print("raw % of all samples: " + "  ".join(f"{k}={v:.1f}" for k, v in b.items()))
    per_thread = {}
    for (comm, k, sym), pct in top.items(): per_thread.setdefault(comm, {}).setdefault(k, 0.0); per_thread[comm][k] += pct
    for comm in sorted(per_thread): print(f"  {comm:16} " + "  ".join(f"{k}={v:.1f}" for k, v in sorted(per_thread[comm].items(), key=lambda x: -x[1])))
    core = {k: b[k] for k in ["deserialize","process","serialize","jit_opaque","engine"]}; s = sum(core.values()) or float("nan")
    print("normalised over deser+process+serialize+jit_opaque+engine: " + "  ".join(f"{k}={100*v/s:.1f}" for k, v in core.items()))
    print("\n  top symbols by bucket (worker + source threads):")
    for (comm, k, sym), pct in sorted(top.items(), key=lambda x: -x[1])[:28]:
        print(f"   {pct:6.2f}%  {comm:16} {k:12} {sym}")
