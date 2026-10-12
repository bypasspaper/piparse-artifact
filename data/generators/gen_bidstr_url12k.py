# SPDX-License-Identifier: Apache-2.0
"""Pad the url field of bid_strings_3GB.csv rows to PAD chars -> ~3-buffer spanning rows at 4 KiB.
Mirrors bigstr_id_12k_500m.csv (12,003 B/row, 500 MiB) but keeps the full 6-field bid schema so q_ex runs unchanged."""
import sys
src, dst, pad, total = sys.argv[1], sys.argv[2], int(sys.argv[3]), 500 * 1024 * 1024
rows = written = 0
with open(src, "rb") as f, open(dst, "wb") as out:
    for line in f:
        line = line.rstrip(b"\n")
        fields = line.split(b",")
        assert len(fields) == 6, fields
        url = fields[5]
        assert len(url) <= pad
        fields[5] = url + b"x" * (pad - len(url))
        row = b",".join(fields) + b"\n"
        if written + len(row) > total:
            break
        out.write(row); written += len(row); rows += 1
print(f"rows={rows} bytes={written} bytes_per_row={written/rows:.1f} spans@4096={written/rows/4096:.2f}")
