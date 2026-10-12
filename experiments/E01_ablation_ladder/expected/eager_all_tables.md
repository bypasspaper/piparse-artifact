## Today's medians (MB/s, W1, n=3) and rep spread
| query | r2_uncompiled | r3_compiled | r3_eager | r3_eager_fast | r3_eager_all | spread max % |
|---|---|---|---|---|---|---|
| q0 | 309 | 1323 | 680 | 669 | 625 | 2.6 |
| qproject | 715 | 3950 | 1657 | 1486 | 1289 | 1.0 |
| qroute | 618 | 3713 | 1570 | 1480 | 1318 | 1.0 |
| q1 | 619 | 1569 | 1141 | 1099 | 966 | 3.2 |
| q2og | 903 | 2302 | 2600 | 2190 | 1781 | 4.4 |
| q2mod | 896 | 4815 | 2601 | 2178 | 1783 | 1.0 |
| q10 | 459 | 1296 | 918 | 857 | 779 | 2.2 |
| q14 | 797 | 2168 | 2015 | 1766 | 1478 | 1.0 |
| q22 | 456 | 1304 | 915 | 851 | 807 | 0.7 |
| qex | 842 | 2507 | 2287 | 2113 | 1777 | 0.7 |

## Anchors vs v7 (today / v7)
| query | r2 | r3 | r3_eager (v7 split, projected) |
|---|---|---|---|
| q0 | 0.99 | 1.00 | – |
| qproject | 1.01 | 1.00 | – |
| qroute | 1.01 | 1.01 | – |
| q1 | 1.01 | 1.00 | – |
| q2og | 1.02 | 1.00 | – |
| q2mod | 1.01 | 1.01 | – |
| q10 | 1.01 | 1.01 | – |
| q14 | 1.01 | 0.99 | – |
| q22 | 1.01 | 1.03 | – |
| qex | 1.01 | 1.00 | – |

## Factor decomposition of the compile bar (today's same-session ratios)
| query | r3/r2 (old compile bar) | **compilation** r3_eager_all/r2 | strings r3_eager_fast/r3_eager_all | numerics r3_eager/r3_eager_fast | **pushdown total** r3_eager/r3_eager_all | lazy+passthrough r3/r3_eager | ns/row r2 | ns/row r3_eager_all |
|---|---|---|---|---|---|---|---|---|
| q0 | 4.28 | **2.02** | 1.07 | 1.02 | **1.09** | 1.95 | 371 | 184 |
| qproject | 5.53 | **1.80** | 1.15 | 1.11 | **1.29** | 2.38 | 161 | 89 |
| qroute | 6.00 | **2.13** | 1.12 | 1.06 | **1.19** | 2.37 | 186 | 87 |
| q1 | 2.54 | **1.56** | 1.14 | 1.04 | **1.18** | 1.38 | 186 | 119 |
| q2og | 2.55 | **1.97** | 1.23 | 1.19 | **1.46** | 0.89 | 127 | 65 |
| q2mod | 5.37 | **1.99** | 1.22 | 1.19 | **1.46** | 1.85 | 128 | 64 |
| q10 | 2.83 | **1.70** | 1.10 | 1.07 | **1.18** | 1.41 | 250 | 147 |
| q14 | 2.72 | **1.85** | 1.19 | 1.14 | **1.36** | 1.08 | 144 | 78 |
| q22 | 2.86 | **1.77** | 1.06 | 1.08 | **1.13** | 1.42 | 252 | 142 |
| qex | 2.98 | **2.11** | 1.19 | 1.08 | **1.29** | 1.10 | 136 | 65 |
| **geomean** | 3.55 | **1.88** | 1.15 | 1.10 | **1.26** | 1.50 | | |

## v7-footing projection (r3_v7 × today's ratios): the parse-all rung as it would sit in the published ladder
| query | r2_v7 | r3_eager_all_v7 | r3_eager_fast_v7 | r3_eager_v7 | r3_v7 |
|---|---|---|---|---|---|
| q0 | 314 | 625 | 669 | 680 | 1323 |
| qproject | 707 | 1286 | 1483 | 1653 | 3941 |
| qroute | 611 | 1308 | 1469 | 1559 | 3687 |
| q1 | 611 | 963 | 1095 | 1137 | 1563 |
| q2og | 889 | 1779 | 2187 | 2597 | 2299 |
| q2mod | 885 | 1766 | 2157 | 2575 | 4768 |
| q10 | 455 | 770 | 847 | 907 | 1281 |
| q14 | 790 | 1490 | 1780 | 2031 | 2185 |
| q22 | 453 | 781 | 824 | 886 | 1262 |
| qex | 830 | 1772 | 2107 | 2280 | 2500 |

wrote /home/user/Notes/nebulastream/benchmark/2_engine_to_e2e/ablation_eager_irdump_2026-10-05/data/eager_all_decomposition.csv
