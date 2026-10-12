#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""E07 — Pi per-query tiers (optimised / native / naive W3), final numbers on build e.

Portable copy of ~/Notes/nebulastream/benchmark/2_engine_to_e2e/pi_inlining_fix_2026-10-05/scripts/compare_pi_tiers.py.
Reads the raw Pi DuckDB exports from <artifact>/results/pi/ (override with --pi-results or env PBENCH_PI_RESULTS):
  pi_tiers_aug_raw.csv  = the Aug-23 binary tiers (pi_stateless_tier, pi_stateful_tier, pi_native_*, pi_naive_*_w3)
  pi_tiers_nb_raw.csv   = new engine (b5d757c9f6), inlining OFF  (chain d, *_nb)
  pi_tiers_nbi_raw.csv  = new engine (b5d757c9f6) + nautilus 0005, inlining ON = BUILD E (*_nbi)  <- the figure input
Writes out/pi_tiers_build_e.csv (one row per query x arm x series: medians over reps) and
out/pi_tiers_build_e_tables.md (the comparison tables), and prints the tables.
No benchmark is run; duckdb only (in-memory).
"""
import argparse, csv, os, pathlib, sys
import duckdb

HERE = pathlib.Path(__file__).resolve().parent
ART = HERE.parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--pi-results", default=os.environ.get("PBENCH_PI_RESULTS", str(ART / "results" / "pi")),
                help="directory holding pi_tiers_{aug,nb,nbi}_raw.csv")
ap.add_argument("--out", default=str(HERE / "out"))
args = ap.parse_args()
D = pathlib.Path(args.pi_results)
OUT = pathlib.Path(args.out); OUT.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()
con.execute(f"create table r as select * from read_csv_auto('{D}/pi_tiers_aug_raw.csv', union_by_name=true) "
            f"union all by name select * from read_csv_auto('{D}/pi_tiers_nb_raw.csv', union_by_name=true) "
            f"union all by name select * from read_csv_auto('{D}/pi_tiers_nbi_raw.csv', union_by_name=true)")
ARM = {  # experiment -> (arm, binary)
 "pi_stateless_tier": ("optimised", "aug23"), "pi_stateful_tier": ("optimised", "aug23"),
 "pi_native_stateless": ("native", "aug23"), "pi_native_stateful": ("native", "aug23"),
 "pi_naive_stateless_w3": ("naive_w3", "aug23"), "pi_naive_stateful_w3": ("naive_w3", "aug23"),
 "pi_stateless_tier_nb": ("optimised", "nb"), "pi_stateful_tier_nb2": ("optimised", "nb"),
 "pi_native_stateless_nb": ("native", "nb"), "pi_native_stateful_nb": ("native", "nb"),
 "pi_naive_stateless_w3_nb": ("naive_w3", "nb"), "pi_naive_stateful_w3_nb": ("naive_w3", "nb"),
 "pi_stateless_tier_nbi": ("optimised", "nbi"), "pi_stateful_tier_nbi": ("optimised", "nbi"),
 "pi_native_stateless_nbi": ("native", "nbi"), "pi_native_stateful_nbi": ("native", "nbi"),
 "pi_naive_stateless_w3_nbi": ("naive_w3", "nbi"), "pi_naive_stateful_w3_nbi": ("naive_w3", "nbi"),
}
rows = con.execute("""select experiment, variant, coalesce(series,'') series, count(*) n, median(throughput_mbps) mbps,
  median(throughput_mrows_s) mrows, median(p50_latency_us)/1000 p50, median(p99_latency_us)/1000 p99, min(git_commit) gitc
  from r where throughput_mbps is not null group by 1,2,3 order by 1,2,3""").fetchall()
med = {}
tidy = []
for e, v, s, n, mbps, mrows, p50, p99, gitc in rows:
    arm, binary = ARM.get(e, ("?", e))
    med[(arm, binary, v, s)] = (mbps, mrows, p50, p99, n)
    tidy.append([arm, binary, e, v, s, n, round(mbps, 2), round(mrows, 4), round(p50, 2), round(p99, 2), gitc])
with open(OUT / "pi_tiers_build_e.csv", "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["arm", "binary", "experiment", "query", "series", "n", "mbps_med", "mrows_s_med", "p50_ms_med", "p99_ms_med", "git_commit"]); w.writerows(tidy)

Q = ["q0", "q_project", "q_route", "q1", "q2_og", "q2_mod", "q10", "q14", "q22", "q_ex", "ysb_1k_varsized", "q8_join", "cm_q2"]
f = lambda x: "–" if x is None else f"{x:.0f}"
r = lambda a, b: "–" if a is None or b is None else f"{a/b:.2f}"
def g(arm, binary, q, s=""):
    for key in ((arm, binary, q, s), (arm, binary, q, "ctrl"), (arm, binary, q, "default"), (arm, binary, q, "")):
        if key in med: return med[key][0]
    return None
lines = []
P = lines.append
P("## Optimised arm (MB/s, median): Aug-23 binary | nb (new engine, no inlining) | nbi (build e, inlining) | nbi/nb | nbi/aug | ovl: nb | nbi")
P("| query | aug | nb ctrl | nbi ctrl | nbi/nb | nbi/aug | nb ovl | nbi ovl | nbi ovl/ctrl |"); P("|---|---|---|---|---|---|---|---|---|")
for q in Q:
    a, b, c = g("optimised", "aug23", q), g("optimised", "nb", q, "ctrl"), g("optimised", "nbi", q, "ctrl")
    bo, co = med.get(("optimised", "nb", q, "ovl"), (None,))[0], med.get(("optimised", "nbi", q, "ovl"), (None,))[0]
    P(f"| {q} | {f(a)} | {f(b)} | {f(c)} | **{r(c,b)}** | {r(c,a)} | {f(bo)} | {f(co)} | {r(co,c)} |")
P("")
P("## Native (no-serde) and naive W3 arms (MB/s): aug | nb | nbi | nbi/nb")
P("| query | native aug | native nb | native nbi | nbi/nb | naive aug | naive nb | naive nbi | nbi/nb |"); P("|---|---|---|---|---|---|---|---|---|")
for q in Q:
    na, nb, nc = g("native", "aug23", q), g("native", "nb", q), g("native", "nbi", q)
    va, vb, vc = g("naive_w3", "aug23", q), g("naive_w3", "nb", q), g("naive_w3", "nbi", q)
    P(f"| {q} | {f(na)} | {f(nb)} | {f(nc)} | {r(nc,nb)} | {f(va)} | {f(vb)} | {f(vc)} | {r(vc,vb)} |")
P("")
P("## p99 latency (ms, median of reps), optimised ctrl: aug | nb | nbi")
P("| query | aug | nb | nbi |"); P("|---|---|---|---|")
for q in Q:
    vals = [med.get(("optimised", b, q, s), (None, None, None, None))[3] for b, s in (("aug23", "default"), ("nb", "ctrl"), ("nbi", "ctrl"))]
    P(f"| {q} | " + " | ".join("–" if x is None else f"{x:.1f}" for x in vals) + " |")
text = "\n".join(lines) + "\n"
(OUT / "pi_tiers_build_e_tables.md").write_text(text)
sys.stdout.write(text)
print(f"\nwrote {OUT}/pi_tiers_build_e.csv ({len(tidy)} rows) and {OUT}/pi_tiers_build_e_tables.md")
