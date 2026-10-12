#!/usr/bin/env python3
"""Count raw + code lines for FILE:START-END ranges (1-based, inclusive).
Code = non-blank, non-comment (C++ // /* */ ; '#' for CMake). Block-comment
state is primed by scanning the file from line 1, so ranges are accurate.
Usage: range.py LABEL FILE:START-END [FILE:START-END ...]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from loc import strip_cpp_comments, kind

def main():
    label = sys.argv[1]
    tr = tc = 0
    for spec in sys.argv[2:]:
        path, rng = spec.rsplit(':', 1)
        a, b = (int(x) for x in rng.split('-'))
        lines = open(path, errors='replace').read().split('\n')
        if lines and lines[-1] == '':
            lines.pop()
        b = min(b, len(lines))
        k = kind(path)
        if k == 'cpp':
            flags = strip_cpp_comments(lines)
            code = sum(1 for i in range(a - 1, b) if flags[i])
        else:
            code = sum(1 for ln in lines[a-1:b]
                       if ln.strip() and not ln.strip().startswith('#'))
        raw = b - a + 1
        tr += raw; tc += code
        print(f"  {raw:5d} raw {code:5d} code   {spec}")
    print(f"  {tr:5d} raw {tc:5d} code   == {label}")

main()
