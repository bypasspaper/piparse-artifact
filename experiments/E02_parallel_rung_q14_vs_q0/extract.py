#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract the W-sweep medians of the par-rung probe (wsweep_q14_vs_q0_parrung, run_group 20261006T181751-4298f356)
from the pbench results DB. The probe runs the r7 cell (InMemory prefill, NES_INMEM_REPEAT=20): the DB stores the
REPORTED throughput, the TRUE value is x20 (the runner counts the file bytes once; see E01 / matrix README).
Columns: variant, series, workers, n, reported_mbps, true_mbps, true_mrows_s, per_worker_mrows_s, scale_vs_w1,
p50_latency_us, p99_latency_us, processing_time_s, rep_spread_pct.
Usage: extract.py [--db] [--run-group 20261006T181751-4298f356] [--out out/wsweep_q14_vs_q0.csv]"""
import argparse, csv, os
from pathlib import Path
import duckdb

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--db", default=os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results" / "tr" / "piparse_bench.duckdb")))
ap.add_argument("--run-group", default="20261006T181751-4298f356")
ap.add_argument("--repeat", type=float, default=20.0, help="NES_INMEM_REPEAT of the run (true = reported x repeat)")
ap.add_argument("--out", default=str(HERE / "out" / "wsweep_q14_vs_q0.csv"))
A = ap.parse_args()
con = duckdb.connect(A.db, read_only=True)
rows = con.execute("""select variant, series, cast(x_value as int) w, count(*), median(throughput_mbps), median(throughput_mrows_s),
 median(p50_latency_us), median(p99_latency_us), median(processing_time_s), (max(throughput_mbps)-min(throughput_mbps))/median(throughput_mbps)*100
 from runs where run_group=? group by 1,2,3 order by 1,2,3""", [A.run_group]).fetchall()
w1 = {(v, s): m for v, s, w, n, m, *_ in rows if w == 1}
out = Path(A.out); out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", newline="") as fh:
    wr = csv.writer(fh)
    wr.writerow(["variant", "series", "workers", "n", "reported_mbps", "true_mbps", "true_mrows_s", "per_worker_mrows_s", "scale_vs_w1", "p50_latency_us", "p99_latency_us", "processing_time_s", "rep_spread_pct"])
    for v, s, w, n, m, mr, p50, p99, t, sp in rows:
        wr.writerow([v, s, w, n, round(m, 2), round(m * A.repeat, 1), round(mr * A.repeat, 3), round(mr * A.repeat / w, 3), round(m / w1[(v, s)], 3), round(p50, 0), round(p99, 0), round(t, 3), round(sp, 1)])
print(f"wrote {out} ({len(rows)} rows)")
for v, s, w, n, m, mr, *_ in rows:
    print(f"{v:12s} W{w:<3d} true {m*A.repeat:8.0f} MB/s  scale {m/w1[(v,s)]:5.2f}  per-worker {mr*A.repeat/w:6.2f} Mrows/s")
