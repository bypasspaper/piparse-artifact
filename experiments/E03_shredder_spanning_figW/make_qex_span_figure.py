# SPDX-License-Identifier: Apache-2.0
"""figW repeat with q_ex: worker-scaling at fixed span (12 KB rows ~= 3 raw buffers @4 KiB, deep queue), e2e only.
4 lines = {q_ex, SELECT id} x {LOCK_FREE, LOCKING}, same binary + session (shredder_worker_probe_qex, 2026-10-05).
Reference: figW's own e2e lines (shredder_worker_probe/workers_12k_span3, 2026-08-31, older binary) -> table only.
Usage: uv run python make_qex_span_figure.py <run_group_new> <outdir>   (run from ~/work/piparse-bench)
Writes <outdir>/figures/figW_qex_{gbps,p99}.{png,svg}, <outdir>/data/qex_span_medians.csv, prints the md tables."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/qex_spanning_2026-10-05/scripts/make_qex_span_figure.py) ----
## Every path is resolved relative to this file. The pbench results DB defaults to
## <artifact>/results/tr/piparse_bench.duckdb; override with `--db PATH` or env PBENCH_DB. Outputs go to ./out/.
import os as _os, sys as _sys
from pathlib import Path as _Path
HERE = _Path(__file__).resolve().parent
ART_DB = _os.environ.get("PBENCH_DB") or str(HERE.parent.parent / "results" / "tr" / "piparse_bench.duckdb")
if "--db" in _sys.argv:
    _i = _sys.argv.index("--db"); ART_DB = _sys.argv[_i + 1]; del _sys.argv[_i:_i + 2]
(HERE / "out").mkdir(exist_ok=True)
## ---------------------------------------------------------------------------------------------------------
import csv
import sys

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

DB = ART_DB
## artifact: defaults = the run_group behind the paper figure and ./out (flat: CSV + figures side by side)
RG_NEW = sys.argv[1] if len(sys.argv) > 1 else "20261005T170750-d5bb1e82"
OUT = sys.argv[2] if len(sys.argv) > 2 else str(HERE / "out")
RG_FIGW = "20260831T173338-1b014b79"
WORKERS = [1, 2, 4, 8, 12, 16, 20, 24]
BLUE, RED = "#1f6fb2", "#c0392b"  # figW's LF/LK hues (validated light mode)
BYTES_PER_ROW = {"qex_12k_span3": 12039.7, "selid_12k_span3": 12003.0}
LABEL = {"qex_12k_span3": "q_ex", "selid_12k_span3": "SELECT id"}

con = duckdb.connect(DB, read_only=True)
Q = """
select variant, series, cast(x_value as int) w, median(throughput_mbps) mbps, median(p50_latency_us) p50,
       median(p99_latency_us) p99, min(processing_time_s) win_min, count(*) n
from runs where run_group = ? group by 1,2,3 order by 1,2,3"""
new = {(v, s, w): (mbps, p50, p99, win, n) for v, s, w, mbps, p50, p99, win, n in con.execute(Q, [RG_NEW]).fetchall()}
figw = {(s, w): (mbps, p50, p99) for v, s, w, mbps, p50, p99, win, n in con.execute(Q, [RG_FIGW]).fetchall()
        if v == "workers_12k_span3"}
commits = con.execute("select distinct git_commit from runs where run_group=?", [RG_NEW]).fetchall()

# tidy csv
with open(f"{OUT}/qex_span_medians.csv", "w", newline="") as f:
    wr = csv.writer(f)
    wr.writerow(["variant", "query", "series", "workers", "gbps", "mrows_s", "p50_ms", "p99_ms", "window_min_s", "n"])
    for (v, s, w), (mbps, p50, p99, win, n) in sorted(new.items()):
        wr.writerow([v, LABEL[v], s, w, f"{mbps/1000:.3f}", f"{mbps*1e6/BYTES_PER_ROW[v]/1e6:.4f}",
                     f"{p50/1000:.3f}", f"{p99/1000:.3f}", f"{win:.2f}", n])

def g(v, s, w, i=0):
    r = new.get((v, s, w)); return None if r is None else r[i]

# md tables
print("## Throughput (e2e, GB/s input, median of n reps)")
print("| W | q_ex LF | q_ex LK | q_ex LF/LK | SELECT id LF | SELECT id LK | SELECT id LF/LK | q_ex/selid LF | q_ex/selid LK | figW Aug-31 LF/LK |")
print("|---|---|---|---|---|---|---|---|---|---|")
for w in WORKERS:
    a, b = g("qex_12k_span3", "lock_free", w), g("qex_12k_span3", "locking", w)
    c, d = g("selid_12k_span3", "lock_free", w), g("selid_12k_span3", "locking", w)
    fw = figw.get(("lock_free", w), (None,))[0]; fk = figw.get(("locking", w), (None,))[0]
    f = lambda x: "–" if x is None else f"{x/1000:.2f}"
    r = lambda x, y: "–" if x is None or y is None else f"{x/y:.2f}"
    print(f"| {w} | {f(a)} | {f(b)} | **{r(a,b)}** | {f(c)} | {f(d)} | **{r(c,d)}** | {r(a,c)} | {r(b,d)} | {r(fw,fk)} |")
print()
print("## Latency (e2e, ms, median of reps) — p50 / p99")
print("| W | q_ex LF p50 | q_ex LK p50 | q_ex LF p99 | q_ex LK p99 | selid LF p50 | selid LK p50 | selid LF p99 | selid LK p99 |")
print("|---|---|---|---|---|---|---|---|---|")
for w in WORKERS:
    f = lambda v, s, i: ("–" if g(v, s, w, i) is None else f"{g(v, s, w, i)/1000:.2f}")
    print(f"| {w} | {f('qex_12k_span3','lock_free',1)} | {f('qex_12k_span3','locking',1)} | {f('qex_12k_span3','lock_free',2)} | {f('qex_12k_span3','locking',2)} | "
          f"{f('selid_12k_span3','lock_free',1)} | {f('selid_12k_span3','locking',1)} | {f('selid_12k_span3','lock_free',2)} | {f('selid_12k_span3','locking',2)} |")
print()
print("## Window lengths (min processing_time_s per cell) and rep counts")
for (v, s, w), (mbps, p50, p99, win, n) in sorted(new.items()):
    print(f"{v:16s} {s:10s} W{w:<3d} win_min={win:.2f}s n={n}")
print("commits:", commits)

# figures
SR = [  # (variant, series, color, ls, marker, filled, label)
    ("qex_12k_span3", "lock_free", BLUE, "-", "o", True, "q_ex  LOCK-FREE"),
    ("qex_12k_span3", "locking", RED, "-", "o", True, "q_ex  naive-LOCKING"),
    ("selid_12k_span3", "lock_free", BLUE, "--", "s", False, "SELECT id  LOCK-FREE"),
    ("selid_12k_span3", "locking", RED, "--", "s", False, "SELECT id  naive-LOCKING"),
]
for metric in ("gbps", "p99"):
    idx = 0 if metric == "gbps" else 2
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    for v, s, col, ls, mk, filled, lab in SR:
        xs = [w for w in WORKERS if g(v, s, w, idx) is not None]
        ys = [g(v, s, w, idx) / 1000.0 for w in xs]
        ax.plot(xs, ys, color=col, ls=ls, marker=mk, ms=7, lw=2.1, mfc=col if filled else "white", label=lab, zorder=3)
    parts = []
    for v in ("qex_12k_span3", "selid_12k_span3"):
        lf, lk = g(v, "lock_free", 24, idx), g(v, "locking", 24, idx)
        if lf and lk:
            parts.append(f"{LABEL[v]} {lf/lk:.2f}×" if metric == "gbps" else f"{LABEL[v]} {lk/lf:.2f}×")
    if parts:
        head = "LF/LK @W24:  " if metric == "gbps" else "LK/LF p99 @W24:  "
        ax.text(0.98, 0.10 if metric == "gbps" else 0.60, head + "  ·  ".join(parts), transform=ax.transAxes,
                ha="right", va="bottom", fontsize=9.5, fontweight="bold", color="#333333",
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#bbbbbb", lw=0.8))
    if metric == "gbps":
        ax.set_ylabel("throughput  [GB/s input]"); ax.set_ylim(0, 5.0)
        ax.set_title("Worker scaling at fixed span (12 KB ≈ 3-buffer span, 4 KiB buffer, deep queue) — e2e, same binary\n"
                     "q_ex (figQ query: filter on channel/auctionId/price, ~0 output) vs SELECT id (figW): the two overlay\n"
                     "LOCK-FREE keeps scaling; naive-LOCKING plateaus as the shredder mutex saturates", fontsize=10)
        ax.legend(frameon=False, fontsize=9, loc="upper left")
    else:
        ax.set_yscale("log"); ax.set_ylabel("p99 ingest→sink latency  [ms, log]")
        ax.set_title("Worker scaling — p99 LATENCY at fixed span (12 KB ≈ 3-buffer span, 4 KiB buffer, deep queue) — e2e\n"
                     "q_ex vs SELECT id, same binary; ⚠ absolute ms inflated by the deep queue (in-flight 8192)", fontsize=10)
        ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.set_xticks(WORKERS); ax.set_xlabel("worker threads"); ax.grid(True, which="both", alpha=0.22)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(f"{OUT}/figW_qex_{metric}.{ext}", dpi=140)
    print(f"wrote {OUT}/figW_qex_{metric}.png/.svg")
