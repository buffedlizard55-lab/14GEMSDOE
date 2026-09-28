#!/usr/bin/env bash
# Download the free, official EXTERNAL datasets that back the hypothesis set.
#
# Every URL in this script was verified reachable and correct on 2026-09-28 by
# reading the official source pages (research/knowledge_base.md, entries E1-E12).
# The Arena sandbox blocks direct binary downloads (TLS), so run this script on
# any unrestricted machine; it writes into data/external/ and records sha256.
#
# Primary source: INGENIOUS Great Basin Regional Dataset Compilation,
#   https://gdr.openei.org/submissions/1391
#   DOI 10.15121/1881483  ·  CC BY 4.0  ·  ~117 MB across 9 files
# This is ALSO the source of the competition's own training labels
# (official rules, section 3.3 footnote 4: Ayling, Faulds, et al. 2022).
#
# Usage:  bash scripts/download_external_data.sh [subset]
#   subset = all (default) | core | faults | thermal
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT="$REPO_ROOT/data/external"
mkdir -p "$EXT"
SUBSET="${1:-all}"

# --- direct-download files from the GDR submission 1391 ---------------------
declare -A URLS=(
  # core structural + label layers
  [qfaults_ingenious_nad83conus117_2023-06-27.zip]="https://gdr.openei.org/files/1391/qfaults_ingenious_nad83conus117_2023-06-27.zip"
  [faults_quaternary_INGENIOUS_regional_data.zip]="https://gdr.openei.org/files/1391/faults_quaternary_INGENIOUS_regional_data.zip"
  [great_basin_q_volcanics.zip]="https://gdr.openei.org/files/1391/great_basin_q_volcanics.zip"
  [study_area_boundary_INGENIOUS_regional_data.zip]="https://gdr.openei.org/files/1391/study_area_boundary_INGENIOUS_regional_data.zip"
  [geodetics_INGENIOUS_regional_data.zip]="https://gdr.openei.org/files/1391/geodetics_INGENIOUS_regional_data.zip"
  [seismicity_INGENIOUS_regional_data.zip]="https://gdr.openei.org/files/1391/seismicity_INGENIOUS_regional_data.zip"
  # thermal / hydrogeochemical expression layers
  [paleo_geothermal_regional.zip]="https://gdr.openei.org/files/1391/paleo_geothermal_regional.zip"
  [2m_temperature_probe_INGENIOUS_regional_data.zip]="https://gdr.openei.org/files/1391/2m_temperature_probe_INGENIOUS_regional_data.zip"
  [wellspringdata.gdb.zip]="https://gdr.openei.org/files/1391/wellspringdata.gdb.zip"
)

# --- DOI landing pages (browse/download manually; each is a USGS ScienceBase
#     data release with its own file list) ------------------------------------
cat <<'EOF'
DOI-managed data releases (open in a browser on the unrestricted machine;
ScienceBase 'Download all' or per-file):

  Slip & dilation tendency of Quaternary faults  https://doi.org/10.5066/P9YL58W6
  Heat flow maps (Great Basin)                   https://doi.org/10.5066/P9BZPVUC
  Electrical conductance maps (MT)               https://doi.org/10.5066/P9TWT2LU
  Gravity & magnetics regional maps              https://doi.org/10.5066/P9Z6SA1Z
  Elevation trend & detrended elevation          https://doi.org/10.5066/P9MQRCBY
  GeoDAWN airborne surveys (feature provenance)  https://doi.org/10.5066/P93LGLVQ
EOF

want() {
  case "$SUBSET" in
    all) return 0 ;;
    core) case "$1" in qfaults*|faults_quaternary*|great_basin_q_volcanics*|study_area*) return 0 ;; *) return 1 ;; esac ;;
    thermal) case "$1" in paleo*|2m_temperature*|wellspring*) return 0 ;; *) return 1 ;; esac ;;
    faults) case "$1" in qfaults*|faults_quaternary*|great_basin_q_volcanics*) return 0 ;; *) return 1 ;; esac ;;
    *) echo "unknown subset '$SUBSET' (use all|core|faults|thermal)" >&2; exit 2 ;;
  esac
}

: > "$EXT/SHA256SUMS.txt"
for name in "${!URLS[@]}"; do
  want "$name" || continue
  if [[ -s "$EXT/$name" ]]; then
    echo "SKIP (present) $name"
  else
    echo "GET  $name"
    curl -fL --retry 3 --retry-delay 2 -o "$EXT/$name" "${URLS[$name]}"
  fi
  sha256sum "$EXT/$name" >> "$EXT/SHA256SUMS.txt"
done

echo
echo "Done. Files and checksums in $EXT/"
echo "Next: unzip what you need and point scripts/build_features.py at the rasters."
