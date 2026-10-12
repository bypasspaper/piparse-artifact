#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Artifact copy of piparse-bench scratchpad/serde_micro/combine_all_raw.py. Changes: bytes/row from scripts/sizes.py, PURE/MIXED read
# from ../data/, output ../out/serde_micro_all_raw.csv (the shipped data/ copy is never modified). Needs the serde_micro_mixed_naive
# run LOG (not shipped); DB-based equivalent: scripts/extract_from_db.py.
"""Combine every serde-micro result into ONE tidy CSV (figures/serde_micro_all_raw.csv):
pure panels (serde_micro_2panel_raw.csv: float64/int64 x 5 arms) + mixed panels
(serde_micro_mixed_raw.csv: i2f/f2i x 4 arms) + the mixed serde_naive rows parsed from the
naive run log (REPEAT=3). Also appends the naive rows into serde_micro_mixed_raw.csv so the
4-panel figure picks them up.

Usage: combine_all_raw.py <mixed_naive_run_log>
"""
import csv
import os
import re
import sys

ROWS = 2_000_000
NAIVE_REPEAT = 3
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent; (HERE / "out").mkdir(exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parent)); from sizes import bytes_per_row
PURE = str(HERE / "data/serde_micro_2panel_raw.csv")
MIXED = str(HERE / "data/serde_micro_mixed_raw.csv")
OUT = str(HERE / "out/serde_micro_all_raw.csv")
DATA_PRE = {"i2f": "int", "f2i": "float"}
FIELDS = ["type", "K", "arm", "throughput_mbps_reported", "bytes_per_row", "inmem_repeat", "mrows_s_true"]


def parse_naive_log(path):
    rx = re.compile(r"^\s+(serde_naive)\s+.*throughput=([\d.]+)\s*MB/s.*(i2f|f2i)k(\d+)\]")
    rows = []
    for line in open(path):
        m = rx.match(line)
        if m:
            mbps, d, K = float(m.group(2)), m.group(3), int(m.group(4))
            bpr = bytes_per_row(d, "serde_naive", K)
            rows.append(dict(type=d, K=K, arm="serde_naive", throughput_mbps_reported=mbps,
                             bytes_per_row=round(bpr, 4), inmem_repeat=NAIVE_REPEAT,
                             mrows_s_true=round(mbps * NAIVE_REPEAT / bpr, 4)))
    return rows


def main(log):
    naive = parse_naive_log(log)
    assert len(naive) == 40, f"expected 40 naive rows (2 dirs x 20 K), got {len(naive)}"
    mixed = list(csv.DictReader(open(MIXED)))
    if not any(r["arm"] == "serde_naive" for r in mixed):
        mixed = mixed + naive   # artifact: never modify data/; the merged mixed rows go to out/ only
    pure = list(csv.DictReader(open(PURE)))
    allrows = pure + mixed
    key = {"float64": 0, "int64": 1, "i2f": 2, "f2i": 3}
    arm_order = {"no_serde": 0, "only_deser": 1, "only_ser": 2, "serde": 3, "serde_naive": 4}
    allrows.sort(key=lambda r: (key[r["type"]], int(r["K"]), arm_order[r["arm"]]))
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(allrows)
    print(f"wrote {OUT} ({len(allrows)} rows: pure {len(pure)} + mixed {len(allrows) - len(pure)})")


if __name__ == "__main__":
    main(sys.argv[1])
