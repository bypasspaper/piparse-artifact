"""Sketch of the predicate sweep: measured N=1,4,10 (filled) + N=2,3,5..9 interpolated (hollow) from piecewise-linear
ns/row between measured points. bytes/row = 6.89 + 10.89*(N-1) (INT32 col + N-1 .6f floats, measured)."""
import csv, sys, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
rows = list(csv.DictReader(open(sys.argv[1]))); stem = sys.argv[2]
ARMS = [("naive", "NES naive", "#6BAED6", "s"), ("compiled_lazy_noovl", "NES bypass, overload OFF", "#3182BD", "^"),
        ("compiled_lazy_ovl", "NES bypass, overload ON", "#08519C", "o"), ("flink", "Apache Flink 2.1", "#D55E00", "D")]
bpr = lambda N: 6.89 + 10.89 * (N - 1)
plt.rcParams.update({"font.size": 11, "font.family": "sans-serif", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#444444", "axes.linewidth": 0.8})
fig, (a, b) = plt.subplots(1, 2, figsize=(11.5, 4.3))
print(f"{'arm':22} " + " ".join(f"N{n:<7}" for n in range(1, 11)))
for arm, label, col, mk in ARMS:
    meas = sorted((int(r["N"]), float(r["ns_per_row"])) for r in rows if r["arm"] == arm)
    mN = [m[0] for m in meas]; mNs = [m[1] for m in meas]
    Ns = list(range(1, 11)); ns = np.interp(Ns, mN, mNs)                      # piecewise-linear in ns/row
    rowss = 1000 / ns; mbps = np.array([bpr(n) for n in Ns]) / ns * 1000       # Mrows/s, MB/s
    print(f"{label:22} " + " ".join(f"{v:7.1f} " for v in ns) + " ns/row")
    for ax, y in ((a, rowss), (b, mbps)):
        ax.plot(Ns, y, ":", color=col, linewidth=1.4, zorder=1)
        meas_i = [Ns.index(n) for n in mN]; proj_i = [i for i in range(10) if Ns[i] not in mN]
        ax.plot([Ns[i] for i in meas_i], [y[i] for i in meas_i], "-", color=col, linewidth=0, marker=mk, markersize=7.5,
                markeredgecolor="white", label=label if ax is a else None, zorder=3)
        ax.scatter([Ns[i] for i in proj_i], [y[i] for i in proj_i], s=42, facecolors="white", edgecolors=col, linewidths=1.4, marker=mk, zorder=2)
        ax.annotate(label.replace("NES ", "").replace("Apache ", ""), (10, y[-1]), textcoords="offset points", xytext=(7, 0), va="center", fontsize=8.5, color="#222")
a.set_yscale("log"); a.set_ylabel("Throughput  (million rows/s)"); a.set_title("(a) rows/s vs N  —  filled = measured, hollow = interpolated", loc="left", fontsize=10)
b.set_yscale("log"); b.set_ylabel("Input throughput  (MB/s, log)"); b.set_title("(b) input MB/s of the same runs", loc="left", fontsize=10)
for ax in (a, b):
    ax.set_xlabel("Fields per row  N  (c0 INT32 predicate column + N−1 FLOAT64)"); ax.set_xticks(range(1, 11)); ax.set_xlim(0.6, 13.4)
    ax.set_axisbelow(True); ax.grid(axis="both", color="#E4E4E4", linewidth=0.7)
h, l = a.get_legend_handles_labels(); fig.legend(h, l, loc="lower center", bbox_to_anchor=(0.5, 0.88), ncol=4, frameon=False, fontsize=9)
fig.subplots_adjust(top=0.78, bottom=0.16, left=0.07, right=0.99, wspace=0.26)
fig.savefig(stem + ".png", dpi=170, bbox_inches="tight"); fig.savefig(stem + ".pdf", bbox_inches="tight"); print("wrote", stem)
