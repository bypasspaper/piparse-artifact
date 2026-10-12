#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the serde-micro float datasets: a base N x 20 float64 CSV, then per-K slices
(first K columns) + their SystemNative .nes binary twins (via csv_to_binary.py).

Usage:
  gen_serde_micro.py base                      # write floatbase.csv (N x 20)
  gen_serde_micro.py slice K [K ...]           # write floatk<K>.{csv,nes} for each K
"""
import subprocess, sys, os
import numpy as np

DATA = "/home/user/work/nebulastream-public/cmake-build-release/nes-systests/testdata/large/serde_micro"
C2B = "/home/user/work/nebulastream-public/nes-systests/testdata/small/csv_to_binary.py"
N = 2_000_000
MAXK = 20
BASE = f"{DATA}/floatbase.csv"

def gen_base():
    os.makedirs(DATA, exist_ok=True)
    rng = np.random.default_rng(20260827)
    # realistic magnitudes: uniform [0, 100000), 6 decimals (~10-12 char text, representative
    # parse cost; ZMIJ serialize cost is ~constant per value regardless of magnitude).
    arr = rng.uniform(0.0, 100000.0, size=(N, MAXK))
    # write once, full 20 cols, %.6f, no header
    np.savetxt(BASE, arr, fmt="%.6f", delimiter=",")
    print(f"wrote {BASE}  ({N} rows x {MAXK} float64)")

def gen_slice(K):
    csv = f"{DATA}/floatk{K}.csv"
    nes = f"{DATA}/floatk{K}.nes"
    # slice first K columns from the base CSV
    with open(BASE) as fin, open(csv, "w") as fout:
        for line in fin:
            parts = line.rstrip("\n").split(",")
            fout.write(",".join(parts[:K]) + "\n")
    schema = ",".join(["float64"] * K)
    subprocess.run([sys.executable, C2B, csv, nes, "--schema", schema], check=True)
    csz, nsz = os.path.getsize(csv), os.path.getsize(nes)
    print(f"K={K:2d}: {csv} ({csz}B) -> {nes} ({nsz}B)  schema={schema}")

if __name__ == "__main__":
    if sys.argv[1] == "base":
        gen_base()
    elif sys.argv[1] == "slice":
        for K in sys.argv[2:]:
            gen_slice(int(K))
