#!/usr/bin/env python3
"""Emission sweep on the real-data gate's saved probability fields.

The gate (`scripts/validate_real.py`) saves a float16 probability field per
fold and arm.  The competition metric is not scored on probabilities: the two
0.156-class submissions the group made were binary support sets at value 1.0,
and the metric algebra (research/hypotheses_round5.md §1) says a support should
be emitted at full value and only where it is likely to buy credit.  So the
decision that actually moves the leaderboard is WHICH pixels to emit.

This script answers that question under the gate's protocol:

  * candidate policies: probability thresholds t, top-q by probability, and
    greedy non-maximum suppression (NMS) at radius r within a top-q budget;
  * for every (fold, arm, policy) it computes the official DTI on
      - the hidden CALIB components  (selection set — never TEST), and
      - the TEST components          (reported set),
    plus the "far" TEST subset (GT pixels > 1,000 m from any context trace),
    the protocol that cannot be won by hugging the catalogue;
  * the policy is CHOSEN on CALIB and REPORTED on TEST, per the standing
    prompt.  The best-on-TEST row is printed too, clearly labelled as an
    oracle upper bound that must not be used for selection.

Usage:
    ./.venv/bin/python scripts/sweep_real.py --gate artifacts/holdout_real.json \
        --out artifacts/emission_sweep.json
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


def rebuild_masks(split_ids: dict, labels: np.ndarray) -> dict:
    lab, _n = ndimage.label(labels, structure=np.ones((3, 3), dtype=int))
    out = {}
    for k, ids in split_ids.items():
        d = {}
        for name in ("test", "calib", "hide"):
            if name in ids and ids[name]:
                d[name] = np.isin(lab, np.asarray(ids[name], dtype=int))
            else:
                d[name] = np.zeros(labels.shape, dtype=bool)
        out[int(k)] = d
    return out


def emit(policy: str, param: float, field: np.ndarray, valid: np.ndarray,
         nms_r: int = 3) -> np.ndarray:
    """Binary support for one emission policy, always valued 1.0."""
    f = np.where(valid, np.asarray(field, dtype=np.float32), np.nan)
    out = np.zeros(f.shape, dtype=np.float32)
    if policy == "thresh":
        out[np.isfinite(f) & (f >= param)] = 1.0
        return out
    n = int(round(param * int(valid.sum())))
    n = max(n, 1)
    flat = np.flatnonzero(np.isfinite(f))
    vals = f.ravel()[flat]
    order = np.argsort(-vals)
    chosen = flat[order[:n]]
    if policy == "topk":
        out.ravel()[chosen] = 1.0
        return out
    if policy == "nms":
        keep = []
        taken = np.zeros(f.shape, dtype=bool)
        for p in chosen:
            if taken.ravel()[p]:
                continue
            keep.append(p)
            r, c = divmod(int(p), f.shape[1])
            r0, r1 = max(0, r - nms_r), min(f.shape[0], r + nms_r + 1)
            c0, c1 = max(0, c - nms_r), min(f.shape[1], c + nms_r + 1)
            taken[r0:r1, c0:c1] = True
        out.ravel()[np.asarray(keep, dtype=np.int64)] = 1.0
        return out
    raise ValueError(policy)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default="artifacts/holdout_real.json")
    ap.add_argument("--fields-dir", default="artifacts/real_fields")
    ap.add_argument("--out", default="artifacts/emission_sweep.json")
    ap.add_argument("--sparse-frac", type=float, default=0.0,
                    help="keep 0 = use the full TEST set (slow); >0 subsamples TEST")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    gate = json.loads(Path(args.gate).read_text())
    arms = [r["arm"] for r in gate["results"]]
    labels = rd.read_labels()
    valid = np.load(ROOT / "data/processed/valid_mask.npy").astype(bool)
    # smoke crops: the gate may have run on a centred window
    fields_dir0 = ROOT / args.fields_dir if not Path(args.fields_dir).is_absolute() else Path(args.fields_dir)
    probe = next(iter(sorted(fields_dir0.glob("fold*_*.npy"))), None)
    if probe is not None:
        fshape = np.load(probe).shape
        if fshape != labels.shape:
            r0 = (labels.shape[0] - fshape[0]) // 2
            c0 = (labels.shape[1] - fshape[1]) // 2
            sl = (slice(r0, r0 + fshape[0]), slice(c0, c0 + fshape[1]))
            labels, valid = labels[sl], valid[sl]
            print(f"[sweep] crop mode {fshape}", flush=True)
    masks = rebuild_masks(gate["split_ids"], labels)
    fields_dir = fields_dir0

    policies = ([("thresh", t) for t in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)]
                + [("topk", q) for q in (0.005, 0.01, 0.02, 0.05)]
                + [("nms", q) for q in (0.01, 0.02, 0.05)])

    rng = np.random.default_rng(args.seed)
    truth = {}
    for k, m in masks.items():
        p = fields_dir / f"fold{k}_truth.npz"
        if not p.exists():
            raise SystemExit(f"missing {p}: run scripts/validate_real.py first")
        z = np.load(p)
        test = z["test"]
        if args.sparse_frac and 0 < args.sparse_frac < 1:
            flat = np.flatnonzero(test.ravel())
            keep = rng.choice(flat, size=max(1, int(args.sparse_frac * flat.size)), replace=False)
            t2 = np.zeros(test.size, dtype=bool)
            t2[keep] = True
            test = t2.reshape(test.shape)
        truth[k] = {"test": test, "sparse": z["sparse"], "far": z["far"],
                    "calib": m.get("calib")}

    rows = []
    t0 = time.time()
    for arm in arms:
        for k in sorted(masks):
            fp = fields_dir / f"fold{k}_{arm}.npy"
            if not fp.exists():
                continue
            field = np.load(fp).astype(np.float32)
            for policy, param in policies:
                pred = emit(policy, param, field, valid)
                npx = int((pred > 0).sum())
                d_test = df.dti_fast(pred, truth[k]["test"], radius_px=3.0, eval_mask=valid)
                d_calib = (df.dti_fast(pred, truth[k]["calib"], radius_px=3.0, eval_mask=valid)
                           if truth[k]["calib"] is not None and truth[k]["calib"].any() else None)
                d_far = (df.dti_fast(pred, truth[k]["far"], radius_px=3.0, eval_mask=valid)
                         if truth[k]["far"] is not None and truth[k]["far"].any() else None)
                rows.append({
                    "arm": arm, "fold": int(k), "policy": policy, "param": param,
                    "n_emit": npx,
                    "test_dti": d_test["dti"], "test_tp": d_test["tp"], "test_fp": d_test["fp"],
                    "calib_dti": None if d_calib is None else d_calib["dti"],
                    "far_dti": None if d_far is None else d_far["dti"],
                })
        print(f"    {arm}: {len([r for r in rows if r['arm']==arm])} policy rows "
              f"({time.time()-t0:.0f} s)", flush=True)

    def mean_by(sel_key, sel_val, key):
        vals = [r[key] for r in rows if r[sel_key] == sel_val and r[key] is not None]
        return float(np.mean(vals)) if vals else None

    summary = []
    for arm in arms:
        arm_rows = [r for r in rows if r["arm"] == arm]
        if not arm_rows:
            continue
        policies_seen = sorted({(r["policy"], r["param"]) for r in arm_rows})
        best = None
        for pol, par in policies_seen:
            sub = [r for r in arm_rows if r["policy"] == pol and r["param"] == par]
            cal = [r["calib_dti"] for r in sub if r["calib_dti"] is not None]
            if not cal:
                continue
            mc = float(np.mean(cal))
            if best is None or mc > best["calib_mean"]:
                best = {"policy": pol, "param": par, "calib_mean": mc,
                        "test_mean": float(np.mean([r["test_dti"] for r in sub])),
                        "far_mean": (float(np.mean([r["far_dti"] for r in sub
                                                    if r["far_dti"] is not None]))
                                     if any(r["far_dti"] is not None for r in sub) else None),
                        "n_emit_mean": float(np.mean([r["n_emit"] for r in sub]))}
        oracle = max(arm_rows, key=lambda r: r["test_dti"])
        summary.append({"arm": arm, "calibrated": best,
                        "oracle_on_test": {"policy": oracle["policy"], "param": oracle["param"],
                                           "test_dti": oracle["test_dti"]}})

    payload = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gate": args.gate,
        "note": ("selection uses calib_dti only (hidden CALIB components); "
                 "oracle_on_test is an upper bound, never a selection rule"),
        "summary": summary,
        "rows": rows,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(f"\n[ sweep] wrote {out} ({len(rows)} rows, {time.time()-t0:.0f} s)")
    for s in summary:
        b = s["calibrated"]
        if b is None:
            continue
        print(f"{s['arm']:10s} selected {b['policy']}:{b['param']}  calib={b['calib_mean']:.4f} "
              f"TEST={b['test_mean']:.4f} far={'—' if b['far_mean'] is None else format(b['far_mean'], '.4f')} "
              f"emit={b['n_emit_mean']:.0f}px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
