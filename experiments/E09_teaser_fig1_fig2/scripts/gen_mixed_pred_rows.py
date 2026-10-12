#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""RECONSTRUCTION (written 2026-10-12 for the artifact) of the 2026-09-27 inline generator of the predicate-sweep datasets
nm{N}.csv -- the original was a one-off numpy snippet typed into the session and was never saved. Documented spec
(fig1_fig2_teaser_2026-09-25.md, 'Fig2 PREDICATE sweep'; queries/multicol/pred_n*.yaml):
  * row = c0 INT32 uniform [0, 1e6)  (the predicate column; 0.8 % of rows satisfy c0 < 8000)
          + (N-1) FLOAT64 payload columns printed with 6 decimals, uniform [0, 1e5)  (=> 6.89 + 10.89*(N-1) bytes/row,
          the per-row size recorded in the result doc; uniform [0,1e5) is the serde-micro float distribution and is
          the range that reproduces 10.89 B/field -- the original snippet's exact float range is not on record)
  * numpy seed 1000 + N, ~200 MB per file (row counts in the query yamls: n1 29,033,025 ... n10 1,906,595)
  * nm{N}_x10.csv for the Flink arm = the file concatenated 10x (same bytes/row, 2 GB, JVM-length jobs).
Regenerated files are statistically equivalent but NOT byte-identical to the measured ones.
usage: gen_mixed_pred_rows.py N out.csv [target_bytes=200000000]
"""
import sys
import numpy as np
N, out = int(sys.argv[1]), sys.argv[2]
target = int(sys.argv[3]) if len(sys.argv) > 3 else 200_000_000
rng = np.random.default_rng(1000 + N)
written = rows = 0
with open(out, "w") as f:
    while written < target:
        chunk = 200_000
        c0 = rng.integers(0, 1_000_000, size=chunk)
        payload = rng.uniform(0.0, 100_000.0, size=(chunk, N - 1)) if N > 1 else None
        for i in range(chunk):
            line = str(c0[i]) + ("," + ",".join(f"{v:.6f}" for v in payload[i]) if N > 1 else "") + "\n"
            f.write(line); written += len(line); rows += 1
            if written >= target:
                break
print(f"wrote {out}: {rows} rows, {written} bytes ({written / rows:.2f} B/row)")
