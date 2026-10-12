#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate K=1..20 INT64 serde-micro query YAMLs + the int experiment (companion to the float gen)."""
import os
QDIR = "/home/user/work/piparse-bench/queries/serde_micro"
EXP = "/home/user/work/piparse-bench/experiments/serde_micro_int_full.yaml"
DATA = "/home/user/work/nebulastream-public/cmake-build-release/nes-systests/testdata/large/serde_micro"
ROWS, KS = 2_000_000, list(range(1, 21))

QTPL = """# SPDX-License-Identifier: Apache-2.0
# serde-micro INT: SELECT * on K={K} int64 columns. CSV + SystemNative binary twin.
query:
  name: serde_micro_intk{K}
  description: "serde micro: SELECT * on {K} int64 cols (passthrough projection)"
  sql: |
    SELECT * FROM src
  sources:
    - name: src
      schema:
{schema}
      data:
        csv:
          file: large/serde_micro/intk{K}.csv
          size_bytes: {csv_sz}
          rows: {rows}
        native:
          file: large/serde_micro/intk{K}.nes
          size_bytes: {nes_sz}
          rows: {rows}
  sink_schema:
{sink}
"""

def gen_queries():
    for K in KS:
        schema = "\n".join(f"        - {{ name: c{i}, type: INT64, not_null: true }}" for i in range(K))
        sink = "\n".join(f"    - {{ name: src.c{i}, type: INT64, not_null: true }}" for i in range(K))
        csv_sz = os.path.getsize(f"{DATA}/intk{K}.csv"); nes_sz = os.path.getsize(f"{DATA}/intk{K}.nes")
        assert nes_sz == ROWS*K*8
        open(f"{QDIR}/intk{K}.yaml","w").write(QTPL.format(K=K,schema=schema,sink=sink,csv_sz=csv_sz,nes_sz=nes_sz,rows=ROWS))
    print(f"wrote {len(KS)} int query YAMLs")

HEAD = """# SPDX-License-Identifier: Apache-2.0
experiment:
  name: serde_micro_int_full
  description: >
    Serde-overhead 2x2 micro, INT64 panel (companion to serde_micro_full's float panel; two-panel figure).
    r3 (compiled default-invoke, no fnattr/inline/tcb, InMemory W1, FastINT64 in / to_chars int out).
    5 arms x K=1..20. y=rows/s (decompose divides by bytes/row: native K*8, CSV size/2M). PER-ARM REPEAT:
    fast arms 20 (x20), serde_naive 3 (x3) -- the stringstream arm is 40x slower so it needs no repeat;
    this avoids the ~50min tail the float run hit with uniform REPEAT=20. Decompose applies REPEAT[arm].
    RUN: cd ~/work/piparse-bench && PBENCH_KEEP_LOGS=1 uv run python bench.py run \\
           experiments/serde_micro_int_full.yaml \\
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
_env_naive: &env_naive { NES_INMEM_PREFILL: 1, NES_INMEM_REPEAT: 3, NES_INMEM_BUFSIZE: 131072, NES_OUTPUT_CODEC: original }

_arms: &arms
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
        query_config.output_parser: {}
    - name: serde
      overrides:
        data_size: csv
        query_config.input_formatter: { type: SequentialCSV, threading_mode: SEQUENTIAL, allow_commas_in_strings: false, eager_parse: true }
        query_config.output_formatter: { type: JSON }
        query_config.input_parser: *iin
        query_config.output_parser: {}
    - name: serde_naive
      overrides:
        data_size: csv
        query_config.input_formatter: { type: SequentialCSV, threading_mode: SEQUENTIAL, allow_commas_in_strings: false, eager_parse: true }
        query_config.output_formatter: { type: JSONUncompiled }
        query_config.input_parser: *iin
        query_config.output_parser: {}
        worker_env: *env_naive

_noop_x: &noop_x { label: "config", parameter: topology, values: [single-node] }
_tput_y: &tput_y { metric: throughput_mbps, label: "Throughput (MB/s)" }

variants:
"""
VTPL = """  - name: k{K}
    description: "K={K} int64 SELECT *"
    query: serde_micro/intk{K}
    axes: {{ x: *noop_x, series: *arms }}
    y: *tput_y
    visualization: {{ type: grouped_bar }}
"""

def gen_exp():
    with open(EXP,"w") as f:
        f.write(HEAD)
        for K in KS: f.write(VTPL.format(K=K))
    print(f"wrote {EXP}")

if __name__ == "__main__":
    gen_queries(); gen_exp()
