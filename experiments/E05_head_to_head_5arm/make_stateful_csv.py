# SPDX-License-Identifier: Apache-2.0
"""Stateful tier paper-style CSV: naive = Aug-14 CORRECTED stateful per-rep; flink/spark = Aug-14
5-arm per-rep; simd/csv_native/native_native = stateful_serde_regen (tip). lo/hi = med-min/max-med.
Derived cols mirror the stateless generator. Run from ~/work/piparse-bench."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/ideal_scaling/scripts/make_stateful_csv.py) ----
## Every path is resolved relative to this file. The pbench results DB defaults to
## <artifact>/results/tr/piparse_bench.duckdb; override with `--db PATH` or env PBENCH_DB. Outputs go to ./out/.
import os as _os, sys as _sys
from pathlib import Path as _Path
HERE = _Path(__file__).resolve().parent
ART_DB = _os.environ.get("PBENCH_DB") or str(HERE.parent.parent / "results" / "tr" / "piparse_bench.duckdb")
if "--db" in _sys.argv:
    _i = _sys.argv.index("--db"); ART_DB = _sys.argv[_i + 1]; del _sys.argv[_i:_i + 2]
(HERE / "out").mkdir(exist_ok=True)
## ---------------------------------------------------------------------------------------------------------
import csv
import statistics

import duckdb

QUERIES = ["ysb_1k_varsized", "q8_join", "cm_q2"]
RAW = str(HERE / "data/nes_vs_flink_vs_spark_5arm_2026-08-14_CORRECTED_per_rep_raw.csv")


def mlh(vals):
    med = statistics.median(vals)
    return med, med - min(vals), max(vals) - med


aug = {}
for r in csv.DictReader(open(RAW)):
    if r["tier"] == "stateful":
        aug.setdefault((r["series"], r["variant"]), []).append(float(r["records_per_s_millions"]))

con = duckdb.connect(ART_DB, read_only=True)
db = {}
for var, ser, val in con.execute(
        "SELECT variant, series, throughput_mrows_s FROM runs WHERE experiment='stateful_serde_regen' AND throughput_mrows_s IS NOT NULL").fetchall():
    db.setdefault((ser, var), []).append(float(val))

print("x,query,naive_med,naive_lo,naive_hi,simd_med,simd_lo,simd_hi,csvnat_med,csvnat_lo,csvnat_hi,"
      "native_med,native_lo,native_hi,flink_med,flink_lo,flink_hi,spark_med,spark_lo,spark_hi,"
      "simd_over_naive,simd_over_flink,simd_over_spark,simd_over_native,csvnat_over_native")
for i, q in enumerate(QUERIES, start=1):
    nm = mlh(aug[("NES-Naive", q)])
    fl = mlh(aug[("Flink", q)])
    sp = mlh(aug[("Spark", q)])
    sm = mlh(db[("simd", q)])
    cn = mlh(db[("csv_native", q)])
    nn = mlh(db[("native_native", q)])
    cells = [f"{v:.3f}" for t in (nm, sm, cn, nn, fl, sp) for v in t]
    print(f"{i},{q}," + ",".join(cells)
          + f",{sm[0]/nm[0]:.1f},{sm[0]/fl[0]:.1f},{sm[0]/sp[0]:.1f},{sm[0]/nn[0]:.2f},{cn[0]/nn[0]:.2f}")
