#!/usr/bin/env python3
"""Fig2 CPU-per-row view (2026-09-25): from cpu_from_artifacts output (per-run per-thread CPU in the sink window),
plot MEDIAN CPU time per row (ns, log) vs fields-per-row N, one line per NES rung, plus wall ns/row for contrast.
Two panels: (a) total CPU ns/row per rung (the "CPU time per row" view); (b) per-thread stack for ONE rung
(default naive, --stack-rung X) showing DataSrc vs WorkerThread vs other CPU per row.
usage: plot_fig2_cpu.py <exp_cpu.csv> <out_stem> [--stack-rung naive|compiled_eager|compiled_lazy]
The CSV has per-run rows; we take the median over reps per (rung, N). Rungs are the ordinal Blues ramp."""
import csv, sys, os, statistics
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
RUNGS = [("naive", "NES naive", "#6BAED6", "s"),
         ("compiled_eager", "NES eager", "#3182BD", "^"),
         ("compiled_lazy", "NES lazy", "#08519C", "o")]
THREADC = {"DataSrc": "#0072B2", "WorkerThread": "#D55E00", "grpc": "#999999", "other": "#CCCCCC"}
plt.rcParams.update({"font.size": 11, "font.family": "sans-serif", "axes.spines.top": False,
                     "axes.spines.right": False, "axes.edgecolor": "#444444", "axes.linewidth": 0.8})
args = [a for a in sys.argv[1:] if not a.startswith("--")]
stack_rung = next((sys.argv[i+1] for i, a in enumerate(sys.argv) if a == "--stack-rung"), "naive")
rows = list(csv.DictReader(open(args[0]))); stem = args[1]
# median helpers
def med(rung, N, col):
    vs = [float(r[col]) for r in rows if r["series"] == rung and r["N"] == str(N) and r.get(col) not in (None, "", "0.0") or
          (r["series"] == rung and r["N"] == str(N) and col in r and r[col] not in (None, ""))]
    vs = [float(r[col]) for r in rows if r["series"] == rung and str(r["N"]) == str(N) and r.get(col) not in (None, "")]
    return statistics.median(vs) if vs else None
Ns = sorted({int(r["N"]) for r in rows if r["N"] not in ("", None)})
thread_cols = [c for c in rows[0].keys() if c.startswith("cpu_s_")]
fig, (a, b) = plt.subplots(1, 2, figsize=(11.0, 4.1))
# (a) total CPU ns/row per rung + wall ns/row dashed
for rung, label, col, mk in RUNGS:
    cpu = [med(rung, n, "cpu_ns_per_row_total") for n in Ns]
    wall = [med(rung, n, "wall_ns_per_row") for n in Ns]
    xs = [n for n, c in zip(Ns, cpu) if c]; ys = [c for c in cpu if c]
    if ys:
        a.plot(xs, ys, "-", color=col, marker=mk, markersize=6.5, markeredgecolor="white", linewidth=2, label=label)
        a.annotate(label.split()[-1], (xs[-1], ys[-1]), textcoords="offset points", xytext=(7, 0), va="center", fontsize=9, color="#222")
    xw = [n for n, c in zip(Ns, wall) if c]; yw = [c for c in wall if c]
    if yw: a.plot(xw, yw, ":", color=col, linewidth=1.2, alpha=0.7)
a.set_yscale("log"); a.set_xlabel("Fields per row  N"); a.set_ylabel("CPU time per row (ns, log)")
a.set_title("(a) total CPU ns/row per rung (dotted = wall ns/row)", loc="left", fontsize=10.5)
# (b) per-thread CPU-ns/row stack for one rung
for n in Ns:
    rowrun = med(stack_rung, n, "rows")
    bottom = 0.0
    for tcol in thread_cols:
        grp = tcol.replace("cpu_s_", "")
        cpu_s = med(stack_rung, n, tcol)
        rr = med(stack_rung, n, "rows")
        if cpu_s is None or not rr: continue
        v = 1e9 * cpu_s / rr
        b.bar(n, v, 0.8, bottom=bottom, color=THREADC.get(grp, "#BBBBBB"),
              edgecolor="white", linewidth=0.8, label=grp if n == Ns[0] else None)
        bottom += v
b.set_xlabel("Fields per row  N"); b.set_ylabel("CPU time per row (ns)")
b.set_title(f"(b) per-thread CPU ns/row — {stack_rung}", loc="left", fontsize=10.5)
for ax in (a, b): ax.set_xticks(Ns); ax.set_axisbelow(True); ax.grid(axis="y", color="#E4E4E4", linewidth=0.7)
ha, la = a.get_legend_handles_labels(); hb, lb = b.get_legend_handles_labels()
a.legend(ha, la, frameon=False, fontsize=9, loc="upper left")
b.legend(hb, lb, frameon=False, fontsize=9, loc="upper left", title="thread")
fig.subplots_adjust(top=0.9, bottom=0.14, left=0.08, right=0.99, wspace=0.24)
fig.savefig(stem + ".pdf", bbox_inches="tight"); fig.savefig(stem + ".png", dpi=170, bbox_inches="tight"); print("wrote", stem)
