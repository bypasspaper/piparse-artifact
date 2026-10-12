#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Export the W-sweep rows (experiment wsweep_output_plateau, run_group 20260806T233701-6b2fbb7e, 2 reps x 8 W x
csv->csv / csv->json q0) from the results DB to ../data/wsweep_output_plateau_raw.csv. The plot script reads that CSV.
usage: extract_wsweep_from_db.py [--db PATH] [out.csv]"""
import csv, os, sys
from pathlib import Path
import duckdb
HERE = Path(__file__).resolve().parent.parent
DB = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results/tr/piparse_bench.duckdb"))
args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] != "--db"]
OUT = Path(args[0]) if args else HERE / "data/wsweep_output_plateau_raw.csv"
con = duckdb.connect(DB, read_only=True)
rows = con.execute("""select run_group, variant, series, worker_threads, repetition, throughput_mbps, throughput_mrows_s, processing_time_s, git_commit, timestamp
                      from runs where experiment='wsweep_output_plateau' order by variant, worker_threads, repetition""").fetchall()
with open(OUT, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["run_group", "variant", "series", "worker_threads", "repetition", "throughput_mbps_reported", "throughput_mrows_s_reported", "processing_time_s", "git_commit", "timestamp"])
    w.writerows(rows)
print(f"wrote {OUT} ({len(rows)} rows); reported values are per-pass, TRUE = x20 (NES_INMEM_REPEAT)")
