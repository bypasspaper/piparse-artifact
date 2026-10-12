#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""E12 — thread-structure study (DPP vs gang vs chunker vs thread-per-query vs round-robin), identical / cost-skewed /
bursty queries, Threadripper | Raspberry Pi 5. Re-plots the two paper figures from the shipped sweep CSVs:

  out/core_story_ws2.{png,pdf}  <- rig/plot_core.py  data/sweep_tr_ws_D64_C1000.csv + data/sweep_tr_ws_rr_D64_C1000.csv (TR, rr rows live in a 2nd file)
                                                      data/sweep_pi_ws2_D64_C1000.csv (Pi, unthrottled re-run incl. rr + chunker_quote)
  out/skew_story.{png,pdf}      <- rig/plot_skew.py  data/sweep_tr_ws_heavy / sweep_tr_ws_burst / sweep_pi_ws2_heavy / sweep_pi_ws2_burst

Originals: ~/Notes/nebulastream/benchmark/1_isolated_to_engine/gang_vs_dpp_2026-09-08/fig/{plot_core,plot_skew}.py
(= rig/ here, unmodified; they take their CSVs as arguments and resolve nothing else). --check compares the PNGs pixel-wise
against expected/. No benchmark is run.

VERIFIED 2026-10-12: with the interpreter the experiment card used (system python3, matplotlib 3.6.3, numpy 1.26.4) both PNGs
are PIXEL-IDENTICAL to expected/. With matplotlib 3.11.0 the curves are identical but tick spacing / label metrics drift
(core_story_ws2 1 px wider, ~7-10 % of pixels touched) -> --check reports DIFFER. Use `--python python3` to reproduce exactly.
"""
import argparse, pathlib, subprocess, sys
HERE = pathlib.Path(__file__).resolve().parent
D, R, OUT, EXP = HERE / "data", HERE / "rig", HERE / "out", HERE / "expected"
ap = argparse.ArgumentParser(); ap.add_argument("--check", action="store_true", help="pixel-compare out/*.png with expected/*.png")
ap.add_argument("--python", default=sys.executable); a = ap.parse_args()
OUT.mkdir(exist_ok=True)
subprocess.run([a.python, str(R / "plot_core.py"), f"{D/'sweep_tr_ws_D64_C1000.csv'}+{D/'sweep_tr_ws_rr_D64_C1000.csv'}",
                str(D / "sweep_pi_ws2_D64_C1000.csv"), str(OUT / "core_story_ws2")], check=True)
subprocess.run([a.python, str(R / "plot_skew.py"), str(D / "sweep_tr_ws_heavy_D64_C1000.csv"), str(D / "sweep_tr_ws_burst_D64_C1000.csv"),
                str(D / "sweep_pi_ws2_heavy_D64_C1000.csv"), str(D / "sweep_pi_ws2_burst_D64_C1000.csv"), str(OUT / "skew_story")], check=True)
if a.check:
    from PIL import Image
    import numpy as np
    ok = True
    for name in ("core_story_ws2.png", "skew_story.png"):
        x, y = np.asarray(Image.open(OUT / name).convert("RGB")), np.asarray(Image.open(EXP / name).convert("RGB"))
        same = x.shape == y.shape and bool((x == y).all())
        diff = (0 if same else (np.abs(x.astype(int) - y.astype(int)).max() if x.shape == y.shape else -1))
        print(f"{name}: shape {x.shape} vs {y.shape} -> {'IDENTICAL PIXELS' if same else f'DIFFER (max channel delta {diff})'}")
        ok &= same
    sys.exit(0 if ok else 1)
