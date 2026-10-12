"""Does Flink 2.1.3 push a row-level predicate into the filesystem csv/json source? Print the optimized plan."""
import os
from pyflink.table import EnvironmentSettings, TableEnvironment
CSV = os.path.expanduser("~/work/nebulastream-public/cmake-build-release/nes-systests/testdata/large/multicol/nf3.csv")
JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nf3.json")
env = TableEnvironment.create(EnvironmentSettings.in_streaming_mode())
for fmt, path in (("csv", CSV), ("json", JSON)):
    env.execute_sql(f"CREATE TABLE t_{fmt} (c0 DOUBLE, c1 DOUBLE, c2 DOUBLE) WITH ('connector'='filesystem','path'='file://{path}','format'='{fmt}')")
    env.execute_sql(f"CREATE TABLE sink_{fmt} (c0 DOUBLE) WITH ('connector'='blackhole')")
    plan = env.explain_sql(f"INSERT INTO sink_{fmt} SELECT c0 FROM t_{fmt} WHERE c1 > 500 AND c2 = 3.5")
    opt = plan.split("== Optimized Physical Plan ==")[1].split("== Optimized Execution Plan ==")[0]
    print(f"\n##### {fmt}: optimized physical plan")
    for l in opt.strip().splitlines(): print("   ", l.strip())
