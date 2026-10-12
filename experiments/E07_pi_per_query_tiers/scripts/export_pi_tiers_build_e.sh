#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Export the Pi per-query tiers (Aug paper tiers, _nb = new engine no inlining, _nbi = new engine + inlining = build e)
# as raw run rows, pull them to the TR, then build the per-query comparison CSV for the figure.
set -euo pipefail
PI='pi@PI-LINK-LOCAL-ADDRESS'
D=~/Notes/nebulastream/benchmark/2_engine_to_e2e/pi_inlining_fix_2026-10-05/data
ssh -o BatchMode=yes -o ConnectTimeout=20 "$PI" 'cd /home/pi/data/repos/piparse-bench && /home/pi/data/repos/piparse-bench/.venv/bin/python - <<"PY"
import duckdb, os
c = duckdb.connect("results/piparse_bench.duckdb", read_only=True)
OUT = "/home/pi/powertest/export"; os.makedirs(OUT, exist_ok=True)
JOBS = [
  ("pi_tiers_aug_raw.csv",  "experiment in (\x27pi_stateless_tier\x27,\x27pi_stateful_tier\x27,\x27pi_native_stateless\x27,\x27pi_native_stateful\x27,\x27pi_naive_stateless_w3\x27,\x27pi_naive_stateful_w3\x27)"),
  ("pi_tiers_nb_raw.csv",   "experiment in (\x27pi_stateless_tier_nb\x27,\x27pi_stateful_tier_nb2\x27,\x27pi_native_stateless_nb\x27,\x27pi_native_stateful_nb\x27,\x27pi_naive_stateless_w3_nb\x27,\x27pi_naive_stateful_w3_nb\x27)"),
  ("pi_tiers_nbi_raw.csv",  "experiment in (\x27pi_stateless_tier_nbi\x27,\x27pi_stateful_tier_nbi\x27,\x27pi_native_stateless_nbi\x27,\x27pi_native_stateful_nbi\x27,\x27pi_naive_stateless_w3_nbi\x27,\x27pi_naive_stateful_w3_nbi\x27)"),
  ("pi_inline_verify_raw.csv", "experiment = \x27pi_inline_verify\x27"),
]
for f, w in JOBS:
    c.execute(f"copy (select * from runs where {w} order by experiment, variant, series, timestamp) to \x27{OUT}/{f}\x27 (HEADER, DELIMITER \x27,\x27)")
    print(f, c.execute(f"select count(*), count(distinct experiment), min(git_commit), max(git_commit) from runs where {w}").fetchone())
PY'
for f in pi_tiers_aug_raw.csv pi_tiers_nb_raw.csv pi_tiers_nbi_raw.csv pi_inline_verify_raw.csv; do
  ssh -o BatchMode=yes "$PI" "cat /home/pi/powertest/export/$f" > "$D/$f"; echo "pulled $f $(wc -l < $D/$f) lines"
done
