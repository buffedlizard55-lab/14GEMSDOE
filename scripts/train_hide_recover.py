#!/usr/bin/env python3
"""Train a fault-probability model through the hide-and-recover protocol.

Model: per-pixel logistic regression (numpy, no heavy framework needed) over
       [catalogue-geometry features computed from the CONTEXT traces,
        field features (elevation/magnetics analogues or the real 19 bands)].
       The reference U-Net (https://github.com/drivendataorg/gems-prize-reference-solution)
       is the intended upgrade once a GPU and the real 418 MB feature stack are
       present; the protocol below is model-agnostic.

Protocol (enforced, not advisory):
  each epoch
    1. hide a random fraction of connected catalogue components (whole traces)
    2. recompute ALL catalogue-geometry features from the visible context only
    3. train on labels = full catalogue (visible + hidden), features never
       contain hidden-trace information (anti-leak assertion runs every epoch)
    4. score DTI on hidden components only -> model selection number
  final model: averaged weights over the last N epochs (simple ensemble)

Usage:
  python3 scripts/train_hide_recover.py --demo          # synthetic region
  python3 scripts/train_hide_recover.py                 # real data in data/processed
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems import hide_recover as hr  # noqa: E402
from gems.features import build_catalogue_feature_stack  # noqa: E402
from gems.dti import dti  # noqa: E402


def standardize_fit(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = X.mean(axis=0)
    sd = X.std(axis=0) + 1e-6
    return mu, sd


def logistic_fit(X: np.ndarray, y: np.ndarray, w: np.ndarray,
                 n_iter: int = 200, lr: float = 0.5, l2: float = 1e-3,
                 rng: np.random.Generator | None = None) -> np.ndarray:
    """Weighted logistic regression via full-batch gradient descent."""
    n, d = X.shape
    beta = np.zeros(d + 1, dtype=np.float64)
    Xb = np.concatenate([X, np.ones((n, 1))], axis=1)
    wsum = w.sum() + 1e-12
    for _ in range(n_iter):
        z = Xb @ beta
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        g = (Xb.T @ (w * (p - y))) / wsum + l2 * np.concatenate([beta[:-1], [0.0]])
        beta -= lr * g
    return beta


def predict_proba(beta: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xb = np.concatenate([X, np.ones((X.shape[0], 1))], axis=1)
    z = Xb @ beta
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def build_feature_matrix(region: dict, context_mask: np.ndarray,
                         extra_keys: tuple[str, ...] = ("f_elev", "f_mag", "strain"),
                         arm: str = "baseline"):
    """Assemble the design matrix.

    ``arm`` selects the round-2 hypothesis feature block (gems/hypotheses.py).
    Arms are additive and catalogue-independent, so the A/B is a pure feature
    comparison under an identical hide-and-recover protocol.
    """
    from gems.hypotheses import build_arm_features

    feats = build_catalogue_feature_stack(context_mask)
    names = []
    cols = []
    for k, v in feats.items():
        if k.startswith("_") or not isinstance(v, np.ndarray) or v.ndim != 2:
            continue
        names.append(k)
        cols.append(v.astype(np.float32).ravel())
    for k in extra_keys:
        if k in region and isinstance(region[k], np.ndarray):
            names.append(k)
            cols.append(region[k].astype(np.float32).ravel())
    if arm and arm.lower() != "baseline":
        # round-3 arms R3A/R3B read the catalogue: they MUST see the visible
        # context (the caller's ``context_mask``), never the full catalogue.
        for k, v in build_arm_features(region, arm, context_mask=context_mask).items():
            if isinstance(v, np.ndarray) and v.ndim == 2:
                names.append(k)
                cols.append(np.asarray(v, dtype=np.float32).ravel())
    X = np.stack(cols, axis=1)
    return X, names, feats


def train(region: dict, *, hide_fraction: float = 0.35, epochs: int = 8,
          seed: int = 7, n_pos_cap: int = 40000, n_neg_cap: int = 40000,
          arm: str = "baseline", verbose: bool = True) -> dict:
    rng = np.random.default_rng(seed)
    traces = region["traces"]
    labels = traces.ravel().astype(np.float64)

    betas = []
    epoch_rows = []
    t0 = time.time()
    for ep in range(epochs):
        plan = hr.sample_hide_plan(traces, hide_fraction, rng, buffer_px=2.0)
        context, hidden = hr.apply_plan(traces, plan)
        leak = hr.assert_no_leak(context, hidden)

        X, names, _feats = build_feature_matrix(region, context, arm=arm)

        # class-balanced sample of pixel rows
        pos = np.nonzero(labels > 0)[0]
        neg = np.nonzero(labels == 0)[0]
        pos_s = rng.choice(pos, size=min(len(pos), n_pos_cap), replace=False)
        neg_s = rng.choice(neg, size=min(len(neg), n_neg_cap), replace=False)
        idx = np.concatenate([pos_s, neg_s])
        y = labels[idx]
        # inverse-frequency weights
        w = np.where(y > 0, 0.5 / max(len(pos_s), 1), 0.5 / max(len(neg_s), 1))
        Xs = X[idx]
        mu, sd = standardize_fit(Xs)
        beta = logistic_fit((Xs - mu) / sd, y, w, n_iter=150, rng=rng)
        betas.append((beta, mu, sd, names))

        # score recovery on hidden components
        pred = predict_proba(beta, (X - mu) / sd).reshape(traces.shape)
        rec = hr.recover_score(pred, hidden)
        row = {
            "epoch": ep,
            "hide_fraction": plan.fraction,
            "hidden_components": int(len(plan.hidden_ids)),
            "leaks": leak["leaks"],
            "recover_dti": rec["dti"],
            "recover_tp": rec["tp"],
            "recover_fn": rec["fn"],
            "recover_fp": rec["fp"],
        }
        epoch_rows.append(row)
        if verbose:
            print(f"epoch {ep:02d}  hidden={row['hidden_components']:3d}  "
                  f"recover DTI={rec['dti']:.4f}  (tp={rec['tp']:.1f} fn={rec['fn']:.1f} "
                  f"fp={rec['fp']:.1f})  leaks={leak['leaks']}")

    # final ensemble prediction = mean of epoch probabilities
    full_X, names, _ = build_feature_matrix(region, traces, arm=arm)  # inference
    probs = np.zeros(traces.size, dtype=np.float64)
    for beta, mu, sd, _n in betas[-3:]:
        probs += predict_proba(beta, (full_X - mu) / sd)
    probs /= max(len(betas[-3:]), 1)
    pred_full = probs.reshape(traces.shape)

    mean_rec = float(np.mean([r["recover_dti"] for r in epoch_rows])) if epoch_rows else 0.0
    return {
        "model": betas,
        "feature_names": names,
        "epochs": epoch_rows,
        "mean_recover_dti": mean_rec,
        "pred_full": pred_full.astype(np.float32),
        "elapsed_s": time.time() - t0,
    }


def load_real_region() -> dict | None:
    proc = Path("data/processed")
    if not (proc / "known_faults.npy").exists():
        return None
    traces = np.load(proc / "known_faults.npy").astype(bool)
    region = {"traces": traces}
    feats_path = Path("data/raw/training_features.tif")
    if feats_path.exists():
        from gems import raster as gr
        bands, _meta = gr.read_multiband(feats_path)
        names = ["f_elev", "f_mag", "strain"]
        for i in range(min(bands.shape[0], 3)):
            region[names[i]] = bands[i]
    return region


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use the synthetic region")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--hide-fraction", type=float, default=0.35)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="artifacts/model_run.json")
    ap.add_argument("--pred-out", default="artifacts/pred.npy")
    args = ap.parse_args()

    if args.demo:
        from gems.synthesize import make_region
        region = make_region(shape=(256, 256), seed=args.seed)
    else:
        region = load_real_region()
        if region is None:
            print("No data/processed/known_faults.npy — run scripts/prepare_data.py first,")
            print("or use --demo on the synthetic region.")
            return 2

    result = train(region, hide_fraction=args.hide_fraction, epochs=args.epochs, seed=args.seed)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "mean_recover_dti": result["mean_recover_dti"],
        "elapsed_s": result["elapsed_s"],
        "feature_names": result["feature_names"],
        "epochs": result["epochs"],
    }
    out.write_text(json.dumps(summary, indent=2))
    np.save(args.pred_out, result["pred_full"])
    print(f"\nmean hidden-recovery DTI = {result['mean_recover_dti']:.4f}")
    print(f"wrote {out} and {args.pred_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
