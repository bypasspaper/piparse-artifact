#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""E03 orchestrator: regenerate every figW / figS / figL / q_ex-twin figure and tidy CSV into ./out from the shipped
inputs (data/logs/*.log for the isolated harness, the pbench results DB for the e2e arms).

  python3 make_figure.py            # regenerate everything into out/
  python3 make_figure.py --verify   # ... and diff every regenerated CSV against the shipped data/ copy
  python3 make_figure.py --db PATH  # use another pbench DuckDB (default: ../../results/tr/piparse_bench.duckdb or $PBENCH_DB)

Steps (each is the original Notes script, made path-portable; run them individually for finer control):
  parse_isolated.py   data/logs/isolated_span_sweep_4k8k.log      -> out/isolated_tidy.csv
  parse_e2e.py        DB: shredder_span_sweep (latest run_group)    -> out/e2e_tidy.csv
  merge_span.py       out/{isolated,e2e}_tidy.csv                   -> out/span_tidy.csv
  make_span_figure.py / make_latency_figure.py  (4 KiB and 8 KiB)   -> out/figS_span_{4k,8k}, out/figL_latency_{4k,8k}
  make_worker_figure.py gbps|mrows|p99 (+ data/logs/isolated_worker_probe_12k_leanprod.log) -> out/figW_workers_12k_final{,_mrows,_p99}
  make_worker_2span.py                                              -> out/figW_2span_e2e
  build_all_data_csv.py                                             -> out/shredder_all_data.csv
  make_qex_span_figure.py <run_group> out                           -> out/qex_span_medians.csv, out/figW_qex_{gbps,p99}
"""
import csv
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
PY = sys.executable
dbargs = []
if "--db" in sys.argv:
    i = sys.argv.index("--db"); dbargs = ["--db", sys.argv[i + 1]]
verify = "--verify" in sys.argv


def run(script, *args):
    cmd = [PY, str(HERE / script), *map(str, args), *dbargs]
    print("$", " ".join(Path(c).name if c.startswith(str(HERE)) else c for c in cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=HERE)


run("parse_isolated.py", HERE / "data/logs/isolated_span_sweep_4k8k.log", OUT / "isolated_tidy.csv")
run("parse_e2e.py", OUT / "e2e_tidy.csv")
run("merge_span.py", OUT / "isolated_tidy.csv", OUT / "e2e_tidy.csv", OUT / "span_tidy.csv")
for buf in (4, 8):
    run("make_span_figure.py", OUT / "span_tidy.csv", OUT / f"figS_span_{buf}k", 24, buf)
    run("make_latency_figure.py", OUT / "e2e_tidy.csv", OUT / f"figL_latency_{buf}k", buf)
run("make_worker_figure.py", OUT / "figW_workers_12k_final", "gbps")
run("make_worker_figure.py", OUT / "figW_workers_12k_mrows", "mrows")
run("make_worker_figure.py", OUT / "figW_workers_12k_final_p99", "p99")
run("make_worker_2span.py", OUT / "figW_2span_e2e")
run("build_all_data_csv.py")
run("make_qex_span_figure.py", "20261005T170750-d5bb1e82", OUT)


def compare_csv(a: Path, b: Path, rel=1e-6):
    """Cell-wise compare: numeric cells within rel tolerance, other cells exact. Returns (ok, message)."""
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
    for name in ("isolated_tidy.csv", "e2e_tidy.csv", "span_tidy.csv", "shredder_all_data.csv", "qex_span_medians.csv"):
        ok, msg = compare_csv(OUT / name, HERE / "data" / name)
        allok &= ok
        print(f"  {'MATCH   ' if ok else 'MISMATCH'} {name}: {msg}")
    figs = sorted(p.name for p in OUT.glob("fig*.png"))
    print(f"  figures written: {len(figs)}: {', '.join(figs)}")
    sys.exit(0 if allok else 1)
