"""GeoTIFF I/O and the submission-format conformance gate.

Official submission format (verified 2026-09-28, problem description
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format):

  * single band, 32-bit float (float32)
  * values between 0 and 1 (probability / confidence of fault presence)
  * same CRS as the training data: UTM zone 11N, EPSG:32611
  * same resolution as the training data: 100 m
  * same bounds as the training data; data outside the bounds is null or NaN

Rejection actually observed by the team on the submission form:
"Predicted values must be in range [0, 1]"
(see research/limitations_and_next.md, incident log 2026-09-2x).
The two mechanical causes are (a) values outside [0, 1] (logits, 0-255 bytes),
(b) NaN sitting INSIDE the template's valid (scored) region, so that the
form's range check (which reads every finite-or-not pixel) trips.  This module
detects both and refuses to bless the file until they are fixed.

Grid constants below are MEASURED from the official template
(data/raw/example_submission.tif) by scripts/prepare_data.py and pinned in
data/processed/grid.json.  Until real data is placed, tests use a synthetic
grid of the same shape so every code path is exercised.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.transform import Affine

# ---------------------------------------------------------------------------
# Pinned grid (placeholders until data/processed/grid.json exists).
# The numbers here are the ones published on the team's measured runs
# (GEMSDOE docs site, measured with rasterio from the official template):
# 3,292 x 3,730 px, EPSG:32611, 100 m.  They are re-measured and overwritten
# by scripts/prepare_data.py the moment the real template lands in data/raw/.
# ---------------------------------------------------------------------------
PINNED_SHAPE = (3730, 3292)  # (rows, cols)
PINNED_EPSG = 32611
PINNED_RES_M = 100.0


def load_grid_meta(processed_dir: Path | str = "data/processed") -> dict:
    """Return grid metadata: shape, transform, crs, res.

    Prefers data/processed/grid.json (measured from the real template);
    falls back to the pinned placeholder values.
    """
    gj = Path(processed_dir) / "grid.json"
    if gj.exists():
        with open(gj) as f:
            return json.load(f)
    rows, cols = PINNED_SHAPE
    return {
        "rows": rows,
        "cols": cols,
        "epsg": PINNED_EPSG,
        "res": PINNED_RES_M,
        "transform": None,  # unknown until the real template is measured
        "source": "pinned-placeholder (no data/processed/grid.json yet)",
    }


def read_band(path: Path | str, band: int = 1) -> tuple[np.ndarray, dict]:
    """Read one band as float32 plus its profile metadata."""
    with rasterio.open(path) as ds:
        arr = ds.read(band).astype(np.float32)
        meta = {
            "shape": (ds.height, ds.width),
            "transform": ds.transform,
            "crs": ds.crs.to_string() if ds.crs else None,
            "res": ds.res,
            "nodata": ds.nodata,
            "count": ds.count,
            "dtypes": ds.dtypes,
        }
    return arr, meta


def read_multiband(path: Path | str) -> tuple[np.ndarray, dict]:
    """Read all bands as float32 array shaped (bands, rows, cols)."""
    with rasterio.open(path) as ds:
        arr = ds.read().astype(np.float32)
        meta = {
            "shape": (ds.height, ds.width),
            "count": ds.count,
            "transform": ds.transform,
            "crs": ds.crs.to_string() if ds.crs else None,
            "res": ds.res,
            "nodata": ds.nodata,
        }
    return arr, meta


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class SubmissionValidationError(Exception):
    """Raised when a candidate submission fails the official format gate."""


def check_submission(
    path: Path | str,
    template_meta: dict,
    *,
    allow_zero_outside: bool = False,
) -> dict:
    """Run the official format gate on a candidate submission file.

    Parameters
    ----------
    path : candidate .tif
    template_meta : dict with keys rows, cols, transform (Affine or 6-tuple or
        None to skip geotransform comparison), crs (string), res
    allow_zero_outside : if True, accepts the "maximum-compatibility" variant
        (0.0 outside the footprint, no NaN anywhere) that some flows emit.

    Returns a report dict; raises SubmissionValidationError on any failure.
    """
    problems: list[str] = []
    report: dict = {"path": str(path), "problems": problems}

    with rasterio.open(path) as ds:
        report["driver"] = ds.driver
        report["count"] = ds.count
        report["dtype"] = ds.dtypes[0]
        report["shape"] = (ds.height, ds.width)
        report["crs"] = ds.crs.to_string() if ds.crs else None
        report["nodata"] = ds.nodata

        if ds.driver != "GTiff":
            problems.append(f"driver is {ds.driver!r}, expected 'GTiff'")
        if ds.count != 1:
            problems.append(f"band count is {ds.count}, expected 1 (single layer)")
        if ds.dtypes[0] != "float32":
            problems.append(f"dtype is {ds.dtypes[0]!r}, expected 'float32'")

        rows, cols = template_meta["rows"], template_meta["cols"]
        if (ds.height, ds.width) != (rows, cols):
            problems.append(
                f"shape is {(ds.height, ds.width)}, expected {(rows, cols)} "
                "(same bounds as the training data)"
            )

        want_epsg = template_meta.get("epsg")
        if want_epsg is not None:
            got = ds.crs.to_epsg() if ds.crs else None
            if got != want_epsg:
                problems.append(f"CRS EPSG is {got}, expected {want_epsg}")

        t = template_meta.get("transform")
        if t is not None:
            want = Affine(*t) if not isinstance(t, Affine) else t
            got = ds.transform
            if not np.allclose([got.a, got.b, got.c, got.d, got.e, got.f],
                               [want.a, want.b, want.c, want.d, want.e, want.f],
                               rtol=0, atol=1e-6):
                problems.append(f"geotransform {tuple(got)[:6]} != template {tuple(want)[:6]}")

        res = template_meta.get("res")
        if res is not None:
            if not np.allclose(ds.res, (res, res), rtol=0, atol=1e-6):
                problems.append(f"resolution {ds.res} != ({res}, {res})")

        arr = ds.read(1)

    # ---- value gate: the exact check behind "Predicted values must be in range [0, 1]"
    nan_mask = np.isnan(arr)
    inf_mask = np.isinf(arr)
    finite = np.isfinite(arr)
    report["n_nan"] = int(nan_mask.sum())
    report["n_inf"] = int(inf_mask.sum())

    if inf_mask.any():
        problems.append(f"{int(inf_mask.sum())} infinite value(s) present; remove infinities")

    if finite.any():
        vmin = float(arr[finite].min())
        vmax = float(arr[finite].max())
    else:
        vmin, vmax = float("nan"), float("nan")
    report["min"] = vmin
    report["max"] = vmax

    if finite.any() and (vmin < 0.0 or vmax > 1.0):
        n_bad = int(((arr < 0.0) | (arr > 1.0)).sum())
        problems.append(
            f"{n_bad} value(s) outside [0, 1] (min={vmin}, max={vmax}) — "
            "this is the mechanical cause of the form error "
            "'Predicted values must be in range [0, 1]'"
        )

    # NaN policy: NaN is only legal strictly outside the scored footprint.
    # Without the real template's valid-region mask we can only enforce the
    # strict variant (no NaN at all) or, with valid_mask provided, the precise
    # rule.  template_meta may carry 'valid_mask_path'.
    vm_path = template_meta.get("valid_mask_path")
    if vm_path and Path(vm_path).exists():
        valid = np.load(vm_path).astype(bool)
        if valid.shape != arr.shape:
            problems.append("valid mask shape mismatch")
        else:
            bad = int((nan_mask & valid).sum())
            report["nan_inside_valid"] = bad
            if bad > 0 and not allow_zero_outside:
                problems.append(
                    f"{bad} NaN pixel(s) INSIDE the scored region — the form will reject "
                    "this with 'Predicted values must be in range [0, 1]'; "
                    "run scripts/build_submission.py --fix-nan to fill them with 0.0"
                )
    else:
        if nan_mask.any() and not allow_zero_outside:
            problems.append(
                f"{int(nan_mask.sum())} NaN pixel(s) present and no valid-region mask is "
                "available to prove they are all outside the footprint. Either provide "
                "data/processed/valid_mask.npy (built by scripts/prepare_data.py) or "
                "rebuild with --zero-outside (0.0 outside, no NaN)."
            )

    report["ok"] = not problems
    if problems:
        raise SubmissionValidationError(
            "submission failed format gate:\n  - " + "\n  - ".join(problems)
        )
    return report
