#!/usr/bin/env python3
"""Continuation-subset diagnostic (research/hypotheses_round7.md, R7-2).

C21 (VERIFIED staff answer): a "new fault" can be "newly mapped geometry of an
existing fault system — a continuation past a mapped tip".  This script measures
how much of an arm's hide-and-recover recovery comes from hidden TEST components
that CONTINUE a visible catalogue trace, as opposed to isolated hidden
components:

    continuation subset = TEST components with an endpoint within --tip-px of a
                          visible-trace endpoint whose strike differs by
                          <= --angle-deg.

It is a post-hoc read of already-written gate outputs (gate JSON + fold fields
+ fold truth masks); it never retrains anything.  Report per arm: DTI on the
full TEST set vs the continuation subset vs the isolated remainder, at the
CALIB-calibrated emission recorded in the gate JSON.

Usage:
    ./.venv/bin/python scripts/continuation_subset.py \
        --gate artifacts/holdout_round6_horse.json --arm geom_horse
    ./.venv/bin/python scripts/continuation_subset.py \
        --gate artifacts/holdout_round7.json        # all arms in the JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gems import dti as gdti  # noqa: E402
from gems import realdata as rd  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))
import validate_real as vr  # noqa: E402


def _endpoints(mask: np.ndarray) -> np.ndarray:
    """(K, 2) array of (row, col) endpoint pixels of a trace mask.

    Pixels with <= 1 mask neighbours count (a 1-pixel component is its own
    endpoint; a normal trace end has exactly 1 neighbour).
    """
    if not mask.any():
        return np.zeros((0, 2), dtype=np.int64)
    nbr = ndimage.convolve(mask.astype(np.uint8), np.ones((3, 3), dtype=np.uint8),
                           mode="constant", cval=0) - mask.astype(np.uint8)
    ends = mask & (nbr <= 1)
    ys, xs = np.nonzero(ends)
    return np.stack([ys, xs], axis=1)


def _angle_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    d = np.abs(a - b) % 180.0
    return np.minimum(d, 180.0 - d)


def continuation_subset(test: np.ndarray, visible: np.ndarray,
                        tip_px: float = 20.0, angle_deg: float = 30.0
                        ) -> tuple[np.ndarray, np.ndarray]:
    """Split ``test`` components into (continuation, isolated) masks.

    A test component is a continuation when one of its endpoints lies within
    ``tip_px`` of a visible endpoint whose local strike is within ``angle_deg``
    of the test component's own strike at that end.

    Strike maps are computed once per mask (the per-component version was
    O(n_components x grid) — the same trap as the old ridge_skeleton loop).
    """
    lab, n = ndimage.label(test, structure=np.ones((3, 3), dtype=int))
    cont = np.zeros(test.shape, dtype=bool)
    if n == 0:
        return cont, cont.copy()
    vis_pts = _endpoints(visible)
    if vis_pts.shape[0] == 0:
        return cont, test.copy()
    vis_strike_map, _ = vr.rc.local_strike(visible, window=9)
    test_strike_map, _ = vr.rc.local_strike(test, window=9)
    vis_strike = vis_strike_map[vis_pts[:, 0], vis_pts[:, 1]]
    # endpoints of ALL test components in one pass, grouped by component id
    nbr = ndimage.convolve(test.astype(np.uint8), np.ones((3, 3), dtype=np.uint8),
                           mode="constant", cval=0) - test.astype(np.uint8)
    ends = test & (nbr <= 1)
    eys, exs = np.nonzero(ends)
    ecids = lab[eys, exs]
    cont_ids = []
    for cid in np.unique(ecids):
        sel = ecids == cid
        pts = np.stack([eys[sel], exs[sel]], axis=1)
        comp_strike = test_strike_map[pts[:, 0], pts[:, 1]]
        d = np.hypot(pts[:, 0][:, None] - vis_pts[None, :, 0],
                     pts[:, 1][:, None] - vis_pts[None, :, 1])
        near = d <= tip_px
        if not near.any():
            continue
        ang = _angle_diff(comp_strike[:, None], vis_strike[None, :])
        if (near & (ang <= angle_deg)).any():
            cont_ids.append(int(cid))
    cont = np.isin(lab, cont_ids) if cont_ids else cont
    return cont, test & ~cont


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gate", default="artifacts/holdout_round6_horse.json")
    ap.add_argument("--arms", nargs="*", default=None,
                    help="arms to report (default: every non-baseline arm + geom)")
    ap.add_argument("--fields-dir", default="artifacts/real_fields")
    ap.add_argument("--tip-px", type=float, default=20.0)
    ap.add_argument("--angle-deg", type=float, default=30.0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    gate = json.loads((ROOT / args.gate).read_text())
    labels = rd.read_labels()
    valid = np.load(ROOT / "data/processed/valid_mask.npy").astype(bool)
    rows = {r["arm"]: r for r in gate["results"]}
    arms = args.arms or list(rows)
    lab_all, _n = ndimage.label(labels, structure=np.ones((3, 3), dtype=int))

    report = {"gate": args.gate, "tip_px": args.tip_px, "angle_deg": args.angle_deg,
              "arms": {}}
    for arm in arms:
        if arm not in rows:
            print(f"[subset] arm {arm!r} not in gate JSON; skipped")
            continue
        folds = rows[arm]["folds"]
        per_fold = []
        for f in folds:
            k = f["fold"]
            ids = gate["split_ids"][str(k)] if str(k) in gate["split_ids"] else \
                gate["split_ids"][k]
            test = np.isin(lab_all, ids["test"])
            hide = np.isin(lab_all, ids["hide"])
            visible = labels & ~(test | np.isin(lab_all, ids.get("calib", [])) | hide)
            cont, iso = continuation_subset(test, visible, args.tip_px, args.angle_deg)
            p = ROOT / args.fields_dir / f"fold{k}_{arm}.npy"
            if not p.exists():
                print(f"[subset] missing {p}; skipping fold {k}")
                continue
            field = np.load(p).astype(np.float32)
            if field.shape != valid.shape:
                raise SystemExit(f"{p} shape {field.shape} != {valid.shape} "
                                 f"(smoke-crop contamination?)")
            pol = f["calib_policy"]
            par = f["calib_param"]
            emitted = vr.emit_policy(field, pol, par, valid)
            row = {
                "fold": k,
                "n_test_px": int(test.sum()),
                "n_cont_px": int(cont.sum()),
                "n_iso_px": int(iso.sum()),
                "dense": gdti.dti(emitted, test, radius_px=3.0, eval_mask=valid)["dti"],
                "cont": (gdti.dti(emitted, cont, radius_px=3.0, eval_mask=valid)["dti"]
                         if cont.any() else None),
                "iso": (gdti.dti(emitted, iso, radius_px=3.0, eval_mask=valid)["dti"]
                        if iso.any() else None),
            }
            per_fold.append(row)
            print(f"[subset][{arm}] fold {k} test {row['n_test_px']} px "
                  f"(cont {row['n_cont_px']} / iso {row['n_iso_px']}) "
                  f"dense {row['dense']:.4f} cont {row['cont'] or 0:.4f} "
                  f"iso {row['iso'] or 0:.4f}", flush=True)
        if per_fold:
            mean = lambda key: float(np.mean([r[key] for r in per_fold if r[key] is not None]))  # noqa: E731
            summary = {"folds": per_fold,
                       "dense_mean": mean("dense"),
                       "cont_mean": mean("cont") if any(r["cont"] is not None for r in per_fold) else None,
                       "iso_mean": mean("iso") if any(r["iso"] is not None for r in per_fold) else None,
                       "cont_share_of_test_px": (float(sum(r["n_cont_px"] for r in per_fold))
                                                 / max(1, sum(r["n_test_px"] for r in per_fold)))}
            report["arms"][arm] = summary
            print(f"[subset][{arm}] mean dense {summary['dense_mean']:.4f} "
                  f"cont {summary['cont_mean'] or 0:.4f} "
                  f"iso {summary['iso_mean'] or 0:.4f} "
                  f"(cont px share {summary['cont_share_of_test_px']:.1%})", flush=True)

    if args.out:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2))
        print(f"[subset] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
