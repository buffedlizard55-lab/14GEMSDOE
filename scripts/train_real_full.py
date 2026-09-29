#!/usr/bin/env python3
"""Train the real-data model on the deployment view and write prediction fields.

This is the *deployment* counterpart of ``scripts/validate_real.py``:

    gate (component folds)   ->  answers "which channels and which emission
                                 policy actually help on the real rasters?"
                                 (hide-and-recover ensemble; its four fold
                                 fields are what scripts/build_real_submission.py
                                 averages)
    this script              ->  trains ONE hide-and-recover model against the
                                 full catalogue and predicts the whole grid
                                 from the submission-time view (the complete
                                 catalogue as context), then calibrates the
                                 emission policy on hidden CALIB components.

Protocol (matches the gate's component protocol, without a TEST split — at
deployment there is no labelled test set; the target is unlabelled structure):

    components -> HIDE   (``--hide-fraction``, default 0.35)  training positives
                CALIB   (``--calib-fraction``, default 0.20)  emission calibration
                rest    visible context
    train view : geometry/context channels built from ``labels & ~hide``
                 (CALIB stays visible, exactly like the gate's feature_ctx),
                 positives = HIDE pixels, negatives = background.  Hide-and-
                 recover: "distance to a known trace = 0" cannot leak the
                 answer because the recovered structures are not in context.
    deploy view: geometry/context channels built from the FULL catalogue
                 (everything visible — what a submission sees), which is what
                 the scored, unmapped structures are predicted against.

Everything is computed from the official rasters in ``data/raw`` with the same
channel library the gate uses (``scripts/validate_real.py``), so the fields this
script writes are the same kind of object the gate measured — no hand-tuning
between the two.

Outputs (all git-ignored):
    artifacts/real_field_<arm>.npy        float32 probability field, full grid
    artifacts/real_field_<arm>.json       policy metadata (threshold, counts)
    artifacts/real_emission_<arm>_*.npy   binary emission (1.0 = emit) ready for
                                          scripts/build_submission.py

Usage:
    ./.venv/bin/python scripts/train_real_full.py --arms geom_horse all6 \\
        --n-pos 20000 --n-neg 40000 --iters 150 --out-dir artifacts
    ./.venv/bin/python scripts/train_real_full.py --arms all6 \\
        --emission topk:0.01        # extra explicit emission specs (optional)
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
from gems import realdata as rd  # noqa: E402

# Importing the gate module keeps the feature definitions in exactly one place.
sys.path.insert(0, str(ROOT / "scripts"))
import validate_real as vr  # noqa: E402

from train_hide_recover import logistic_fit, standardize_fit  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="*", default=["geom_horse"],
                    help=f"feature arms; choices: {', '.join(vr.ARM_SPEC)}")
    ap.add_argument("--hide-fraction", type=float, default=0.35,
                    help="share of catalogue components hidden from the context "
                         "and used as training positives (hide-and-recover)")
    ap.add_argument("--calib-fraction", type=float, default=0.20,
                    help="share of catalogue components used (only) to calibrate "
                         "the emission policy")
    ap.add_argument("--iters", "--max-iter", dest="iters", type=int, default=150)
    ap.add_argument("--n-pos", type=int, default=20000)
    ap.add_argument("--n-neg", type=int, default=40000)
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--chunk-rows", type=int, default=256)
    ap.add_argument("--out-dir", default="artifacts")
    ap.add_argument("--emission", nargs="*", default=None,
                    help="extra emission specs, e.g. 'topk:0.01' 'thresh:0.5' "
                         "'nms3:0.01' — written in addition to the CALIB-"
                         "calibrated policy")
    args = ap.parse_args()

    bad = [a for a in args.arms if a not in vr.ARM_SPEC]
    if bad:
        raise SystemExit(f"unknown arm(s) {bad}; choices: {list(vr.ARM_SPEC)}")

    t0 = time.time()
    labels = rd.read_labels()
    tpl = rd.read_template()
    valid = np.load(ROOT / "data/processed/valid_mask.npy").astype(bool)
    if valid.shape != labels.shape:      # smoke-crop safety: never mix grids
        valid = tpl["valid"]
    shape = labels.shape
    print(f"[train] grid {shape} valid={int(valid.sum())} "
          f"catalogue={int(labels.sum())}", flush=True)

    # ---- component split: HIDE (positives) / CALIB / visible ----------------
    lab, n = ndimage.label(labels, structure=np.ones((3, 3), dtype=int))
    rng = np.random.default_rng(args.seed)
    perm = rng.permutation(np.arange(1, n + 1))
    n_hide = max(1, int(round(args.hide_fraction * n)))
    n_calib = max(1, int(round(args.calib_fraction * n)))
    hide_ids = perm[:n_hide]
    calib_ids = perm[n_hide:n_hide + n_calib]
    hide = np.isin(lab, hide_ids)
    calib = np.isin(lab, calib_ids)
    feature_ctx = labels & ~hide                 # gate's feature_ctx without TEST
    print(f"[train] {n} components: HIDE {n_hide} ({int(hide.sum())} px) / "
          f"CALIB {n_calib} ({int(calib.sum())} px) / visible "
          f"{n - n_hide - n_calib}", flush=True)

    # ---- channels ----------------------------------------------------------
    cache = ROOT / "data/processed/channels"
    print("[train] building geophysical channels …", flush=True)
    static = vr.build_static_channels(cache, quiet=False, use_cache=True)
    static = {k: np.asarray(v, dtype=np.float16) for k, v in static.items()}
    print(f"[train] static channels in {time.time()-t0:.0f} s", flush=True)

    # ---- phase 1: train every arm against the hidden components ------------
    geom_train = vr.build_geom_channels(feature_ctx)
    print(f"[train] train-view geometry in {time.time()-t0:.0f} s", flush=True)
    betas: dict[str, tuple] = {}
    names_by_arm: dict[str, list[str]] = {}
    for arm in args.arms:
        ta = time.time()
        names, r5, geo = vr.arm_channels(arm)
        ch_train = dict(geom_train)
        if geo:
            ch_train.update(static)
        if r5:
            ch_train.update(vr.build_round5_channels(feature_ctx, static, valid, r5))
        names_now = [nm for nm in names if nm in ch_train]
        idx, y = vr.sample_pixels(hide, valid, np.random.default_rng(args.seed),
                                  args.n_pos, args.n_neg)
        X = vr.design_matrix(ch_train, names_now, idx)
        mu, sd = standardize_fit(X)
        beta = logistic_fit((X - mu) / sd, y, np.ones_like(y),
                            n_iter=args.iters, lr=0.5, l2=1e-3)
        del X, ch_train
        betas[arm] = (beta, mu, sd)
        names_by_arm[arm] = names_now
        print(f"[train][{arm}] trained on {idx.size} px ({len(names_now)} feats) "
              f"in {time.time()-ta:.0f} s", flush=True)
    del geom_train

    # ---- phase 2: predict with the submission-time context -----------------
    # Deployment view: the FULL catalogue is visible (a submission sees every
    # mapped trace); the scored structures are the ones that are not in it.
    geom_pred = vr.build_geom_channels(labels)
    print(f"[train] deploy-view geometry in {time.time()-t0:.0f} s", flush=True)

    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for arm in args.arms:
        ta = time.time()
        names, r5, geo = vr.arm_channels(arm)
        ch_pred = dict(geom_pred)
        if geo:
            ch_pred.update(static)
        if r5:
            ch_pred.update(vr.build_round5_channels(labels, static, valid, r5))
        names_now = [nm for nm in names_by_arm[arm] if nm in ch_pred]
        beta, mu, sd = betas[arm]
        field = vr.predict_full_std(beta, mu, sd, ch_pred, names_now, valid,
                                    args.chunk_rows)
        del ch_pred
        print(f"[train][{arm}] field in {time.time()-ta:.0f} s "
              f"(mean {float(field[valid].mean()):.4f})", flush=True)
        np.save(out_dir / f"real_field_{arm}.npy", field.astype(np.float32))

        # CALIB-calibrated emission — the same policy family the gate measures.
        pol = vr.calibrate_policy(field, calib, valid, seed=100)
        emitted = vr.emit_policy(field, pol["policy"], pol["param"], valid)
        n_emit = int((emitted > 0).sum())
        tag = f"{pol['policy']}{pol['param']:g}"
        np.save(out_dir / f"real_emission_{arm}_{tag}.npy", emitted)
        print(f"[train][{arm}] calibrated {pol['policy']}:{pol['param']:g} "
              f"(calib dti {pol['calib_dti']:.4f}, {n_emit} px)", flush=True)

        summary = {
            "arm": arm,
            "spec": vr.ARM_SPEC.get(arm, arm),
            "n_features": len(names_now),
            "features": names_now,
            "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "protocol": {
                "hide_fraction": args.hide_fraction,
                "calib_fraction": args.calib_fraction,
                "n_components": int(n),
                "train_view": "labels & ~hide (CALIB visible, gate-equivalent)",
                "deploy_view": "full catalogue (submission-time context)",
                "learner": f"logistic regression, {args.iters} GD iters, lr 0.5, l2 1e-3",
                "n_pos": args.n_pos, "n_neg": args.n_neg, "seed": args.seed,
            },
            "calib_policy": pol["policy"],
            "calib_param": float(pol["param"]),
            "calib_dti": float(pol["calib_dti"]),
            "n_emit": n_emit,
            "emit_fraction": n_emit / float(valid.sum()),
            "field_mean_valid": float(field[valid].mean()),
            "field_mean_hide": (float(field[hide].mean()) if hide.any() else None),
            "field_mean_calib": (float(field[calib].mean()) if calib.any() else None),
        }
        (out_dir / f"real_field_{arm}.json").write_text(json.dumps(summary, indent=2))
        summaries[arm] = summary

        if args.emission:
            for spec in args.emission:
                policy, _, param = spec.partition(":")
                if policy == "thresh":
                    pred = df.emit_thresh(field, valid, float(param))
                elif policy == "topk":
                    pred = df.emit_topk(field, valid,
                                        int(float(param) * int(valid.sum())))
                elif policy == "nms3":
                    pred = df.emit_nms(field, valid,
                                       int(float(param) * int(valid.sum())), 3)
                else:
                    raise SystemExit(f"unknown emission policy {policy!r}")
                name = f"real_emission_{arm}_{spec.replace(':', '')}.npy"
                np.save(out_dir / name, pred)
                print(f"[train][{arm}] {spec}: {int((pred > 0).sum())} px "
                      f"-> {out_dir/name}", flush=True)
        del field, emitted

    (out_dir / "real_field_meta.json").write_text(json.dumps(summaries, indent=2))
    print(f"[train] wrote {out_dir}/real_field_meta.json in {time.time()-t0:.0f} s",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
