#!/usr/bin/env python3
"""Bucket async-profiler collapsed stacks (cpu event, `threads,ann`) of a pbench Flink run into
deserialize / process / serialize / internal (engine-internal record serde across a keyBy) for the
Fig1-on-Flink figure. Mirrors classify.py of the NES Fig1 (2026-08-19):

  * thread = the primary split. `Source Data Fetcher ...` = Flink's CSV parse thread = DESERIALIZE
    (100% of its non-read, non-kernel samples, like NES's DataSrc thread). Task threads (Flink task
    names, `... (i/p)#a`) = query operators + JSON sink writer, split by NEAREST CLASSIFIED FRAME
    walking from the leaf up (a memcpy/HashMap/GenericRowData leaf inherits its caller's stage).
  * excluded (like NES kernel+idle): GC / C2 / VM / class-loading / coordinator / metrics threads,
    kernel-leaf samples, and file READ frames on the fetcher (NES nulled the read via InMemory
    prefill; Flink reads the page-cache-warm file on the fetcher thread).
  * residual = task-thread frames matching nothing (StreamTask/mailbox/SourceOperator glue) ->
    conservatively counted as PROCESS (biases against the serde claim).
Usage: classify_flink.py <query-name> <collapsed-file> [<collapsed-file> ...]
"""
import sys, re, collections

SER = [  # producing the output text: Flink json format + Jackson generator/databind + sink writer glue
    "org/apache/flink/formats/json/", "jackson2/com/fasterxml/jackson/core/", "jackson2/com/fasterxml/jackson/databind/",
    "FormatBlackHoleTableSinkFactory", "streaming/runtime/operators/sink/", "streaming/api/functions/sink/",
    "org/apache/flink/table/runtime/functions/SqlDateTimeUtils", "table/utils/DateTimeUtils", "DateTimeUtils",  # q10 DATE_FORMAT (NES: CASTFROMUNIXTS counted as serialize)
    "java/lang/Double.toString", "FloatingDecimal.toJavaFormatString", "jdk/internal/math/FloatingDecimal$BinaryToASCII",
    "Long.toString", "Integer.toString", "Long.getChars", "Integer.getChars", "StringBuilder", "StringConcatHelper",
]
DESER = [  # producing typed rows from input text
    "org/apache/flink/formats/csv/", "jackson2/com/fasterxml/jackson/dataformat/csv/",
    "org/apache/flink/connector/file/src/", "connector/file/table/", "StreamFormatAdapter",
    "Long.parseLong", "Integer.parseInt", "Double.parseDouble", "FloatingDecimal.readJavaFormatString",
    "FloatingDecimal.parseDouble", "BinaryStringData.fromString", "StringData.fromString",
    "org/apache/flink/connector/base/source/reader/",  # SplitFetcher / RecordsWithSplitIds handoff on the fetcher
    # Flink's csv format hands out LAZY strings (BinaryStringData.fromString(javaString)); the UTF-8
    # materialization + copy into the engine's binary string format happens in the FIRST operator that
    # touches the field (StringDataSerializer.copy inside the generated Calc). That is the tail of
    # deserialization (text -> engine-native representation), the exact analog of NES's varsized
    # string copy (getBasicStringParseFunction, counted as deserialize in the NES Fig1). YSB: ~27%.
    "BinaryStringData.materialize", "LazyBinaryFormat.ensureMaterialized", "BinaryStringData.ensureMaterialized",
    "StringUtf8Utils.encodeUTF8", "BinaryStringData.copy", "StringDataSerializer.copy", "BinarySegmentUtils.allocateReuseBytes",
]
READ = [  # raw file read (excluded — NES nulled it)
    "java/io/FileInputStream.readBytes", "FileInputStream.read", "sun/nio/ch/FileDispatcherImpl", "sun/nio/ch/FileChannelImpl",
    "java/io/RandomAccessFile.read", "org/apache/flink/core/fs/local/LocalDataInputStream",
]
INTERNAL = [  # engine-internal record (de)serialization across the keyBy network shuffle
    "org/apache/flink/runtime/io/network/", "runtime/io/network/api/writer/RecordWriter", "DataOutputSerializer",
    "DataInputDeserializer", "BinaryRowDataSerializer", "StreamElementSerializer", "SpillingAdaptiveSpanningRecordDeserializer",
    "streaming/runtime/io/StreamTaskNetworkInput", "streaming/runtime/io/RecordWriterOutput", "runtime/plugable/",
    "RowDataSerializer", "TypeSerializer", "BinaryRowDataUtil", "org/apache/flink/table/runtime/typeutils/",
]
PROC = [  # the actual query: generated Calc / aggregation / window code + table runtime operators
    "StreamExecCalc", "StreamExecWatermarkAssigner", "WatermarkAssigner", "GlobalWindowAggsHandler", "LocalWindowAggsHandler",
    "GroupingWindowAggsHandler", "WindowAggsHandler", "org/apache/flink/table/runtime/generated/",
    "org/apache/flink/table/runtime/operators/", "org/apache/flink/table/runtime/util/", "org/apache/flink/table/runtime/dataview/",
    "org/apache/flink/table/runtime/functions/", "org/apache/flink/runtime/state/", "org/apache/flink/streaming/api/operators/TimestampsAndWatermarks",
    "org/apache/flink/table/data/binary/BinaryRowData", "org/apache/flink/table/data/writer/", "BinaryRowWriter",
    "org/apache/flink/table/runtime/operators/aggregate/", "org/apache/flink/table/runtime/operators/window/",
    "StreamExecLocalWindowAggregate", "StreamExecGlobalWindowAggregate",
]
# frames that carry no stage information on their own -> skip while walking upward
GENERIC = re.compile(r"^(java/|jdk/|sun/|itable stub|vtable stub|\[|_|__|Interpreter|call_stub|JavaCalls|"
                     r"SharedRuntime|OptoRuntime|Runtime1|G1|TLAB|MemAllocator|InstanceKlass|ObjArrayKlass|"
                     r"TypeArrayKlass|Copy::|memcpy|memmove|memset|__memmove|__memcpy|__memset|malloc|free|"
                     r"libjvm|libc|/usr/lib|org/apache/flink/table/data/GenericRowData|org/apache/flink/table/data/binary/BinaryStringData|"
                     r"org/apache/flink/table/data/StringData|org/apache/flink/table/data/RowData|org/apache/flink/types/RowKind|"
                     r"org/apache/flink/table/data/TimestampData|org/apache/flink/table/data/DecimalData)")

def strip_ann(f):  # 'foo_[j]' -> 'foo'
    return re.sub(r"_\[[a-z0-9]\]$", "", f)

def is_kernel(f):
    return f.endswith("_[k]")

def match(f, keys):
    return any(k in f for k in keys)

def thread_kind(name):
    if name.startswith("[Source Data Fetcher"):
        return "fetcher"
    if re.search(r"\(\d+/\d+\)#\d+", name):   # Flink task thread name "... (1/1)#0"
        return "task"
    return "other"

def classify_stack(kind, frames):
    """frames: leaf-first list (thread name removed). Returns bucket."""
    if frames and is_kernel(frames[0]):
        # kernel leaf: read syscalls on the fetcher -> read; anything else -> kernel (excluded)
        if any(match(strip_ann(x), READ) for x in frames):
            return "read"
        return "kernel"
    if kind == "fetcher":
        for f in frames:
            if match(strip_ann(f), READ):
                return "read"
        return "deserialize"
    # task thread: nearest classified frame from the leaf up
    for f in frames:
        s = strip_ann(f)
        if match(s, DESER):    return "deserialize"   # before INTERNAL: StringDataSerializer.copy lives under typeutils/
        if match(s, INTERNAL): return "internal"
        if match(s, SER):      return "serialize"
        if match(s, PROC):     return "process"
        # generic frames are skipped implicitly (no match)
    return "residual"

def analyze(paths):
    buckets = collections.Counter(); per_thread = collections.Counter(); resid = collections.Counter()
    ser_top = collections.Counter(); proc_top = collections.Counter(); total = 0
    for p in paths:
        for line in open(p):
            stack, cnt = line.rsplit(" ", 1); cnt = int(cnt); total += cnt
            fr = stack.split(";")
            th = fr[0]; frames = list(reversed(fr[1:]))   # leaf first
            kind = thread_kind(th)
            per_thread[(kind, th[:60])] += cnt
            if kind == "other":
                buckets["other_threads"] += cnt; continue
            b = classify_stack(kind, frames)
            buckets[b] += cnt
            if b == "residual":
                # first non-generic frame, for the sanity list
                key = next((strip_ann(f)[:90] for f in frames if not GENERIC.match(strip_ann(f))), strip_ann(frames[0])[:90] if frames else "?")
                resid[key] += cnt
            elif b == "process":
                key = next((strip_ann(f)[:90] for f in frames if match(strip_ann(f), PROC)), "?"); proc_top[key] += cnt
            elif b == "serialize" and kind == "task":
                key = next((strip_ann(f)[:90] for f in frames if match(strip_ann(f), SER)), "?"); ser_top[key] += cnt
    return total, buckets, per_thread, resid, proc_top, ser_top

if __name__ == "__main__":
    q = sys.argv[1]; paths = sys.argv[2:]
    total, b, per_thread, resid, proc_top, ser_top = analyze(paths)
    pct = lambda k: 100.0 * b[k] / total
    print(f"[{q}] total samples {total}")
    print("per-thread share (kind, name):")
    for (k, n), c in per_thread.most_common(8): print(f"   {100*c/total:6.2f}%  {k:8} {n}")
    print("raw buckets (% of ALL samples):")
    for k in ["deserialize", "process", "residual", "serialize", "internal", "read", "kernel", "other_threads"]:
        print(f"   {k:14} {pct(k):6.2f}")
    # normalized like NES: stages = deser + process(+residual) + serialize (+internal shown separately)
    stages = {"deserialize": b["deserialize"], "process": b["process"] + b["residual"], "serialize": b["serialize"], "internal": b["internal"]}
    s = sum(stages.values())
    print("normalized over engine stages (%):", {k: round(100.0 * v / s, 1) for k, v in stages.items()})
    print("normalized WITHOUT internal (3-stage, NES footing):",
          {k: round(100.0 * stages[k] / (s - stages['internal']), 1) for k in ["deserialize", "process", "serialize"]})
    print("top residual anchors (counted as process):")
    for f, c in resid.most_common(8): print(f"   {100*c/total:6.2f}%  {f}")
    print("top process anchors:")
    for f, c in proc_top.most_common(6): print(f"   {100*c/total:6.2f}%  {f}")
    print("top serialize anchors (task thread):")
    for f, c in ser_top.most_common(6): print(f"   {100*c/total:6.2f}%  {f}")
    # machine-readable line
    print("CSV", q, ",".join(f"{k}={pct(k):.2f}" for k in ["deserialize", "process", "residual", "serialize", "internal", "read", "kernel", "other_threads"]))
