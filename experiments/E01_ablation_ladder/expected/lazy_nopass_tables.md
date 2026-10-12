## Medians (MB/s, W1, n=3) + rep spread; anchors vs the afternoon session and v7
| query | r3_eager_all | r3_lazy_nopass | r3_compiled | spread max % | eager_all now/prev | r3 now/prev | r3 now/v7 |
|---|---|---|---|---|---|---|---|
| q0 | 619 | 935 | 1320 | 3.6 | 0.99 | 1.00 | 1.00 |
| qproject | 1285 | 2125 | 3933 | 1.8 | 1.00 | 1.00 | 1.00 |
| qroute | 1313 | 3052 | 3693 | 0.5 | 1.00 | 0.99 | 1.00 |
| q1 | 968 | 1129 | 1567 | 1.4 | 1.00 | 1.00 | 1.00 |
| q2og | 1787 | 2295 | 2285 | 0.8 | 1.00 | 0.99 | 0.99 |
| q2mod | 1775 | 4688 | 4818 | 3.5 | 1.00 | 1.00 | 1.01 |
| q10 | 779 | 900 | 1297 | 3.5 | 1.00 | 1.00 | 1.01 |
| q14 | 1477 | 1948 | 2161 | 0.6 | 1.00 | 1.00 | 0.99 |
| q22 | 807 | 898 | 1303 | 0.7 | 1.00 | 1.00 | 1.03 |
| qex | 1764 | 2528 | 2504 | 0.8 | 0.99 | 1.00 | 1.00 |

## Laziness split (same session) and the full compile-bar chain
| query | **lazy code gen** nopass/eager_all | **passthrough** r3/nopass | product r3/eager_all | compilation r2→eager_all (afternoon) | old bar r3/r2 (afternoon) | chain product | ns/row eager_all | ns/row nopass | ns/row r3 |
|---|---|---|---|---|---|---|---|---|---|
| q0 | **1.51** | **1.41** | 2.13 | 2.02 | 4.28 | 4.31 | 186 | 123 | 87 |
| qproject | **1.65** | **1.85** | 3.06 | 1.80 | 5.53 | 5.52 | 89 | 54 | 29 |
| qroute | **2.32** | **1.21** | 2.81 | 2.13 | 6.00 | 5.99 | 87 | 38 | 31 |
| q1 | **1.17** | **1.39** | 1.62 | 1.56 | 2.54 | 2.53 | 119 | 102 | 73 |
| q2og | **1.28** | **1.00** | 1.28 | 1.97 | 2.55 | 2.52 | 64 | 50 | 50 |
| q2mod | **2.64** | **1.03** | 2.71 | 1.99 | 5.37 | 5.40 | 65 | 25 | 24 |
| q10 | **1.15** | **1.44** | 1.66 | 1.70 | 2.83 | 2.83 | 147 | 128 | 89 |
| q14 | **1.32** | **1.11** | 1.46 | 1.85 | 2.72 | 2.71 | 78 | 59 | 53 |
| q22 | **1.11** | **1.45** | 1.62 | 1.77 | 2.86 | 2.85 | 142 | 128 | 88 |
| qex | **1.43** | **0.99** | 1.42 | 2.11 | 2.98 | 3.00 | 65 | 45 | 46 |
| **geomean** | **1.50** | **1.26** | 1.89 | 1.88 | 3.55 | 3.55 | | | |

## v7-footing projection of the new rung (r3_v7 × nopass/r3 today)
| query | r2_v7 | r3_eager_all_v7 (afternoon proj.) | r3_lazy_nopass_v7 | r3_v7 |
|---|---|---|---|---|
| q0 | 314 | 625 | 937 | 1323 |
| qproject | 707 | 1286 | 2129 | 3941 |
| qroute | 611 | 1308 | 3047 | 3687 |
| q1 | 611 | 963 | 1127 | 1563 |
| q2og | 889 | 1779 | 2309 | 2299 |
| q2mod | 885 | 1766 | 4639 | 4768 |
| q10 | 455 | 770 | 888 | 1281 |
| q14 | 790 | 1490 | 1971 | 2185 |
| q22 | 453 | 781 | 870 | 1262 |
| qex | 830 | 1772 | 2524 | 2500 |

wrote /home/user/Notes/nebulastream/benchmark/2_engine_to_e2e/ablation_eager_irdump_2026-10-05/data/lazy_nopass_decomposition.csv
