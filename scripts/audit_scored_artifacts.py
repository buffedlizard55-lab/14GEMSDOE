#!/usr/bin/env python3
"""Artifact audit: are the group's submissions distinct, byte for byte?

Answers the standing question ("are we copying the same work over and over?")
with hashes, not with leaderboard scores.  A four-decimal score tie is not
evidence of duplicate work; an identical SHA-256 is.

What it computes, per artifact
------------------------------
* file SHA-256 (byte identity)
* prediction-array SHA-256 (pixel identity, independent of the TIFF container:
  two files can differ in tags while carrying the same field)
* positive-pixel count, prediction mass, value range, NaN count
* positives on the catalogue, and the fraction of positives within the 300 m
  scoring kernel of a catalogue pixel
* pairwise Jaccard overlap of the positive-pixel sets

Usage
-----
    python3 scripts/audit_scored_artifacts.py PATH [PATH ...] [--json OUT]
    python3 scripts/audit_scored_artifacts.py --fetch-scored   # group's vendored
                                                              # scored artifacts

``--fetch-scored`` downloads the artifacts the group vendored in
``buffedlizard55-lab/7GEMSDOE/external/scored`` (which carry a documented
leaderboard score each) through the GitHub API and reads their manifest for the
score attribution.  Those scores are group-reported/leaderboard observations;
this script does not re-verify them by upload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gems import realdata as rd  # noqa: E402

SCORED_REPO = "buffedlizard55-lab/7GEMSDOE"
SCORED_DIR = "external/scored"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_prediction(path: Path):
    import rasterio

    with rasterio.open(path) as src:
        arr = src.read(1).astype(np.float32)
        meta = {"shape": (src.height, src.width), "crs": src.crs.to_string(),
                "dtype": src.dtypes[0], "nodata": src.nodata,
                "transform": tuple(src.transform.to_gdal()[:6]), "count": src.count}
    return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0), arr, meta


def fetch_scored(dest: Path) -> list[Path]:
    """Pull the vendored scored artifacts + their manifest via the GitHub API."""
    dest.mkdir(parents=True, exist_ok=True)
    listing = json.loads(subprocess.run(
        ["gh", "api", f"repos/{SCORED_REPO}/contents/{SCORED_DIR}"],
        capture_output=True, text=True, check=True).stdout)
    paths = []
    for item in listing:
        if not item["name"].endswith((".tif", ".json")):
            continue
        out = dest / item["name"]
        raw = subprocess.run(
            ["gh", "api", f"repos/{SCORED_REPO}/contents/{item['path']}",
             "-H", "Accept: application/vnd.github.raw"],
            capture_output=True, check=True).stdout
        out.write_bytes(raw)
        paths.append(out)
    return sorted(p for p in paths if p.suffix == ".tif")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--fetch-scored", action="store_true")
    ap.add_argument("--cache", default="/tmp/gemsdoe_scored")
    ap.add_argument("--json", default="artifacts/scored_artifact_audit.json")
    args = ap.parse_args()

    files: list[Path] = list(args.paths)
    scores: dict[str, float | None] = {}
    # a manifest.json next to the artifacts supplies the score attribution
    for d in {f.parent for f in files}:
        man = d / "manifest.json"
        if man.exists():
            try:
                for entry in json.loads(man.read_text()).get("files", []):
                    scores.setdefault(entry["file"], entry.get("public_score"))
            except Exception:
                pass
    if args.fetch_scored:
        cache = Path(args.cache)
        files += fetch_scored(cache)
        manifest = cache / "manifest.json"
        if manifest.exists():
            for entry in json.loads(manifest.read_text())["files"]:
                scores[entry["file"]] = entry.get("public_score")
    if not files:
        print("no artifacts given; pass paths or --fetch-scored")
        return 2

    labels = rd.read_labels() if (rd.RAW / rd.F_LABELS).exists() else None
    rows = []
    masks = []
    for f in files:
        raw = f.read_bytes()
        pred, arr, meta = read_prediction(f)
        mask = pred > 0
        row = {
            "file": f.name,
            "score": scores.get(f.name),
            "bytes": len(raw),
            "sha256_file": sha256_bytes(raw),
            "sha256_prediction": sha256_bytes(np.ascontiguousarray(pred).tobytes()),
            "n_pos": int(mask.sum()),
            "mass": float(pred.sum()),
            "min": float(np.nanmin(arr)) if np.isfinite(arr).any() else None,
            "max": float(np.nanmax(arr)) if np.isfinite(arr).any() else None,
            "nan_px": int(np.isnan(arr).sum()),
            "meta": meta,
        }
        if labels is not None and labels.shape == mask.shape:
            from scipy import ndimage
            near = ndimage.distance_transform_edt(~labels) <= 3.0
            row["pos_on_catalogue"] = int((mask & labels).sum())
            row["frac_pos_within_300m_of_catalogue"] = float((mask & near).sum() / max(mask.sum(), 1))
        rows.append(row)
        masks.append(mask)

    print(f"{'artifact':34s} {'score':>7} {'bytes':>9} {'file-sha256':>16} {'pix-sha256':>16} "
          f"{'n_pos':>8} {'mass':>9} {'on_cat':>7} {'<300m':>6}")
    for r in rows:
        print(f"{r['file'][:34]:34s} {str(r['score']):>7} {r['bytes']:>9} "
              f"{r['sha256_file'][:16]} {r['sha256_prediction'][:16]} {r['n_pos']:>8} "
              f"{r['mass']:>9.1f} {r.get('pos_on_catalogue', -1):>7} "
              f"{r.get('frac_pos_within_300m_of_catalogue', float('nan')):>6.3f}")

    dup_file = {}
    dup_pix = {}
    for r in rows:
        dup_file.setdefault(r["sha256_file"], []).append(r["file"])
        dup_pix.setdefault(r["sha256_prediction"], []).append(r["file"])
    file_dups = {k: v for k, v in dup_file.items() if len(v) > 1}
    pix_dups = {k: v for k, v in dup_pix.items() if len(v) > 1}

    print("\n-- identity --")
    print(f"distinct files: {len(dup_file)}/{len(rows)}   distinct prediction arrays: {len(dup_pix)}/{len(rows)}")
    for k, v in file_dups.items():
        print(f"  IDENTICAL BYTES: {v}  sha256={k[:16]}")
    for k, v in pix_dups.items():
        print(f"  IDENTICAL PIXELS: {v}  pix-sha256={k[:16]}")

    if len(rows) > 1:
        print("\n-- pairwise Jaccard of positive-pixel sets --")
        print("      " + " ".join(f"{i:>5}" for i in range(len(rows))))
        for i, a in enumerate(masks):
            line = []
            for j, b in enumerate(masks):
                inter = np.count_nonzero(a & b)
                union = np.count_nonzero(a | b)
                line.append(f"{inter/union:5.2f}" if union else " 1.00")
            print(f"{i:>3}   " + " ".join(line))

    out = {
        "artifacts": rows,
        "duplicate_files": file_dups,
        "duplicate_prediction_arrays": pix_dups,
        "score_note": ("Leaderboard scores are group-reported/leaderboard observations. "
                       "Equal rounded scores are NOT evidence of equal rasters; the "
                       "sha256_prediction column is the only identity evidence."),
    }
    outpath = ROOT / args.json
    outpath.parent.mkdir(parents=True, exist_ok=True)
    outpath.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {outpath}")
    return 1 if (file_dups or pix_dups) else 0


if __name__ == "__main__":
    raise SystemExit(main())
