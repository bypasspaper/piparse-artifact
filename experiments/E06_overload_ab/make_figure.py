#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Overload-knob A/B tables + ratio figure (E06). Regenerates the two per-query tables of
~/Notes/nebulastream/benchmark/2_engine_to_e2e/overload_ab_2026-10-05/RESULT.md from the raw per-repetition exports in data/
(TR: tr_simd_overload_ab.csv, series NES-SIMD vs NES-SIMD-ovl, 10 reps; Pi: pi_tier_overload_ab.csv, series ctrl vs ovl,
7 reps) and checks the TR table against the shipped data/tr_ctrl_vs_ovl_vs_aug14.csv. With --db the TR rows are pulled
live from the pbench DB (run groups 20261005T114637-61a8f600 stateless, 20261005T120141-75e0e42c stateful) instead of
the CSV; the Pi rows exist only in the Pi's DB and are always read from the CSV.
Outputs: out/tr_overload_ab_table.csv, out/pi_overload_ab_table.csv, out/overload_ab_tables.md, out/overload_ab_ratio.{png,svg}
Usage: make_figure.py [--db [PATH]] [--out out/]"""
import argparse, csv, os, statistics
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ORDER = ["q0", "q1", "q10", "q14", "q22", "q2_mod", "q2_og", "q_ex", "q_project", "q_route", "cm_q2", "q8_join", "ysb_1k_varsized"]
TR_RG = ["20261005T114637-61a8f600", "20261005T120141-75e0e42c"]


def med(xs): return statistics.median(xs)


def table(rows, ctrl, ovl):
    by = {}
    for r in rows:
        by.setdefault((r["variant"], r["series"]), []).append(r)
    out = []
    for q in sorted({k[0] for k in by}, key=lambda q: ORDER.index(q) if q in ORDER else 99):
        c, o = by.get((q, ctrl), []), by.get((q, ovl), [])
        if not c or not o:
            continue
        f = lambda rs, k: med([float(r[k]) for r in rs if r.get(k) not in (None, "")])
        out.append(dict(variant=q, reps=len(c), ctrl_mbps=round(f(c, "throughput_mbps"), 1), ovl_mbps=round(f(o, "throughput_mbps"), 1),
                        ovl_over_ctrl=round(f(o, "throughput_mbps") / f(c, "throughput_mbps"), 3),
                        ctrl_mrows=round(f(c, "throughput_mrows_s"), 2), ovl_mrows=round(f(o, "throughput_mrows_s"), 2),
                        p99_ms_ctrl=round(f(c, "p99_latency_us") / 1000, 2), p99_ms_ovl=round(f(o, "p99_latency_us") / 1000, 2)))
    return out


def md(rows, title):
    s = [f"## {title}", "| query | reps | ctrl MB/s | ovl MB/s | ovl/ctrl | ctrl Mrows/s | ovl Mrows/s | p99 ms ctrl | p99 ms ovl |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        s.append(f"| {r['variant']} | {r['reps']} | {r['ctrl_mbps']:.0f} | {r['ovl_mbps']:.0f} | {r['ovl_over_ctrl']:.2f} | {r['ctrl_mrows']:.1f} | {r['ovl_mrows']:.1f} | {r['p99_ms_ctrl']} | {r['p99_ms_ovl']} |")
    return "\n".join(s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", nargs="?", const=os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results" / "tr" / "piparse_bench.duckdb")), default=None)
    ap.add_argument("--out", default=str(HERE / "out"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    if a.db:
        import duckdb
        con = duckdb.connect(a.db, read_only=True)
        cols = ["variant", "series", "throughput_mbps", "throughput_mrows_s", "p99_latency_us"]
        tr_rows = [dict(zip(cols, r)) for r in con.execute(f"select {','.join(cols)} from runs where run_group in (?,?)", TR_RG).fetchall()]
        src = f"DB {a.db} run groups {TR_RG}"
    else:
        tr_rows = list(csv.DictReader(open(HERE / "data" / "tr_simd_overload_ab.csv"))); src = "data/tr_simd_overload_ab.csv"
    pi_rows = list(csv.DictReader(open(HERE / "data" / "pi_tier_overload_ab.csv")))
    tr = table(tr_rows, "NES-SIMD", "NES-SIMD-ovl"); pi = table(pi_rows, "ctrl", "ovl")
    for name, rows in (("tr_overload_ab_table.csv", tr), ("pi_overload_ab_table.csv", pi)):
        with open(out / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    text = md(tr, f"Threadripper, 2026-10-05, W23+io1, binary b5d757c9f6 (from {src})") + "\n\n" + md(pi, "Raspberry Pi 5, Pi clock 2026-09-29 (real 2026-10-05), W3+io1, Aug-23 binary (PRE overload-fix: INVALID as an overload verdict, superseded by E07)")
    (out / "overload_ab_tables.md").write_text(text + "\n"); print(text)
    # check against the shipped TR summary table
    ref = {r["variant"]: r for r in csv.DictReader(open(HERE / "data" / "tr_ctrl_vs_ovl_vs_aug14.csv"))}
    worst = 0.0
    for r in tr:
        x = ref[r["variant"]]
        for k in ("ctrl_mbps", "ovl_mbps", "ovl_over_ctrl"):
            d = abs(float(x[k]) - r[k]) / float(x[k]); worst = max(worst, d)
    print(f"\ncheck vs data/tr_ctrl_vs_ovl_vs_aug14.csv: max relative deviation {worst*100:.3f} % over ctrl_mbps/ovl_mbps/ovl_over_ctrl, {len(tr)} queries")
    # ratio figure
    plt.rcParams.update({"font.size": 11, "svg.fonttype": "none"})
    fig, ax = plt.subplots(figsize=(11, 4.2))
    qs = [r["variant"] for r in tr]; x = range(len(qs)); wdt = 0.38
    ax.bar([i - wdt / 2 for i in x], [r["ovl_over_ctrl"] for r in tr], wdt, label="Threadripper (b5d757c9f6, overload fix IN)", color="#1f618d")
    pim = {r["variant"]: r["ovl_over_ctrl"] for r in pi}
    ax.bar([i + wdt / 2 for i in x], [pim.get(q, 0) for q in qs], wdt, label="Pi 5 (Aug-23 binary, PRE-fix — invalid, see E07)", color="#bdc3c7")
    ax.axhline(1, color="#555", lw=0.8); ax.set_xticks(list(x)); ax.set_xticklabels(qs, rotation=30, ha="right")
    ax.set_ylabel("throughput with overload / without"); ax.set_ylim(0.6, 1.3); ax.grid(axis="y", alpha=0.3); ax.legend(fontsize=9)
    ax.set_title("Lazy-overload knob A/B on the optimised NES arm (same-session ctrl vs ovl, medians)")
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(out / f"overload_ab_ratio.{ext}", dpi=140, bbox_inches="tight", facecolor="white")
    print("wrote", out / "overload_ab_ratio.{png,svg}", "+ tables")


if __name__ == "__main__":
    main()
