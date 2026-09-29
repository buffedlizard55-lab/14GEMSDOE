#!/usr/bin/env python3
"""Train the real-data model and write a submission-ready prediction field.

This is the *deployment* counterpart of ``scripts/validate_real.py``:

    gate (component folds)   ->  answers "which channels, and which emission
                                  policy, actually help on the real rasters?"
    this script              ->  trains on the submission-time context (the full
                                  catalogue minus a held-out slice), predicts the
                                  whole grid, calibrates the emission on that
                                  hidden slice, and writes the binary emission
                                  that ``scripts/build_submission.py`` turns
                                  into a conformant GeoTIFF.

Hide-and-recover is structural here, exactly as in the gate: the feature
channels are built from ``context = labels & ~hold``, so every channel derived
from the catalogue ("distance to the nearest mapped trace", strike, relay
corridors, densities) is blind to the held-out components that the emission is
scored against.  The held-out slice is therefore an honest calibration set, and
it is the only thing the emitted budget is fitted on.

Everything is computed from the official rasters in ``data/raw`` with the same
channel library the gate uses, so the field the site ships is the same kind of
object the gate measured.

Outputs (all git-ignored):
    artifacts/real_field_<arm>.npy       float32 probability field, full grid
    artifacts/real_field_meta.json       per-arm policy metadata + holdout score
    artifacts/real_emission_<arm>.npy    binary emission ready for build_submission

Usage:
    ./.venv/bin/python scripts/train_real_full.py --arms all
    ./.venv/bin/python scripts/train_real_full.py --arms geom_curv --holdout-fraction 0.30
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
sys.path.insert(0, str(ROOT / "scripts"))

from gems import realdata as rd  # noqa: E402

# Importing the gate module keeps the channel definitions in exactly one place.
import validate_real as vr  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="*", default=["all"],
                    help="gate arm names (geom, geo, geom_curv, all, ...)")
    ap.add_argument("--holdout-fraction", type=float, default=0.30,
                    help="share of catalogue components hidden from the training "
                         "channels and used to calibrate the emission")
    ap.add_argument("--n-pos", type=int, default=40000)
    ap.add_argument("--n-neg", type=int, default=80000)
    ap.add_argument("--iters", type=int, default=150)
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--chunk-rows", type=int, default=256)
    ap.add_argument("--out-dir", default="artifacts")
    ap.add_argument("--cache", default="data/processed/channels")
    args = ap.parse_args()

    t0 = time.time()
    labels = rd.read_labels()
    valid = np.load(ROOT / "data/processed/valid_mask.npy").astype(bool)
    print(f"[train] grid {labels.shape} valid={int(valid.sum())} "
          f"catalogue={int(labels.sum())}", flush=True)

    lab, n = ndimage.label(labels, structure=np.ones((3, 3), dtype=int))
    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(np.arange(1, n + 1))
    n_hold = max(1, int(round(args.holdout_fraction * n)))
    hold_ids = set(perm[:n_hold].tolist())
    hold = np.isin(lab, list(hold_ids))               # calibration slice
    context = labels & ~hold                          # what the features see
    print(f"[train] {n} components: {n_hold} hidden ({int(hold.sum())} px), "
          f"context {int(context.sum())} px", flush=True)

    static = vr.build_static_channels(ROOT / args.cache)
    print(f"[train] static channels in {time.time()-t0:.0f} s", flush=True)
    geom = vr.build_geom_channels(context)
    print(f"[train] geometry channels in {time.time()-t0:.0f} s", flush=True)

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries: dict[str, dict] = {}
    for arm in args.arms:
        ta = time.time()
        names, r5, geo = vr.arm_channels(arm)
        ch = dict(geom)
        if geo:
            ch.update(static)
        if r5:
            ch.update(vr.build_round5_channels(context, static, valid, r5))
        names_now = [nm for nm in names if nm in ch]
        # training pixels: real context traces are positive, everything else in
        # the valid footprint is background; the hidden slice is only used later.
        idx, y = vr.sample_pixels(context, valid, np.random.default_rng(args.seed),
                                  args.n_pos, args.n_neg)
        X = vr.design_matrix(ch, names_now, idx)
        mu, sd = vr.standardize_fit(X)
        beta = vr.logistic_fit((X - mu) / sd, y, np.ones_like(y),
                               n_iter=args.iters, lr=0.5, l2=1e-3)
        del X
        field = vr.predict_full_std(beta, mu, sd, ch, names_now, valid,
                                    args.chunk_rows)
        del ch
        np.save(out_dir / f"real_field_{arm}.npy", field.astype(np.float32))

        # emission budget calibrated on the HIDDEN components only
        pol = vr.calibrate_policy(field, hold, valid, seed=args.seed)
        emitted = vr.emit_policy(field, pol["policy"], pol["param"], valid)
        np.save(out_dir / f"real_emission_{arm}.npy", emitted.astype(np.float32))
        d = vr.score_field(emitted, hold, valid)
        summaries[arm] = {
            "arm": arm, "spec": vr.ARM_SPEC.get(arm, arm),
            "n_features": len(names_now), "n_train_px": int(idx.size),
            "hidden_components": n_hold, "hidden_px": int(hold.sum()),
            "n_emit": int((emitted > 0).sum()),
            "policy": pol["policy"], "param": float(pol["param"]),
            "hidden_dti": float(pol["calib_dti"]) if pol["calib_dti"] else None,
            "hidden_tp": int(d["tp"]), "hidden_fp": int(d["fp"]),
            "hidden_fn": int(d["fn"]),
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_s": round(time.time() - ta, 1),
        }
        hd = summaries[arm]["hidden_dti"]
        print(f"[train][{arm}] {len(names_now)} feats, {pol['policy']}:{pol['param']:g}, "
              f"hidden dti={'n/a' if hd is None else format(hd, '.4f')}, "
              f"{summaries[arm]['n_emit']} px ({summaries[arm]['elapsed_s']:.0f} s)",
              flush=True)

    (out_dir / "real_field_meta.json").write_text(json.dumps(summaries, indent=2))
    print(f"[train] wrote {out_dir}/real_field_meta.json in {time.time()-t0:.0f} s",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
