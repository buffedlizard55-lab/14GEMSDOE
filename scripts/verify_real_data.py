#!/usr/bin/env python3
"""Verify the real competition rasters against the OFFICIAL specification.

Every check below is a comparison between something measured on the files in
``data/raw/`` and something stated in an official document or measured
independently; nothing is assumed.  Exit code 0 = all checks pass.

Sources for the expected values
-------------------------------
* grid, CRS, resolution, band count, template dtype  — problem description,
  "Submission format" and "Provided features":
  https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
* template == the catalogue itself (bit-comparable), i.e. the example
  submission is the published USGS/INGENIOUS fault raster — verified here by
  comparing the template's positive pixels with the label raster.
* catalogue pixel count 60,988 and footprint 5,167,373 px — measured here AND
  published independently on the group's GEMSDOE/5GEMSDOE sites
  (https://buffedlizard55-lab.github.io/GEMSDOE/docs/index.html, "Known faults
  60,988 / 1.18% of valid area").  Agreement between two independent
  measurements of the same file is the evidence that the mirror is the real
  raster, not a re-drawn proxy.
* feature nodata sentinel: float32 minimum (-3.4028235e+38), observed in the
  file and consistent with the 5GEMSDOE/12GEMSDOE findings.

Writes ``artifacts/real_data_audit.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gems import realdata as rd  # noqa: E402

EXPECT = {
    "shape": (3730, 3292),
    "epsg": "EPSG:32611",
    "res": 100.0,
    "bands": 19,
    "transform": (243350.0, 100.0, 0.0, 4508550.0, 0.0, -100.0),  # GDAL (c,a,b,f,d,e)
    "template_dtype": "float32",
    "labels_dtype": "int8",
    "catalogue_px": 60988,
    "footprint_px": 5167373,
    "feature_nodata": float(np.finfo(np.float32).min),
}


def main() -> int:
    import rasterio

    out: dict = {"checks": [], "ok": True}
    fpath = rd.RAW / rd.F_FEATURES
    lpath = rd.RAW / rd.F_LABELS
    tpath = rd.RAW / rd.F_TEMPLATE
    for p in (fpath, lpath, tpath):
        if not p.exists():
            print(f"MISSING {p} — run scripts/bridge_team_mirror.sh first")
            return 2

    def check(name: str, got, exp, note: str = ""):
        ok = got == exp
        out["checks"].append({"check": name, "measured": got, "expected": exp, "ok": bool(ok), "note": note})
        out["ok"] = out["ok"] and bool(ok)
        print(f"[{'OK ' if ok else 'FAIL'}] {name}: measured={got} expected={exp} {note}")

    with rasterio.open(fpath) as src:
        fmeta = {"shape": (src.height, src.width), "epsg": src.crs.to_string(),
                 "res": src.res[0], "bands": src.count, "dtypes": src.dtypes[0],
                 "nodata": float(src.nodata), "transform": tuple(src.transform.to_gdal()[:6]),  # GDAL order (c,a,b,f,d,e)
                 "descriptions": [src.tags(i).get("description", "") for i in range(1, src.count + 1)],
                 "categories": [src.tags(i).get("data_category", "") for i in range(1, src.count + 1)]}
    with rasterio.open(lpath) as src:
        lmeta = {"shape": (src.height, src.width), "dtypes": src.dtypes[0],
                 "nodata": float(src.nodata), "epsg": src.crs.to_string(),
                 "transform": tuple(src.transform.to_gdal()[:6])}
    with rasterio.open(tpath) as src:
        tmeta = {"shape": (src.height, src.width), "dtypes": src.dtypes[0],
                 "nodata": src.nodata, "epsg": src.crs.to_string(),
                 "transform": tuple(src.transform.to_gdal()[:6])}

    out["files"] = {"features": fmeta, "labels": lmeta, "template": tmeta}
    out["sha256"] = {str(p.name): rd.sha256_file(p) for p in (fpath, lpath, tpath)}

    check("features.shape", fmeta["shape"], EXPECT["shape"])
    check("features.epsg", fmeta["epsg"], EXPECT["epsg"])
    check("features.res", fmeta["res"], EXPECT["res"])
    check("features.bands", fmeta["bands"], EXPECT["bands"])
    check("features.dtype", fmeta["dtypes"], "float32")
    check("features.transform", fmeta["transform"], EXPECT["transform"],
          "compared after ordering both sides to GDAL (c,a,b,f,d,e); an earlier run "
          "flagged a false FAIL because one side was in affine (a,b,c,d,e,f) order")
    check("features.nodata", fmeta["nodata"], EXPECT["feature_nodata"])
    check("features.band_descriptions_named", sum(1 for d in fmeta["descriptions"] if d.strip()),
          EXPECT["bands"], "resolves the earlier '4 unnamed bands' flag (KB C23)")
    check("labels.shape", lmeta["shape"], EXPECT["shape"])
    check("labels.dtype", lmeta["dtypes"], EXPECT["labels_dtype"])
    check("template.shape", tmeta["shape"], EXPECT["shape"])
    check("template.dtype", tmeta["dtypes"], EXPECT["template_dtype"])
    check("template.epsg", tmeta["epsg"], EXPECT["epsg"])
    check("template.transform", tmeta["transform"], EXPECT["transform"],
          "same GDAL-order comparison as features.transform")
    check("template.nodata_is_nan", bool(np.isnan(tmeta["nodata"])), True,
          "official format: null/NaN outside the footprint")

    labels = rd.read_labels()
    check("catalogue_px", int(labels.sum()), EXPECT["catalogue_px"],
          "matches the number published independently on the group's GEMSDOE site")
    tpl = rd.read_template()
    valid = tpl["valid"]
    check("footprint_px", int(valid.sum()), EXPECT["footprint_px"])
    check("template_is_catalogue", bool(np.array_equal(valid & (np.asarray(
        rasterio.open(tpath).read(1)) > 0.5), labels)),
        True, "the example submission reproduces the published catalogue bit-for-bit")
    check("labels_outside_footprint", int((labels & ~valid).sum()), 0)

    finite_minmax = []
    for i in range(1, fmeta["bands"] + 1):
        a = rd.read_band(i)
        finite_minmax.append({"band": i, "description": fmeta["descriptions"][i - 1],
                              "category": fmeta["categories"][i - 1],
                              "finite_px": int(np.isfinite(a).sum()),
                              "min": float(np.nanmin(a)), "max": float(np.nanmax(a)),
                              "finite_and_below_-1e37": int((np.isfinite(a) & (a < -1e37)).sum())})
    out["bands"] = finite_minmax
    check("bands_with_finite_data", sum(1 for b in finite_minmax if b["finite_px"] > 0), fmeta["bands"])
    check("sentinel_leaks_into_bands", sum(b["finite_and_below_-1e37"] for b in finite_minmax), 0,
          "no sentinel value survives the NaN masking of realdata.read_band")

    outpath = ROOT / "artifacts" / "real_data_audit.json"
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {outpath}")
    print("ALL CHECKS PASS" if out["ok"] else "SOME CHECKS FAILED")
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
