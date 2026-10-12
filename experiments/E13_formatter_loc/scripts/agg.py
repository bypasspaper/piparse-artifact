#!/usr/bin/env python3
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loc import strip_cpp_comments, kind

def rc(spec):
    path, rng = spec.rsplit(':', 1)
    a, b = (int(x) for x in rng.split('-'))
    lines = open(path, errors='replace').read().split('\n')
    if lines and lines[-1] == '': lines.pop()
    b = min(b, len(lines)); a = max(a, 1)
    if kind(path) == 'cpp':
        fl = strip_cpp_comments(lines)
        code = sum(1 for i in range(a-1, b) if fl[i])
    else:
        code = sum(1 for l in lines[a-1:b] if l.strip() and not l.strip().startswith('#'))
    return b - a + 1, code

per = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
rows = []
for line in open(sys.argv[1]):
    line = line.rstrip('\n')
    if not line or line.startswith('#'): continue
    plug, cat, spec, note = line.split('\t')
    r, c = rc(spec)
    per[plug][cat][0] += r; per[plug][cat][1] += c
    rows.append((plug, cat, r, c, spec, note))

if '--detail' in sys.argv:
    for p, cat, r, c, spec, note in rows:
        print(f"{p:16s} {cat}  {r:5d} {c:5d}  {spec:95s} {note}")
    print()
print(f"{'plugin':16s} {'M raw':>7s}{'M code':>7s} {'K raw':>7s}{'K code':>7s} "
      f"{'O raw':>7s}{'O code':>7s} {'B raw':>7s}{'B code':>7s} | {'ALLraw':>7s}{'ALLcode':>8s} | {'ship raw':>9s}{'ship code':>10s}")
for p in per:
    d = per[p]
    g = lambda k, i: d[k][i] if k in d else 0
    tr = sum(g(k, 0) for k in 'MKOB'); tc = sum(g(k, 1) for k in 'MKOB')
    sr = sum(g(k, 0) for k in 'MKO'); sc = sum(g(k, 1) for k in 'MKO')
    print(f"{p:16s} {g('M',0):7d}{g('M',1):7d} {g('K',0):7d}{g('K',1):7d} "
          f"{g('O',0):7d}{g('O',1):7d} {g('B',0):7d}{g('B',1):7d} | {tr:7d}{tc:8d} | {sr:9d}{sc:10d}")
