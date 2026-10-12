#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""E10 driver: regenerate the serde-micro figures from the shipped tidy CSVs (data/) into out/, re-derive the float64
decomposition from the shipped float run log, and -- with --db [PATH] -- rebuild every tidy CSV from the results DB and
diff against data/."""
import os, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; S = HERE / "scripts"; O = HERE / "out"; O.mkdir(exist_ok=True); PY = sys.executable
def run(*a): print("+", " ".join(map(str, a))); subprocess.run([PY, *map(str, a)], check=True, cwd=HERE)
run(S / "make_serde_micro_4panel.py")            # paper figure: float | int | i2f | f2i
run(S / "make_serde_micro_2panel.py")            # float | int
run(S / "make_serde_micro.py")                   # float only, annotated per-field law
run(S / "make_serde_micro_linear.py")
run(S / "decompose_serde.py")                    # float log -> out/serde_micro_decomposition.csv
run(S / "emit_2panel_csv.py")                    # float+int logs -> out/serde_micro_2panel_raw.csv
if "--db" in sys.argv:
    i = sys.argv.index("--db"); db = sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--") else os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results/tr/piparse_bench.duckdb"))
    run(S / "extract_from_db.py", "--db", db)
    run(S / "make_serde_micro_4panel.py", O)     # the 4-panel figure again, from the DB-derived tidy CSVs in out/
print("\nwrote", sorted(p.name for p in O.iterdir()))
