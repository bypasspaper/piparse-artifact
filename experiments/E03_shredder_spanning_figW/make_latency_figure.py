# SPDX-License-Identifier: Apache-2.0
"""e2e latency figure (one buffer size): LOCK_FREE vs naive-LOCKING, p50 & p99, across row size (W24).
Log-y. Shows the lock hurts latency more than throughput (LOCKING median ≈ tail = mutex convoy).
⚠ absolute ms inflated by the deep-queue throughput config; the LF/LK contrast is the signal."""

## ---- artifact portability header (added for the SIGMOD artifact; original: ~/Notes/nebulastream/benchmark/2_engine_to_e2e/bypass_scaling_2026-08-28/span_figure/scripts/make_latency_figure.py) ----
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
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

TIDY = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "data/e2e_tidy.csv")
OUT = sys.argv[2] if len(sys.argv) > 2 else str(HERE / "out/figL_latency")
BUF = int(sys.argv[3]) if len(sys.argv) > 3 else 4

rows = [r for r in csv.DictReader(open(TIDY)) if int(r["buffer_kb"]) == BUF]
p = defaultdict(dict)
span_of = {}
for r in rows:
    rk = int(r["row_kb"]); span_of[rk] = int(r["span_buffers"])
    if r["p50_ms"] != "":
        p[(r["mode"], "p50")][rk] = float(r["p50_ms"])
    if r["p99_ms"] != "":
        p[(r["mode"], "p99")][rk] = float(r["p99_ms"])
xs = sorted(span_of)
BLUE, RED = "#1f6fb2", "#c0392b"

fig, ax = plt.subplots(figsize=(8.8, 5.6))
DEF = [
    (("LOCKING", "p99"), RED, "-", "s", "naive-LOCKING  p99"),
    (("LOCKING", "p50"), RED, "--", "o", "naive-LOCKING  p50"),
    (("LOCK_FREE", "p99"), BLUE, "-", "s", "LOCK-FREE  p99"),
    (("LOCK_FREE", "p50"), BLUE, "--", "o", "LOCK-FREE  p50"),
]
for key, col, ls, mk, lab in DEF:
    d = p[key]
    ax.plot(xs, [d.get(x) for x in xs], color=col, ls=ls, marker=mk, ms=6.5, lw=2.1,
            mfc=col if ls == "-" else "white", label=lab)

ax.set_xscale("log", base=2)
ax.set_yscale("log")
ax.set_xticks(xs)
ax.set_xticklabels([f"{x}KB\n(span {span_of[x]})" for x in xs])
ax.set_xlabel(f"spanning tuple size — row size  (span count @ {BUF} KiB buffer)")
ax.set_ylabel("ingest→sink latency  [ms, log]   (W24)")
ax.set_title(f"The lock hurts LATENCY more than throughput  ({BUF} KiB buffer)\n"
             "e2e p50 & p99, LOCK-FREE vs naive-LOCKING\n"
             "⚠ absolute ms inflated by the deep-queue throughput config — the LF/LK contrast is the signal",
             fontsize=10)
ax.grid(True, which="both", alpha=0.22)
ax.legend(frameon=False, fontsize=9, loc="best")
fig.tight_layout()
for ext in ("png", "svg"):
    fig.savefig(f"{OUT}.{ext}", dpi=140)
print(f"wrote {OUT}.png / .svg  (buffer={BUF}KB)")
