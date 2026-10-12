# Artifact: compiling, lazily evaluated (de)serialization for text-format stream processing in NebulaStream

Reproducibility package for the SIGMOD submission. It contains (1) pointers to the frozen source of the
prototype system and the benchmark harness, (2) the data recipes, (3) the exact experiment definitions, raw
measurements and commands behind every figure and table, and (4) the scripts that turn the measurements into the
paper's figures. Everything in this repository is Apache-2.0 (`LICENSE`); the two source repositories carry their
own copies.

| component | where | frozen at |
| --- | --- | --- |
| Prototype system (NebulaStream engine with the lazy-(de)serialization formatters, the JIT context layer and the lock-free sequence shredder) | `github.com/ANON-ACCOUNT/nebulastream-snapshot`, branch `benchmark-piparse-lazyparse-fast-csv` | tag **`piparse-artifact-v1`** (`184ec91f50`) |
| Benchmark harness (YAML experiments → worker/Flink/Spark runs → DuckDB → figures) | `github.com/ANON-ACCOUNT/piparse-bench-snapshot` | tag **`piparse-artifact-v1`** (`33e7603`) |
| This package: environment, data recipes, per-figure experiments, raw results, figure scripts | this repository | 2026-10-12 |

`MANIFEST.md` lists every exact version, hash and binary; `env/README.md` the hardware and software;
`data/README.md` the datasets; `results/README.md` the raw measurement store; `experiments/E*/README.md` one
page per paper element.

## 1. Paper element → directory

| paper element | directory | machine | re-measure time |
| --- | --- | --- | --- |
| Ablation ladder r1…r7 (v9: overloads ON on r6b and r7) incl. the compile-rung split (1.88 × 1.50 × 1.26) | `experiments/E01_ablation_ladder` | TR | ~2 h (suite 180 runs + r5 + r7 cell + new rungs 19 + 12 min + overload re-run 2 × 15 min) |
| Parallel-rung gain classes (q14 16.9× vs q0 6.1×: JSON output-serializer ceiling) | `experiments/E02_parallel_rung_q14_vs_q0` | TR | 18 min |
| Shredder thread scaling on spanning rows (figW), spanning-size sweep (figS), latency (figL), q_ex twin | `experiments/E03_shredder_spanning_figW` | TR | ~45 min e2e (4 runs of 13–14 min) + the isolated rig sweeps |
| q_ex 1→23 worker sweep, serde matrix (figQ) | `experiments/E04_qex_serde_matrix_figQ` | TR | ~30 min (figQ 14 min + locking 4 min + figI 13 min) |
| 5-arm head-to-head (NES optimised / native / naive, Flink, Spark), stateless + stateful tiers | `experiments/E05_head_to_head_5arm` | TR | ~3.5 h (stateless 500 runs 2 h 25 + stateful 150 runs 1 h) + ~1 h regen layers |
| Overload-knob A/B | `experiments/E06_overload_ab` | TR, Pi | 40 min |
| Pi per-query tiers (optimised build e / native / naive W3) | `experiments/E07_pi_per_query_tiers` | Pi | ~1 h 45 min (`_nbi` chain) |
| Many-source scaling N = 1…1000 + latency, NES/Flink/Spark/naive/native | `experiments/E08_scaling_ladders_n1_1000` | TR, Pi | TR ≈ 52 h for all seven ladders; Pi 14–20 h per engine ladder |
| §2 teaser Fig1 (CPU/tuple by stage) and Fig2 (predicate-sweep cost laws) | `experiments/E09_teaser_fig1_fig2` | TR | ~2 h incl. the perf profiles (see its README) |
| Serde micro-benchmarks (K = 1…20 float/int, i2f/f2i) | `experiments/E10_serde_micro` | TR | ~3 h (float + int + mixed K sweeps); smokes 3 min |
| Cross-format 4×4 matrix (CSV/JSON/HL7/XML × 3 rungs) + W sweep | `experiments/E11_cross_format_matrix` | TR | ≈ 5.5 h (1440 runs + the 480-run r_par re-measurement + W sweep) |
| Thread structures (DPP vs gang vs chunker vs thread-per-query vs rr), cost skew, bursts | `experiments/E12_thread_structure_gang_dpp_rr_skew` | TR, Pi | ~1 h 45 min TR, ~2 h 20 min Pi |
| Lines of code to add a formatter | `experiments/E13_formatter_loc` | — | seconds (static analysis) |

Every directory holds the experiment YAML(s), the measured data (`data/`), the figure as submitted (`expected/`),
a `make_figure.py` that regenerates it from the shipped data, and a `run.sh` with the exact re-measurement command.

## 2. Getting started (≈ 30 min after the build; the build itself is 1–2 h host or ~40 min in the dev container)

1. **Regenerate all figures from the shipped data (no hardware needed, ~2 min).**
   ```
   python3 -m venv .venv && .venv/bin/pip install -r scripts/requirements.txt
   PYTHON=.venv/bin/python scripts/make_all_figures.sh        # writes experiments/E*/out/, compare with experiments/E*/expected/
   ```
2. **Build the engine** at the tag (see `env/README.md` §3; host or container route):
   ```
   git clone https://github.com/ANON-ACCOUNT/nebulastream-snapshot nes && cd nes
   git checkout -B benchmark-piparse-lazyparse-fast-csv piparse-artifact-v1
   NES_SRC=$PWD NES_BUILD_DIR=$PWD/cmake-build-release ../env/tr/build_release.sh      # add NES_DEV_IMAGE=... for the container route
   ```
3. **Functional check (seconds):** the two systests shipped with the freeze exercise the lazy-vs-eager
   hoisting knob and the cast plugins end to end:
   ```
   for t in HoistingQRoute MixedCastSmoke; do
     cmake-build-release/nes-systests/systest/systest -t nes-systests/formatter/$t.test --workingDir cmake-build-release/nes-systests/artifact_$t
   done        # expected: "All queries passed." twice (2 + 2 queries, < 1 s each on the reference box, 2026-10-12)
   ```
4. **Fetch the public datasets** (~12 GB; the smoke test needs only `bid_653M.csv`):
   `NES_SRC=... NES_BUILD_DIR=... data/fetch_testdata.sh`
5. **Install the harness and run the smoke experiment (~1 min):**
   ```
   git clone https://github.com/ANON-ACCOUNT/piparse-bench-snapshot && cd piparse-bench && git checkout piparse-artifact-v1 && uv sync
   pkill -9 -x main; PBENCH_KEEP_LOGS=1 uv run python bench.py run <artifact>/scripts/smoke_q0_small.yaml \
       --build-dir $NES_BUILD_DIR --worker-port 9099
   ```
   Expected: `Done: 1 completed, 0 failed` and a throughput line (3.7 GB/s = 101 Mrows/s on the reference box at
   W4, run 2026-10-12; the Mrows/s figure uses the catalog's 18,106,394 input rows).

## 3. Full reproduction

Set `NES_BUILD_DIR` (the build from step 2) and `PBENCH_DIR` (the harness checkout), then for any element
`experiments/E*/run.sh` prints its wall time and runs the exact `pbench run` command(s) of the paper (each YAML's
`description:` also carries the `RUN:` line and the pitfalls met while running it). Afterwards
`make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb --run-group <id printed by pbench>` draws the figure
from the new run. Datasets beyond the public ones are generated/converted with `data/generators` and
`data/converters` and gated with `data/checksum_gates` (anchor `31300000,269477267979` for every format twin).
Pi experiments need the aarch64 build (`env/README.md` §4) and the Pi-side paths noted in E07/E08/E12.

## 4. Things a reader of the paper must know (collected caveats)

- **Lazy-overload knob — paper policy (author, 2026-10-12): ON for every comparison on an id** (ids are always
  decimal strings, so the raw-text compare is safe). pbench treats a missing `overload` key as OFF, and the following
  shipped TR data sets were measured OFF: the 5-arm tables (E05), figQ (E04), figW and its q_ex twin (E03), the
  q14-vs-q0 W sweep (E02) and ladder rung r7 (E01). Only id-filter queries are affected: on the TR the knob adds
  +18 % to q2_og and is flat elsewhere (E06, `nes_simd_overload_*`); on the Pi it is 1.84× on q2_og and E07 ships both
  series (`ctrl` OFF, `ovl` ON — the paper uses `ovl`). The Fig1 v2 optimised bar and the Fig2 `ovl` arm are ON.
- **Pi optimised numbers = build e (Nautilus inlining ON through port patch 0005).** The Aug-23 and "nb" Pi tiers are
  superseded. The Pi's many-source ladders and latency curves were *not* retaken on build e (author decision
  2026-10-06); the ~6× per-core Pi/TR gap is expected.
- **Latency curves:** the paper uses the engine default of 64 in-flight buffers per source (`default_max_inflight_buffers`)
  for every NES arm (author decision). E08 ships the probe showing that a cap of 16 is throughput-neutral and lowers
  low-N latency; it is context, not a paper number.
- **Ablation ladder — paper policy (author, 2026-10-12): r6b (lazy overloads) and r7 (parallelisation) both with
  overloads ON.** Re-measured 2026-10-12 on the frozen binary (E01, run_groups `20261012T150636-97b18744` W1 and
  `20261012T151153-401837a8` W23; control arms reproduce the v7 ladder within 0.1 % / 1.8 %): ladder **v9** replaces
  the pre-fix r6b and the overload-OFF r7 (`E01/data/ablation_ladder_v9_bidstr.csv`). Overloads: 1.96× on q2og and
  1.18× on q_ex at W1, 1.19× / 1.03× at W23, flat elsewhere; cumulative r1→r7 geomean 68.9×. The former r3_eager rung
  was not a parse-all rung (IR proof in E01); the new rungs r3_eager_all / r3_lazy_nopass split the compile bar.
- **figW:** the paper cites LF/LK 1.37× @W24 from the 2026-08-31 build (`shredder_worker_probe`, run_group
  20260831T173338-1b014b79). The same-binary re-take of 2026-10-05 (1.30×) is shipped in E03 as supplementary data only.
  sets are shipped (E03); decide which binary the figure cites.
- **Cross-format matrix:** r_par cells come from the 480-run re-measurement with `ccx_aware_task_queues=false,
  pin_threads=false` (the ccx+pin combination is a ~2× single-source pathology); InMemory r_par runs carry a ×20
  repeat correction (E11).
- **Flink N=1000 on the Pi** needed `-Xmx8g` and a 30-min heartbeat (`flink_jvm_args`, `flink_config` in the YAML);
  the Pi N=1000 naive point is not a clean page-cache point (E08).
- **Pi power:** all cited Pi runs post-date the 2026-09-22 PSU fix and passed `vcgencmd get_throttled == 0x0`.

## 5. Double-blind review copy

SIGMOD's research track is double-anonymous and requires that "the link and materials should preserve anonymity".
This repository is the authors' internal version and is **not** anonymous: it names the GitHub account of the
harness repository, the user and group directories of the reference box, the university's data server, the Raspberry
Pi's hostname and address, and the clinical cooperation behind the working example. Build the review copy with

```
scripts/anonymize/make_anonymous_copy.sh ../piparse-artifact-anon     # rsync without history → regex scrub (scripts/anonymize/terms.tsv)
                                                                      # → DuckDB/parquet hostname + config scrub → fresh git history as "anonymous"
                                                                      # → residual-term audit (exit 1 if anything is left)
```

Then build the two source snapshots and publish all three repositories under a GitHub account created only for the
submission (no link shortener, not referenced from any non-anonymous page):

```
scripts/anonymize/make_anonymous_snapshots.sh ../piparse-anon-snapshots   # engine tag + harness tag → scrubbed single-commit trees
gh auth login                                                             # as the anonymous account (gh keeps several accounts)
scripts/anonymize/push_review_repos.sh <anonymous-account>                # fills ANON-ACCOUNT in the review copy, creates + pushes
                                                                          # piparse-artifact, nebulastream-snapshot, piparse-bench-snapshot
gh auth switch --user <your account>
```

The review copy's `MANIFEST.md` points at the two snapshots (the original repositories' git histories carry author names,
so the tags themselves cannot be published anonymously; the snapshots are the tag trees as one commit by "anonymous", with
code-owner / mailmap files removed). In the two source snapshots only personal identity, the edge box and the clinical
cooperation are scrubbed; the project's public institution references, repository links and its ExternalData URL stay,
because the paper names the system and the test-data fetch needs that URL. After the review period the de-anonymised repositories replace them. The scripts leave
three things to you:

1. **System name.** NebulaStream / `nes-*` is not scrubbed by default (binary, target and path names such as
   `nes-single-node-worker` would break); the commented block at the end of `terms.tsv` turns it on if the paper
   anonymizes the system name.
2. **The anonymous GitHub account** (signup needs an e-mail inbox, CAPTCHA and 2FA — a person's five minutes); the
   three repositories are public so reviewers need no login.
3. **Data hosting (author decision 2026-10-12).** The six public datasets stay on the engine's own ExternalData share
   (`data/fetch_testdata.sh`): that URL is part of the public NebulaStream tree and reveals nothing beyond the system
   name, which the paper states. Everything submission-specific — the five `bid_strings_3GB` twins and `bid_1GB`
   (~25 GB, md5s in `data/README.md`) — must **not** go there. Upload them to an anonymous host that serves plain
   HTTPS downloads by file name (a Hugging Face dataset repository under a throwaway account handles multi-GB files
   for free; GitHub release assets would need 2 GB splits) and pass the base URL as `DATA_URL=…` to
   `scripts/anonymize/push_review_repos.sh`, which fills the `DATA-URL-PLACEHOLDER` in the review copy's `data/fetch_twins.sh`
   and `data/README.md` (the URL itself stays out of this repository). Do not use a link shortener.

After the review period the de-anonymised version (this repository) replaces the anonymous copy.

## 6. Layout

```
README.md  MANIFEST.md  LICENSE
env/         hardware + software, tr/build_release.sh, pi/ (nautilus 0005 patch, offline Pi build scripts, patched source tarball)
data/        README (datasets, sizes, md5), fetch_testdata.sh, generators/, converters/{hl7,xml}, checksum_gates/, PAPER_WORKLOAD.md
results/     tr/piparse_bench.duckdb (all TR runs), tr/matrix_snapshot_*.duckdb, pi/*.csv (Pi exports)
experiments/ E01 … E13, one directory per paper element (README, yaml/, data/, expected/, make_figure.py, run.sh)
scripts/     make_all_figures.sh, smoke_q0_small.yaml, requirements.txt, anonymize/ (double-blind review copy)
```
