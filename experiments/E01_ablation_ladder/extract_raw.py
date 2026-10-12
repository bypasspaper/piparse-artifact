#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Dump the per-repetition rows of the new-rung run groups (and, with --v7, of the v7 ladder run groups) from the
pbench results DB to a tidy CSV: run_group,experiment,query,rung,rep,mbps,mrows_s,window_s,git_commit,timestamp.
Default run groups = the two 2026-10-05 sessions behind data/ablation_new_rungs_raw_2026-10-05.csv.
Usage: extract_raw.py [--db] [--out out/ablation_new_rungs_raw.csv] [--run-groups RG ...] [--v7]"""
import argparse, csv, os
from pathlib import Path
import duckdb

HERE = Path(__file__).resolve().parent
NEW = ["20261005T182825-4660e569", "20261005T191325-76194e52"]
V7 = ["20260824T163459-fa906b40", "20260824T165156-908bd862", "20260824T171809-9e392631"]  # r7 (x20!), r1-r4/r6/r6b, r5
ap = argparse.ArgumentParser()
ap.add_argument("--db", default=os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results" / "tr" / "piparse_bench.duckdb")))
ap.add_argument("--out", default=None)
ap.add_argument("--run-groups", nargs="*", default=None)
ap.add_argument("--v7", action="store_true", help="dump the v7 ladder run groups instead (r7 rows are REPORTED values: true = x20)")
A = ap.parse_args()
rgs = A.run_groups or (V7 if A.v7 else NEW)
out = Path(A.out) if A.out else HERE / "out" / ("ablation_v7_raw.csv" if A.v7 else "ablation_new_rungs_raw.csv")
out.parent.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(A.db, read_only=True)
# column conventions of the shipped data/ablation_new_rungs_raw_2026-10-05.csv: mbps rounded to 2 decimals, mrows_s derived from
# the (unrounded) mbps at 114.87 B/row (bid_strings_3GB) and rounded to 4 decimals, window_s = processing_time_s to 3 decimals
BPR = 114.87
rows = con.execute(f"""select run_group, experiment, variant, series, repetition, round(throughput_mbps, 2),
 round(throughput_mbps / {BPR}, 4), round(processing_time_s, 3), git_commit, timestamp
 from runs where run_group in ({','.join('?' * len(rgs))}) order by run_group, variant, series, repetition""", rgs).fetchall()
with open(out, "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["run_group", "experiment", "query", "rung", "rep", "mbps", "mrows_s", "window_s", "git_commit", "timestamp"]); w.writerows(rows)
print(f"wrote {out} ({len(rows)} rows from {len(rgs)} run groups)")
