import csv, glob, re, statistics as st
from collections import defaultdict
rows=list(csv.DictReader(open('probe_trough_tr.csv')))
# the rig writes arm=dpp for all three tags; order of the CSV = order of the runs (ring16 x5, ring8 x5, ring32 x5)
tags=['ring16']*5+['ring8']*5+['ring32']*5
print("tag\tN\tGB/s\tp50ms\tp99ms\tcpu_s/GB")
for t,r in zip(tags,rows):
    print(f"{t}\t{r['N']}\t{float(r['GBps']):.1f}\t{float(r['p50_us'])/1e3:.2f}\t{float(r['p99_us'])/1e3:.2f}\t{float(r['cpu_s_per_GB']):.3f}")
print("\nperf fill sources (DPP, ring16), fills per KiB parsed:")
bytesN={r['N']:float(r['bytes']) for t,r in zip(tags,rows) if t=='ring16'}
srcs=['lcl_l2','int_cache','ext_cache_local','ext_cache_remote','mem_io_local','mem_io_remote']
print("N\t"+"\t".join(srcs)+"\tdram+remote share")
for f in sorted(glob.glob('logs/probe_trough_perf_ring16_N*.txt'), key=lambda x:int(re.search(r'N(\d+)',x).group(1))):
    n=re.search(r'N(\d+)',f).group(1); v={}
    for line in open(f):
        parts=line.strip().split(',')
        if len(parts)>2 and 'ls_dmnd_fills_from_sys' in parts[2]:
            try: v[parts[2].split('.')[1]]=float(parts[0])
            except ValueError: v[parts[2].split('.')[1]]=float('nan')
    # perf counts the whole run (warmup + window); bytes is window-only -> per-KiB figures are relative across N, not absolute
    kib=bytesN.get(n,float('nan'))/1024
    tot=sum(v.get(k,0) for k in srcs)
    print(n+"\t"+"\t".join(f"{v.get(k,float('nan'))/kib:.2f}" for k in srcs)+f"\t{(v.get('ext_cache_remote',0)+v.get('mem_io_local',0)+v.get('mem_io_remote',0))/tot*100:.0f}% (ext_remote {v.get('ext_cache_remote',0)/tot*100:.0f}%, dram {(v.get('mem_io_local',0)+v.get('mem_io_remote',0))/tot*100:.0f}%)")
