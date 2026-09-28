#!/usr/bin/env python3
"""Assemble, validate, and name a submission GeoTIFF.

Pipeline:
    prediction raster (.npy/.tif, any float type)
      -> NaN handling (fill inside the footprint, keep NaN outside)
      -> clamp to [0, 1]  (fixes "Predicted values must be in range [0, 1]")
      -> write single-band float32 GeoTIFF on the template grid
      -> format gate (gems.raster.check_submission) — file is NOT blessed if it fails
      -> unique filename + short NOTE + MANIFEST.json (sha256, histogram, policy)

Output naming (so submissions can never collide or be confused again):
    GEMS_<policy-slug>_<UTC yyyymmddTHHMMSSZ>_<sha8>.tif
    GEMS_<policy-slug>_<UTC yyyymmddTHHMMSSZ>_<sha8>.NOTE.txt
    GEMS_<policy-slug>_<UTC yyyymmddTHHMMSSZ>_<sha8>.MANIFEST.json

Usage:
    python3 scripts/build_submission.py PRED.npy --policy "h29 relay-corr holdout0.31"
    python3 scripts/build_submission.py PRED.tif --policy-name h29 --note "short comment"
    python3 scripts/build_submission.py PRED.npy --zero-outside   # max-compat variant
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems import raster as gr  # noqa: E402


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s.strip().lower()).strip("-")
    return (s[:40] or "run")


def load_pred(path: Path) -> np.ndarray:
    if path.suffix == ".npy":
        arr = np.load(path)
    else:
        arr, _meta = gr.read_band(path)
    if arr.ndim != 2:
        raise SystemExit(f"prediction must be 2-D, got shape {arr.shape}")
    return arr.astype(np.float32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pred", help="prediction raster (.npy or .tif), probabilities/logits-like")
    ap.add_argument("--policy", default="", help="full policy description (used for the note)")
    ap.add_argument("--policy-name", default="", help="short slug; default derived from --policy")
    ap.add_argument("--note", default="", help="short comment for the DrivenData Note field")
    ap.add_argument("--template", default="data/raw/sample_submission.tif")
    ap.add_argument("--outdir", default="submissions")
    ap.add_argument("--fix-nan", action="store_true",
                    help="fill NaN inside the footprint with 0.0 (reported in the manifest)")
    ap.add_argument("--zero-outside", action="store_true",
                    help="max-compatibility variant: 0.0 outside the footprint, no NaN anywhere")
    args = ap.parse_args()

    pred_path = Path(args.pred)
    if not pred_path.exists():
        print(f"prediction not found: {pred_path}")
        return 2

    # The template is the grid of record when present; data/processed/grid.json
    # (measured from the template by prepare_data.py) is the fallback.
    tmpl = Path(args.template)
    if tmpl.exists():
        _a, tmeta = gr.read_band(tmpl)
        grid = {
            "rows": tmeta["shape"][0],
            "cols": tmeta["shape"][1],
            "epsg": int(str(tmeta["crs"]).split(":")[-1]) if tmeta["crs"] and ":" in str(tmeta["crs"]) else None,
            "res": float(tmeta["res"][0]),
            "transform": list(tmeta["transform"])[:6],
            "source": f"measured from {tmpl.name}",
        }
    else:
        grid = gr.load_grid_meta()

    arr = load_pred(pred_path)

    if arr.shape != (grid["rows"], grid["cols"]):
        raise SystemExit(
            f"prediction shape {arr.shape} != grid {(grid['rows'], grid['cols'])} "
            "(the submission must cover the whole GeoDAWN grid)"
        )

    valid_path = Path("data/processed/valid_mask.npy")
    valid = np.load(valid_path).astype(bool) if valid_path.exists() \
        else np.ones(arr.shape, dtype=bool)

    # ---- NaN policy ------------------------------------------------------
    n_nan_total = int(np.isnan(arr).sum())
    n_nan_inside = int((np.isnan(arr) & valid).sum())
    if n_nan_inside and not args.fix_nan:
        raise SystemExit(
            f"{n_nan_inside} NaN pixel(s) inside the scored footprint — the submission form "
            "rejects these with 'Predicted values must be in range [0, 1]'. "
            "Re-run with --fix-nan to fill them with 0.0 (recommended), or fix the upstream "
            "prediction so the footprint is fully finite."
        )
    if n_nan_inside and args.fix_nan:
        arr = np.where(np.isnan(arr) & valid, np.float32(0.0), arr)

    # ---- clamp to [0, 1] -------------------------------------------------
    finite = np.isfinite(arr)
    vmin = float(arr[finite].min()) if finite.any() else float("nan")
    vmax = float(arr[finite].max()) if finite.any() else float("nan")
    n_clipped = int(((arr < 0.0) | (arr > 1.0)).sum())
    arr = np.clip(arr, 0.0, 1.0).astype(np.float32)

    # ---- outside-footprint policy ---------------------------------------
    if args.zero_outside:
        arr = np.where(valid, arr, np.float32(0.0))
        nodata = None
    else:
        arr = np.where(valid, arr, np.float32("nan"))
        nodata = float("nan")

    # ---- write ----------------------------------------------------------
    import rasterio
    from rasterio.transform import Affine

    if tmpl.exists():
        transform = tmeta["transform"]
        crs = tmeta["crs"]
    else:
        t = grid.get("transform")
        transform = Affine(*t) if t else Affine(grid["res"], 0, 500000.0, 0, -grid["res"], 4500000.0)
        crs = f"EPSG:{grid['epsg']}"

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    utc = datetime.now(timezone.utc)
    stamp = utc.strftime("%Y%m%dT%H%M%SZ")
    policy_slug = slugify(args.policy_name or args.policy or "run")

    # provisional file to hash the actual bytes we write
    tmp = outdir / f"_tmp_{stamp}.tif"
    profile = {
        "driver": "GTiff",
        "height": arr.shape[0],
        "width": arr.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "compress": "deflate",
    }
    if nodata is not None:
        profile["nodata"] = nodata
    with rasterio.open(tmp, "w", **profile) as ds:
        ds.write(arr, 1)

    sha = gr.sha256_file(tmp)
    base = f"GEMS_{policy_slug}_{stamp}_{sha[:8]}"
    tif = outdir / f"{base}.tif"
    tmp.rename(tif)

    # ---- format gate ----------------------------------------------------
    if tmpl.exists():
        tmeta_out = template_meta_from(tmpl)
    else:
        tmeta_out = {
            "rows": grid["rows"], "cols": grid["cols"], "epsg": grid["epsg"],
            "res": grid["res"], "transform": list(transform)[:6],
            "valid_mask_path": str(valid_path),
        }
    try:
        report = gr.check_submission(tif, tmeta_out, allow_zero_outside=args.zero_outside)
    except gr.SubmissionValidationError as e:
        tif.unlink(missing_ok=True)
        print("REFUSED — the file would be rejected by the submission form:\n" + str(e))
        return 1

    # ---- note + manifest -------------------------------------------------
    note = args.note or (
        f"{args.policy or policy_slug} · DTI(holdout)=see MANIFEST · "
        f"built {stamp} · sha8={sha[:8]}"
    )
    (outdir / f"{base}.NOTE.txt").write_text(
        "Paste this into the DrivenData 'Note (optional)' field:\n\n" + note + "\n"
    )

    hist = {
        "px_0": int((arr == 0.0).sum()),
        "px_1": int((arr == 1.0).sum()),
        "px_mid": int(((arr > 0.0) & (arr < 1.0)).sum()),
        "px_nan": int(np.isnan(arr).sum()),
    }
    prediction_sha256 = hashlib.sha256(
        np.ascontiguousarray(arr, dtype=np.float32).tobytes(order="C")
    ).hexdigest()
    manifest = {
        "file": tif.name,
        "sha256": sha,
        "prediction_sha256": prediction_sha256,
        "prediction_hash_scope": "full float32 array in C order after output/nodata policy",
        "built_utc": utc.isoformat(),
        "policy": args.policy or policy_slug,
        "note": note,
        "input_pred": str(pred_path),
        "grid": grid,
        "value_range_before_clamp": [vmin, vmax],
        "n_values_clipped_to_01": n_clipped,
        "n_nan_filled_inside_footprint": n_nan_inside if args.fix_nan else 0,
        "outside_footprint": "nan" if not args.zero_outside else "zero",
        "histogram": hist,
        "format_gate": report,
    }
    (outdir / f"{base}.MANIFEST.json").write_text(json.dumps(manifest, indent=2, default=str))

    print(f"PASS — {tif}")
    print(f"  note:     {note}")
    print(f"  sha256:   {sha}")
    print(f"  clipped:  {n_clipped} value(s) to [0,1] (was min={vmin}, max={vmax})")
    print(f"  NaN in:   {n_nan_inside} filled" if args.fix_nan else "  NaN in:   none")
    print(f"  upload:   {tif.name}   (or zip it; the form accepts either)")
    return 0


def template_meta_from(path: Path) -> dict:
    _arr, meta = gr.read_band(path)
    return {
        "rows": meta["shape"][0],
        "cols": meta["shape"][1],
        "epsg": int(str(meta["crs"]).split(":")[-1]) if meta["crs"] and ":" in str(meta["crs"]) else None,
        "res": float(meta["res"][0]),
        "transform": list(meta["transform"])[:6],
        "valid_mask_path": "data/processed/valid_mask.npy",
    }


if __name__ == "__main__":
    raise SystemExit(main())
