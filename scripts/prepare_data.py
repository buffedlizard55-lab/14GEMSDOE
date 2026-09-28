#!/usr/bin/env python3
"""Prepare competition data: measure the grid of record and build derived masks.

Reads data/raw/{sample_submission.tif,training_labels.tif,training_features.tif}
and writes data/processed/:
    grid.json         shape / transform / CRS / resolution of the official template
    valid_mask.npy    bool, True inside the scored footprint (finite region of template)
    known_faults.npy  bool raster of catalogue fault pixels (labels > 0)
    layer_index.json  band index -> meaning, once the feature dictionary is available

Run after scripts/download_competition_data.sh.  If the raw files are missing,
this script exits with instructions (exit code 2) and nothing is invented.

Verified facts used here (research/knowledge_base.md):
  * template is single-band float32, values in [0,1], NaN outside bounds
    (problem description, submission-format section).
  * the scored population EXCLUDES known-fault pixels (staff ruling, forum
    thread 11516), so known_faults.npy doubles as the scoring eval mask's
    complement once predictions are built.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems import raster as gr  # noqa: E402

RAW = Path("data/raw")
PROC = Path("data/processed")


def main() -> int:
    template = RAW / "sample_submission.tif"
    labels = RAW / "training_labels.tif"
    features = RAW / "training_features.tif"

    missing = [p.name for p in (template, labels) if not p.exists()]
    if missing:
        print("MISSING in data/raw: " + ", ".join(missing))
        print("Fetch them from the DrivenData data tab (login required) — see")
        print("scripts/download_competition_data.sh for exact names and next steps.")
        return 2

    PROC.mkdir(parents=True, exist_ok=True)

    # --- grid of record, measured from the official template -----------------
    arr, meta = gr.read_band(template)
    grid = {
        "rows": meta["shape"][0],
        "cols": meta["shape"][1],
        "epsg": int(meta["crs"].split(":")[-1]) if meta["crs"] and ":" in meta["crs"] else meta["crs"],
        "res": float(meta["res"][0]),
        "transform": list(meta["transform"])[:6],
        "nodata": meta["nodata"],
        "source": f"measured from {template.name} on this machine",
    }
    with open(PROC / "grid.json", "w") as f:
        json.dump(grid, f, indent=2)
    print(f"grid.json written: {grid['rows']}x{grid['cols']} epsg={grid['epsg']} res={grid['res']}")

    # --- valid footprint: pixels of the template that are NOT NaN ------------
    valid = np.isfinite(arr)
    np.save(PROC / "valid_mask.npy", valid)
    print(f"valid_mask.npy: {int(valid.sum())} valid px / {valid.size} total "
          f"({100*valid.mean():.2f}% of grid)")

    # --- catalogue fault pixels --------------------------------------------
    lab, lmeta = gr.read_band(labels)
    known = (lab > 0) & np.isfinite(lab)
    np.save(PROC / "known_faults.npy", known)
    print(f"known_faults.npy: {int(known.sum())} catalogue fault px "
          f"({100*known.sum()/max(valid.sum(),1):.2f}% of valid area)")

    # --- features (presence is checked, not assumed) ------------------------
    if features.exists():
        _f, fmeta = gr.read_band(features)  # band 1 probe
        with rasterio_open_meta(features) as m:
            n = m["count"]
        (PROC / "layer_index.json").write_text(json.dumps({
            "training_features.tif": {
                "bands": n,
                "shape": fmeta["shape"],
                "crs": fmeta["crs"],
                "res": fmeta["res"],
                "note": ("Band meanings follow the problem-description list (19 named "
                         "layers; exact band order is read from the data dictionary "
                         "shipped with the download when present)."),
            }
        }, indent=2))
        print(f"layer_index.json written ({n} bands)")
    else:
        print("training_features.tif not present yet — layer_index.json skipped")

    print("\nNext: python3 scripts/build_features.py && python3 scripts/train_hide_recover.py")
    return 0


class rasterio_open_meta:
    """Context helper returning {'count': ...} for a raster path."""

    def __init__(self, path):
        import rasterio
        self._ds = rasterio.open(path)

    def __enter__(self):
        return {"count": self._ds.count, "dtypes": self._ds.dtypes}

    def __exit__(self, *exc):
        self._ds.close()
        return False


if __name__ == "__main__":
    raise SystemExit(main())
