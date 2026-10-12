"""Does Flink 2.1.3 push `SELECT c0` into the filesystem csv / json decoders? Print the optimized plan's source scan."""
import os, re, sys
from pyflink.table import EnvironmentSettings, TableEnvironment
CSV = os.path.expanduser("~/work/nebulastream-public/cmake-build-release/nes-systests/testdata/large/multicol/nf3.csv")
JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nf3.json")
env = TableEnvironment.create(EnvironmentSettings.in_streaming_mode())
for fmt, path in (("csv", CSV), ("json", JSON)):
    env.execute_sql(f"DROP TABLE IF EXISTS t_{fmt}")
    env.execute_sql(f"""CREATE TABLE t_{fmt} (c0 DOUBLE, c1 DOUBLE, c2 DOUBLE) WITH (
        'connector' = 'filesystem', 'path' = 'file://{path}', 'format' = '{fmt}')""")
    env.execute_sql(f"DROP TABLE IF EXISTS sink_{fmt}")
    env.execute_sql(f"CREATE TABLE sink_{fmt} (c0 DOUBLE) WITH ('connector' = 'blackhole')")
    plan = env.explain_sql(f"INSERT INTO sink_{fmt} SELECT c0 FROM t_{fmt}")
    opt = plan.split("== Optimized Physical Plan ==")[1].split("==")[0] if "== Optimized Physical Plan ==" in plan else plan
    scan = [l.strip() for l in opt.splitlines() if "TableSourceScan" in l]
    print(f"\n##### {fmt}: optimized physical plan, source scan line(s):")
    for l in scan: print("   ", l)
    print("    pushdown:", "YES (project=[...] on the scan)" if any("project=" in l for l in scan) else "NO (scan reads all fields)")
