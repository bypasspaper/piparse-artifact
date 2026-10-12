#!/usr/bin/env python3
"""LOC counter for NebulaStream formatter LOC study (2026-10-07).

Per file emits three numbers:
  raw   : every line in the file
  code  : non-blank, non-comment lines (C++: // /// /* */ ; CMake/py/yaml: #)
  nolic : raw minus the Apache-2.0 license preamble block (and one blank
          line following it), i.e. "what the author actually typed"

Usage: loc.py [--tsv] FILE...
"""
import sys, os

CPP = {'.hpp', '.cpp', '.h', '.cc', '.inc', '.in'}
HASH = {'.txt', '.cmake', '.py', '.yaml', '.yml', '.sh', '.test'}


def kind(path):
    base = os.path.basename(path)
    if base == 'CMakeLists.txt':
        return 'hash'
    ext = os.path.splitext(path)[1]
    if path.endswith('.inc.in'):
        return 'cpp'
    if ext in CPP:
        return 'cpp'
    if ext in HASH:
        return 'hash'
    return 'hash'


def strip_cpp_comments(lines):
    """Return list of booleans: True if the line has code outside comments."""
    out = []
    in_block = False
    for ln in lines:
        has_code = False
        i = 0
        n = len(ln)
        while i < n:
            if in_block:
                j = ln.find('*/', i)
                if j < 0:
                    i = n
                else:
                    in_block = False
                    i = j + 2
                continue
            c = ln[i]
            if c == '/' and i + 1 < n and ln[i + 1] == '/':
                break  # rest of line is comment
            if c == '/' and i + 1 < n and ln[i + 1] == '*':
                in_block = True
                i += 2
                continue
            if c in ('"', "'"):
                has_code = True
                q = c
                i += 1
                while i < n:
                    if ln[i] == '\\':
                        i += 2
                        continue
                    if ln[i] == q:
                        i += 1
                        break
                    i += 1
                continue
            if not c.isspace():
                has_code = True
            i += 1
        out.append(has_code)
    return out


def license_span(lines, k):
    """Number of leading lines occupied by the Apache preamble (+1 blank)."""
    head = '\n'.join(lines[:20])
    if 'Licensed under the Apache License' not in head:
        return 0
    if k == 'cpp':
        # leading /* ... */ block
        start = None
        for i, ln in enumerate(lines[:5]):
            if ln.strip().startswith('/*'):
                start = i
                break
        if start is None:
            return 0
        for i in range(start, min(len(lines), 40)):
            if '*/' in lines[i]:
                end = i
                break
        else:
            return 0
        span = end + 1
    else:
        # leading run of '#'-comment / blank lines up to 'limitations under'
        end = None
        for i, ln in enumerate(lines[:40]):
            if 'limitations under the License' in ln:
                end = i
                break
        if end is None:
            return 0
        span = end + 1
    if span < len(lines) and lines[span].strip() == '':
        span += 1
    return span


def count(path):
    with open(path, 'r', errors='replace') as f:
        text = f.read()
    lines = text.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    raw = len(lines)
    k = kind(path)
    if k == 'cpp':
        flags = strip_cpp_comments(lines)
        code = sum(1 for i, ln in enumerate(lines) if flags[i])
    else:
        code = sum(1 for ln in lines
                   if ln.strip() and not ln.strip().startswith('#'))
    lic = license_span(lines, k)
    return raw, code, raw - lic, lic


def main():
    tsv = '--tsv' in sys.argv
    files = [a for a in sys.argv[1:] if not a.startswith('--')]
    tr = tc = tn = 0
    for p in files:
        r, c, nl, lic = count(p)
        tr += r; tc += c; tn += nl
        if tsv:
            print(f"{p}\t{r}\t{c}\t{nl}\t{lic}")
        else:
            print(f"{r:6d} {c:6d} {nl:6d}  (lic {lic:2d})  {p}")
    if len(files) > 1:
        if tsv:
            print(f"TOTAL\t{tr}\t{tc}\t{tn}\t")
        else:
            print(f"{tr:6d} {tc:6d} {tn:6d}  TOTAL ({len(files)} files)")


if __name__ == '__main__':
    main()
