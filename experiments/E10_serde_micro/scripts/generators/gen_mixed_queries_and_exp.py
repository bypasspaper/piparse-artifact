#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the MIXED-TYPE serde-micro query YAMLs + experiment (companion to the float/int gens).

Two directions, reusing the existing pure-panel datasets (no new data):
  i2f: int64 CSV/native in  -> TOFLOAT64(c_i) -> FLOAT64 out  (cheap parse, expensive serialize)
  f2i: float64 CSV/native in -> TOINT64(c_i)  -> INT64 out    (expensive parse, cheap serialize)

Needs the TOFLOAT64/TOINT64 conversion function plugins in the worker binary (uncommitted,
nes-{logical,physical}-operators ToFloat64/ToInt64 plugin files on branch
benchmark-piparse-lazyparse-fast-csv). 4 arms per direction: the no_serde arm is the CAST-COST
CONTROL (native->native still pays the per-field cast + Map that SELECT * didn't have).
"""
import os

QDIR = "/home/user/work/piparse-bench/queries/serde_micro"
EXP = "/home/user/work/piparse-bench/experiments/serde_micro_mixed_full.yaml"
DATA = "/home/user/work/nebulastream-public/cmake-build-release/nes-systests/testdata/large/serde_micro"
ROWS, KS = 2_000_000, list(range(1, 21))

DIRS = {
    "i2f": dict(func="TOFLOAT64", in_t="INT64", out_t="FLOAT64", data_pre="int",
                desc="int64 in -> FLOAT64 out (cheap parse, expensive float serialize)"),
    "f2i": dict(func="TOINT64", in_t="FLOAT64", out_t="INT64", data_pre="float",
                desc="float64 in -> INT64 out (expensive float parse, cheap int serialize)"),
}

QTPL = """# SPDX-License-Identifier: Apache-2.0
# serde-micro MIXED {d}: {func} cast on K={K} {in_t} columns -> {out_t} output.
# Reuses the pure-panel {data_pre}k{K} datasets; needs the {func} function plugin in the binary.
query:
  name: serde_micro_{d}k{K}
  description: "serde micro mixed: {desc}, K={K}"
  sql: |
    SELECT {projection} FROM src
  sources:
    - name: src
      schema:
{schema}
      data:
        csv:
          file: large/serde_micro/{data_pre}k{K}.csv
          size_bytes: {csv_sz}
          rows: {rows}
        native:
          file: large/serde_micro/{data_pre}k{K}.nes
          size_bytes: {nes_sz}
          rows: {rows}
  sink_schema:
{sink}
"""


def gen_queries():
    for d, c in DIRS.items():
        for K in KS:
            projection = ", ".join(f"{c['func']}(c{i}) AS c{i}" for i in range(K))
            schema = "\n".join(f"        - {{ name: c{i}, type: {c['in_t']}, not_null: true }}" for i in range(K))
            sink = "\n".join(f"    - {{ name: c{i}, type: {c['out_t']}, not_null: true }}" for i in range(K))
            csv_sz = os.path.getsize(f"{DATA}/{c['data_pre']}k{K}.csv")
            nes_sz = os.path.getsize(f"{DATA}/{c['data_pre']}k{K}.nes")
            assert nes_sz == ROWS * K * 8
            open(f"{QDIR}/{d}k{K}.yaml", "w").write(QTPL.format(
                d=d, K=K, projection=projection, schema=schema, sink=sink,
                csv_sz=csv_sz, nes_sz=nes_sz, rows=ROWS, **c))
    print(f"wrote {len(KS) * len(DIRS)} mixed query YAMLs")


HEAD = """# SPDX-License-Identifier: Apache-2.0
experiment:
  name: serde_micro_mixed_full
  description: >
    Serde-overhead micro, MIXED-TYPE panels: i2f (int64 in -> TOFLOAT64 -> float64 JSON out) and
    f2i (float64 in -> TOINT64 -> int64 JSON out). Companion to serde_micro_full (float) +
    serde_micro_int_full (int): shows the FLOAT half alone (serialize in i2f, parse in f2i) bounds
    the mixed pipeline from below. Same r3 footing (compiled default-invoke, no fnattr/inline/tcb,
    InMemory W1); 4 arms x 20 K x 2 directions x 3 reps = 480 runs. NO naive arm (its story is told).
    GOTCHAS: (1) needs the uncommitted TOFLOAT64/TOINT64 function plugins in the release binary --
    if the worker rejects the query with FunctionNotImplemented, the binary is stale (build-dir
    gotcha: ALWAYS NES_BUILD_DIR=cmake-build-release). (2) no_serde here is NOT a pure memcpy
    passthrough: the cast forces a Map that rewrites every row -- that arm IS the cast-cost control;
    compare it against the pure panels' no_serde to price the cast+Map overhead. (3) value
    distributions shift on the serialize side vs the pure panels (ints cast to double are
    integral-valued -> short ZMIJ output; floats [0,1e5) 6-decimals truncate to <=6-digit ints) --
    footnote, don't compare serialize ns/field across panels at face value. (4) y=rows/s: decompose
    divides throughput_mbps by per-arm INPUT bytes/row (native K*8, CSV size/2M) x REPEAT (20).
    RUN: cd ~/work/piparse-bench && PBENCH_KEEP_LOGS=1 uv run python bench.py run \\
           experiments/serde_micro_mixed_full.yaml \\
           --build-dir ~/work/nebulastream-public/cmake-build-release --worker-port 9099
  primary_metric: throughput_mbps
  higher_is_better: true
  repetitions: 3
  aggregation: median

defaults:
  system: nebulastream
  branch: benchmark-piparse-lazyparse-fast-csv
  mode: worker-cli
  build: native
  data_size: csv
  topology: single-node
  warm_read: true
  completion_timeout_s: 1800
  overload: false
  worker:
    query_engine:
      number_of_worker_threads: 1
      number_of_io_threads: 1
      invoke_mode_configuration: default
      inline_invoke_calls: false
      trace_constant_bytes: false
      pin_threads: true
      ccx_aware_task_queues: false
      admission_queue_size: 1024
    default_query_execution: { operator_buffer_size: 131072, execution_mode: COMPILER }
    number_of_buffers_in_global_buffer_manager: 16384
    dump_compilation_result: NONE
  query_config:
    source_type: InMemory
    sink_type: Monitoring
    input_formatter: { type: SequentialCSV, threading_mode: SEQUENTIAL, allow_commas_in_strings: false }
    output_formatter: { type: JSON }
    input_parser: {}
    output_parser: {}
  generator: { repeat: 1 }
  worker_env: { NES_INMEM_PREFILL: 1, NES_INMEM_REPEAT: 20, NES_INMEM_BUFSIZE: 131072 }

_iin: &iin { int64: FastINT64 }
_fin: &fin { f64: EiselFloatF64 }
_fout: &fout { f64: ZMIJF64 }

# i2f: int parse side, float serialize side
_arms_i2f: &arms_i2f
  label: "serde arm"
  explicit:
    - name: no_serde
      baseline: true
      overrides:
        data_size: native
        query_config.input_formatter: { type: SystemNative, string_length: "1" }
        query_config.output_formatter: { type: NATIVE }
        query_config.input_parser: {}
        query_config.output_parser: {}
    - name: only_deser
      overrides:
        data_size: csv
        query_config.input_formatter: { type: SequentialCSV, threading_mode: SEQUENTIAL, allow_commas_in_strings: false, eager_parse: true }
        query_config.output_formatter: { type: NATIVE }
        query_config.input_parser: *iin
        query_config.output_parser: {}
    - name: only_ser
      overrides:
        data_size: native
        query_config.input_formatter: { type: SystemNative, string_length: "1" }
        query_config.output_formatter: { type: JSON }
        query_config.input_parser: {}
        query_config.output_parser: *fout
    - name: serde
      overrides:
        data_size: csv
        query_config.input_formatter: { type: SequentialCSV, threading_mode: SEQUENTIAL, allow_commas_in_strings: false, eager_parse: true }
        query_config.output_formatter: { type: JSON }
        query_config.input_parser: *iin
        query_config.output_parser: *fout

# f2i: float parse side, int serialize side (default to_chars int output)
_arms_f2i: &arms_f2i
  label: "serde arm"
  explicit:
    - name: no_serde
      baseline: true
      overrides:
        data_size: native
        query_config.input_formatter: { type: SystemNative, string_length: "1" }
        query_config.output_formatter: { type: NATIVE }
        query_config.input_parser: {}
        query_config.output_parser: {}
    - name: only_deser
      overrides:
        data_size: csv
        query_config.input_formatter: { type: SequentialCSV, threading_mode: SEQUENTIAL, allow_commas_in_strings: false, eager_parse: true }
        query_config.output_formatter: { type: NATIVE }
        query_config.input_parser: *fin
        query_config.output_parser: {}
    - name: only_ser
      overrides:
        data_size: native
        query_config.input_formatter: { type: SystemNative, string_length: "1" }
        query_config.output_formatter: { type: JSON }
        query_config.input_parser: {}
        query_config.output_parser: {}
    - name: serde
      overrides:
        data_size: csv
        query_config.input_formatter: { type: SequentialCSV, threading_mode: SEQUENTIAL, allow_commas_in_strings: false, eager_parse: true }
        query_config.output_formatter: { type: JSON }
        query_config.input_parser: *fin
        query_config.output_parser: {}

_noop_x: &noop_x { label: "config", parameter: topology, values: [single-node] }
_tput_y: &tput_y { metric: throughput_mbps, label: "Throughput (MB/s)" }

variants:
"""

VTPL = """  - name: {d}_k{K}
    description: "K={K} {desc}"
    query: serde_micro/{d}k{K}
    axes: {{ x: *noop_x, series: *arms_{d} }}
    y: *tput_y
    visualization: {{ type: grouped_bar }}
"""


def gen_exp():
    with open(EXP, "w") as f:
        f.write(HEAD)
        for d, c in DIRS.items():
            for K in KS:
                f.write(VTPL.format(d=d, K=K, desc=c["desc"]))
    print(f"wrote {EXP}")


if __name__ == "__main__":
    gen_queries()
    gen_exp()
