# SPDX-License-Identifier: Apache-2.0
"""Assemble the coherent tip NES columns: simd (csv->JSON, remeasured), csv_native (deser-only, new),
native_native (from w23_native_native_regen) — med + lo/hi offsets, vs the paper's Aug-14 simd anchors.
Run from ~/work/piparse-bench."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/ideal_scaling/scripts/extract_simd_csvnative_regen.py) ----
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
import statistics

import duckdb

PAPER_SIMD = {"q0": 141.264, "qproject": 446.770, "qroute": 370.126, "q1": 233.127, "q2og": 498.771,
              "q2mod": 497.625, "q10": 201.162, "q14": 367.764, "q22": 228.023, "qex": 495.561}
ORDER = list(PAPER_SIMD)

con = duckdb.connect(ART_DB, read_only=True)
reps = {}
for exp, arm in (("w23_simd_csvnative_regen", "simd"), ("w23_simd_csvnative_regen", "csv_native"),
                 ("w23_native_native_regen", "native_native")):
    for var, ser, val in con.execute(
            "SELECT variant, series, throughput_mrows_s FROM runs WHERE experiment=? AND throughput_mrows_s IS NOT NULL",
            [exp]).fetchall():
        if ser == arm:
            reps.setdefault((arm, var), []).append(float(val))


def stat(arm, q):
    vals = reps.get((arm, q))
    if not vals:
        return None
    med = statistics.median(vals)
    return med, med - min(vals), max(vals) - med, len(vals)


print("query,simd_med,simd_lo,simd_hi,csvnat_med,csvnat_lo,csvnat_hi,natnat_med,natnat_lo,natnat_hi,"
      "paper_simd,simd_new_over_paper,simd_over_natnat,csvnat_over_natnat")
for q in ORDER:
    s, c, n = stat("simd", q), stat("csv_native", q), stat("native_native", q)
    if not (s and c and n):
        print(f"{q},MISSING s={bool(s)} c={bool(c)} n={bool(n)}")
        continue
    print(f"{q},{s[0]:.3f},{s[1]:.3f},{s[2]:.3f},{c[0]:.3f},{c[1]:.3f},{c[2]:.3f},"
          f"{n[0]:.3f},{n[1]:.3f},{n[2]:.3f},{PAPER_SIMD[q]:.3f},{s[0]/PAPER_SIMD[q]:.2f},"
          f"{s[0]/n[0]:.2f},{c[0]/n[0]:.2f}")
