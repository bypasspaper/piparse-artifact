#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""E04 orchestrator: regenerate figQ (q_ex serde matrix + locking companion, W1..23) and figI (q2_mod 4-arm ideal
sweep) into ./out from the pbench results DB (latest run_group of each experiment = the paper runs).

  python3 make_figure.py            # out/figQ_qex_serde_matrix.{png,svg} + _medians.csv, out/figI_ideal_workers_q2mod.{png,svg} + _medians.csv
  python3 make_figure.py --verify   # ... and diff the regenerated medians CSVs against the shipped data/ copies
  python3 make_figure.py --db PATH  # another pbench DuckDB (default ../../results/tr/piparse_bench.duckdb or $PBENCH_DB)
"""
import csv
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
dbargs = []
if "--db" in sys.argv:
    i = sys.argv.index("--db"); dbargs = ["--db", sys.argv[i + 1]]
verify = "--verify" in sys.argv


def run(script, *args):
    cmd = [sys.executable, str(HERE / script), *map(str, args), *dbargs]
    print("$", script, *args, flush=True)
    subprocess.run(cmd, check=True, cwd=HERE)


run("make_qex_matrix_figure.py", OUT / "figQ_qex_serde_matrix")
run("make_ideal_figure.py", OUT / "figI_ideal_workers_q2mod")


def compare_csv(a: Path, b: Path, rel=1e-6):
    ra, rb = list(csv.reader(open(a))), list(csv.reader(open(b)))
    if ra[0] != rb[0]:
        return False, f"header differs: {ra[0]} vs {rb[0]}"
    if len(ra) != len(rb):
        return False, f"row count {len(ra) - 1} vs {len(rb) - 1}"
    worst, bad = 0.0, []
    for i, (x, y) in enumerate(zip(ra[1:], rb[1:]), start=2):
        for j, (u, v) in enumerate(zip(x, y)):
            if u == v:
                continue
            try:
                fu, fv = float(u), float(v)
            except ValueError:
                bad.append(f"row {i} col {ra[0][j]}: {u!r} vs {v!r}"); continue
            d = abs(fu - fv) / max(abs(fv), 1e-12)
            worst = max(worst, d)
            if d > rel:
                bad.append(f"row {i} col {ra[0][j]}: {u} vs {v} (rel {d:.2e})")
    return (not bad), (f"{len(ra) - 1} rows, max rel dev {worst:.1e}" + (f"; {len(bad)} cells differ: " + "; ".join(bad[:5]) if bad else ""))


if verify:
    print("\n== verification: out/ vs shipped data/ ==")
    allok = True
    for name in ("figQ_qex_serde_matrix_medians.csv", "figI_ideal_workers_q2mod_medians.csv"):
        ok, msg = compare_csv(OUT / name, HERE / "data" / name)
        allok &= ok
        print(f"  {'MATCH   ' if ok else 'MISMATCH'} {name}: {msg}")
    print("  figures written:", ", ".join(sorted(p.name for p in OUT.glob("fig*.png"))))
    sys.exit(0 if allok else 1)
