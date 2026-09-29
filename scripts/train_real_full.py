#!/usr/bin/env python3
"""Train the real-data model and write a submission-ready prediction field.

This is the *deployment* counterpart of ``scripts/validate_real.py``:

    gate (component folds)   ->  answers "which channels and which emission
                                  policy actually help on the real rasters?"
    this script              ->  trains on the FULL catalogue context (that is
                                  what a submission sees), predicts the whole
                                  grid, and writes the field + an emissions
                                  file that ``scripts/build_submission.py``
                                  turns into a conformant GeoTIFF.

Everything is computed from the official rasters in ``data/raw`` with the same
channel library the gate uses, so the field the site ships is the same kind of
object the gate measured — no hand-tuning between the two.

Outputs (all git-ignored):
    artifacts/real_field_<arm>.npy        float32 probability field, full grid
    artifacts/real_field_<arm>.json       policy metadata (threshold, counts)
    artifacts/real_emission_<name>.npy    binary emission ready for build_submission

Usage:
    ./.venv/bin/python scripts/train_real_full.py --arms baseline ALL \
        --holdout-fraction 0.30 --out-dir artifacts
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gems import dti_fast as df  # noqa: E402
from gems import realchannels as rc  # noqa: E402
from gems import realdata as rd  # noqa: E402

# Importing the gate module keeps the feature definitions in exactly one place.
sys.path.insert(0, str(ROOT / "scripts"))
import validate_real as vr  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="*", default=["baseline", "ALL"])
    ap.add_argument("--holdout-fraction", type=float, default=0.30,
                    help="share of catalogue components held out to calibrate the "
                         "emission threshold (they are also hidden from the context "
                         "used to train, per hide-and-recover)")
    ap.add_argument("--max-iter", type=int, default=150)
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--chunk-rows", type=int, default=256)
    ap.add_argument("--out-dir", default="artifacts")
    ap.add_argument("--emission", nargs="*", default=None,
                    help="emission specs, e.g. 'thresh:0.35' 'topk:0.02' 'nms3:0.02'")
    args = ap.parse_args()

    t0 = time.time()
    labels = rd.read_labels()
    tpl = rd.read_template()
    valid = tpl["valid"]
    shape = labels.shape
    print(f"[train] grid {shape} valid={int(valid.sum())} catalogue={int(labels.sum())}",
          flush=True)

    lab, n = ndimage.label(labels, structure=np.ones((3, 3), dtype=int))
    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(np.arange(1, n + 1))
    n_hold = max(1, int(round(args.holdout_fraction * n)))
    hold_ids = perm[:n_hold]
    hold = np.isin(lab, hold_ids)                 # calibration + honest check
    context = labels & ~hold                      # what the training features see
    print(f"[train] {n} components: {n_hold} held out ({int(hold.sum())} px), "
          f"context {int(context.sum())} px", flush=True)

    print("[train] building geophysical channels …", flush=True)
    geo = vr.geo_channels()
    print(f"[train] geo channels in {time.time()-t0:.0f} s", flush=True)
    ch = {**geo, **vr.context_channels(context, geo, fit_mask=labels)}
    print(f"[train] context channels in {time.time()-t0:.0f} s", flush=True)

    train_idx, y = vr.sample_training_pixels(hold, valid, rng)
    print(f"[train] training pixels: {int((y > 0).sum())} pos + {int((y < 1).sum())} neg",
          flush=True)

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for arm in args.arms:
        extra = vr.ARM_EXTRA[arm]
        base = [nm for nm in (vr.BASE_NAMES + extra) if nm in ch]
        X = vr.stack_matrix(ch, base, train_idx)
        clf = vr.fit_model(X, y, seed=args.seed, max_iter=args.max_iter)
        del X
        t1 = time.time()
        field = vr.predict_full(clf, ch, base, shape, valid=valid,
                                chunk_rows=args.chunk_rows, tag=f"{arm} predict")
        print(f"[train][{arm}] field in {time.time()-t1:.0f} s "
              f"(mean {float(field[valid].mean()):.4f})", flush=True)
        np.save(out_dir / f"real_field_{arm}.npy", field.astype(np.float32))

        # calibrate the emission threshold on the held-out components only
        best = None
        for t in (0.05, 0.15, 0.25, 0.35, 0.5):
            pred = df.emit_thresh(field, valid, t)
            r = df.dti_fast(pred, hold)
            if best is None or r["dti"] > best[1]["dti"]:
                best = (t, r)
        print(f"[train][{arm}] calibrated threshold {best[0]} "
              f"(holdout dti {best[1]['dti']:.4f}, "
              f"{int((df.emit_thresh(field, valid, best[0]) > 0).sum())} px)", flush=True)
        summaries[arm] = {
            "n_features": len(base),
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "calibrated_threshold": best[0],
            "holdout_dti": best[1]["dti"],
            "holdout_px": int(hold.sum()),
            "field_mean_valid": float(field[valid].mean()),
            "field_mean_holdout": float(field[hold].mean()),
        }

    (out_dir / "real_field_meta.json").write_text(json.dumps(summaries, indent=2))
    print(f"[train] wrote {out_dir}/real_field_meta.json in {time.time()-t0:.0f} s",
          flush=True)

    if args.emission:
        for spec in args.emission:
            policy, _, param = spec.partition(":")
            arm = args.arms[-1]
            field = np.load(out_dir / f"real_field_{arm}.npy")
            if policy == "thresh":
                pred = df.emit_thresh(field, valid, float(param))
            elif policy == "thresh_d1":
                pred = vr.dilate_valid(df.emit_thresh(field, valid, float(param)), valid, 1)
            elif policy == "thresh_d2":
                pred = vr.dilate_valid(df.emit_thresh(field, valid, float(param)), valid, 2)
            elif policy == "topk":
                pred = df.emit_topk(field, valid, int(float(param) * int(valid.sum())))
            elif policy == "nms3":
                pred = df.emit_nms(field, valid, int(float(param) * int(valid.sum())), 3)
            else:
                raise SystemExit(f"unknown emission policy {policy!r}")
            name = f"real_emission_{arm}_{spec.replace(':', '')}.npy"
            np.save(out_dir / name, pred)
            print(f"[train] {spec}: {int((pred > 0).sum())} px -> {out_dir/name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
