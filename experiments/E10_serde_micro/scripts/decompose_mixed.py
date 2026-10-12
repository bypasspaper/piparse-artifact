#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Artifact copy of piparse-bench scratchpad/serde_micro/decompose_mixed.py. Changes: bytes/row from scripts/sizes.py, PURE =
# ../data/serde_micro_2panel_raw.csv, output default ../out/serde_micro_mixed_raw.csv. NOTE: needs the serde_micro_mixed_full
# run LOG (session scratch, not shipped); the DB-based equivalent is scripts/extract_from_db.py.
"""Decompose the MIXED-TYPE serde-micro sweep (i2f: int64->TOFLOAT64->float64 JSON;
f2i: float64->TOINT64->int64 JSON) and compare against the pure panels.

Same accounting as decompose_serde.py: rows/s = MB/s*1e6/bytes_per_row (native K*8,
CSV size/2M rows) x REPEAT(20). ns/row t = 1e3/Mrows_s.
Mixed decomposition (every arm contains the cast+Map, so it cancels in the deltas):
  parse     = t(only_deser) - t(no_serde)   [input-type parse]
  serialize = t(only_ser)   - t(no_serde)   [output-type serialize]
  cast+Map  = t(no_serde_mixed) - t(no_serde_pure)   [vs pure panel, both 8B native rows]
Cross-panel bound claims (the point of the experiment):
  i2f: serialize_i2f ~ serialize_float_pure ; t(serde_i2f) >= t(only_ser)-ish floor
  f2i: parse_f2i     ~ parse_float_pure     ; t(serde_f2i) >= t(only_deser)-ish floor

Usage: decompose_mixed.py <mixed_run_log> [tidy_csv_out]
Pure-panel reference: figures/serde_micro_2panel_raw.csv (medianed tidy, canonical).
"""
import csv
import os
import re
import sys

ROWS = 2_000_000
REPEAT = 20
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent; (HERE / "out").mkdir(exist_ok=True)
sys.path.insert(0, str(Path(__file__).resolve().parent)); from sizes import bytes_per_row as _bpr
PURE = str(HERE / "data/serde_micro_2panel_raw.csv")
NATIVE_ARMS = {"no_serde", "only_ser"}
ARMS = ["no_serde", "only_deser", "only_ser", "serde"]
DATA_PRE = {"i2f": "int", "f2i": "float"}  # input-side dataset prefix


def bytes_per_row(direction, arm, K):
    return _bpr(direction, arm, K)


def parse_log(path):
    out = {"i2f": {}, "f2i": {}}
    rx = re.compile(r"^\s+(no_serde|only_deser|only_ser|serde)\s+.*throughput=([\d.]+)\s*MB/s.*(i2f|f2i)k(\d+)\]")
    for line in open(path):
        m = rx.match(line)
        if m:
            arm, mbps, d, K = m.group(1), float(m.group(2)), m.group(3), int(m.group(4))
            out[d].setdefault(K, {})[arm] = mbps
    return out


def load_pure():
    """{('float64'|'int64', K, arm): mrows_s_true} from the canonical tidy CSV."""
    ref = {}
    for row in csv.DictReader(open(PURE)):
        ref[(row["type"], int(row["K"]), row["arm"])] = float(row["mrows_s_true"])
    return ref


def main(path, csv_out=None):
    data = parse_log(path)
    pure = load_pure()
    tidy = []
    for d in ["i2f", "f2i"]:
        pure_in = "int64" if d == "i2f" else "float64"    # input-type pure panel
        pure_out = "float64" if d == "i2f" else "int64"   # output-type pure panel
        print(f"\n=== {d} ({pure_in} in -> {pure_out} out) ===")
        print(f"{'K':>2} | {'noSerde':>8} {'deser':>7} {'ser':>7} {'serde':>7} "
              f"| {'parse':>6} {'ser':>6} {'cast':>5} {'add%':>5} | {'p_pure':>6} {'s_pure':>6}  (Mrows/s ; ns/row)")
        print("-" * 100)
        for K in sorted(data[d]):
            arms = data[d][K]
            if len(arms) < 4:
                print(f"{K:>2} | incomplete {sorted(arms)}")
                continue
            r = {a: arms[a] * 1e6 / bytes_per_row(d, a, K) / 1e6 * REPEAT for a in arms}  # true Mrows/s
            t = {a: 1e3 / r[a] for a in r}  # ns/row
            parse = t["only_deser"] - t["no_serde"]
            serialize = t["only_ser"] - t["no_serde"]
            additive = t["no_serde"] + parse + serialize
            addpct = 100 * (t["serde"] / additive - 1)
            # cast+Map cost vs the pure input-type panel's no_serde (both K*8 native rows)
            pure_ns = pure.get((pure_in, K, "no_serde"))
            cast = (t["no_serde"] - 1e3 / pure_ns) if pure_ns else float("nan")
            # pure-panel parse (input type) and serialize (output type) references, ns/row
            def pure_t(typ, arm):
                v = pure.get((typ, K, arm))
                return 1e3 / v if v else float("nan")
            p_pure = pure_t(pure_in, "only_deser") - pure_t(pure_in, "no_serde")
            s_pure = pure_t(pure_out, "only_ser") - pure_t(pure_out, "no_serde")
            print(f"{K:>2} | {r['no_serde']:>8.1f} {r['only_deser']:>7.1f} {r['only_ser']:>7.1f} {r['serde']:>7.1f} "
                  f"| {parse:>6.1f} {serialize:>6.1f} {cast:>5.1f} {addpct:>+5.1f} | {p_pure:>6.1f} {s_pure:>6.1f}")
            for a in ARMS:
                tidy.append(dict(type=d, K=K, arm=a, throughput_mbps_reported=arms[a],
                                 bytes_per_row=round(bytes_per_row(d, a, K), 4),
                                 inmem_repeat=REPEAT, mrows_s_true=round(r[a], 4)))
    if csv_out:
        with open(csv_out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(tidy[0].keys()))
            w.writeheader()
            w.writerows(tidy)
        print(f"\nwrote {csv_out} ({len(tidy)} rows)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else str(HERE / "out/serde_micro_mixed_raw.csv"))
