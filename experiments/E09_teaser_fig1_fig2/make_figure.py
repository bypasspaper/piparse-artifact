#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""E09 driver: regenerate the §2 teaser figures (Fig1 v2, Fig2 predicate sweep) and the Fig2 alternatives from the
shipped CSVs in data/ into out/. With --db [PATH] the Fig2 medians are additionally re-extracted from the pbench results
DB (default ../../results/tr/piparse_bench.duckdb) and diffed against data/ (Fig1's stage shares cannot be re-derived
here: they need the perf profiles + results/artifacts, see README)."""
import csv, os, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; S = HERE / "scripts"; D = HERE / "data"; O = HERE / "out"; O.mkdir(exist_ok=True)
PY = sys.executable
def run(*a): print("+", " ".join(map(str, a))); subprocess.run([PY, *map(str, a)], check=True)
# 1. Fig1 v2 (paper): CPU per tuple by stage, naive | Flink | optimised
run(S / "plot_teaser2.py", D / "fig1_teaser2_naive_flink_optimised_2026-09-28_data.csv", O / "fig1_teaser2_naive_flink_optimised")
# 2. Fig2 C (paper): predicate sweep, 4 arms, from the shipped medians
run(S / "extract_fig2_pred.py", "--from-csv", D / "fig2_pred_rowss_mbps_4arm_2026-09-28_data.csv", "--tag", "fig2_pred_rowss_mbps_4arm", O)
# 3. alternatives: full projection (3 rungs + Flink; teaser variant), one projected field, stage CPU vs N (linear + log)
run(S / "plot_fig2_v2.py", D / "fig2_v2_rowss_mbps_2026-09-25_data.csv", O / "fig2_v2_rowss_mbps_3rung")
run(S / "plot_fig2_v2.py", D / "fig2_v2_rowss_mbps_2026-09-25_data.csv", O / "fig2_v2_rowss_mbps_teaser", "--teaser")
run(S / "extract_fig2_pred.py", "--from-csv", D / "fig2_proj1_rowss_mbps_3arm_2026-09-26_data.csv", "--tag", "fig2_proj1_rowss_mbps_3arm", O)
run(S / "plot_fig2_stage.py", D / "fig2_v2_stage_cpu_naive_vs_lazy_2026-09-25_data.csv", O / "fig2_v2_stage_cpu_naive_vs_lazy")
run(S / "plot_fig2_stage_log.py", D / "fig2_v2_stage_cpu_naive_vs_lazy_2026-09-25_data.csv", O / "fig2_v2_stage_cpu_per_tuple_log")
if "--db" in sys.argv:
    i = sys.argv.index("--db"); db = sys.argv[i + 1] if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--") else os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results/tr/piparse_bench.duckdb"))
    print(f"\n== re-extracting Fig2 medians from {db} ==")
    run(S / "extract_fig2_pred.py", "--db", db, "--nes-exp", "fig2_pred_nes", "--flink-exp", "fig2_pred_flink", "--tag", "fig2_pred_redo", O)
    run(S / "extract_fig2_pred.py", "--db", db, "--tag", "fig2_proj1_redo", O)
    run(S / "extract_fig2_v2.py", "fig2_fieldsweep_v2", O, "--db", db)
    def load(p, keys=("arm", "N"), val="throughput_Mrows_s"):
        return {tuple(r[k] for k in keys): float(r[val]) for r in csv.DictReader(open(p))}
    for a, b, keys in ((D / "fig2_pred_rowss_mbps_4arm_2026-09-28_data.csv", O / "fig2_pred_redo_data.csv", ("arm", "N")),
                       (D / "fig2_proj1_rowss_mbps_3arm_2026-09-26_data.csv", O / "fig2_proj1_redo_data.csv", ("arm", "N")),
                       (D / "fig2_v2_rowss_mbps_2026-09-25_data.csv", O / "fig2_fieldsweep_v2_data.csv", ("rung", "N"))):
        x, y = load(a, keys), load(b, keys); common = sorted(set(x) & set(y))
        worst = max(abs(x[k] / y[k] - 1) for k in common) if common else float("nan")
        print(f"DIFF {a.name} vs {b.name}: {len(common)} cells, max |rel dev| = {100 * worst:.3f} %  ({'OK' if worst < 0.005 else 'CHECK'})")
print("\nwrote", sorted(p.name for p in O.iterdir()))
