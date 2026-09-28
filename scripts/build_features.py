#!/usr/bin/env python3
"""Build the feature stack for training/inference.

Outputs data/processed/features.npz with the catalogue-geometry features
computed from the CONTEXT traces plus any field rasters available:

    context-dependent (recomputed per hide-plan during training):
        dist_trace, az_to_trace, across_strike, along_strike, dist_endpoint,
        relay_corridor, trace_density, junction_density,
        catalogue_strike, catalogue_strike_conf
    field rasters (static):
        f_* bands from data/raw/training_features.tif (or the demo region)
        slip_tendency, dilation_tendency  (if data/external has them)

Usage:
    python3 scripts/build_features.py            # real data (needs prepare_data first)
    python3 scripts/build_features.py --demo     # synthetic region
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems.features import build_catalogue_feature_stack, load_external_raster  # noqa: E402

OUT = Path("data/processed/features.npz")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--window", type=int, default=9)
    args = ap.parse_args()

    if args.demo:
        from gems.synthesize import make_region
        region = make_region(shape=(320, 320), seed=42)
        traces = region["traces"]
        fields = {"f_elev": region["f_elev"], "f_mag": region["f_mag"],
                  "strain": region["strain"]}
        grid = {"rows": 320, "cols": 320, "epsg": 32611, "res": 100.0,
                "transform": [100.0, 0.0, 500000.0, 0.0, -100.0, 4500000.0]}
    else:
        kp = Path("data/processed/known_faults.npy")
        if not kp.exists():
            print("data/processed/known_faults.npy missing — run scripts/prepare_data.py first")
            return 2
        traces = np.load(kp).astype(bool)
        fields = {}
        feats = Path("data/raw/training_features.tif")
        if feats.exists():
            from gems import raster as gr
            bands, meta = gr.read_multiband(feats)
            for i in range(bands.shape[0]):
                fields[f"band_{i+1:02d}"] = bands[i].astype(np.float32)
        grid = json.loads(Path("data/processed/grid.json").read_text())

        # external slip/dilation tendency if the team has downloaded it
        for name, key in (("slip_tendency.tif", "slip_tendency"),
                          ("dilation_tendency.tif", "dilation_tendency")):
            p = Path("data/external") / name
            if p.exists():
                try:
                    fields[key] = load_external_raster(p, grid)
                except Exception as e:
                    print(f"NOTE: could not warp {p.name}: {e}")

    print(f"building catalogue-geometry features on {traces.shape} ...")
    feats = build_catalogue_feature_stack(traces, window=args.window)

    arrays = {}
    for k, v in feats.items():
        if k.startswith("_") or not isinstance(v, np.ndarray) or v.ndim != 2:
            continue
        arrays[k] = v.astype(np.float32)
    for k, v in fields.items():
        if v.shape == traces.shape:
            arrays[k] = v.astype(np.float32)
        else:
            print(f"NOTE: field {k} shape {v.shape} != {traces.shape}, skipped")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT, **arrays)
    meta = feats.get("_meta", {})
    print(f"wrote {OUT} with {len(arrays)} layers "
          f"({', '.join(sorted(arrays)[:8])}...)")
    print(f"relay corridor pairs detected: {meta.get('relay_pairs', 'n/a')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
