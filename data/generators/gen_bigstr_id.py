#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Synthetic spanning-row CSV for the shredder experiments (figW / figS):
rows `<id>,<N filler chars>` until ~500 MiB. One row = one UINT64 id + one VARSIZED string of N bytes, so a
row of N > buffer size spans several raw buffers and the SequenceShredder has to coordinate.

Usage:  gen_bigstr_id.py <N> > bigstr_id_<N/1000>k_500m.csv
        e.g. gen_bigstr_id.py 12000 > bigstr_id_12k_500m.csv   (12,003 B/row = 2.93 spans @ 4 KiB)
             gen_bigstr_id.py 40000 > bigstr_id_40k_500m.csv   (10 spans @ 4 KiB)
Sizes used in the paper: 4k 8k 12k 16k 40k 80k 160k 320k 640k (see experiments/E03_*/README.md).
Recorded verbatim from SPANNING_SWEEP_HANDOVER.md §2 (the data was generated ad hoc with this one-liner).
"""
import sys

n = int(sys.argv[1])
total = 500 * 1024 * 1024
i = 0
w = sys.stdout.write
while total > 0:
    line = f"{i},{'x' * n}\n"
    w(line)
    total -= len(line)
    i += 1
