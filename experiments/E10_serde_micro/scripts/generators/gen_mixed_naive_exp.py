#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the mixed-type serde-micro NAIVE-arm experiment (the arm gen_mixed_queries_and_exp.py
skipped): serde_naive for i2f/f2i x K=1..20. Reuses the i2f/f2i query YAMLs."""

EXP = "/home/user/work/piparse-bench/experiments/serde_micro_mixed_naive.yaml"
KS = list(range(1, 21))

HEAD = """# SPDX-License-Identifier: Apache-2.0
experiment:
  name: serde_micro_mixed_naive
  description: >
    The serde_naive arm for the MIXED-TYPE serde-micro panels (companion to serde_micro_mixed_full,
    same run recipe/footing): CSV in (eager_parse) -> compiled cast Map (TOFLOAT64/TOINT64 plugins,
    binary must contain them) -> JSONUncompiled sink + NES_OUTPUT_CODEC=original (the genuine
    stringstream writer). i2f parses int64 (FastINT64), serializes float64 naively; f2i parses float64
    (EiselFloatF64), serializes int64 naively. PER-ARM REPEAT=3 (the 40x-slower stringstream arm needs
    no repeat -- the uniform-REPEAT=20 tail cost the original float run ~50min). Decompose applies
    REPEAT=3 for this arm. 2 directions x 20 K x 3 reps = 120 runs.
    RUN: cd ~/work/piparse-bench && PBENCH_KEEP_LOGS=1 uv run python bench.py run \\
           experiments/serde_micro_mixed_naive.yaml \\
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
    input_formatter: { type: SequentialCSV, threading_mode: SEQUENTIAL, allow_commas_in_strings: false, eager_parse: true }
    output_formatter: { type: JSONUncompiled }
    input_parser: {}
    output_parser: {}
  generator: { repeat: 1 }
  worker_env: { NES_INMEM_PREFILL: 1, NES_INMEM_REPEAT: 3, NES_INMEM_BUFSIZE: 131072, NES_OUTPUT_CODEC: original }

_arms_i2f: &arms_i2f
  label: "serde arm"
  explicit:
    - name: serde_naive
      baseline: true
      overrides:
        query_config.input_parser: { int64: FastINT64 }

_arms_f2i: &arms_f2i
  label: "serde arm"
  explicit:
    - name: serde_naive
      baseline: true
      overrides:
        query_config.input_parser: { f64: EiselFloatF64 }

_noop_x: &noop_x { label: "config", parameter: topology, values: [single-node] }
_tput_y: &tput_y { metric: throughput_mbps, label: "Throughput (MB/s)" }

variants:
"""

VTPL = """  - name: {d}_k{K}
    description: "K={K} {d} naive stringstream serializer"
    query: serde_micro/{d}k{K}
    axes: {{ x: *noop_x, series: *arms_{d} }}
    y: *tput_y
    visualization: {{ type: grouped_bar }}
"""

with open(EXP, "w") as f:
    f.write(HEAD)
    for d in ["i2f", "f2i"]:
        for K in KS:
            f.write(VTPL.format(d=d, K=K))
print(f"wrote {EXP}")
