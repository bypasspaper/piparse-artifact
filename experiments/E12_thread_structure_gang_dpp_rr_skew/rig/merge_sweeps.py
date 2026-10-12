#!/usr/bin/env python3
"""Layered merge: sweep_<m>.csv = first pass (cores-1 workers) overlaid by the all-cores re-run of the pooled arms,
overlaid by the indexer-cutter re-run of the chunker. Later layers replace all rows of the arms they contain."""
import csv, sys
from pathlib import Path
here = Path(__file__).parent
## The figure uses the quote-free kernel for every design, so the chunker must be the quote-free one: local newline
## search at the cut points (layers W24 / W4). The full-scan cutter (W24idx / W4idx) is the general-CSV variant and is
## appendix data -- include it only with --with-scan (it would be unfair to pair it with quote-free DPP).
with_scan = "--with-scan" in sys.argv
## Final D=1 layering: first pass -> all-cores pooled arms -> chunker with the SEQUENTIAL SCAN cutter (scan_D1, the agreed
## chunker definition). The full-index cutter (idx) is appendix-only (--with-scan keeps the old name for that switch).
LAYERS = {"tr": ["W23", "W24", "scan_D1"] + (["W24idx"] if with_scan else []),
          "pi": ["W3", "W4", "scan_D1"] + (["W4idx"] if with_scan else []),
}
for machine, tags in LAYERS.items():
    rows, fields = [], None
    for tag in tags:
        f = here / f"sweep_{machine}_{tag}.csv"
        if not f.exists():
            print(machine, tag, "missing, skipped"); continue
        new = list(csv.DictReader(open(f)))
        fields = fields or list(new[0].keys())
        arms = {r["arm"] for r in new}
        rows = [r for r in rows if r["arm"] not in arms] + new
        print(f"{machine} + {tag}: arms {sorted(arms)} -> {len(rows)} rows")
    if rows:
        with open(here / f"sweep_{machine}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

## D=64 (backlog) figure: sweep_<m>_D64.csv (all arms; chunker rows truncated by the offer/take race) overlaid by
## sweep_<m>_fix_D64.csv (chunker re-run after the fix) -> sweep_<m>_D64m.csv
for machine in ("tr", "pi"):
    base, fix = here / f"sweep_{machine}_D64.csv", here / f"sweep_{machine}_fix_D64.csv"
    if not base.exists():
        print(machine, "D64: base missing"); continue
    rows = list(csv.DictReader(open(base)))
    if fix.exists():
        new = list(csv.DictReader(open(fix)))
        arms = {r["arm"] for r in new}
        rows = [r for r in rows if r["arm"] not in arms] + new
        print(f"{machine} D64 + fix: arms {sorted(arms)} -> {len(rows)} rows")
    else:
        print(machine, "D64: no fix layer yet ->", len(rows), "rows")
    with open(here / f"sweep_{machine}_D64m.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
