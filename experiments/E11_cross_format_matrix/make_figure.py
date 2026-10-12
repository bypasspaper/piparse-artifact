#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""E11 driver: regenerate the 4x4 cross-format matrix figure (+ its numeric table) from the per-run parquet archives in
data/, and the q0 W-sweep figure from data/wsweep_output_plateau_raw.csv, into out/. --db [PATH] re-exports the W-sweep
rows from the results DB first (the matrix itself is drawn from the archived per-run rows, which ARE the raw data)."""
import csv, os, re, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; S = HERE / "scripts"; O = HERE / "out"; O.mkdir(exist_ok=True); PY = sys.executable
def run(*a): print("+", " ".join(map(str, a))); subprocess.run([PY, *map(str, a)], check=True, cwd=HERE)
if "--db" in sys.argv:
    i = sys.argv.index("--db"); db = sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--") else os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results/tr/piparse_bench.duckdb"))
    run(S / "extract_wsweep_from_db.py", "--db", db, O / "wsweep_output_plateau_raw.csv")
run(S / "plot_matrix_figure.py")
run(S / "wsweep_parallelization.py")
# numeric check of the regenerated table against the v2 table in expected/MATRIX_RESULTS_2026-08-05.md
md = (HERE / "expected/MATRIX_RESULTS_2026-08-05.md").read_text().split("# V1 (SUPERSEDED)")[0]
exp = {}
for m in re.finditer(r"^\| \*\*(csv|json|hl7|xml)\*\*\s*\|(.*)$", md, re.M):
    cells = [c.strip() for c in m.group(2).split("|") if c.strip()]
    for o, c in zip(["csv", "json", "hl7", "xml"], cells):
        t, cp, pr = re.match(r"\*\*([\d.]+)\*\* = ([\d.]+) x ([\d.]+)", c).groups(); exp[(m.group(1), o)] = (float(t), float(cp), float(pr))
got = {(r["in"], r["out"]): (float(r["total"]), float(r["comp"]), float(r["par"])) for r in csv.DictReader(open(O / "matrix_table_v2.csv"))}
worst = max(abs(got[k][j] - exp[k][j]) for k in exp for j in range(3))
print(f"TABLE CHECK vs MATRIX_RESULTS v2: 16 cells x 3 numbers, max |abs dev| = {worst:.2f} (values are printed to 1 decimal in the md; {'OK' if worst <= 0.06 else 'CHECK'})")
print("\nwrote", sorted(p.name for p in O.iterdir()))
