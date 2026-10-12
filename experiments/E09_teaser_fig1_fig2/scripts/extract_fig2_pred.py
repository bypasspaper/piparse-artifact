#!/usr/bin/env python3
# Artifact copy of fig1_fig2_teaser_2026-09-25_scratch/pred_sweep/proj1_extract_plot.py (2026-09-28; the script that
# produced BOTH fig2_pred_rowss_mbps_4arm (--nes-exp fig2_pred_nes --flink-exp fig2_pred_flink --tag fig2_pred) and
# fig2_proj1_rowss_mbps_3arm (defaults)). Changes: DB = ../../../results/tr/piparse_bench.duckdb (--db / PBENCH_DB);
# NEW --from-csv <data.csv>: skip the DB and plot the shipped medians; out dir default ../out.
"""Fig2 PROJECTION sweep (SELECT c0 over N columns): extract medians for naive / compiled_lazy (fig2_proj1_nes) and
Flink (fig2_proj1_flink) from pbench DuckDB, fit ns/row = a + b*N per arm, write CSV, plot two panels (rows/s log,
MB/s log) vs N. usage: proj1_extract_plot.py [--smoke] [out_dir]   (--smoke reads the *_smoke experiments)"""
import duckdb, csv, re, os, sys, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
smoke = "--smoke" in sys.argv; args = [a for a in sys.argv[1:] if not a.startswith("--")]
def opt(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default
NES_EXP = opt("--nes-exp", None); FLINK_EXP = opt("--flink-exp", None); TAG = opt("--tag", None)
for v in (NES_EXP, FLINK_EXP, TAG):
    if v in args: args.remove(v)   # option values are not positional args
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
DB = opt("--db", os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results/tr/piparse_bench.duckdb")))
FROM_CSV = opt("--from-csv", None)
for v in (DB, FROM_CSV):
    if v in args: args.remove(v)
OUT = args[0] if args else str(HERE / "out")
Path(OUT).mkdir(parents=True, exist_ok=True)
sfx = "_smoke" if smoke else ""
con = duckdb.connect(DB, read_only=True) if not FROM_CSV else None
def rows(exp):
    return con.sql(f"""select series, query_ref, repetition, throughput_mbps, throughput_mrows_s, processing_time_s
                       from runs where experiment='{exp}' and throughput_mrows_s is not null""").fetchall()
data = {}   # arm -> N -> [(mbps, mrows, win)]
if FROM_CSV:
    for r in csv.DictReader(open(FROM_CSV)):   # shipped medians: one pseudo-rep per cell, reps column carried in window_s slot
        # carry the shipped reps count and ns/row through so a from-csv replot reproduces the shipped table exactly
        data.setdefault(r["arm"], {}).setdefault(int(r["N"]), []).append((float(r["input_MBps"]), float(r["throughput_Mrows_s"]), float(r.get("window_s") or 0), int(r.get("reps") or 1), r.get("ns_per_row")))
else:
    for s, q, rep, mb, mr, t in rows(NES_EXP or f"fig2_proj1_nes{sfx}"):
        data.setdefault(s, {}).setdefault(int(re.search(r"_n(\d+)$", q).group(1)), []).append((mb, mr, t))
    for s, q, rep, mb, mr, t in rows(FLINK_EXP or f"fig2_proj1_flink{sfx}"):
        data.setdefault("flink", {}).setdefault(int(re.search(r"_n(\d+)$", q).group(1)), []).append((mb, mr, t))
ARMS = [("naive", "NES naive (interpreted, parses all N)", "#6BAED6", "s", "-"),
        ("compiled_lazy", "NES bypass (lazy pushdown + passthrough)", "#08519C", "o", "-"),
        ("compiled_lazy_noovl", "NES bypass, overload OFF (c0 parsed)", "#3182BD", "^", "--"),
        ("compiled_lazy_ovl", "NES bypass, overload ON (raw-digit predicate)", "#08519C", "o", "-"),
        ("flink", "Apache Flink 2.1 (csv→json)", "#D55E00", "D", "-")]
med = {}
with open(f"{OUT}/{TAG or ('fig2_proj1' + sfx)}_data.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["arm", "N", "input_MBps", "throughput_Mrows_s", "ns_per_row", "window_s", "reps"])
    for arm, *_ in ARMS:
        if arm not in data: continue
        print(f"\n== {arm} ==\n{'N':>2} {'MB/s':>8} {'Mrows/s':>8} {'ns/row':>7} {'win s':>6} {'reps':>4}")
        for N in sorted(data[arm]):
            v = data[arm][N]; mb = statistics.median(x[0] for x in v); mr = statistics.median(x[1] for x in v); t = statistics.median(x[2] for x in v)
            reps = v[0][3] if (FROM_CSV and len(v) == 1 and len(v[0]) > 3) else len(v)
            ns_row = v[0][4] if (FROM_CSV and len(v) == 1 and len(v[0]) > 4 and v[0][4]) else f"{1000/mr:.2f}"
            med[(arm, N)] = (mb, mr); print(f"{N:>2} {mb:8.1f} {mr:8.2f} {1000/mr:7.1f} {t:6.1f} {reps:>4}")
            w.writerow([arm, N, f"{mb:.1f}", f"{mr:.3f}", ns_row, f"{t:.2f}", reps])
print("\n== cost law ns/row = a + b*N ==")
for arm, *_ in ARMS:
    pts = [(N, 1000 / med[(arm, N)][1]) for N in range(1, 11) if (arm, N) in med]
    if len(pts) < 2: continue
    n = len(pts); sx = sum(p[0] for p in pts); sy = sum(p[1] for p in pts); sxx = sum(p[0]**2 for p in pts); sxy = sum(p[0]*p[1] for p in pts)
    b = (n*sxy - sx*sy)/(n*sxx - sx*sx); a = (sy - b*sx)/n
    ss_res = sum((p[1]-(a+b*p[0]))**2 for p in pts); ss_tot = sum((p[1]-sy/n)**2 for p in pts) or 1
    r0, r9 = pts[0][1], pts[-1][1]
    print(f"{arm:14}: a = {a:6.1f} ns/row  b = {b:6.2f} ns/field  R2 = {1-ss_res/ss_tot:.4f}  (n={n}; rows/s span {r9/r0:.2f}x over N={pts[0][0]}..{pts[-1][0]})")
# plot
plt.rcParams.update({"font.size": 11, "font.family": "sans-serif", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#444444", "axes.linewidth": 0.8})
fig, (a, b) = plt.subplots(1, 2, figsize=(11.0, 4.1))
for arm, label, col, mk, ls in ARMS:
    Ns = [N for N in range(1, 11) if (arm, N) in med]
    if not Ns: continue
    a.plot(Ns, [med[(arm, N)][1] for N in Ns], ls, color=col, marker=mk, markersize=6.5, markeredgecolor="white", linewidth=2, label=label)
    b.plot(Ns, [med[(arm, N)][0] for N in Ns], ls, color=col, marker=mk, markersize=6.5, markeredgecolor="white", linewidth=2)
    DY = {"naive": 6, "flink": -6}   # the two low arms sit within a few % of each other at N=10: stagger their labels
    for ax, y in ((a, med[(arm, Ns[-1])][1]), (b, med[(arm, Ns[-1])][0])):
        ax.annotate(label.split(" (")[0].replace("NES ", ""), (Ns[-1], y), textcoords="offset points", xytext=(7, DY.get(arm, 0)), va="center", fontsize=9, color="#222")
a.set_yscale("log"); a.set_ylabel("Throughput  (million rows/s)"); a.set_title("(a) rows/s vs N" + (", one projected field" if not TAG else ""), loc="left", fontsize=11)
b.set_yscale("log"); b.set_ylabel("Input throughput  (MB/s, log)"); b.set_title("(b) input MB/s of the same runs", loc="left", fontsize=11)
for ax in (a, b):
    ax.set_xlabel("Fields per row  N"); ax.set_xticks(range(1, 11)); ax.set_xlim(0.6, 12.6); ax.set_axisbelow(True); ax.grid(axis="both", color="#E4E4E4", linewidth=0.7)
h, l = a.get_legend_handles_labels(); fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, 0.88), ncol=3, frameon=False, fontsize=9.2)
fig.subplots_adjust(top=0.78, bottom=0.15, left=0.07, right=0.99, wspace=0.26)
stem = f"{OUT}/{TAG or ('fig2_proj1' + sfx)}"; fig.savefig(stem + ".pdf", bbox_inches="tight"); fig.savefig(stem + ".png", dpi=170, bbox_inches="tight")
print("wrote", stem + ".{pdf,png} and _data.csv")
