#!/usr/bin/env bash
# Download the GEMS Prize competition data into data/raw/.
#
# TWO possible paths, tried in order:
#   1. TEAM-PROVIDED DROPBOX SHARES — links were supplied in the project brief.
#      The share pages and filenames are reachable, but their provenance as
#      official competition mirrors and the binary contents have NOT been
#      independently verified. A successful download is not authorization or
#      proof of official identity. Verify TIFF metadata/grid against the
#      official DrivenData data tab before using these files for training.
#   2. OFFICIAL DATA-TAB DOWNLOAD — requires a DrivenData account with access;
#      instructions are printed if the shares fail or are not trusted.
#
# SHA256SUMS records the bytes and source URL after download; it proves local
#      integrity from that point forward, not that a shared file is official.
#
# Checked 2026-09-28: anonymous access to the DrivenData data tab is login-gated;
# binary Dropbox downloads are blocked from this sandbox by its TLS policy. The
# file-share pages can be reached by the research fetch tool, but no binary file
# has been downloaded or verified in this checkout.
#
# Usage:  bash scripts/download_competition_data.sh
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$REPO_ROOT/data/raw"
mkdir -p "$RAW"
SUMS="$RAW/SHA256SUMS"

# canonical name | dropbox mirror URL (verbatim from the team thread)
MIRRORS=(
"sample_submission.tif|https://www.dropbox.com/scl/fi/6rgvnuady818ol8yqgis4/example_submission.tif?rlkey=kbykilvau066xuogoosbf4cq8&st=8junzdyw&dl=1"
"training_labels.tif|https://www.dropbox.com/scl/fi/t7fyt03qdh9egyme0itwo/existing_faults.tif?rlkey=yiao96uluqdkipf0h5vju71jf&st=rnino7ya&dl=1"
"training_features.tif|https://www.dropbox.com/scl/fi/3vz9o0wwavi26xaeoxlwr/gems-geodawn-numerical-features.tif?rlkey=je8d8fepqfbst9lnwsq9rkplu&st=zj1lag1r&dl=1"
"1m_DEM_links.pdf|https://www.dropbox.com/scl/fi/ig0mban712ns1atphgphe/Digital-elevation-model-links-JSON.pdf?rlkey=zm77f1vbtt2if8hlruymptnu3&st=srhhir10&dl=1"
"GEMS_96647_rules.pdf|https://www.dropbox.com/scl/fi/aemhtutjgcp6tr3tint94/GEMS_96647.pdf?rlkey=rek210cj2smnmzb8n0sla1vmd&st=wz4kofki&dl=1"
)

record_sha() { # file url
  local h base
  h=$(sha256sum "$1" | cut -d' ' -f1)
  base=$(basename "$1")
  if [[ -f "$SUMS" ]]; then
    awk -v name="$base" '$2 != name' "$SUMS" > "$SUMS.tmp"
  else
    : > "$SUMS.tmp"
  fi
  printf '%s  %s  %s\n' "$h" "$base" "$2" >> "$SUMS.tmp"
  mv "$SUMS.tmp" "$SUMS"
  echo "  sha256=$h  (recorded in SHA256SUMS; source identity still unverified)"
}

fetch_mirror() { # url out
  curl -fSL --max-time 1800 --retry 2 -o "$2" "$1"
}

NEED_MANUAL=0
for row in "${MIRRORS[@]}"; do
  name="${row%%|*}"; url="${row#*|}"
  if [[ -s "$RAW/$name" ]]; then
    h=$(sha256sum "$RAW/$name" | cut -d' ' -f1)
    echo "PRESENT $name  bytes=$(stat -c %s "$RAW/$name")  sha256=$h"
    continue
  fi
  echo "FETCH   $name  <- team-provided Dropbox share (unverified source)"
  if fetch_mirror "$url" "$RAW/$name"; then
    record_sha "$RAW/$name" "$url"
  else
    echo "  mirror unreachable from this machine (TLS allowlist? offline?)"
    rm -f "$RAW/$name"
    NEED_MANUAL=1
  fi
done

# TIF sanity: every .tif in data/raw must start with the TIFF magic
for f in "$RAW"/*.tif; do
  [[ -e "$f" ]] || continue
  magic=$(head -c 4 "$f" | od -An -tx1 | tr -d ' \n')
  case "$magic" in
    49492a00|4d4d002a) echo "TIF-OK  $(basename "$f") (magic $magic)" ;;
    *) echo "TIF-BAD $(basename "$f") (magic $magic) — not a TIFF; deleting"
       rm -f "$f"; NEED_MANUAL=1 ;;
  esac
done

cat <<'EOF'

------------------------------------------------------------------------
If mirrors failed, place the files by hand (needs a DrivenData account):
  data tab: https://www.drivendata.org/competitions/306/competition-doe-gems/data/
  data/raw/training_features.tif   19-band GeoTIFF (3292 x 3730, EPSG:32611, 100 m)
  data/raw/training_labels.tif     fault labels raster
  data/raw/sample_submission.tif   official template (grid of record)
  data/raw/1m_DEM_links.csv        1 m DEM tile URL list
then run:  python3 scripts/prepare_data.py
------------------------------------------------------------------------
EOF

if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY' || NEED_MANUAL=1
import os, sys
raw = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
core = ["sample_submission.tif", "training_labels.tif", "training_features.tif"]
missing = [f for f in core if not os.path.exists(os.path.join(raw, f))]
status = ", ".join(f + (" OK" if f not in missing else " MISSING") for f in core)
print("core files:", status)
sys.exit(1 if missing else 0)
PY
fi

exit $NEED_MANUAL
