#!/usr/bin/env python3
"""Spatially-blocked holdout validation (the only number allowed to gate
submission slots).

Rules enforced here (standing prompt):
  * NO submission-slot decisions from random-split scores — splits are spatial
    blocks, optionally with a purge buffer across block edges.
  * A candidate idea must BEAT the current holdout best before it may consume
    one of the three weekly submission slots (rules section 3.2/3.4: three
    submissions per week, one final selection).

Protocol per fold k (mirrors hide-and-recover at block scale):
    context  = catalogue traces OUTSIDE fold k's blocks (minus purge buffer)
    target   = catalogue traces INSIDE fold k
    score    = DTI(prediction given context, target, eval near target)
This is the honest local analogue of the prize test: predict traces the
catalogue does not show you, from the features.

Usage:
  python3 scripts/validate_blocks.py --demo
  python3 scripts/validate_blocks.py --pred artifacts/pred.npy
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems.blocks import assign_folds, holdout_masks  # noqa: E402
from gems.dti import dti  # noqa: E402


def score_folds(pred: np.ndarray, traces: np.ndarray, *, n_folds: int = 5,
                block_px: int = 64, seed: int = 11, policy: str = "buffer",
                buffer_px: int = 3) -> dict:
    if pred.shape != traces.shape:
        raise ValueError("pred and traces shapes differ")
    fold_map = assign_folds(traces.shape, block_px, n_folds, seed=seed)
    rows = []
    for k in range(n_folds):
        train_m, test_m = holdout_masks(traces, fold_map, k, policy=policy, buffer_px=buffer_px)
        if test_m.sum() == 0:
            continue
        rec = dti(pred, test_m, eval_mask=None)
        rows.append({
            "fold": k,
            "n_test_px": int(test_m.sum()),
            "n_train_px": int(train_m.sum()),
            "dti": rec["dti"],
            "tp": rec["tp"], "fp": rec["fp"], "fn": rec["fn"],
        })
    dtis = [r["dti"] for r in rows]
    return {
        "folds": rows,
        "mean_dti": float(np.mean(dtis)) if dtis else 0.0,
        "min_dti": float(np.min(dtis)) if dtis else 0.0,
        "max_dti": float(np.max(dtis)) if dtis else 0.0,
        "n_folds_used": len(rows),
        "policy": policy,
        "block_px": block_px,
        "buffer_px": buffer_px if policy == "buffer" else 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--pred", default="artifacts/pred.npy")
    ap.add_argument("--traces", default="data/processed/known_faults.npy")
    ap.add_argument("--n-folds", type=int, default=5)
    ap.add_argument("--block-px", type=int, default=64)
    ap.add_argument("--policy", default="buffer", choices=["block", "buffer"])
    ap.add_argument("--buffer-px", type=int, default=3)
    ap.add_argument("--out", default="artifacts/holdout.json")
    args = ap.parse_args()

    if args.demo:
        from gems.synthesize import make_region
        from scripts.train_hide_recover import train
        region = make_region(shape=(256, 256), seed=5)
        result = train(region, hide_fraction=0.35, epochs=6, seed=5, verbose=False)
        pred, traces = result["pred_full"], region["traces"]
    else:
        pred_path = Path(args.pred)
        traces_path = Path(args.traces)
        if not pred_path.exists() or not traces_path.exists():
            print(f"need {pred_path} and {traces_path} (or use --demo)")
            return 2
        pred = np.load(pred_path)
        traces = np.load(traces_path).astype(bool)

    report = score_folds(pred, traces, n_folds=args.n_folds, block_px=args.block_px,
                         policy=args.policy, buffer_px=args.buffer_px)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2))
    print(f"mean blocked-holdout DTI = {report['mean_dti']:.4f} "
          f"(folds: {report['n_folds_used']}, policy={report['policy']})")
    for r in report["folds"]:
        print(f"  fold {r['fold']}: DTI={r['dti']:.4f}  test_px={r['n_test_px']}")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
