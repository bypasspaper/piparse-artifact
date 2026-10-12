# Data

Every dataset the paper's experiments read, how it comes to exist, and its checksum. Paths are relative to the
engine build tree's test-data directory `<build>/nes-systests/testdata/large/` (pbench resolves `file:` entries of
the query catalog against it; synthetic files live in the gitignored source-tree directory
`nes-systests/testdata/large/formatter/` and are symlinked into the build tree).

## 1. Public datasets (fetched: `./fetch_testdata.sh`)

CMake ExternalData, `.md5` stubs in the engine tree, server `DATA-HOST.example` (see the script header).

| file | bytes | rows | role |
| --- | --- | --- | --- |
| `nexmark/bid_6GB.csv` | 6,678,514,674 | 183,991,721 | NEXMark bid stream, 4 numeric fields `ts,auctionId,bidder,price`; parent of `bid_1GB` |
| `nexmark/bid_653M.csv` | 666,738,765 | 18,106,394 | 5-field bid variant (`small` size of `nexmark/bid_star`); the getting-started smoke test |
| `nexmark/person_840MB.csv` | 876,941,057 | 4,000,000 | NEXMark persons (varsized-heavy; q8 join, robustness twins) |
| `nexmark/auction_707MB.csv` | 729,852,154 | — | NEXMark auctions (q8 join) |
| `ysb/ysb_10k_data_479M.csv` | 497,209,125 | 5,000,000 | Yahoo Streaming Benchmark (stateful tier) |
| `cluster_monitoring/google-cluster-data-original_1G.csv` | 1,527,761,977 | — | Google cluster monitoring (cm_q2, stateful tier) |

md5 (measured 2026-10-12 on the Threadripper copies): person `e57c35d04194779cf2372ede06b2056b`,
auction `0afc101cff43022e292bbbb375f07285`, ysb_10k `57f10923ac30c02dbf06ea5982c34c9a`,
cluster `1543213c4f95ade501aee5b931d92c44`. (`bid_6GB` and `bid_653M` are addressed by their ExternalData md5
stubs in the engine tree.)

## 2. The paper workload dataset `bid_strings_3GB` and its format twins (derived; fetched: `./fetch_twins.sh`)

These files are **not** on the engine's ExternalData server. They are served from a separate, anonymous data host
(author decision 2026-10-12: the engine's the authors' university share is public NebulaStream infrastructure and stays, but nothing
submission-specific may be hosted there). `DATA_URL=<base url> ./fetch_twins.sh` downloads the six files below by
name into the build tree and verifies the md5s listed here. Base URL of the review copy: `https://huggingface.co/datasets/bypasspaper/bypass-artifact-data/resolve/main`
(filled by `scripts/anonymize/push_review_repos.sh` from its `DATA_URL` environment variable, see `../README.md` §5).

`bid_strings_3GB.csv` is the first **31,300,000 rows** of the NEXMark bid stream *with the two string columns
kept*: `ts UINT64, auctionId INT32, bidder INT32, price FLOAT64, channel VARSIZED, url VARSIZED` (channel ∈
{apple, google, facebook, baidu, …}, url = the NEXMark generator's `https://www.nexmark.com/…/item.htm?query=1&
channel_id=N` pattern, 71 chars). Its first rows are byte-identical to `bid_6GB.csv` except for the two appended
string columns, i.e. both files are projections of the same generator output. **Gap:** the exact generator
invocation that produced the six-field file (2026-07-13) was not recorded in the notes; the file itself is the
reference (md5 below) and should be published with the artifact (3.6 GB). `bid_1GB.csv` =
`head -n 31300000 nexmark/bid_6GB.csv` (the 4-field twin of the same 31.3 M rows).

The four twins carry the same logical rows (checksum anchor **31300000 rows / 269477267979** reproduced by every
input formatter — `checksum_gates/`):

| file | bytes | B/row | produced by |
| --- | --- | --- | --- |
| `nexmark/bid_strings_3GB.csv` | 3,595,281,395 | 114.87 | reference (see above) |
| `nexmark/bid_strings_3GB.json` | 5,567,181,395 | 177.9 | NDJSON, uppercase keys; `csv_to_ndjson.py` (session scratch 2026-07-22, **not preserved** — any csv→ndjson row transform with keys `TIMESTAMP,AUCTIONID,BIDDER,PRICE,CHANNEL,URL` reproduces it; gate = the SchemaJSON checksum) |
| `nexmark/bid_strings_3GB.hl7` | 5,723,681,395 | 182.9 | `converters/hl7/convert_csv_to_hl7.sh <build> converters/hl7/bid_strings_to_hl7.yaml <out> 31300000` — the engine's own HL7 output formatter is the generator (MLLP FS-CR trailer framing) |
| `nexmark/bid_strings_3GB.xml` | 5,661,081,395 | 180.9 | `converters/xml/convert_csv_to_xml.py bid_strings_3GB.csv bid_strings_3GB.xml --tags ts,aid,bid,pr,ch,url` (packed record-per-line XML, parsed by the HL7 indexer by configuration) |
| `nexmark/bid_strings_3GB.nes` | 3,443,000,000 | 110 | `generators/csv_to_binary.py` (packed little-endian native rows; VARSIZED as length-prefixed, `string_length "13,73"`) |
| `nexmark/bid_1GB.csv` | 1,089,194,961 | 34.8 | `head -n 31300000 bid_6GB.csv` |
| `nexmark/bid_1GB.nes` | 751,200,000 | 24 | `csv_to_binary.py` of bid_1GB (uint64,int32,int32,float64) |

md5: csv `0ed6153950e7a16d6c5ead724be37321`, json `cd54f09fcc48180edb1765c692014d33`, hl7
`2f0c9a0b940fe8618b02b4ea09b773d3`, xml `f62231cdc727a3938a1b76719b15e0b3`, nes `644785e0a090a078580a72a248a651f4`,
bid_1GB.csv `320bc07bed5e114b9bda4bf0eb4333e3`.

## 3. Synthetic datasets (generated: `generators/`)

| file(s) | bytes | generator | used by |
| --- | --- | --- | --- |
| `formatter/bigstr_id_{4,8,12,16,40,80,160,320,640}k_500m.csv` | ~524 M each | `gen_bigstr_id.py <N>` (rows `<id>,<N × 'x'>`) | E03 shredder spanning sweeps (figW = 12k) |
| `formatter/bidstr_url12k_500m.csv` | 524,279,918 (43,546 rows) | `gen_bidstr_url12k.py <bid_strings_3GB.csv> <out> 12000` (url padded to 12,000 chars) | E03 q_ex twin of figW |
| `formatter/bench_5xUINT64_512m.csv` (+ `.nes`) | 536,880,336 | `gen_formatter_csv.py <out> --target-mb 512` (5 × UINT64 `creationTS,key,v1,v2,v3`); `.nes` via `csv_to_binary.py --schema uint64,uint64,uint64,uint64,uint64` | E12 thread-structure rig, isolated formatter-scaling-benchmark |
| `formatter/bench_5xUINT64_5g.csv` | 5,368,801,906 | same, `--target-mb 5120` | isolated sweeps |
| `multicol/nf{1..10}.csv` (+ `_x10` = file concatenated 10×) | ~200 M / ~2 G | `gen_float_csv.py` (N FLOAT64 columns) | E09 Fig2 all-fields / proj1 sweeps |
| `multicol/nm{1..10}.csv` (+ `_x10`) | ~200 M / ~2 G | mixed rows: INT32 predicate column + FLOAT64 payload — see `../experiments/E09_teaser_fig1_fig2/README.md` for the generator | E09 Fig2 predicate sweep |
| `multicol/n{1,2,4,8,16,32}_w{1..20}.csv`, `f16.csv`, `mixed_n16.csv`, `bid_250M.csv` | ~210 M | width/field sweeps (`gen_widthsweep.c`, see E10/E09 READMEs) | isolated field-scaling, serde micro |

md5 (TR copies): bench_5xUINT64_512m.csv `c8c078300619ec8b29a41cbc3d10bafb`, bidstr_url12k_500m.csv
`cea6eee930a340501b1698133875ca6f`, bigstr_id_12k_500m.csv `3094a1f72c0054d54d0442e359e2d891`.

## 4. Checksum gates (`checksum_gates/`)

pbench experiments that run every workload query through every input formatter (compiled and uncompiled, CSV /
SchemaJSON / HL7 / XML) and compare the sink's `(rows, value checksum)` against the anchor
`31300000,269477267979` (robustness twins: ysb `5000000,25115005162`, person `4000000,83746084707`). Run them
before benchmarking a freshly generated twin:

```
cd $PBENCH_DIR && uv run python bench.py run <this dir>/checksum_gates/bid_seq_hl7_gate.yaml --build-dir $NES_BUILD_DIR --worker-port 9099
```

`PAPER_WORKLOAD.md` is the frozen definition of the 10 stateless + 3 stateful queries (SQL shapes, rung
definitions, HOSP readings) that every experiment references.
