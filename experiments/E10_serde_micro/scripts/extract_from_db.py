#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rebuild the serde-micro tidy CSVs from the pbench results DB (replaces the run-log parsing of the original
emit_2panel_csv.py / decompose_mixed.py / combine_all_raw.py, whose mixed-run logs were session scratch and are not
shipped). Per (experiment, K, arm): median reported MB/s over the 3 reps -> rows/s via the arm's bytes/row
(native K*8, CSV = dataset bytes / 2M rows) x NES_INMEM_REPEAT (20; 3 for the slow naive stringstream arms).
Writes out/serde_micro_{2panel,mixed,all}_raw.csv (same columns as data/) and out/serde_micro_decomposition.csv
(float64 panel parse/serialize decomposition, same columns as data/). usage: extract_from_db.py [--db PATH]"""
import csv, json, os, re, sys, math
from pathlib import Path
import duckdb
sys.path.insert(0, str(Path(__file__).resolve().parent)); from sizes import bytes_per_row
HERE = Path(__file__).resolve().parent.parent; OUT = HERE / "out"; OUT.mkdir(exist_ok=True)
DB = sys.argv[sys.argv.index("--db") + 1] if "--db" in sys.argv else os.environ.get("PBENCH_DB", str(HERE.parent.parent / "results/tr/piparse_bench.duckdb"))
EXPS = {"serde_micro_full": "20260827T192927-af1c11f6", "serde_micro_int_full": "20260828T102231-6300a167",
        "serde_micro_mixed_full": "20260903T105905-615bada9", "serde_micro_mixed_naive": "20260903T131049-928bd2c3"}
TYPE = {"float": "float64", "int": "int64", "i2f": "i2f", "f2i": "f2i"}
FIELDS = ["type", "K", "arm", "throughput_mbps_reported", "bytes_per_row", "inmem_repeat", "mrows_s_true"]
con = duckdb.connect(DB, read_only=True)
tidy = []
for exp, rg in EXPS.items():
    rows = con.execute("""select query_ref, series, median(throughput_mbps), min(json_extract_string(config,'$.worker_env.NES_INMEM_REPEAT')), count(*)
                          from runs where experiment=? and run_group=? and throughput_mbps is not null group by 1,2""", [exp, rg]).fetchall()
    for q, arm, mbps, rep, n in rows:
        m = re.search(r"serde_micro/(float|int|i2f|f2i)k(\d+)$", q); typ, K = TYPE[m.group(1)], int(m.group(2)); rep = int(rep)
        bpr = bytes_per_row(typ, arm, K)
        # the shipped CSVs carry the log's 1-decimal print of the median -> round the same way for a like-for-like compare
        mbps_r = round(mbps, 1)
        tidy.append(dict(type=typ, K=K, arm=arm, throughput_mbps_reported=mbps_r, bytes_per_row=round(bpr, 4), inmem_repeat=rep,
                         mrows_s_true=round(mbps_r * 1e6 / bpr * rep / 1e6, 4)))
order_t = {"float64": 0, "int64": 1, "i2f": 2, "f2i": 3}; order_a = {"no_serde": 0, "only_deser": 1, "only_ser": 2, "serde": 3, "serde_naive": 4}
tidy.sort(key=lambda r: (order_t[r["type"]], r["K"], order_a[r["arm"]]))
def dump(name, rows):
    with open(OUT / name, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    print(f"wrote out/{name} ({len(rows)} rows)")
dump("serde_micro_all_raw.csv", tidy)
dump("serde_micro_2panel_raw.csv", [r for r in tidy if r["type"] in ("float64", "int64")])
dump("serde_micro_mixed_raw.csv", [r for r in tidy if r["type"] in ("i2f", "f2i")])
# float64 decomposition (decompose_serde.py accounting)
f = {(r["K"], r["arm"]): r["mrows_s_true"] for r in tidy if r["type"] == "float64"}
cols = ["K", "no_serde_Mrows", "only_deser_Mrows", "only_ser_Mrows", "serde_Mrows", "serde_naive_Mrows", "parse_ns_row", "serialize_ns_row",
        "parse_xcheck_ns", "serialize_xcheck_ns", "serde_actual_ns", "serde_additive_ns", "superadd_pct", "naive_over_serde"]
with open(OUT / "serde_micro_decomposition_from_db.csv", "w") as fh:
    fh.write(",".join(cols) + "\n")
    for K in range(1, 21):
        r = {a: f[(K, a)] for a in order_a}; t = {a: 1e3 / r[a] for a in r}
        ser = t["only_ser"] - t["no_serde"]; ser_x = t["serde"] - t["only_deser"]; par = t["only_deser"] - t["no_serde"]; par_x = t["serde"] - t["only_ser"]
        add = t["no_serde"] + par + ser
        vals = [K, r["no_serde"], r["only_deser"], r["only_ser"], r["serde"], r["serde_naive"], par, ser, par_x, ser_x, t["serde"], add, 100 * (t["serde"] / add - 1), t["serde_naive"] / t["serde"]]
        fh.write(",".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in vals) + "\n")
print("wrote out/serde_micro_decomposition_from_db.csv")
# compare with shipped data/
for name in ("serde_micro_all_raw.csv", "serde_micro_2panel_raw.csv", "serde_micro_mixed_raw.csv"):
    a = {(r["type"], r["K"], r["arm"]): float(r["mrows_s_true"]) for r in csv.DictReader(open(HERE / "data" / name))}
    b = {(r["type"], r["K"], r["arm"]): float(r["mrows_s_true"]) for r in csv.DictReader(open(OUT / name))}
    common = sorted(set(a) & set(b)); worst = max(abs(a[k] / b[k] - 1) for k in common)
    print(f"DIFF data/{name} vs out/: {len(a)}/{len(b)} rows, {len(common)} common, max |rel dev| {100*worst:.3f} % ({'OK' if worst < 0.002 else 'CHECK'})")
a = {r["K"]: r for r in csv.DictReader(open(HERE / "data/serde_micro_decomposition.csv"))}; b = {r["K"]: r for r in csv.DictReader(open(OUT / "serde_micro_decomposition_from_db.csv"))}
worst = max(abs(float(a[k][c]) / float(b[k][c]) - 1) for k in a for c in cols[1:6])
print(f"DIFF decomposition Mrows columns: max |rel dev| {100*worst:.3f} % ({'OK' if worst < 0.002 else 'CHECK'})")
