#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the spanning-row CSVs behind figW / figS / figL: rows `<id>,<N filler chars>\n` up to 500 MiB.

This is the one-liner recorded in SPANNING_SWEEP_HANDOVER.md §2 (the ad-hoc generator used for the paper's data
was not kept; this reproduces it byte-for-byte: ids count up from 0, filler = N times 'x').

Usage:  python3 gen_bigstr_id.py <filler_chars> > bigstr_id_<KB>k_500m.csv
  e.g.  python3 gen_bigstr_id.py 12000 > bigstr_id_12k_500m.csv   # 12,003 B/row -> 2.93 raw buffers @4 KiB (figW)
        for n in 4 16 40 80 160 320 640; do python3 gen_bigstr_id.py $((n*1000)) > bigstr_id_${n}k_500m.csv; done   # figS/figL
Place the files in <engine>/nes-systests/testdata/large/formatter/ (gitignored) and symlink them into
<build>/nes-systests/testdata/large/formatter/ for the pbench e2e arm; the isolated harness reads them directly.
Row/size facts the queries assume (yaml/queries/formatter/bigstr_id_pass_*.yaml): 12k -> 43,667 rows / 524,298,559 B;
80k -> 6,554 rows / 524,358,214 B.
"""
import sys

n = int(sys.argv[1])
total = 500 * 1024 * 1024
i = 0
w = sys.stdout.write
filler = "x" * n
while total > 0:
    line = f"{i},{filler}\n"
    w(line)
    total -= len(line)
    i += 1
