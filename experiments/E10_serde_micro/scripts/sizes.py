# SPDX-License-Identifier: Apache-2.0
"""Shared helper: bytes/row per (type, K, arm) from data/serde_micro_dataset_sizes.csv (derived from the query yamls),
replacing the original scripts' os.path.getsize() on the build tree / hardcoded CSV_SZ tables."""
import csv
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
ROWS = 2_000_000
NATIVE_ARMS = {"no_serde", "only_ser"}
INPUT_TYPE = {"float64": "float64", "int64": "int64", "i2f": "int64", "f2i": "float64"}   # input-side dataset per panel
_S = {(r["type"], int(r["K"])): r for r in csv.DictReader(open(HERE / "data/serde_micro_dataset_sizes.csv"))}
def csv_size(typ, K):
    """csv bytes of the INPUT dataset of panel `typ` at K (i2f reads intk, f2i reads floatk; sizes identical by construction)."""
    return int(_S[(typ, K)]["csv_size_bytes"])
def bytes_per_row(typ, arm, K):
    return K * 8 if arm in NATIVE_ARMS else csv_size(typ, K) / ROWS
