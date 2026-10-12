#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the INT64 serde-micro datasets (companion to gen_serde_micro.py's float ones):
base N x 20 int64 CSV, then per-K slices (first K cols) + SystemNative .nes binary twins."""
import subprocess, sys, os
import numpy as np

DATA = "/home/user/work/nebulastream-public/cmake-build-release/nes-systests/testdata/large/serde_micro"
C2B = "/home/user/work/nebulastream-public/nes-systests/testdata/small/csv_to_binary.py"
N, MAXK = 2_000_000, 20
BASE = f"{DATA}/intbase.csv"

def gen_base():
    os.makedirs(DATA, exist_ok=True)
    rng = np.random.default_rng(20260828)
    arr = rng.integers(0, 1_000_000_000, size=(N, MAXK), dtype=np.int64)  # ~9-10 digit ints
    np.savetxt(BASE, arr, fmt="%d", delimiter=",")
    print(f"wrote {BASE}  ({N} rows x {MAXK} int64)")

def gen_slice(K):
    csv = f"{DATA}/intk{K}.csv"; nes = f"{DATA}/intk{K}.nes"
    with open(BASE) as fin, open(csv, "w") as fout:
        for line in fin:
            fout.write(",".join(line.rstrip("\n").split(",")[:K]) + "\n")
    schema = ",".join(["int64"] * K)
    subprocess.run([sys.executable, C2B, csv, nes, "--schema", schema], check=True)
    print(f"K={K:2d} csv={os.path.getsize(csv)} nes={os.path.getsize(nes)}")

if __name__ == "__main__":
    if sys.argv[1] == "base": gen_base()
    elif sys.argv[1] == "slice":
        for K in sys.argv[2:]: gen_slice(int(K))
