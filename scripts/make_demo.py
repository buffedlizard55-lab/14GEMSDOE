#!/usr/bin/env python3
"""End-to-end demo on the synthetic region — proves the entire pipeline runs
without the login-gated competition data.

Produces:
    data/demo/sample_submission.tif   synthetic template (NaN outside footprint)
    data/demo/training_labels.tif     synthetic catalogue
    data/demo/valid_mask.npy
    data/demo/grid.json
    artifacts/demo_pred.npy           hide-and-recover prediction
    submissions/GEMS_demo_*.tif       a format-VALIDATED demo submission
                                     (clearly labelled demo — NOT for upload)

Run:  python3 scripts/make_demo.py
Then: python3 scripts/build_site_payload.py   (ships the demo pixels to the site)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems.synthesize import make_region  # noqa: E402
from gems import raster as gr  # noqa: E402


def write_template(path: Path, footprint: np.ndarray, res: float = 100.0) -> None:
    import rasterio
    from rasterio.transform import Affine
    arr = np.where(footprint, np.float32(0.0), np.float32("nan"))
    transform = Affine(res, 0, 500000.0, 0, -res, 4500000.0)
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
        count=1, dtype="float32", crs="EPSG:32611", transform=transform,
        nodata=float("nan"),
    ) as ds:
        ds.write(arr, 1)


def main() -> int:
    demo = Path("data/demo")
    demo.mkdir(parents=True, exist_ok=True)
    region = make_region(shape=(320, 320), seed=42)

    write_template(demo / "sample_submission.tif", region["footprint"])
    write_template(demo / "training_labels.tif", region["footprint"])
    # labels on top of the template frame
    import rasterio
    lab = region["traces"].astype(np.float32)
    lab = np.where(region["footprint"], lab, np.float32("nan"))
    with rasterio.open(demo / "training_labels.tif", "r+") as ds:
        ds.write(lab, 1)

    np.save(demo / "valid_mask.npy", region["footprint"])
    _a, meta = gr.read_band(demo / "sample_submission.tif")
    (demo / "grid.json").write_text(json.dumps({
        "rows": meta["shape"][0], "cols": meta["shape"][1], "epsg": 32611,
        "res": float(meta["res"][0]), "transform": list(meta["transform"])[:6],
        "source": "synthetic demo grid (make_demo.py)",
    }, indent=2))

    print("training hide-and-recover on the synthetic region ...")
    from scripts.train_hide_recover import train
    result = train(region, hide_fraction=0.35, epochs=6, seed=42, verbose=True)
    Path("artifacts").mkdir(exist_ok=True)
    np.save("artifacts/demo_pred.npy", result["pred_full"])
    (artifacts := Path("artifacts/demo_run.json")).write_text(json.dumps({
        "mean_recover_dti": result["mean_recover_dti"],
        "epochs": result["epochs"],
        "feature_names": result["feature_names"],
        "note": "synthetic region — numbers here are demo values, NOT holdout estimates "
                "for the real GeoDAWN data",
    }, indent=2))
    print(f"mean hidden-recovery DTI (synthetic) = {result['mean_recover_dti']:.4f}")

    print("\nbuilding a format-validated demo submission ...")
    rc = subprocess.call([
        sys.executable, "scripts/build_submission.py", "artifacts/demo_pred.npy",
        "--policy", "demo synthetic hide-and-recover — NOT FOR UPLOAD",
        "--policy-name", "demo", "--note",
        "DEMO ONLY (synthetic region) — do not upload this file",
        "--template", "data/demo/sample_submission.tif",
        "--outdir", "submissions", "--fix-nan",
    ])
    if rc != 0:
        return rc

    print("\nvalidating the demo submission against the format gate ...")
    subs = sorted(Path("submissions").glob("GEMS_demo_*.tif"))
    rc = subprocess.call([
        sys.executable, "scripts/validate_submission.py", str(subs[-1]),
        "--template", "data/demo/sample_submission.tif",
    ])
    print(f"\ndemo complete: {subs[-1]} (demo artifact — the real submission needs the "
          f"real data in data/raw/)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
