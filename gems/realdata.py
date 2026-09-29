"""Real competition data access (GeoDAWN / GEMS Prize).

Provenance of the rasters this module reads (see research/knowledge_base.md §6
and scripts/bridge_team_mirror.sh):

  * ``data/raw/training_labels.tif``  == official ``existing_faults.tif`` /
    ``labels.tif``  (USGS/INGENIOUS catalogue rasterised on the competition grid)
  * ``data/raw/sample_submission.tif`` == official ``example_submission.tif``
    (the template: CRS, shape, geotransform, NaN outside the scored footprint)
  * ``data/raw/training_features.tif`` == official
    ``gems-geodawn-numerical-features.tif`` (19 bands, LZW, float32, nodata
    -3.4028235e+38)

Nothing here invents values: every array is read from those files, and the
grid/metadata are measured, not assumed.  The files themselves are NOT tracked
in git (licence-gated competition data); ``scripts/bridge_team_mirror.sh``
fetches them from the group's own mirrors and verifies their SHA-256 against
the pins recorded in ``research/knowledge_base.md`` §6.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"

# Canonical file names on the official data tab (problem description, data tab).
F_LABELS = "training_labels.tif"
F_TEMPLATE = "sample_submission.tif"
F_FEATURES = "training_features.tif"

# Official no-data sentinel for the feature stack (measured, not assumed).
FEATURE_NODATA = float(np.finfo(np.float32).min)  # -3.4028234663852886e+38


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def read_labels(path: Path | str | None = None) -> np.ndarray:
    """Boolean catalogue mask on the competition grid (True = mapped fault)."""
    import rasterio

    p = Path(path) if path is not None else RAW / F_LABELS
    with rasterio.open(p) as src:
        a = src.read(1)
        nodata = src.nodata
    if nodata is not None and np.isfinite(nodata):
        return (a == a.dtype.type(1)) if nodata == -1 else ((a > 0) & (a != nodata))
    return a > 0


def read_template(path: Path | str | None = None) -> dict:
    """Grid of record measured from the official template."""
    import rasterio

    p = Path(path) if path is not None else RAW / F_TEMPLATE
    with rasterio.open(p) as src:
        a = src.read(1)
        return {
            "rows": src.height,
            "cols": src.width,
            "crs": src.crs.to_string() if src.crs else None,
            "transform": list(src.transform.to_gdal()),
            "nodata": None if src.nodata is None else float(src.nodata),
            "dtype": src.dtypes[0],
            "valid": np.isfinite(a),
            "path": str(p),
        }


def grid_json() -> dict:
    with open(PROC / "grid.json") as f:
        return json.load(f)


def band_names(features_path: Path | str | None = None) -> list[str]:
    """Band descriptions read from the file itself (never guessed).

    The competition ships each band's ``description`` tag; the earlier
    "4 bands unnamed" flag is resolved by reading them (knowledge_base C23).
    """
    import rasterio

    p = Path(features_path) if features_path is not None else RAW / F_FEATURES
    with rasterio.open(p) as src:
        return [src.tags(i).get("description", "") for i in range(1, src.count + 1)]


def read_band(index: int, features_path: Path | str | None = None, *, masked: bool = True) -> np.ndarray:
    """Read one feature band (1-based) as float32.

    ``masked=True`` maps the official no-data sentinel to NaN *only* where it
    occurs; every other value is returned untouched.
    """
    import rasterio

    p = Path(features_path) if features_path is not None else RAW / F_FEATURES
    with rasterio.open(p) as src:
        a = src.read(index).astype(np.float32, copy=False)
        nodata = src.nodata
    if masked:
        # The official sentinel is -3.4028234663852886e+38 (float32 minimum).
        # No real geophysical value in this stack is below -1e38, so masking
        # there is exact and does not clip data (measured: min finite band
        # value is far above it — see artifacts/real_data_audit.json).
        nd = FEATURE_NODATA if nodata is None else float(nodata)
        sentinel_cut = min(-1.0e38, nd * 0.5)
        a = np.where(np.isfinite(a) & (a > sentinel_cut), a, np.nan)
    return a


def channel_dir(create: bool = False) -> Path:
    d = PROC / "channels"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def save_channel(name: str, arr: np.ndarray) -> Path:
    """Persist a channel as float16 .npy (halves RAM; values are robust-scaled)."""
    d = channel_dir(create=True)
    p = d / f"{name}.npy"
    np.save(p, np.asarray(arr, dtype=np.float16))
    return p


def load_channel(name: str) -> np.ndarray:
    return np.load(channel_dir() / f"{name}.npy").astype(np.float32)


def available_channels() -> list[str]:
    d = channel_dir()
    if not d.exists():
        return []
    return sorted(p.stem for p in d.glob("*.npy"))
