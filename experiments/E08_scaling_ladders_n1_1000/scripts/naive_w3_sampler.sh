#!/bin/bash
# 5 s sampler for the NES-Naive scaling ladder. The column that matters is worker_threads:
# BlockingFile allocates ONE OS THREAD PER SOURCE, so this is the direct read on the
# thread-per-source risk at N=250/500/1000. fds matter too (ulimit -n 65536 is load-bearing).
OUT=/home/pi/powertest/naive_w3_scale.tsv
echo -e "epoch\tavail_mb\tbuffcache_mb\tworker_rss_mb\tworker_threads\tworker_fds\trunnable\ttemp_c\tthrottled" > "$OUT"
while true; do
  pid=$(pgrep -x main | head -1)
  if [ -n "$pid" ]; then
    rss=$(awk '/^VmRSS:/{print int($2/1024)}' /proc/$pid/status 2>/dev/null)
    thr=$(awk '/^Threads:/{print $2}' /proc/$pid/status 2>/dev/null)
    fds=$(ls /proc/$pid/fd 2>/dev/null | wc -l)
  else
    rss=0; thr=0; fds=0
  fi
  run=$(awk '{print $4}' /proc/loadavg | cut -d/ -f1)
  read -r avail bc < <(free -m | awk '/^Mem:/{print $7, $6}')
  t=$(vcgencmd measure_temp | sed 's/[^0-9.]//g')
  th=$(vcgencmd get_throttled | cut -d= -f2)
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$(date +%s)" "$avail" "$bc" "${rss:-0}" "${thr:-0}" "${fds:-0}" "$run" "$t" "$th" >> "$OUT"
  sleep 5
done
