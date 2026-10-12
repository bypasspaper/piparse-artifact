#!/usr/bin/env bash
# Pi chain 2 (2026-09-23 10:45): burst sweep re-run after the seed/timer double-admission fix (first run INVALID_seedbug_* on the Pi),
# then the gang k=4 spin-50 cells (N=2..32) the heavy sweep lost to the gang duplicate-execution stall (appends to ws2_heavy).
cd "$(dirname "$0")"
echo "pi chain2 pid $$ start $(date -Is)"
MACHINE=pi ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 BURST=20,20 TAG=ws2_burst ./run_fig.sh
MACHINE=pi ARMS="gprivate 4" PI_STREAMS=1 LOWN=2,4,8,16,32 DW=64 CAP=1000 HEAVY=0.1,4 TAG=ws2_heavy ./run_fig.sh
echo "PI CHAIN DONE $(date -Is)"
