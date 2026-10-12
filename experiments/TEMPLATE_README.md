# E<nn> — <paper element, e.g. "Ablation ladder r1…r7 (Fig. X)">

**Claim in the paper.** <one or two sentences: what the figure/table shows and the headline number(s)>

**Machine.** <Threadripper PRO 5965WX (W23 + 1 io thread) | Raspberry Pi 5 (W3 + 1 io thread) | both>; binary = <engine tag / build id>, run date(s) <YYYY-MM-DD>.

**Measured with.** pbench experiment(s) `experiments/<name>.yaml` (copies in `yaml/`), query catalog entries `queries/<...>`, run_group id(s) `<id>` in `results/tr/piparse_bench.duckdb` (or Pi export `results/pi/<file>`).

## Files

| path | what |
| --- | --- |
| `yaml/*.yaml` | the exact experiment definitions (copied from piparse-bench at tag `piparse-artifact-v1`) |
| `data/*.csv` | the measured numbers the figure is drawn from (medians / tidy tables) |
| `expected/*` | the figure(s) and table(s) as used for the submission |
| `make_figure.py` | regenerates `out/` from `data/` (and/or the results DB); must reproduce `expected/` |
| `run.sh` | re-measures: the exact `pbench run` command(s); prints the expected wall time first |

## Reproduce the figure from the shipped data (seconds)

```
python3 make_figure.py            # writes out/<figure>.{png,svg|pdf} (+ out/*.csv where the script re-derives medians)
```

## Re-measure (<estimated wall time>, <machine>)

```
./run.sh                           # needs NES_BUILD_DIR, PBENCH_DIR (see ../../README.md §3)
python3 make_figure.py --db $PBENCH_DIR/results/piparse_bench.duckdb --run-group <new id>
```

## Caveats / provenance notes

- <anything a reviewer must know: knob states (overload ON/OFF), binary differences, superseded variants, known defects>
