#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Fetch the datasets that are NOT part of the engine's ExternalData set (the paper-workload file bid_strings_3GB and its
# format twins, bid_1GB) from an anonymous host, verify md5, and place them where pbench expects them.
#
#   DATA_URL=https://<anonymous-host>/<path> NES_BUILD_DIR=<build dir> ./fetch_twins.sh [name ...]
#
# DATA_URL is the base URL that serves the files below by name (e.g. a Hugging Face dataset repository:
# https://huggingface.co/datasets/<account>/<repo>/resolve/main). Files are written to
# $NES_BUILD_DIR/nes-systests/testdata/large/nexmark/ (the directory the query catalog's `large/nexmark/...` entries
# resolve to). ~25 GB in total; each file is skipped when it is already present with the right md5.
set -euo pipefail
DATA_URL="${DATA_URL:-https://huggingface.co/datasets/bypasspaper/bypass-artifact-data/resolve/main}"   # filled with the anonymous data host by scripts/anonymize/push_review_repos.sh (env DATA_URL)
case "$DATA_URL" in *PLACEHOLDER*) echo "DATA_URL is not set: export DATA_URL=<base url of the data host> (see data/README.md §2)"; exit 1;; esac
NES_BUILD_DIR="${NES_BUILD_DIR:-$HOME/work/nebulastream-public/cmake-build-release}"
DEST="$NES_BUILD_DIR/nes-systests/testdata/large/nexmark"
mkdir -p "$DEST"
# name  bytes  md5   (measured 2026-10-12 on the reference copies; see data/README.md §2)
FILES="
bid_strings_3GB.csv  3595281395 0ed6153950e7a16d6c5ead724be37321
bid_strings_3GB.json 5567181395 cd54f09fcc48180edb1765c692014d33
bid_strings_3GB.hl7  5723681395 2f0c9a0b940fe8618b02b4ea09b773d3
bid_strings_3GB.xml  5661081395 f62231cdc727a3938a1b76719b15e0b3
bid_strings_3GB.nes  3443000000 644785e0a090a078580a72a248a651f4
bid_1GB.csv          1089194961 320bc07bed5e114b9bda4bf0eb4333e3
"
want=("$@")
echo "$FILES" | awk 'NF==3' | while read -r name bytes md5; do
  if [ ${#want[@]} -gt 0 ] && ! printf '%s\n' "${want[@]}" | grep -qx "$name"; then continue; fi
  f="$DEST/$name"
  if [ -f "$f" ] && [ "$(stat -c %s "$f")" = "$bytes" ] && [ "$(md5sum "$f" | cut -d' ' -f1)" = "$md5" ]; then
    echo "ok       $name (present, md5 verified)"; continue
  fi
  echo "fetching $name ($bytes bytes) from $DATA_URL/$name"
  curl -fL --retry 5 -C - -o "$f" "$DATA_URL/$name"
  got=$(md5sum "$f" | cut -d' ' -f1)
  [ "$got" = "$md5" ] || { echo "MD5 MISMATCH for $name: $got != $md5"; exit 1; }
  echo "verified $name"
done
echo "done -> $DEST"
