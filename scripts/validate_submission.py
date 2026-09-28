#!/usr/bin/env python3
"""Validate a candidate submission GeoTIFF against the official format.

The team has already been burned once on the submission form:
    "Predicted values must be in range [0, 1]"
This tool refuses to bless a file that would trigger that message (or any other
format rejection) and prints exactly which pixels/conditions are at fault.

Usage:
    python3 scripts/validate_submission.py CANDIDATE.tif [--template data/raw/sample_submission.tif]
                                            [--zero-outside]

Exit codes: 0 = pass, 1 = fail, 2 = missing inputs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems import raster as gr  # noqa: E402


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--template", default="data/raw/sample_submission.tif")
    ap.add_argument("--zero-outside", action="store_true",
                    help="accept the max-compatibility variant (0.0 outside, no NaN)")
    args = ap.parse_args()

    cand = Path(args.candidate)
    if not cand.exists():
        print(f"candidate not found: {cand}")
        return 2

    tmpl = Path(args.template)
    if tmpl.exists():
        tmeta = template_meta_from(tmpl)
    else:
        print(f"NOTE: template {tmpl} not found — using pinned grid "
              f"{gr.PINNED_SHAPE} EPSG:{gr.PINNED_EPSG} without geotransform check")
        tmeta = {
            "rows": gr.PINNED_SHAPE[0], "cols": gr.PINNED_SHAPE[1],
            "epsg": gr.PINNED_EPSG, "res": gr.PINNED_RES_M, "transform": None,
            "valid_mask_path": "data/processed/valid_mask.npy",
        }

    try:
        report = gr.check_submission(cand, tmeta, allow_zero_outside=args.zero_outside)
    except gr.SubmissionValidationError as e:
        print("FAIL")
        print(str(e))
        return 1

    print("PASS — submission is format-conformant.")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
