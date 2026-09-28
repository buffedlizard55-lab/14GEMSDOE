#!/usr/bin/env bash
# Download the GEMS Prize competition data into data/raw/.
#
# VERIFIED 2026-09-28 (see research/knowledge_base.md):
#   * The data tab https://www.drivendata.org/competitions/306/competition-doe-gems/data/
#     redirects to the DrivenData LOGIN page for unauthenticated clients.  There is no
#     anonymous download URL for training_features.tif / labels / sample_submission.tif /
#     1m_DEM_links.csv.  A human with a DrivenData account must fetch them once.
#   * This script therefore does two things:
#       1. verifies what it CAN verify (expected filenames, sizes, sha256 if provided);
#       2. tells you exactly what to fetch by hand and where to put it.
#
# Usage:  bash scripts/download_competition_data.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAW="$REPO_ROOT/data/raw"
mkdir -p "$RAW"

cat <<'EOF'
========================================================================
 GEMS Prize Challenge — competition data placement (manual step required)
========================================================================
The competition data tab requires a DrivenData login (verified: the URL
below redirects to /accounts/login/ for anonymous clients):

  https://www.drivendata.org/competitions/306/competition-doe-gems/data/

Log in with an account that has joined the competition, download these
files, and place them in data/raw/ EXACTLY under these names:

  data/raw/training_features.tif   (multiband GeoTIFF, 19 bands per the
                                    problem description; 3292 x 3730 px,
                                    EPSG:32611, 100 m)
  data/raw/training_labels.tif     (raster labels; vector labels are also
                                    provided — keep those too if present)
  data/raw/sample_submission.tif   (the official template: single-band
                                    float32, the grid of record)
  data/raw/1m_DEM_links.csv        (URL list for the 1 m DEM tiles)

Optional but recommended (anything else the data tab offers: vector
labels, metadata, feature dictionaries) — same folder.

The team's mirrored copies (Dropbox links shared in the project thread)
are equivalent IF their sha256 matches the originals after you download
them on an unrestricted machine.  Dropbox is NOT reachable from the
Arena sandbox (TLS handshake closed, verified 2026-09-28), so fetch them
outside the sandbox if you use the mirrors.

Then run:  python3 scripts/prepare_data.py
========================================================================
EOF

FOUND=0
for f in training_features.tif training_labels.tif sample_submission.tif 1m_DEM_links.csv; do
  if [[ -f "$RAW/$f" ]]; then
    sz=$(stat -c %s "$RAW/$f" 2>/dev/null || stat -f %z "$RAW/$f")
    h=$(sha256sum "$RAW/$f" | cut -d' ' -f1)
    echo "FOUND  $f  bytes=$sz  sha256=$h"
    FOUND=$((FOUND+1))
  else
    echo "MISSING $f"
  fi
done

if [[ "$FOUND" -ge 3 ]]; then
  echo
  echo "Core files present. Next: python3 scripts/prepare_data.py"
  exit 0
else
  echo
  echo "Place the files above into $RAW and re-run this script."
  exit 2
fi
