#!/usr/bin/env bash
# Pi chain 2026-09-23: unthrottled re-run of the main window with rr added (+ quote-aware chunker appended to the same CSV),
# then cost-skew and bursty sweeps over all five arms. Governor ondemand (holds 2.4 GHz under load). User go 00:20.
cd "$(dirname "$0")"
echo "pi chain pid $$ start $(date -Is)"
MACHINE=pi ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 TAG=ws2 ./run_fig.sh
MACHINE=pi CUT=quote ARMS="chunker 4" DW=64 CAP=1000 TAG=ws2 ./run_fig.sh
MACHINE=pi ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 HEAVY=0.1,4 TAG=ws2_heavy ./run_fig.sh
MACHINE=pi ARMS="dpp 1|gprivate 1|gprivate 4|chunker 4|rr 1" DW=64 CAP=1000 BURST=20,20 TAG=ws2_burst ./run_fig.sh
echo "PI CHAIN DONE $(date -Is)"
