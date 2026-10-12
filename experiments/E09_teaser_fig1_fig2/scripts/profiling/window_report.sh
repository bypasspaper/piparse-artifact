#!/usr/bin/env bash
# Restrict a perf.data to the time window where the pipeline threads are busy (the query burst), then dump the
# flat per-comm/per-dso/per-symbol report for classify_v2.py.  usage: window_report.sh <perf.data> <out_symbols.txt> [min_samples_per_100ms]
set -u
DATA="$1"; OUT="$2"; MIN="${3:-100}"
# 1. sample density of DataSrc|WorkerThread per 100 ms bin
perf script -i "$DATA" -F time,comm 2>/dev/null | awk -v min="$MIN" '
  $1 ~ /^(DataSrc|WorkerThread)/ { for (i=2;i<=NF;i++) if ($i ~ /^[0-9]+\.[0-9]+:?$/) { t=$i; sub(/:$/,"",t); bin=int(t*10); c[bin]++; break } }
  END { for (b in c) if (c[b] >= min) print b }' | sort -n > "$OUT.bins"
if [ ! -s "$OUT.bins" ]; then echo "no busy bins (min=$MIN)"; exit 1; fi
S=$(head -1 "$OUT.bins"); E=$(tail -1 "$OUT.bins")
START=$(awk -v s="$S" 'BEGIN{printf "%.3f", s/10.0}'); STOP=$(awk -v e="$E" 'BEGIN{printf "%.3f", (e+1)/10.0}')
NB=$(wc -l < "$OUT.bins")
echo "busy window: ${START}s .. ${STOP}s  ($NB busy 100ms-bins, contiguous span $(awk -v s=$S -v e=$E 'BEGIN{print (e-s+1)/10.0}') s)"
perf report -i "$DATA" --stdio -g none --percent-limit 0 --sort comm,dso,symbol --time "${START},${STOP}" 2>/dev/null > "$OUT"
echo "wrote $OUT ($(grep -c '%' "$OUT") rows)"; grep -m2 -E '^# (Samples|Total)' "$OUT"
