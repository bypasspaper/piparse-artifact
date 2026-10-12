#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""E08 — many-source scaling ladders N = 1 … 1000 (+ latency curves), Threadripper and Raspberry Pi 5.

Portable, pbench-free re-implementation of the six piparse-bench plot scripts in scripts/ (they imported
`piparse_bench.store.Store`; here duckdb is opened directly on the shipped results DB) plus two Pi views built from the
CSV exports in <artifact>/results/pi/. Every figure is written to out/ under the ORIGINAL file stem so it can be compared
with expected/.

  --db       path to piparse_bench.duckdb   (default <artifact>/results/tr/piparse_bench.duckdb, env PBENCH_DB)
  --pi       dir with the Pi CSV exports    (default <artifact>/results/pi, env PBENCH_PI_RESULTS)
  --only     comma list of figure keys to render (default: all)
  --check    pixel-compare each out/*.png with expected/*.png (reports %-differing pixels; drift of a few % is font
             rendering, a different curve is tens of %)

Figure keys (original script -> output stem):
  scaling3   plot_nes_flink_spark_scaling.py  nes_vs_flink_vs_spark_scaling_step20 + _spark_mb   -> nes_vs_flink_vs_spark_scaling_step20
  nes3       plot_nes_naive_simd_native_scaling.py                                                 -> nes_naive_simd_native_scaling
  five_lowN  plot_5arm_lowN.py                                                                     -> five_arm_lowN_1to100
  fine_simd  plot_nes_fine_vs_coarse.py NES-SIMD nes_simd_scaling_lowN_fine csv                    -> nes_simd_fine_vs_coarse_1to100
  fine_nat   plot_native_fine_vs_coarse.py                                                         -> native_fine_vs_coarse_1to100
  passthru   plot_flink_vs_nes_latency_scaling.py (July bid-passthrough csv->csv ladder, 1..1024)   -> flink_vs_nes_latency_scaling
  pi_avail   NEW: the Pi ladder arms whose exports are on this box (Flink 1..1000, NES-naive W1, NES-naive W3)  -> pi_scaling_available_arms
  pi_inflight NEW: the in-flight-window probe table (naive W3, N x cap)                             -> pi_naive_inflight_probe.md
"""
import argparse, csv, os, pathlib, statistics, sys
from collections import defaultdict
import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = pathlib.Path(__file__).resolve().parent
ART = HERE.parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--db", default=os.environ.get("PBENCH_DB", str(ART / "results" / "tr" / "piparse_bench.duckdb")))
ap.add_argument("--pi", default=os.environ.get("PBENCH_PI_RESULTS", str(ART / "results" / "pi")))
ap.add_argument("--out", default=str(HERE / "out"))
ap.add_argument("--only", default="")
ap.add_argument("--check", action="store_true")
A = ap.parse_args()
OUT = pathlib.Path(A.out); OUT.mkdir(parents=True, exist_ok=True)
PI = pathlib.Path(A.pi)
con = duckdb.connect(A.db, read_only=True)

CSV_BPR = 3595281395 / 31300000      # 114.865 csv bytes per bid_strings row
NAT_BPR = 3443000000 / 31300000      # 110.000 native bytes per row
COLORS = {"NebulaStream": "#2ca02c", "Flink": "#7d5bbe", "Spark": "#e69f00",
          "NES-Naive": "#d62728", "NES-SIMD": "#2ca02c", "NES-Native": "#1f77b4"}
MARKERS = {"NebulaStream": "o", "Flink": "s", "Spark": "^", "NES-Naive": "s", "NES-SIMD": "o", "NES-Native": "^"}


def save(fig, stem):
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{stem}.{ext}", dpi=140, bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT / f"{stem}.png")


def latest_rg(exp):
    r = con.execute("SELECT run_group FROM runs WHERE experiment=? AND run_group IS NOT NULL ORDER BY timestamp DESC LIMIT 1", [exp]).fetchone()
    return r[0] if r else None


def curves(exp, rg, series_filter=None, rename=None):
    """{series: {N: {tp, p50, p99, p999}}} medianed over reps (the originals' `curves`)."""
    out = {}
    q = "SELECT series, x_value, throughput_mbps, p50_latency_us, p99_latency_us, p999_latency_us FROM runs WHERE experiment=? AND run_group=?"
    for series, x, tp, p50, p99, p999 in con.execute(q, [exp, rg]).fetchall():
        if series_filter and series != series_filter:
            continue
        name = rename.get(series, series) if rename else series
        d = out.setdefault(name, {}).setdefault(int(float(x)), {"tp": [], "p50": [], "p99": [], "p999": []})
        for k, v in (("tp", tp), ("p50", p50), ("p99", p99), ("p999", p999)):
            if v is not None:
                d[k].append(v)
    return {s: {n: {k: (statistics.median(v) if v else None) for k, v in d.items()} for n, d in byn.items()} for s, byn in out.items()}


# ---------------------------------------------------------------- scaling3: plot_nes_flink_spark_scaling.py
def fig_scaling3():
    exps = ["nes_vs_flink_vs_spark_scaling_step20", "nes_vs_flink_vs_spark_scaling_step20_spark_mb"]
    data, used = {}, []
    for exp in exps:
        rg = latest_rg(exp)
        if rg is None:
            continue
        for series, byn in curves(exp, rg).items():
            data.setdefault(series, {}).update(byn)
        used.append(f"{exp}@{rg}")
    print(f"[scaling3] experiments={used} series={list(data)}")
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("Many-source scaling: NebulaStream vs Apache Flink vs Apache Spark\n"
                 "10-query stateless mix, csv -> json, warm page cache — per-batch ingest->sink latency", fontsize=13, fontweight="bold")
    order = ["NebulaStream", "Flink", "Spark"]
    for series in sorted(data, key=lambda x: order.index(x) if x in order else 99):
        c = data[series]; ns = sorted(n for n in c if c[n]["tp"] is not None)
        if not ns:
            continue
        axL.plot(ns, [c[n]["tp"] / 1000 for n in ns], "-", marker=MARKERS.get(series, "o"), color=COLORS.get(series), lw=2.5, ms=7, label=series)
        nsp = [n for n in ns if c[n]["p99"] is not None]
        if nsp:
            axR.plot(nsp, [c[n]["p99"] / 1000 for n in nsp], "-", marker=MARKERS.get(series, "o"), color=COLORS.get(series), lw=2.5, ms=7, label=series)
    axL.set_xscale("log", base=2); axL.set_xlabel("# concurrent sources / queries (N)", fontsize=11)
    axL.set_ylabel("Aggregate throughput (GB/s, csv input bytes)", fontsize=11); axL.set_title("Throughput vs N", fontsize=11)
    axL.legend(fontsize=10, loc="best"); axL.grid(True, which="both", ls=":", alpha=0.4)
    axR.set_xscale("log", base=2); axR.set_yscale("log"); axR.set_xlabel("# concurrent sources / queries (N)", fontsize=11)
    axR.set_ylabel("p99 per-batch latency (ms)", fontsize=11); axR.set_title("p99 latency vs N (tail)", fontsize=11)
    axR.legend(fontsize=10, loc="best"); axR.grid(True, which="both", ls=":", alpha=0.4)
    fig.tight_layout(rect=(0, 0, 1, 0.93)); save(fig, "nes_vs_flink_vs_spark_scaling_step20")


# ---------------------------------------------------------------- nes3: plot_nes_naive_simd_native_scaling.py
SIMD_EXP, SIMD_RG, NEW_EXP = "nes_vs_flink_vs_spark_scaling_step20", "20260817T164347-3ec56b98", "nes_naive_native_scaling_step20"
BPR = {"NES-Naive": CSV_BPR, "NES-SIMD": CSV_BPR, "NES-Native": NAT_BPR}


def fig_nes3():
    data, used = {}, []
    rg_new = latest_rg(NEW_EXP)
    if rg_new:
        data.update(curves(NEW_EXP, rg_new)); used.append(f"{NEW_EXP}@{rg_new}")
    simd = curves(SIMD_EXP, SIMD_RG, series_filter="NebulaStream", rename={"NebulaStream": "NES-SIMD"})
    if simd:
        data.update(simd); used.append(f"{SIMD_EXP}@{SIMD_RG} (SIMD)")
    print(f"[nes3] sources={used} series={list(data)}")
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("NES many-source scaling — Naive vs SIMD vs Native (no parse/serde)\n"
                 "10-query stateless mix, warm page cache; throughput in records/s (format-invariant)", fontsize=13, fontweight="bold")
    order = ["NES-Naive", "NES-SIMD", "NES-Native"]
    for series in sorted(data, key=lambda x: order.index(x) if x in order else 99):
        c = data[series]; bpr = BPR.get(series, CSV_BPR); ns = sorted(n for n in c if c[n]["tp"] is not None)
        if ns:
            axL.plot(ns, [c[n]["tp"] / bpr for n in ns], "-", marker=MARKERS.get(series, "o"), color=COLORS.get(series), lw=2.5, ms=7, label=series)
        nsp = [n for n in sorted(c) if c[n]["p99"] is not None]
        if nsp:
            axR.plot(nsp, [c[n]["p99"] / 1000 for n in nsp], "-", marker=MARKERS.get(series, "o"), color=COLORS.get(series), lw=2.5, ms=7, label=series)
    axL.set_xlabel("# concurrent sources / queries (N)", fontsize=11); axL.set_ylabel("Aggregate throughput (Mrecords/s)", fontsize=11)
    axL.set_title("Throughput vs N (records/s, format-invariant)", fontsize=11); axL.legend(fontsize=10, loc="best"); axL.grid(True, which="both", ls=":", alpha=0.4)
    axR.set_yscale("log"); axR.set_xlabel("# concurrent sources / queries (N)", fontsize=11); axR.set_ylabel("p99 per-batch latency (ms)", fontsize=11)
    axR.set_title("p99 latency vs N (tail)", fontsize=11); axR.legend(fontsize=10, loc="best"); axR.grid(True, which="both", ls=":", alpha=0.4)
    fig.tight_layout(rect=(0, 0, 1, 0.93)); save(fig, "nes_naive_simd_native_scaling")


# ---------------------------------------------------------------- five_lowN: plot_5arm_lowN.py
GRID = [1, 2, 3, 4, 5, 6, 8, 10, 13, 16, 20, 25, 32, 40, 45, 50, 56, 63, 71, 79, 89, 100]
C5 = {"NES-Naive": "#d62728", "NES-SIMD": "#2ca02c", "NES-Native": "#1f77b4", "Flink": "#7d5bbe", "Spark": "#e69f00"}
M5 = {"NES-Naive": "s", "NES-SIMD": "o", "NES-Native": "^", "Flink": "D", "Spark": "v"}
ORDER5 = ["NES-Native", "NES-SIMD", "NES-Naive", "Flink", "Spark"]
SRC5 = {  # arm: (experiment, run_group or None=latest, series, bytes_per_row)
    "NES-Native": ("nes_native_scaling_lowN_fine", None, "NES-Native", NAT_BPR),
    "NES-SIMD": ("nes_simd_scaling_lowN_fine", None, "NES-SIMD", CSV_BPR),
    "NES-Naive": ("nes_naive_flink_spark_lowN_fine", "20260901T175023-5d971803", "NES-Naive", CSV_BPR),
    "Flink": ("nes_naive_flink_spark_lowN_fine", "20260901T175023-5d971803", "Flink", CSV_BPR),
    "Spark": ("nes_naive_flink_spark_lowN_fine", "20260901T175023-5d971803", "Spark", CSV_BPR),
}


def pull(exp, rg, series, nmax=None):
    rg = rg or latest_rg(exp)
    q = "SELECT cast(x_value as int) n, throughput_mbps, p99_latency_us FROM runs WHERE experiment=? AND run_group=? AND series=?"
    args = [exp, rg, series]
    if nmax is not None:
        q += " AND cast(x_value as int)<=?"; args.append(nmax)
    return {n: (tp, p99) for n, tp, p99 in con.execute(q + " ORDER BY n", args).fetchall()}


def fig_five_lowN():
    data = {arm: pull(e, rg, ser) for arm, (e, rg, ser, _) in SRC5.items()}
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("Five-arm low-N scaling (N=1..100, 22-pt grid): Naive / SIMD / Native / Flink / Spark\n"
                 "10-query stateless mix, warm cache; throughput records/s (format-invariant)", fontsize=13, fontweight="bold")
    for arm in ORDER5:
        d = data[arm]; bpr = SRC5[arm][3]
        ns = [n for n in GRID if n in d and d[n][0] is not None]
        axL.plot(ns, [d[n][0] / bpr for n in ns], "-", marker=M5[arm], color=C5[arm], lw=2, ms=6, label=arm)
        nsp = [n for n in GRID if n in d and d[n][1] is not None]
        axR.plot(nsp, [d[n][1] / 1000 for n in nsp], "-", marker=M5[arm], color=C5[arm], lw=2, ms=6, label=arm)
    axL.set_yscale("log"); axL.set_xlabel("# concurrent sources / queries (N)"); axL.set_ylabel("Aggregate throughput (Mrecords/s)")
    axL.set_title("Throughput vs N"); axL.legend(fontsize=9); axL.grid(True, which="both", ls=":", alpha=0.4)
    axR.set_yscale("log"); axR.set_xlabel("# concurrent sources / queries (N)"); axR.set_ylabel("p99 per-batch latency (ms)")
    axR.set_title("p99 latency vs N (tail)"); axR.legend(fontsize=9); axR.grid(True, which="both", ls=":", alpha=0.4)
    fig.tight_layout(rect=(0, 0, 1, 0.92)); save(fig, "five_arm_lowN_1to100")
    for arm in ORDER5:
        d = data[arm]; bpr = SRC5[arm][3]; vals = {n: d[n][0] / bpr for n in GRID if n in d}; pk = max(vals, key=vals.get)
        print(f"  {arm:>11}: N=1 {vals.get(1, float('nan')):7.1f}  peak {vals[pk]:7.1f} @N={pk}  N=100 {vals.get(100, float('nan')):7.1f} Mrec/s")


# ---------------------------------------------------------------- fine_simd / fine_nat: plot_nes_fine_vs_coarse.py / plot_native_fine_vs_coarse.py
COARSE_EXP, COARSE_RG = "nes_naive_native_scaling_step20", "20260901T024303-4285bc04"


def fig_fine(series, fine_exp, bpr, color, stem, title):
    fine_rg = latest_rg(fine_exp)
    fine = pull(fine_exp, fine_rg, series, 100)
    coarse = pull(COARSE_EXP, COARSE_RG, series, 100)
    if not coarse and series == "NES-SIMD":
        coarse = pull("nes_vs_flink_vs_spark_scaling_step20", "20260817T164347-3ec56b98", "NebulaStream", 100)
    print(f"[{stem}] fine={fine_exp}@{fine_rg} ({len(fine)}) coarse ({len(coarse)})")
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle(title, fontsize=13, fontweight="bold")
    fn, cn = sorted(fine), sorted(coarse)
    axL.plot(fn, [fine[n][0] / bpr for n in fn], "-", color=color, lw=1.8, ms=3, marker="o", label="fine (step 1)")
    axL.plot(cn, [coarse[n][0] / bpr for n in cn], "D", color="#d62728", ms=9, mfc="none", mew=2, label="coarse (step 20)")
    axL.set_xlabel("# concurrent sources / queries (N)"); axL.set_ylabel("Aggregate throughput (Mrecords/s)")
    axL.set_title("Throughput vs N"); axL.legend(); axL.grid(True, ls=":", alpha=0.4)
    axR.plot(fn, [fine[n][1] / 1000 for n in fn], "-", color=color, lw=1.8, ms=3, marker="o", label="fine (step 1)")
    axR.plot(cn, [coarse[n][1] / 1000 for n in cn], "D", color="#d62728", ms=9, mfc="none", mew=2, label="coarse (step 20)")
    axR.set_xlabel("# concurrent sources / queries (N)"); axR.set_ylabel("p99 per-batch latency (ms)")
    axR.set_title("p99 latency vs N"); axR.legend(); axR.grid(True, ls=":", alpha=0.4)
    fig.tight_layout(rect=(0, 0, 1, 0.94)); save(fig, stem)


# ---------------------------------------------------------------- passthru: plot_flink_vs_nes_latency_scaling.py
def curve_all_rg(exp, series=None):
    q = "SELECT x_value, p99_latency_us, p50_latency_us, throughput_mbps FROM runs WHERE experiment=? AND p99_latency_us IS NOT NULL"
    args = [exp]
    if series:
        q += " AND series IN (%s)" % ",".join("?" * len(series)); args += series
    d = {}
    for x, p99, p50, tp in con.execute(q, args).fetchall():
        n = int(float(x)); d.setdefault(n, {"p99": [], "p50": [], "tp": []})
        d[n]["p99"].append(p99); d[n]["p50"].append(p50); d[n]["tp"].append(tp)
    return {n: {k: statistics.median(v) for k, v in d[n].items()} for n in d}


def fig_passthru():
    NES_GREEN, FLINK_COL = "#2ca02c", "#7d5bbe"
    flink = curve_all_rg("latency_flink_passthrough_scaling")
    nes = curve_all_rg("shredder_fragments_source_scaling", ["lock_free_fragments", "default"])
    best = con.execute("SELECT p99_latency_us, p50_latency_us, throughput_mbps FROM runs WHERE x_value='1024' AND experiment LIKE 'shredder_fragments_n1024%' "
                       "AND throughput_mbps IS NOT NULL ORDER BY throughput_mbps DESC LIMIT 1").fetchone()
    if best:
        nes[1024] = {"p99": best[0], "p50": best[1], "tp": best[2]}
    xs = lambda c: sorted(c); col = lambda c, key, scale: [c[n][key] / scale for n in sorted(c)]
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("File-source scaling, 1 -> 1024 sources: NebulaStream (CCX cells + fragment shredder) vs Apache Flink\n"
                 "bid passthrough, warm page cache — e2e ingest->sink latency, same per-buffer methodology on both engines", fontsize=13, fontweight="bold")
    axL.plot(xs(nes), col(nes, "tp", 1000), "-o", color=NES_GREEN, lw=2.5, ms=7, label="NebulaStream (CCX cells + fragment shredder)")
    axL.plot(xs(flink), col(flink, "tp", 1000), "-s", color=FLINK_COL, lw=2.5, ms=6, label="Apache Flink (N single-threaded pipelines)")
    axL.set_xscale("log", base=2); axL.set_xlabel("# File sources (= concurrent queries)", fontsize=11); axL.set_ylabel("Aggregate throughput (GB/s)", fontsize=11)
    axL.set_title("Throughput: NES ~40 GB/s flat; Flink pinned at the 24-core parse ceiling ~1.4 GB/s", fontsize=11)
    axL.axhspan(38, 42, color=NES_GREEN, alpha=0.08); axL.legend(fontsize=10, loc="center left"); axL.grid(True, which="both", ls=":", alpha=0.4)
    axR.plot(xs(nes), col(nes, "p99", 1000), "-o", color=NES_GREEN, lw=2.5, ms=7, label="NebulaStream")
    axR.plot(xs(flink), col(flink, "p99", 1000), "-s", color=FLINK_COL, lw=2.5, ms=6, label="Apache Flink")
    axR.set_xscale("log", base=2); axR.set_yscale("log"); axR.set_xlabel("# File sources (= concurrent queries)", fontsize=11); axR.set_ylabel("p99 latency (ms)", fontsize=11)
    axR.set_title("p99 latency: NES bounded ~4 ms at every N; Flink's tail collapses past core count", fontsize=11)
    axR.axhspan(3, 5, color=NES_GREEN, alpha=0.08)
    axR.annotate("NES p99 bounded ~4 ms\n(fixed 16-worker shared pool,\nLittle's law) — flat to 1024", xy=(64, 4.19), xytext=(3, 12), fontsize=9, color=NES_GREEN, arrowprops=dict(arrowstyle="->", color=NES_GREEN))
    axR.annotate("Flink 1198 ms @1024\n(~180x NES): N pipelines =\n~2N threads oversubscribe\n24 cores -> HOL tail", xy=(1024, 1197.7), xytext=(20, 400), fontsize=9, color=FLINK_COL, arrowprops=dict(arrowstyle="->", color=FLINK_COL))
    axR.legend(fontsize=10, loc="center left"); axR.grid(True, which="both", ls=":", alpha=0.4)
    fig.tight_layout(rect=(0, 0, 1, 0.94)); save(fig, "flink_vs_nes_latency_scaling")


# ---------------------------------------------------------------- pi_avail (NEW): the Pi ladder arms exported to this box
def pi_rows(fname):
    p = PI / fname
    if not p.exists():
        print(f"[pi] missing {p}"); return {}
    byn = defaultdict(lambda: {"tp": [], "p50": [], "p99": [], "p999": []})
    for r in csv.DictReader(open(p)):
        if not r.get("throughput_mbps"):
            continue
        n = int(float(r["x_value"])); byn[n]["tp"].append(float(r["throughput_mbps"]))
        for k in ("p50", "p99", "p999"):
            v = r.get(f"{k}_latency_us")
            if v:
                byn[n][k].append(float(v))
    return {n: {k: (statistics.median(v) if v else None) for k, v in d.items()} for n, d in byn.items()}


def fig_pi_avail():
    arms = [("Flink (PyFlink 2.1.3, p=3)", "flink_scaling.csv", "#7d5bbe", "s"),
            ("NES naive, W3 (fair budget)", "naive_scaling_w3.csv", "#d62728", "s"),
            ("NES naive, W1 (reference)", "naive_scaling.csv", "#ff9896", "x")]
    data = {lab: pi_rows(f) for lab, f, _, _ in arms}
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(15, 6))
    fig.suptitle("Raspberry Pi 5 many-source ladder, N = 1 .. 1000 — the arms whose exports are shipped\n"
                 "(NES optimised `pi_scaling_file_*`, Spark `pi_spark_mb_*`, no-serde `pi_noserde_scaling_*` live only in the Pi DB: see README)",
                 fontsize=12, fontweight="bold")
    for lab, f, colr, mk in arms:
        c = data[lab]; ns = sorted(n for n in c if c[n]["tp"] is not None)
        if not ns:
            continue
        axL.plot(ns, [c[n]["tp"] for n in ns], "-", marker=mk, color=colr, lw=2, ms=6, label=lab)
        nsp = [n for n in ns if c[n]["p99"] is not None]
        axR.plot(nsp, [c[n]["p99"] / 1000 for n in nsp], "-", marker=mk, color=colr, lw=2, ms=6, label=lab)
    for ax in (axL, axR):
        ax.set_xscale("log", base=2); ax.set_xlabel("# concurrent sources / queries (N)"); ax.grid(True, which="both", ls=":", alpha=0.4); ax.legend(fontsize=9)
    axL.set_ylabel("Aggregate throughput (MB/s, csv input bytes)"); axL.set_title("Throughput vs N")
    axR.set_yscale("log"); axR.set_ylabel("p99 per-batch latency (ms)"); axR.set_title("p99 latency vs N")
    fig.tight_layout(rect=(0, 0, 1, 0.91)); save(fig, "pi_scaling_available_arms")
    with open(OUT / "pi_scaling_available_arms.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["arm", "N", "throughput_mbps_med", "p50_ms_med", "p99_ms_med", "p999_ms_med"])
        for lab, f, _, _ in arms:
            for n in sorted(data[lab]):
                d = data[lab][n]
                w.writerow([lab, n, round(d["tp"], 2) if d["tp"] else "", *[round(d[k] / 1000, 2) if d[k] else "" for k in ("p50", "p99", "p999")]])
    print("wrote", OUT / "pi_scaling_available_arms.csv")


def table_pi_inflight():
    p = PI / "naive_inflight_probe.csv"
    if not p.exists():
        print(f"[pi] missing {p}"); return
    cells = defaultdict(lambda: {"tp": [], "p50": [], "p99": []})
    for r in csv.DictReader(open(p)):
        if not r.get("throughput_mbps"):
            continue
        cells[(int(float(r["x_value"])), r["series"])]["tp"].append(float(r["throughput_mbps"]))
        cells[(int(float(r["x_value"])), r["series"])]["p50"].append(float(r["p50_latency_us"]))
        cells[(int(float(r["x_value"])), r["series"])]["p99"].append(float(r["p99_latency_us"]))
    lines = ["| N | series (in-flight cap) | reps | MB/s | p50 ms | p99 ms |", "|---|---|---|---|---|---|"]
    for (n, s), d in sorted(cells.items()):
        lines.append(f"| {n} | {s} | {len(d['tp'])} | {statistics.median(d['tp']):.1f} | {statistics.median(d['p50'])/1000:.1f} | {statistics.median(d['p99'])/1000:.1f} |")
    (OUT / "pi_naive_inflight_probe.md").write_text("\n".join(lines) + "\n"); print("wrote", OUT / "pi_naive_inflight_probe.md")


FIGS = {
    "scaling3": fig_scaling3, "nes3": fig_nes3, "five_lowN": fig_five_lowN,
    "fine_simd": lambda: fig_fine("NES-SIMD", "nes_simd_scaling_lowN_fine", CSV_BPR, "#2ca02c", "nes_simd_fine_vs_coarse_1to100", "NES-SIMD: fine steps-of-1 vs coarse step-20, N=1..100"),
    "fine_nat": lambda: fig_fine("NES-Native", "nes_native_scaling_lowN_fine", NAT_BPR, "#1f77b4", "native_fine_vs_coarse_1to100", "NES-Native (no parse/serde): fine steps-of-1 vs coarse step-20, N=1..100"),
    "passthru": fig_passthru, "pi_avail": fig_pi_avail, "pi_inflight": table_pi_inflight,
}
keys = [k for k in A.only.split(",") if k] or list(FIGS)
for k in keys:
    FIGS[k]()

if A.check:
    from PIL import Image
    import numpy as np
    rc = 0
    for png in sorted((HERE / "expected").glob("*.png")):
        o = OUT / png.name
        if not o.exists():
            continue
        x, y = np.asarray(Image.open(o).convert("RGB")).astype(int), np.asarray(Image.open(png).convert("RGB")).astype(int)
        if x.shape != y.shape:
            print(f"CHECK {png.name}: shape {x.shape} vs expected {y.shape} (size drift)"); h, w = min(x.shape[0], y.shape[0]), min(x.shape[1], y.shape[1]); x, y = x[:h, :w], y[:h, :w]
        m = (np.abs(x - y).max(axis=2) > 40)
        print(f"CHECK {png.name}: {100*m.mean():.2f}% pixels differ (>40/255)")
        rc |= int(m.mean() > 0.05)
    sys.exit(rc)
