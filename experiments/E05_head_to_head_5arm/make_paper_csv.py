# SPDX-License-Identifier: Apache-2.0
"""Regenerate the paper's stateless 5-arm CSV with the new tip data, mimicking the original
structure/columns exactly. Sources: naive = Aug-14 CORRECTED per-rep (genuine original codecs);
simd = w23_simd_csvnative_regen (tip, csv->JSON); native = w23_native_native_regen (tip, TRUE
native->native, replaces the old native->JSON arm); flink/spark = Aug-14 values verbatim (external
engines, unchanged). lo/hi = med-min / max-med over reps (verified = the original convention).
Derived cols reverse-engineered from the original: conn_lo=spark_med, conn_up=simd-spark,
stack_gain=simd-naive, ceil_lo=min(simd,native), ceil_up=|simd-native|.
Run from ~/work/piparse-bench."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/ideal_scaling/scripts/make_paper_csv.py) ----
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

QUERIES = [  # (label, corrected-csv variant, db variant, flink med/lo/hi, spark med/lo/hi)
    ("q0", "q0", "q0", (1.088, 0.067, 0.037), (0.589, 0.014, 0.006)),
    ("q-proj", "q_project", "qproject", (2.159, 0.077, 0.123), (1.071, 0.074, 0.015)),
    ("q-route", "q_route", "qroute", (1.797, 0.113, 0.062), (0.956, 0.021, 0.023)),
    ("q1", "q1", "q1", (1.647, 0.073, 0.040), (0.722, 0.014, 0.011)),
    ("q2-og", "q2_og", "q2og", (2.075, 0.101, 0.047), (1.528, 0.034, 0.032)),
    ("q2-mod", "q2_mod", "q2mod", (2.032, 0.076, 0.099), (1.284, 0.119, 0.051)),
    ("q10", "q10", "q10", (1.030, 0.020, 0.040), (0.551, 0.007, 0.011)),
    ("q14", "q14", "q14", (1.991, 0.054, 0.065), (1.051, 0.013, 0.032)),
    ("q22", "q22", "q22", (1.188, 0.083, 0.065), (0.683, 0.008, 0.007)),
    ("q-ex", "q_ex", "qex", (1.865, 0.040, 0.050), (1.361, 0.065, 0.052)),
]


def mlh(vals):
    med = statistics.median(vals)
    return med, med - min(vals), max(vals) - med


con = duckdb.connect(ART_DB, read_only=True)

## naive = Aug-14 CORRECTED (per user: the tip naive retake was unwanted; keep the intended column).
## natjson = the OLD native arm (SystemNative -> JSON), Aug-14 values (not remeasured on all 10 at tip).
naive, natjson = {}, {}
for r in csv.DictReader(open(HERE / "data/nes_vs_flink_vs_spark_5arm_2026-08-14_CORRECTED_per_rep_raw.csv")):
    if r["tier"] != "stateless":
        continue
    if r["series"] == "NES-Naive":
        naive.setdefault(r["variant"], []).append(float(r["records_per_s_millions"]))
    elif r["series"] == "NES-Native":
        natjson.setdefault(r["variant"], []).append(float(r["records_per_s_millions"]))
db = {}
for exp, arm in (("w23_simd_csvnative_regen", "simd"), ("w23_simd_csvnative_regen", "csv_native"),
                 ("w23_native_native_regen", "native_native")):
    for var, ser, val in con.execute(
            "SELECT variant, series, throughput_mrows_s FROM runs WHERE experiment=? AND throughput_mrows_s IS NOT NULL",
            [exp]).fetchall():
        if ser == arm:
            db.setdefault((arm, var), []).append(float(val))

header = ("x,x_nes,x_flink,x_spark,g_naive,g_simd,g_flink,g_spark,query,naive_med,naive_lo,naive_hi,"
          "simd_med,simd_lo,simd_hi,native_med,native_lo,native_hi,flink_med,flink_lo,flink_hi,"
          "spark_med,spark_lo,spark_hi,simd_over_naive,simd_over_flink,simd_over_spark,simd_over_native,"
          "conn_lo,conn_up,stack_gain,ceil_lo,ceil_up,"
          "csvnat_med,csvnat_lo,csvnat_hi,natjson_med,natjson_lo,natjson_hi")
print(header)
for i, (label, nkey, dkey, fl, sp) in enumerate(QUERIES, start=1):
    nm, nl, nh = mlh(naive[nkey])
    sm, sl, sh = mlh(db[("simd", dkey)])
    vm, vl, vh = mlh(db[("native_native", dkey)])
    cm, cl, ch = mlh(db[("csv_native", dkey)])
    jm, jl, jh = mlh(natjson[nkey])
    print(f"{i},{i - 0.25:.3f},{i:.3f},{i + 0.25:.3f},{i - 0.33:.3f},{i - 0.11:.3f},{i + 0.11:.3f},{i + 0.33:.3f},"
          f"{label},{nm:.3f},{nl:.3f},{nh:.3f},{sm:.3f},{sl:.3f},{sh:.3f},{vm:.3f},{vl:.3f},{vh:.3f},"
          f"{fl[0]:.3f},{fl[1]:.3f},{fl[2]:.3f},{sp[0]:.3f},{sp[1]:.3f},{sp[2]:.3f},"
          f"{sm / nm:.1f},{sm / fl[0]:.1f},{sm / sp[0]:.1f},{sm / vm:.2f},"
          f"{sp[0]:.3f},{sm - sp[0]:.3f},{sm - nm:.3f},{min(sm, vm):.3f},{abs(sm - vm):.3f},"
          f"{cm:.3f},{cl:.3f},{ch:.3f},{jm:.3f},{jl:.3f},{jh:.3f}")
