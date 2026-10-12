#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Decompose from PER-RUN log lines (works on a partially-complete run): pair each
'[N/300] kK/arm ... rep=R' line with the following '-> X MB/s', median over reps, then
the same parse/serialize decomposition as decompose_serde.py."""
import re, sys, statistics as st, math

ROWS, REPEAT = 2_000_000, 20
CSV_SZ = {1:25777108,2:51554041,3:77331899,4:103109490,5:128887182,6:154664216,7:180441578,
          8:206218351,9:231996484,10:257774320,11:283552675,12:309330847,13:335108417,
          14:360885972,15:386663393,16:412440402,17:438218991,18:463996003,19:489774326,20:515552573}
NATIVE = {"no_serde","only_ser"}
bpr = lambda arm,K: K*8 if arm in NATIVE else CSV_SZ[K]/ROWS

def parse(path):
    runs = {}  # (K,arm) -> [mbps,...]
    cur = None
    hdr = re.compile(r"\[\d+/\d+\]\s+k(\d+)/(\w+)\s+x=.*rep=\d+")
    res = re.compile(r"→\s+([\d.]+)\s*MB/s")
    for line in open(path):
        m = hdr.search(line)
        if m: cur = (int(m.group(1)), m.group(2)); continue
        r = res.search(line)
        if r and cur: runs.setdefault(cur, []).append(float(r.group(1)))
    med = {}
    for (K,arm),v in runs.items(): med.setdefault(K,{})[arm] = st.median(v)
    return med

def rows_s(mbps,arm,K): return mbps*1e6/bpr(arm,K)/1e6*REPEAT
def gm(xs): xs=[x for x in xs if x>0]; return math.exp(sum(map(math.log,xs))/len(xs)) if xs else float('nan')

data = parse(sys.argv[1])
print(f"{'K':>2} | {'noSerde':>7} {'deser':>6} {'ser':>6} {'serde':>6} {'naive':>6} "
      f"| {'parse':>5} {'ser':>5} {'/field p/s':>10} {'add?':>6} {'nv/srd':>6}  (Mrows/s ; ns/row)")
print("-"*104)
pser,psx,ppar,ppx=[],[],[],[]
for K in sorted(data):
    d=data[K]
    if len(d)<5: continue
    r={a:rows_s(d[a],a,K) for a in d}; t={a:1e9/(r[a]*1e6) for a in r}
    ser=t["only_ser"]-t["no_serde"]; serx=t["serde"]-t["only_deser"]
    par=t["only_deser"]-t["no_serde"]; parx=t["serde"]-t["only_ser"]
    add=t["no_serde"]+par+ser; supp=100*(t["serde"]/add-1)
    pser.append(ser);psx.append(serx);ppar.append(par);ppx.append(parx)
    print(f"{K:>2} | {r['no_serde']:7.1f} {r['only_deser']:6.2f} {r['only_ser']:6.2f} {r['serde']:6.2f} "
          f"{r['serde_naive']:6.2f} | {par:5.0f} {ser:5.0f}  {par/K:4.1f}/{ser/K:<4.1f} {supp:+5.1f}% "
          f"{t['serde_naive']/t['serde']:5.1f}x")
print("-"*104)
print(f"per-field: parse {gm([p/ (k) for k,p in zip(sorted(data),ppar)]):.1f}ns  "
      f"serialize {gm([s/(k) for k,s in zip(sorted(data),pser)]):.1f}ns")
print(f"serialize ns/row cross-check: native-pair {gm(pser):.0f} vs csv-pair {gm(psx):.0f}")
print(f"parse     ns/row cross-check: Native-out {gm(ppar):.0f} vs JSON-out {gm(ppx):.0f}")
