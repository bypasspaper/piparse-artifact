# SPDX-License-Identifier: Apache-2.0
"""Compare the paper's W1 table columns against the w1_column_replication run (current tip).

Paper values pasted from the user's message (med only). Prints per-query:
  simd:   paper vs measured simd (csv->JSON lazy)         -> expect MATCH (~1%)
  native: paper vs measured native_json (SystemNative->JSON) and csv_native_out (csv->NATIVE)
          -> which arm tracks the paper column in level AND shape?
Run from ~/work/piparse-bench: uv run python .../compare_w1_columns.py
"""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/ideal_scaling/scripts/compare_w1_columns.py) ----
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
import duckdb

PAPER = {  # query -> (simd_med, native_med)
    "q0":       (11.091, 17.101),
    "qproject": (34.350, 69.243),
    "qroute":   (28.377, 49.241),
    "q1":       (14.253, 52.321),
    "q2og":     (32.337, 94.143),
    "q2mod":    (40.704, 92.590),
    "q10":      (11.914, 15.674),
    "q14":      (21.190, 89.042),
    "q22":      (12.329, 20.874),
    "qex":      (44.655, 91.461),
}
ORDER = list(PAPER)

con = duckdb.connect(ART_DB, read_only=True)
meas = {}
for var, ser, val in con.execute(
        "SELECT variant, series, throughput_mrows_s FROM aggregated WHERE experiment='w1_column_replication'").fetchall():
    if val is not None:
        meas[(var, ser)] = float(val)

print(f"{'query':>9} | {'paper':>7} {'simd':>7} {'dev':>6} | {'paper':>7} {'nat_js':>7} {'dev':>6} {'csv_nat':>8} {'dev':>6}")
print("-" * 78)
devs = {"simd": [], "nj": [], "cn": []}
for q in ORDER:
    ps, pn = PAPER[q]
    s = meas.get((q, "simd"))
    nj = meas.get((q, "native_json"))
    cn = meas.get((q, "csv_native_out"))
    def d(m, p, key):
        if m is None:
            return "   n/a"
        r = (m - p) / p * 100
        devs[key].append(abs(r))
        return f"{r:+5.0f}%"
    print(f"{q:>9} | {ps:>7.2f} {s or 0:>7.2f} {d(s, ps, 'simd'):>6} | {pn:>7.2f} {nj or 0:>7.2f} {d(nj, pn, 'nj'):>6} {cn or 0:>8.2f} {d(cn, pn, 'cn'):>6}")
for k, lab in (("simd", "simd vs paper-simd"), ("nj", "native_json vs paper-native"), ("cn", "csv_native_out vs paper-native")):
    if devs[k]:
        print(f"avg |dev| {lab}: {sum(devs[k])/len(devs[k]):.1f}%")
