# SPDX-License-Identifier: Apache-2.0
"""Extract the regenerated native->native W23 column (w23_native_native_regen) in the paper CSV's
style: med + lo/hi offsets (med-min, max-med) per query, from the 10 per-rep runs. Also prints the
old paper native_med next to it. Run from ~/work/piparse-bench."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/ideal_scaling/scripts/extract_native_regen.py) ----
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

PAPER_NATIVE = {"q0": 17.101, "qproject": 69.243, "qroute": 49.241, "q1": 52.321, "q2og": 94.143,
                "q2mod": 92.590, "q10": 15.674, "q14": 89.042, "q22": 20.874, "qex": 91.461}
ORDER = list(PAPER_NATIVE)

con = duckdb.connect(ART_DB, read_only=True)
reps = {}
for var, val in con.execute(
        "SELECT variant, throughput_mrows_s FROM runs WHERE experiment='w23_native_native_regen' AND throughput_mrows_s IS NOT NULL").fetchall():
    reps.setdefault(var, []).append(float(val))

print("query,native_med,native_lo,native_hi,n,paper_native_med,new_over_paper")
for q in ORDER:
    vals = reps.get(q)
    if not vals:
        print(f"{q},MISSING")
        continue
    med = statistics.median(vals)
    print(f"{q},{med:.3f},{med - min(vals):.3f},{max(vals) - med:.3f},{len(vals)},{PAPER_NATIVE[q]:.3f},{med / PAPER_NATIVE[q]:.2f}")
