#!/usr/bin/env python3
"""Round-3 hypothesis gate — same blocked holdout, same protocol as round 2.

The standing prompt: "Validate the top candidate on our spatially-blocked
holdout set before touching a weekly submission slot."  Round 3 re-runs the
EXACT round-2 protocol (176 px regions, seeds 11/12/13, 4 folds of 48 px
blocks with a 3 px purge buffer, 5 hide-and-recover epochs, hide fraction
0.35, blend weight 0.5) so every number is comparable with
``artifacts/holdout_round2.json``.

Pre-registered arms (no post-hoc selection; the full list runs whatever the
outcome):

  baseline    round-2 baseline (catalogue geometry + field bands)  — reference
  BMUL        round-2 PROMOTED incumbent: classifier x (1 + 0.5 * prior)
              where the prior is the round-2 ALL geophysical block
  R3A         baseline features + tip-continuation cones (catalogue geometry,
              computed from the visible context only)
  R3B         baseline features + completeness-angle residual
  R3C         baseline features + magnetic-basement lineaments
  R3D         baseline features + scarplet curvature-linkage
  R3AC        baseline features + R3A + R3C
  BMUL-R3A    classifier over baseline+R3A, boosted by the round-2 prior
  BMUL-R3AC   classifier over baseline+R3AC, boosted by the round-2 prior

Gate metric: combined DTI on the fold's off-context population
(held-out catalogue traces + blind traces), identical to round 2.

HONESTY: synthetic forward model (see round-2 honesty statement).  The real
rasters are still login-gated; the same script runs unchanged on
``data/processed/``.

Usage:
    python3 scripts/validate_round3.py
    python3 scripts/validate_round3.py --arms R3A R3C --seeds 11
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
from gems.hypotheses import build_arm_features  # noqa: E402
from gems.synthesize import make_region  # noqa: E402
from scripts.train_hide_recover import train  # noqa: E402

DISCOVERY_RADIUS_PX = 3.0          # same 300 m kernel the prize uses
BLEND_W = 0.5                      # round-2 interior optimum

ALL_ARMS = ("baseline", "BMUL", "R3A", "R3B", "R3C", "R3D", "R3AC",
            "BMUL-R3A", "BMUL-R3AC", "BMUL-R3Dp")
# which classifier feature block each arm trains on.  BMUL must be EXACTLY
# the round-2 promoted emission: classifier over the ALL block, multiplied by
# the prior (validate_round2.py mapped its BLEND-* arms onto ALL).
FEATURE_ARM = {
    "baseline": "baseline",
    "BMUL": "ALL",
    "R3A": "R3A",
    "R3B": "R3B",
    "R3C": "R3C",
    "R3D": "R3D",
    "R3AC": "R3AC",
    "BMUL-R3A": "ALLR3A",
    "BMUL-R3AC": "ALLR3AC",
    "BMUL-R3Dp": "ALL",
}
# which arms multiply the classifier by the round-2 geophysical prior
PRIOR_BOOSTED = ("BMUL", "BMUL-R3A", "BMUL-R3AC", "BMUL-R3Dp")


def round2_geo_prior(region: dict) -> np.ndarray:
    """The round-2 BLEND-MUL prior: max-normalised ALL geophysical block."""
    geo = build_arm_features(region, "ALL")
    shape = np.asarray(region["traces"]).shape
    prior = np.zeros(shape, dtype=np.float32)
    for key in ("n1_term_field", "n2_seis_ridge", "n3_cap_margin"):
        v = geo.get(key)
        if v is None:
            continue
        v = np.asarray(v, dtype=np.float64)
        m = float(v.max())
        if m > 0:
            prior = np.maximum(prior, (v / m).astype(np.float32))
    return prior


def run_arm(arm: str, *, shape, seeds, epochs, hide_fraction, block_px,
            n_folds, buffer_px, verbose) -> dict:
    feature_arm = FEATURE_ARM[arm]
    boosted = arm in PRIOR_BOOSTED
    rec, disc, comb = [], [], []
    fold_rows = []
    t0 = time.time()
    n_feat = 0
    for seed in seeds:
        region = make_region(shape=shape, seed=seed)
        traces = region["traces"]
        blind = region["blind_traces"]
        if not blind.any():
            raise SystemExit(f"seed {seed} produced no blind traces; raise n_blind")
        prior = round2_geo_prior(region) if boosted else None
        fold_map = assign_folds(shape, block_px, n_folds, seed=1000 + seed)
        for k in range(n_folds):
            ctx_m, test_m = holdout_masks(traces, fold_map, k,
                                          policy="buffer", buffer_px=buffer_px)
            if test_m.sum() == 0 or ctx_m.sum() == 0:
                continue
            # the model only ever sees the context; the fold's traces and the
            # blind faults are never training labels.  R3A/R3B read the context
            # via sub["traces"] and the explicit context_mask in train().
            sub = dict(region)
            sub["traces"] = ctx_m
            res = train(sub, hide_fraction=hide_fraction, epochs=epochs,
                        seed=seed * 31 + k, arm=feature_arm, verbose=False)
            pred = res["pred_full"]
            n_feat = len(res["feature_names"])
            if boosted:
                pred = np.clip(pred * (1.0 + BLEND_W * prior), 0.0, 1.0).astype(np.float32)

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
            })
            if verbose:
                print(f"    arm={arm:9s} seed={seed} fold={k} "
                      f"recovery={r_rec['dti']:.4f} discovery={r_disc['dti']:.4f} "
                      f"combined={r_comb['dti']:.4f}", flush=True)
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
    ap.add_argument("--arms", nargs="+", default=list(ALL_ARMS), choices=ALL_ARMS)
    ap.add_argument("--seeds", nargs="+", type=int, default=[11, 12, 13])
    ap.add_argument("--shape", type=int, default=176)
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--hide-fraction", type=float, default=0.35)
    ap.add_argument("--block-px", type=int, default=48)
    ap.add_argument("--n-folds", type=int, default=4)
    ap.add_argument("--buffer-px", type=int, default=3)
    ap.add_argument("--out", default="artifacts/holdout_round3.json")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    verbose = not args.quiet
    results = []
    for arm in args.arms:
        if verbose:
            print(f"  arm {arm} ...", flush=True)
        results.append(run_arm(arm, shape=(args.shape, args.shape), seeds=args.seeds,
                               epochs=args.epochs, hide_fraction=args.hide_fraction,
                               block_px=args.block_px, n_folds=args.n_folds,
                               buffer_px=args.buffer_px, verbose=verbose))

    base = next((r for r in results if r["arm"] == "baseline"), None)
    incumbent = next((r for r in results if r["arm"] == "BMUL"), None)
    ref = incumbent or base
    for r in results:
        if base is not None and r is not base:
            r["delta_recovery_vs_baseline"] = round(
                r["recovery_dti_mean"] - base["recovery_dti_mean"], 5)
            r["delta_discovery_vs_baseline"] = round(
                r["discovery_dti_mean"] - base["discovery_dti_mean"], 5)
            r["delta_combined_vs_baseline"] = round(
                r["combined_dti_mean"] - base["combined_dti_mean"], 5)
        if ref is not None and r is not ref:
            r["delta_combined_vs_incumbent"] = round(
                r["combined_dti_mean"] - ref["combined_dti_mean"], 5)
            # the gate: a candidate earns a slot only by beating the INCUMBENT
            r["beats_incumbent_on_combined"] = bool(
                r["combined_dti_mean"] > ref["combined_dti_mean"])

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
            "blend_weight": BLEND_W,
            "identical_to_round2_protocol": True,
            "discovery_target": "blind_traces (absent from catalogue, never a label)",
            "recovery_target": "fold-held-out catalogue traces",
            "gate_metric": "combined DTI vs incumbent BMUL (round-2 promoted arm)",
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
    print(f"\nwrote {out}")
    print(f"{'arm':12s} {'n_feat':>6s} {'recovery':>9s} {'discovery':>9s} "
          f"{'combined':>9s} {'d vs incumbent':>14s}")
    for r in results:
        d = r.get("delta_combined_vs_incumbent")
        ds = "—" if d is None else f"{d:+.4f}"
        print(f"{r['arm']:12s} {r['n_features']:6d} {r['recovery_dti_mean']:9.4f} "
              f"{r['discovery_dti_mean']:9.4f} {r['combined_dti_mean']:9.4f} {ds:>14s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
