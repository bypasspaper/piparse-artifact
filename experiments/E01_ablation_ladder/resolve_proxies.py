# SPDX-License-Identifier: Apache-2.0
"""Resolve nautilus proxy-call addresses in a dumped post-opt .ll against the worker's symbol table.
PIE: base is 0x1000-aligned, so (addr & 0xfff) == (sym & 0xfff) for the true match; pick the base that resolves
the most addresses to function starts. Prints per-proxy call counts."""
import re, sys, collections
ll, syms = sys.argv[1], sys.argv[2]
text = open(ll).read()
decl = re.findall(r'^declare .*?@"(0x[0-9a-f]+)"', text, re.M)
calls = collections.Counter(re.findall(r'call [^@\n]*@"(0x[0-9a-f]+)"', text))
addrs = sorted(int(a, 16) for a in decl)
S = {}
for line in open(syms):
    p = line.rstrip("\n").split(" ", 2)
    if len(p) < 3: continue
    S[int(p[0], 16)] = p[2]
by_low = collections.defaultdict(list)
for s in S: by_low[s & 0xfff].append(s)
# candidate bases from the first address
best = (0, None)
for s in by_low[addrs[0] & 0xfff]:
    base = addrs[0] - s
    if base <= 0: continue
    hits = sum(1 for a in addrs if (a - base) in S)
    if hits > best[0]: best = (hits, base)
hits, base = best
print(f"base=0x{base:x} resolved {hits}/{len(addrs)}")
for a in addrs:
    name = S.get(a - base, "???")
    name = name[:170]
    print(f"{calls.get(f'0x{a:x}', 0):3d} calls  0x{a:x}  {name}")
