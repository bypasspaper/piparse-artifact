#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Artifact copy of piparse-bench scratchpad/serde_micro/emit_2panel_csv.py. Changes: logs = ../data/logs/serde_{,int_}full_run.log,
# bytes/row from ../data/serde_micro_dataset_sizes.csv (scripts/sizes.py) instead of os.path.getsize on the build tree, output ../out/.
"""Emit the combined float64+int64 serde-micro raw CSV (tidy long format):
type, K, arm, throughput_mbps (reported, per-pass), bytes_per_row, repeat, mrows_s (true)."""
import re, os, csv as csvmod

import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
(HERE / "out").mkdir(exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parent)); from sizes import bytes_per_row
FLOG = str(HERE / "data/logs/serde_full_run.log")
ILOG = str(HERE / "data/logs/serde_int_full_run.log")
OUT  = str(HERE / "out/serde_micro_2panel_raw.csv")
ROWS = 2_000_000
NATIVE = {"no_serde", "only_ser"}
REP = {"float": {a: 20 for a in ["no_serde","only_deser","only_ser","serde","serde_naive"]},
       "int":   {"no_serde":20,"only_deser":20,"only_ser":20,"serde":20,"serde_naive":3}}
ARM_ORDER = ["no_serde","only_deser","only_ser","serde","serde_naive"]

def bpr(arm, K, pre):
    return bytes_per_row("float64" if pre == "float" else "int64", arm, K)

def parse(log, pre, panel):
    rx = re.compile(r"^\s+(no_serde|only_deser|only_ser|serde|serde_naive)\s+.*throughput=([\d.]+)\s*MB/s.*"+pre+r"k(\d+)\]")
    rows = []
    for line in open(log):
        m = rx.match(line)
        if m:
            arm, mbps, K = m.group(1), float(m.group(2)), int(m.group(3))
            b = bpr(arm, K, pre); rep = REP[panel][arm]
            mrows = mbps*1e6/b*rep/1e6
            rows.append((pre if pre=="int" else "float64", K, arm, mbps, round(b,4), rep, round(mrows,4)))
    return rows

allrows = parse(FLOG, "float", "float") + parse(ILOG, "int", "int")
# type label: float->float64, int->int64
allrows = [("float64" if t in ("float","float64") else "int64", K, a, mb, b, r, m) for (t,K,a,mb,b,r,m) in allrows]
allrows.sort(key=lambda x: (x[0], x[1], ARM_ORDER.index(x[2])))
with open(OUT, "w", newline="") as f:
    w = csvmod.writer(f)
    w.writerow(["type","K","arm","throughput_mbps_reported","bytes_per_row","inmem_repeat","mrows_s_true"])
    w.writerows(allrows)
print(f"wrote {OUT}  ({len(allrows)} rows)")
