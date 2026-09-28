#!/usr/bin/env python3
"""Round-2 hypothesis A/B on the spatially-blocked holdout.

This is the gate the standing prompt demands: *"Validate the top candidate on
our spatially-blocked holdout set before touching a weekly submission slot - do
not spend a submission slot on an idea that hasn't beaten the current holdout
best."*

Protocol (identical for every arm, so the comparison is a pure feature A/B):

  for each seed, for each spatial fold k
      context = catalogue traces OUTSIDE fold k's blocks, purge buffer applied
      train   = hide-and-recover logistic model, labels = context traces,
                features = catalogue geometry (from context) + field features
                + the arm's extra block; hidden components are re-drawn every
                epoch and the anti-leak assertion runs every epoch
      score   = DTI(prediction, fold-k traces)                -> "recovery"
                DTI(prediction, blind_traces)                 -> "discovery"

``blind_traces`` are faults that exist in the synthetic geophysics but are
absent from the catalogue by construction (>= ``blind_min_sep_px`` from every
catalogue trace) and are never used as training labels.  They are the local
analogue of the sponsor's private test set, which staff confirmed consists of
"any fault pixel not already captured by USGS/INGENIOUS" (forum 11536).

HONESTY RULE: this script cannot produce a number for the real competition.  The
real rasters are behind a DrivenData login (verified: the data tab redirects to
/accounts/login/).  What it validates is (a) the machinery, and (b) the
*sign* and rough magnitude of each arm's effect under a geologically explicit
synthetic forward model.  When ``data/processed/`` exists the same script runs
unchanged on the real rasters.

Usage:
    python3 scripts/validate_round2.py                 # default quick sweep
    python3 scripts/validate_round2.py --arms N1 N2 --seeds 11 12 --shape 224
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems.blocks import assign_folds, holdout_masks  # noqa: E402
from gems.dti import dti  # noqa: E402
from gems.hypotheses import ARMS  # noqa: E402
from gems.synthesize import make_region  # noqa: E402
from scripts.train_hide_recover import train  # noqa: E402

DISCOVERY_RADIUS_PX = 3.0  # same 300 m kernel the prize uses

ALL_ARMS = list(ARMS) + ["GEO-ONLY", "BLEND", "BLEND-ADD", "BLEND-MUL"]


def run_arm(arm: str, *, shape, seeds, epochs, hide_fraction, block_px,
            n_folds, buffer_px, verbose, args_blend_weight: float = 0.5) -> dict:
    """Blocked holdout for one feature arm, averaged over seeds and folds.

    ``arm`` values:
      baseline / N1 / N2 / N3 / N5 / ALL  - logistic classifier + that feature block
      GEO-ONLY                            - emission is the geophysical prior alone
      BLEND                               - max(classifier, geophysical prior)
      BLEND-ADD  w=0.25                   - classifier + 0.25 * prior (clipped)
      BLEND-MUL  w=0.5                    - classifier * (1 + 0.5 * prior)
    """
    from gems.hypotheses import build_arm_features
    from gems.features import distance_and_azimuth

    rec, disc, comb = [], [], []
    fold_rows = []
    t0 = time.time()
    for seed in seeds:
        region = make_region(shape=shape, seed=seed)
        traces = region["traces"]
        blind = region["blind_traces"]
        if not blind.any():
            raise SystemExit(f"seed {seed} produced no blind traces; raise n_blind")
        fold_map = assign_folds(shape, block_px, n_folds, seed=1000 + seed)
        for k in range(n_folds):
            ctx_m, test_m = holdout_masks(traces, fold_map, k,
                                          policy="buffer", buffer_px=buffer_px)
            if test_m.sum() == 0 or ctx_m.sum() == 0:
                continue

            # geophysical prior: catalogue-independent, so it is identical
            # whatever the context is (that is exactly why it is leak-free)
            geo = build_arm_features(region, "ALL")
            geo_prior = np.zeros(shape, dtype=np.float32)
            for key in ("n1_term_field", "n2_seis_ridge", "n3_cap_margin"):
                v = geo.get(key)
                if v is None:
                    continue
                v = np.asarray(v, dtype=np.float64)
                m = float(v.max())
                if m > 0:
                    geo_prior = np.maximum(geo_prior, (v / m).astype(np.float32))

            if arm == "GEO-ONLY":
                pred = geo_prior
                n_feat = 0
            else:
                # the model only ever sees the context; the fold's traces and
                # the blind faults are never training labels
                sub = dict(region)
                sub["traces"] = ctx_m
                res = train(sub, hide_fraction=hide_fraction, epochs=epochs,
                            seed=seed * 31 + k, arm=arm, verbose=False)
                pred = res["pred_full"]
                n_feat = len(res["feature_names"])
                if arm == "BLEND":
                    pred = np.maximum(pred, geo_prior).astype(np.float32)
                elif arm == "BLEND-ADD":
                    pred = np.clip(pred + 0.25 * geo_prior, 0.0, 1.0).astype(np.float32)
                elif arm == "BLEND-MUL":
                    pred = np.clip(pred * (1.0 + args_blend_weight * geo_prior),
                                   0.0, 1.0).astype(np.float32)

            # the prize's own masking rule: pixels of known faults are excluded.
            # Emitting on the visible context therefore costs nothing and gains
            # nothing; we score exactly the off-context population.
            target = test_m | blind
            r_rec = dti(pred, test_m, radius_px=DISCOVERY_RADIUS_PX)
            r_disc = dti(pred, blind, radius_px=DISCOVERY_RADIUS_PX)
            r_comb = dti(pred, target, radius_px=DISCOVERY_RADIUS_PX)
            rec.append(r_rec["dti"])
            disc.append(r_disc["dti"])
            comb.append(r_comb["dti"])
            fold_rows.append({
                "seed": seed, "fold": k, "n_ctx_px": int(ctx_m.sum()),
                "n_test_px": int(test_m.sum()),
                "recovery_dti": r_rec["dti"], "discovery_dti": r_disc["dti"],
                "combined_dti": r_comb["dti"],
                "n_target_px": int(target.sum()),
            })
            if verbose:
                print(f"    arm={arm:9s} seed={seed} fold={k} "
                      f"recovery={r_rec['dti']:.4f} discovery={r_disc['dti']:.4f} "
                      f"combined={r_comb['dti']:.4f}")
    return {
        "arm": arm,
        "n_features": n_feat,
        "n_folds_scored": len(rec),
        "recovery_dti_mean": float(np.mean(rec)) if rec else 0.0,
        "recovery_dti_std": float(np.std(rec)) if rec else 0.0,
        "discovery_dti_mean": float(np.mean(disc)) if disc else 0.0,
        "discovery_dti_std": float(np.std(disc)) if disc else 0.0,
        "combined_dti_mean": float(np.mean(comb)) if comb else 0.0,
        "combined_dti_std": float(np.std(comb)) if comb else 0.0,
        "folds": fold_rows,
        "elapsed_s": round(time.time() - t0, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", default=["baseline", "N1", "N2", "N3",
                                                  "N5", "GEO-ONLY", "BLEND",
                                                  "BLEND-ADD", "BLEND-MUL"],
                    choices=ALL_ARMS)
    ap.add_argument("--seeds", nargs="+", type=int, default=[11, 12])
    ap.add_argument("--shape", type=int, default=192)
    ap.add_argument("--epochs", type=int, default=6)
    ap.add_argument("--hide-fraction", type=float, default=0.35)
    ap.add_argument("--block-px", type=int, default=48)
    ap.add_argument("--n-folds", type=int, default=4)
    ap.add_argument("--buffer-px", type=int, default=3)
    ap.add_argument("--out", default="artifacts/holdout_round2.json")
    ap.add_argument("--blend-weight", type=float, default=0.5,
                    help="w in classifier*(1+w*prior) for BLEND-MUL")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    verbose = not args.quiet
    results = []
    for arm in args.arms:
        if verbose:
            print(f"  arm {arm} ...")
        results.append(run_arm(arm, shape=(args.shape, args.shape), seeds=args.seeds,
                               epochs=args.epochs, hide_fraction=args.hide_fraction,
                               block_px=args.block_px, n_folds=args.n_folds,
                               buffer_px=args.buffer_px, verbose=verbose,
                               args_blend_weight=args.blend_weight))

    base = next((r for r in results if r["arm"] == "baseline"), None)
    for r in results:
        if base is not None and r is not base:
            r["delta_recovery_vs_baseline"] = round(
                r["recovery_dti_mean"] - base["recovery_dti_mean"], 5)
            r["delta_discovery_vs_baseline"] = round(
                r["discovery_dti_mean"] - base["discovery_dti_mean"], 5)
            r["delta_combined_vs_baseline"] = round(
                r["combined_dti_mean"] - base["combined_dti_mean"], 5)
            # GATE: the prize scores only faults absent from the visible
            # catalogue, so the gate metric is the combined (off-context) DTI.
            r["beats_baseline_on_combined"] = bool(
                r["combined_dti_mean"] > base["combined_dti_mean"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "protocol": {
            "spatial_blocks_px": args.block_px,
            "n_folds": args.n_folds,
            "purge_buffer_px": args.buffer_px,
            "hide_fraction": args.hide_fraction,
            "epochs": args.epochs,
            "shape": [args.shape, args.shape],
            "seeds": args.seeds,
            "discovery_target": "blind_traces (absent from catalogue, never a label)",
            "recovery_target": "fold-held-out catalogue traces",
            "model": "logistic regression, numpy, identical across arms",
        },
        "caveat": (
            "SYNTHETIC forward model. The competition rasters are behind a "
            "DrivenData login (verified). These numbers validate the machinery "
            "and the sign of each arm's effect, not the real leaderboard score."
        ),
        "results": results,
    }
    out.write_text(json.dumps(payload, indent=2))

    print("\n=== round-2 blocked-holdout A/B ===")
    print(f"{'arm':10s} {'#feat':>6s} {'recovery':>10s} {'discovery':>11s} "
          f"{'combined':>10s} {'d_comb':>8s}  gate")
    for r in results:
        d_comb = r.get("delta_combined_vs_baseline", 0.0)
        gate = "baseline" if r["arm"] == "baseline" else (
            "PASS (beats baseline on the off-catalogue target)"
            if r.get("beats_baseline_on_combined") else "fail")
        print(f"{r['arm']:10s} {r['n_features']:6d} "
              f"{r['recovery_dti_mean']:10.4f} {r['discovery_dti_mean']:11.4f} "
              f"{r['combined_dti_mean']:10.4f} {d_comb:+8.4f}  {gate}")

    winners = [r for r in results if r.get("beats_baseline_on_combined")]
    print(f"\nwrote {out}")
    if winners:
        print("SLOT-ELIGIBLE arms (must still be re-run on the real rasters before "
              "upload): " + ", ".join(w["arm"] for w in winners))
    else:
        print("No arm beat the baseline on the off-catalogue target -> "
              "no submission slot may be spent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
