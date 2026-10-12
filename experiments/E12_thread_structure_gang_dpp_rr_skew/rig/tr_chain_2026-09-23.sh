#!/usr/bin/env bash
# TR chain 2026-09-23: rr rows for the main figure, then cost-skew and bursty sweeps over all five arms (user go 00:20).
cd "$(dirname "$0")"
echo "tr chain pid $$ start $(date -Is)"
MACHINE=tr ARMS="rr 1" DW=64 CAP=1000 TAG=ws_rr ./run_fig.sh
MACHINE=tr ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 HEAVY=0.1,4 TAG=ws_heavy ./run_fig.sh
MACHINE=tr ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 BURST=20,20 TAG=ws_burst ./run_fig.sh
echo "TR CHAIN DONE $(date -Is)"
