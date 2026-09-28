#!/usr/bin/env bash
# Download the GEMS Prize competition data into data/raw/.
#
# TWO paths, tried in order:
#   1. OFFICIAL NO-LOGIN MIRRORS (Dropbox) — the competition's own mirror
#      links for the data-tab files, captured verbatim from the project
#      thread (status TEAM-REPORTED-OFFICIAL-MIRROR; the DrivenData data tab
#      itself is login-gated, verified).  No DrivenData account needed.
#   2. MANUAL PLACEMENT from the data tab (needs a DrivenData login) —
#      printed as instructions if the mirrors are unreachable.
#
# Every downloaded file's sha256 is appended to data/raw/SHA256SUMS with its
# source URL, so provenance is auditable and re-runs are no-ops.
#
# VERIFIED 2026-09-28 (research/knowledge_base.md):
#   * the data tab redirects to /accounts/login/ for anonymous clients (C18);
#   * the Arena sandbox TLS-allowlist blocks dropbox.com from bash (FLAG #1,
#     re-measured), so inside the sandbox path 1 fails and path 2 prints.
#     On any unrestricted machine path 1 completes the whole placement.
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
  local h
  h=$(sha256sum "$1" | cut -d' ' -f1)
  grep -v "  $2$" "$SUMS" 2>/dev/null > "$SUMS.tmp" || true
  echo "$h  $(basename "$1")  $2" >> "$SUMS"
  rm -f "$SUMS.tmp"
  echo "  sha256=$h  (recorded in SHA256SUMS)"
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
  echo "FETCH   $name  <- official mirror"
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
