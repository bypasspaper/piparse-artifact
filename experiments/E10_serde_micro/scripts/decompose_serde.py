#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Artifact copy of piparse-bench scratchpad/serde_micro/decompose_serde.py. Changes: defaults = ../data/logs/serde_full_run.log ->
# ../out/serde_micro_decomposition.csv (CSV_SZ table unchanged = the floatk*.csv sizes, cf. data/serde_micro_dataset_sizes.csv).
"""Decompose the serde-micro sweep: input-MB/s -> rows/s (per-arm bytes/row), then per-K the
parse/serialize costs (in ns/row) + both cross-checks + the additivity (serde vs sum-of-halves).

rows/s = MB/s * 1e6 / bytes_per_row ; bytes/row: native arms = K*8, CSV arms = csv_size/ROWS.
True rows/s = per-pass * REPEAT(20). Ratios / ns-per-row deltas are REPEAT-invariant.
Arms: no_serde(nat) only_deser(csv) only_ser(nat) serde(csv) serde_naive(csv).
Decomposition (time/row t = 1/rows_s):
  serialize = t(only_ser)-t(no_serde)  [native pair]  ~=  t(serde)-t(only_deser)  [csv pair]
  parse     = t(only_deser)-t(no_serde)[Native-out]   ~=  t(serde)-t(only_ser)    [JSON-out]
  additive? t(serde) vs t(no_serde)+parse+serialize
"""
import re, sys

ROWS = 2_000_000
REPEAT = 20
CSV_SZ = {1:25777108,2:51554041,3:77331899,4:103109490,5:128887182,6:154664216,7:180441578,
          8:206218351,9:231996484,10:257774320,11:283552675,12:309330847,13:335108417,
          14:360885972,15:386663393,16:412440402,17:438218991,18:463996003,19:489774326,20:515552573}
NATIVE_ARMS = {"no_serde", "only_ser"}

def bytes_per_row(arm, K):
    return K * 8 if arm in NATIVE_ARMS else CSV_SZ[K] / ROWS

def parse_log(path):
    """summary lines: '    serde   x=single-node  throughput=17.1 MB/s ... bidstr? no -> [serde_micro/floatkK]'"""
    out = {}
    rx = re.compile(r"^\s+(no_serde|only_deser|only_ser|serde|serde_naive)\s+.*throughput=([\d.]+)\s*MB/s.*floatk(\d+)\]")
    for line in open(path):
        m = rx.match(line)
        if m:
            arm, mbps, K = m.group(1), float(m.group(2)), int(m.group(3))
            out.setdefault(K, {})[arm] = mbps
    return out

def rows_s(mbps, arm, K):          # true Mrows/s
    return mbps * 1e6 / bytes_per_row(arm, K) / 1e6 * REPEAT

def main(path, csv_out):
    data = parse_log(path)
    cols = ["K","no_serde_Mrows","only_deser_Mrows","only_ser_Mrows","serde_Mrows","serde_naive_Mrows",
            "parse_ns_row","serialize_ns_row","parse_xcheck_ns","serialize_xcheck_ns",
            "serde_actual_ns","serde_additive_ns","superadd_pct","naive_over_serde"]
    rowsout = []
    print(f"{'K':>2} | {'noSerde':>8} {'deser':>7} {'ser':>7} {'serde':>7} {'naive':>7} "
          f"| {'parse':>6} {'ser':>6} {'add?':>6} {'naive/serde':>11}  (Mrows/s ; ns/row)")
    print("-"*104)
    for K in sorted(data):
        d = data[K]
        if len(d) < 5:
            print(f"{K:>2} | incomplete {sorted(d)}"); continue
        r = {a: rows_s(d[a], a, K) for a in d}            # true Mrows/s
        t = {a: 1e9 / (r[a]*1e6) for a in r}              # ns/row
        serialize = t["only_ser"] - t["no_serde"]         # native pair
        serialize_x = t["serde"] - t["only_deser"]        # csv pair (cross-check)
        parse = t["only_deser"] - t["no_serde"]           # Native-out pair
        parse_x = t["serde"] - t["only_ser"]              # JSON-out pair (cross-check)
        serde_add = t["no_serde"] + parse + serialize
        superadd = 100*(t["serde"]/serde_add - 1)
        rowsout.append([K, r["no_serde"], r["only_deser"], r["only_ser"], r["serde"], r["serde_naive"],
                        parse, serialize, parse_x, serialize_x, t["serde"], serde_add, superadd,
                        t["serde_naive"]/t["serde"]])
        print(f"{K:>2} | {r['no_serde']:8.2f} {r['only_deser']:7.2f} {r['only_ser']:7.2f} {r['serde']:7.2f} "
              f"{r['serde_naive']:7.2f} | {parse:6.1f} {serialize:6.1f} {superadd:+5.1f}% {t['serde_naive']/t['serde']:10.2f}x")
    with open(csv_out, "w") as f:
        f.write(",".join(cols)+"\n")
        for row in rowsout:
            f.write(",".join(f"{v:.3f}" if isinstance(v,float) else str(v) for v in row)+"\n")
    print(f"\n[wrote {csv_out}]")
    # geomeans of the two cross-check pairs
    import math
    def gm(xs): xs=[x for x in xs if x>0]; return math.exp(sum(map(math.log,xs))/len(xs)) if xs else float('nan')
    ser  = [row[7] for row in rowsout]; ser_x = [row[9] for row in rowsout]
    par  = [row[6] for row in rowsout]; par_x = [row[8] for row in rowsout]
    print(f"serialize ns/row: native-pair geomean {gm(ser):.1f} vs csv-pair {gm(ser_x):.1f}  (cross-check)")
    print(f"parse     ns/row: Native-out geomean {gm(par):.1f} vs JSON-out {gm(par_x):.1f}  (cross-check)")

if __name__ == "__main__":
    from pathlib import Path
    HERE = Path(__file__).resolve().parent.parent; (HERE / "out").mkdir(exist_ok=True)
    main(sys.argv[1] if len(sys.argv) > 1 else str(HERE / "data/logs/serde_full_run.log"),
         sys.argv[2] if len(sys.argv) > 2 else str(HERE / "out/serde_micro_decomposition.csv"))
