#!/usr/bin/env bash
# TR chain 2 (2026-09-23 10:45): burst sweep re-run after the seed/timer double-admission fix (first run INVALID_seedbug_*).
cd "$(dirname "$0")"
echo "tr chain2 pid $$ start $(date -Is)"
MACHINE=tr ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 BURST=20,20 TAG=ws_burst ./run_fig.sh
echo "TR CHAIN DONE $(date -Is)"
