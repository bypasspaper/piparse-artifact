#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Regenerate every figure/table of the paper from the shipped data (no benchmark runs; seconds to a few minutes).
# Usage: ./make_all_figures.sh [python]      (default python: the pbench venv if present, else python3)
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${1:-${PYTHON:-}}"
if [ -z "$PY" ]; then
  if [ -x "${PBENCH_DIR:-$HOME/work/piparse-bench}/.venv/bin/python" ]; then PY="${PBENCH_DIR:-$HOME/work/piparse-bench}/.venv/bin/python"; else PY=python3; fi
fi
echo "python: $PY"; "$PY" -c "import duckdb, matplotlib" || { echo "install scripts/requirements.txt into $PY first"; exit 1; }
fail=0
for d in experiments/E*/; do
  [ -f "$d/make_figure.py" ] || { echo "-- $d: no make_figure.py (static-analysis element: see its README and run.sh)"; continue; }
  echo "== $d"
  ( cd "$d" && "$PY" make_figure.py ) && echo "   ok -> $d/out/" || { echo "   FAILED"; fail=1; }
done
exit $fail
