import duckdb, os
c = duckdb.connect("results/piparse_bench.duckdb", read_only=True)
OUT = "/home/pi/powertest/export"
os.makedirs(OUT, exist_ok=True)

CLEAN_FLINK_A = "20260824T024940-530263c1"   # the real 60-run group; excludes the aborted attempt

JOBS = [
    # archive: EVERY row in the database (the file's documented rule)
    ("ALL_pi_runs_raw.csv", "true"),
    # plot-ready per-engine scaling curves
    ("nes_scaling.csv",
     "experiment in ('pi_scaling_file_a','pi_scaling_file_b','pi_scaling_file_c')"),
    ("flink_scaling.csv",
     "(experiment = 'pi_flink_scaling_a' and run_group = '%s') "
     "or experiment in ('pi_flink_scaling_b','pi_flink_scaling_c','pi_flink_scaling_c_n1000')" % CLEAN_FLINK_A),
    # THE SPARK RESULT: corrected 64 MiB buffer-granularity ladder (custom file-microbatch-csv
    # source). Throughput AND latency both come from this run.
    ("spark_scaling.csv",
     "experiment in ('pi_spark_mb_a','pi_spark_mb_b','pi_spark_mb_c')"),
    # THE NES-NAIVE RESULT: the naive stack (W1, BlockingFile, SequentialUncompiledOldCSV
    # sequential, JSONUncompiled, empty parser maps, NES_*_CODEC=original) on the SAME ladder as
    # NES/Flink/Spark, so all four curves overlay. 74 rows = 20x3 + 4x3 + 500 + 1000.
    # NOT to be confused with naive.csv, which is the PER-QUERY TIER arm (pi_naive_stateless +
    # pi_naive_stateful, all 13 queries) -- same relationship as nes.csv vs nes_scaling.csv.
    # !! N=1000 IS NOT A CLEAN PAGE-CACHE POINT: worker RSS reached 14,044 MB and evicted the
    # 3429 MB csv to <=37% residency over the 20.4 h run (75% of samples below csv size); only
    # the first ~5 h were fully resident. NVMe is not the binding limit (~30 MB/s of disk against
    # an 888 MB/s ceiling) so the mechanism is still oversubscription, but Spark's N=1000 cache
    # held and NES's fell only to ~86%, so naive's is the least resident of the four. Say so.
    ("naive_scaling.csv",
     "experiment in ('pi_naive_scaling_a','pi_naive_scaling_b','pi_naive_scaling_c',"
     "'pi_naive_scaling_d')"),
    # THE NES-NAIVE W3 RE-RUN (2026-10-02 real / Pi clock 2026-09-26): IDENTICAL naive stack and
    # ladder, number_of_worker_threads 1 -> 3 (= the optimized arm's W3+io1 budget). W1 funnelled
    # every stream's JSONUncompiled stringstream output through ONE worker (sequential source runs
    # the formatter inline, the output stage runs on the pool) -- the reference box already re-ran
    # its naive many-source arm at the optimized budget (W16) on 2026-09-01. Governor performance,
    # get_throttled 0x0 throughout (naive_w3_continuity.log + naive_w3_scale.tsv). 74 rows.
    # naive_scaling.csv (W1) stays as the single-worker reference; THIS is the fair naive curve.
    ("naive_scaling_w3.csv",
     "experiment in ('pi_naive_scaling_w3_a','pi_naive_scaling_w3_b','pi_naive_scaling_w3_c',"
     "'pi_naive_scaling_w3_d')"),
    # THE NO-SERDE RESULT: native->native (SystemNative .nes input, output_formatter NATIVE -
    # no parse, no serialization anywhere) on the SAME ladder, the fifth arm and the no-parsing
    # upper bound. INTERNAL NAME MISMATCH IS COSMETIC: experiments are pi_noserde_* but the file
    # is native_scaling.csv, beside native.csv (matching nes.csv/nes_scaling.csv). 74 rows.
    # !! ITS MB/s IS OVER NATIVE INPUT BYTES (3,443,000,000 B vs csv 3,595,281,395 B): multiply
    # by 1.0442 for a csv-byte basis, or quote aggregate rows/s (= N x 31.3M / elapsed).
    # !! THE N=1000 ROW RUNS default_max_inflight_buffers=16 (frozen default 64) - the ONLY
    # config deviation in the campaign; with 64 the point needs ~15.5 GB and took the box down
    # twice. Validated throughput-neutral at N=100/250 (pi_noserde_inflight_probe*, 0.24% spread,
    # p99 preserved at 16 but NOT at 8). Say so whenever quoting N=1000, especially its p99.
    # Unlike naive's, this N=1000 IS a clean page-cache point: min cache 3,291 MB >= the 3,284 MB
    # .nes file, peak RSS 12,229 MB, zero degradation (2,019.6 s processing, plateau holds).
    ("native_scaling.csv",
     "experiment in ('pi_noserde_scaling_a','pi_noserde_scaling_b','pi_noserde_scaling_c',"
     "'pi_noserde_scaling_d')"),
    # SUPERSEDED stock-reader Spark ladder. Its THROUGHPUT is valid (whole-file-batching control,
    # quantifies the micro-batching cost); its LATENCY is whole-file and MUST NOT BE PUBLISHED.
    ("spark_scaling_stockreader_SUPERSEDED_raw.csv",
     "experiment in ('pi_spark_scaling_a','pi_spark_scaling_b','pi_spark_scaling_c')"),
    # supporting
    ("pi_scaling_file_a_rev_raw.csv", "experiment = 'pi_scaling_file_a_rev'"),
    ("pi_scaling_iocontrol_raw.csv",  "experiment = 'pi_scaling_iocontrol'"),
    ("pi_scaling_probe_raw.csv",      "experiment = 'pi_scaling_probe'"),
    ("pi_asyncmmap_raw.csv",
     "experiment in ('pi_asyncmmap_bench','pi_asyncmmap_highn','pi_asyncmmap_n1000')"),
    # not results
    ("pi_asyncmmap_gate_raw.csv",     "experiment = 'pi_asyncmmap_gate'"),
    # Checksum sink -> throughput NULL by design. Proves File is the ONLY source that reads
    # SystemNative correctly (31,300,000 / 292199638827, = the csv-path value); both mmap
    # sources drop exactly the last tuple.
    ("pi_noserde_gate_raw.csv",       "experiment = 'pi_noserde_gate'"),
    # None of it a result: smoke (both sources, sized the ladder), memprobe (NATIVE vs JSON
    # output formatter - refuted 'NATIVE output is the memory consumer'), inflight probes
    # (the default_max_inflight_buffers 64/16/8 validation behind the N=1000 deviation).
    ("pi_noserde_calibration_raw.csv",
     "experiment in ('pi_noserde_scaling_smoke','pi_noserde_memprobe','pi_noserde_memprobe_n100',"
     "'pi_noserde_inflight_probe','pi_noserde_inflight_probe250')"),
    ("pi_flink_scaling_smoke_raw.csv","experiment = 'pi_flink_scaling_smoke'"),
    ("pi_naive_scaling_probe_raw.csv", "experiment = 'pi_naive_scaling_probe'"),
    ("pi_spark_calibration_raw.csv",
     "experiment in ('pi_spark_mb_smoke','pi_spark_mb_probe','pi_spark_scaling_smoke',"
     "'pi_spark_scaling_smoke_p4','pi_spark_scaling_probe')"),
]

for fname, where in JOBS:
    path = os.path.join(OUT, fname)
    c.execute("copy (select * from runs where %s order by experiment, timestamp) "
              "to '%s' (HEADER, DELIMITER ',')" % (where, path))
    n = c.execute("select count(*) from runs where %s" % where).fetchone()[0]
    print("%-46s %5d rows" % (fname, n))

total = c.execute("select count(*) from runs").fetchone()[0]
print("\nDB total: %d rows (ALL_pi_runs_raw.csv must equal this)" % total)
