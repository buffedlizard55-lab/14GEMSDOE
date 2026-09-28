"""Distance-weighted Tversky index (DTI) — the official GEMS Prize metric.

Source (transcribed verbatim, 2026-09-28):
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric

    TI(a, b) = sum_x p(x)g(x)
               / [sum_x p(x)g(x) + a * sum_x p(x)(1-g(x)) + b * sum_x (1-p(x))g(x)]

    k(d) = (1 - d / R)+ = max(1 - d/R, 0),   R = 300 m  (3 pixels at 100 m)

    TP_w = sum_{g in G}      max_{x : d(x,g) <= R} p(x) k(d(x,g))
    FP_w = sum_{x : p(x)>0}  p(x) [1 - max_{g in G} k(d(x,g))]
    FN_w = sum_{g in G}      [1 - max_{x : d(x,g) <= R} p(x) k(d(x,g))]

    DTI(a, b) = TP_w / (TP_w + a * FP_w + b * FN_w + eps)

Competition parameters:  alpha = 0.2  (false positives cheap),
                         beta  = 0.8  (false negatives expensive),
                         eps   = 1e-9.

Official worked example (page 967 scoring example): TP_w = 3.00, FP_w = 1.89,
FN_w = 2.00 -> TI_w = 3.00 / (3.00 + 0.2*1.89 + 0.8*2.00) = 0.60.  The figure
pixels behind that example are not machine-readable text, so this module is
validated against our own analytically-computed test vectors instead (see
tests/test_dti.py) and against the printed equations above, line by line.

Known-fault masking (official staff ruling, forum thread 11516, 2026-09-16):
"Pixels corresponding to known USGS/INGENIOUS faults are masked / excluded from
evaluation, so they do not count towards penalty terms."  This module therefore
accepts an ``eval_mask``: pixels where eval_mask is False are excluded from BOTH
sides of the metric (prediction side and ground-truth side).  This is the only
interpretation under which the staff statement "it should not matter whether
these known faults are included with predictions or not" is exactly true.
IRREGULARITY FLAG: the alternative reading (mask only the FP term) is not
excluded by the wording; sensitivity to that choice is measurable once real
labels are present (see research/scoring_analysis.md).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

DEFAULT_ALPHA = 0.2
DEFAULT_BETA = 0.8
DEFAULT_R_PX = 3.0  # 300 m at 100 m/px
DEFAULT_EPS = 1e-9


def triangular_kernel(dist: np.ndarray, radius_px: float = DEFAULT_R_PX) -> np.ndarray:
    """k(d) = max(1 - d/R, 0), elementwise."""
    d = np.asarray(dist, dtype=np.float64)
    return np.maximum(1.0 - d / radius_px, 0.0)


def _kernel_offsets(radius_px: float):
    """All integer pixel offsets (di, dj) inside the kernel with k > 0.

    Includes the zero offset (k = 1).  Offsets at exactly d = radius have k = 0
    and contribute nothing, so they are skipped.
    """
    r = int(np.ceil(radius_px))
    for di in range(-r, r + 1):
        for dj in range(-r, r + 1):
            d = float(np.hypot(di, dj))
            k = max(1.0 - d / radius_px, 0.0)
            if k > 0.0:
                yield di, dj, d, k


def kernel_weighted_max(pred: np.ndarray, radius_px: float = DEFAULT_R_PX) -> np.ndarray:
    """M(g) = max over x of p(x) * k(d(x, g)), computed for every pixel g.

    Implemented as an elementwise maximum over shifted copies of pred, each
    pre-multiplied by its offset kernel weight.  Pixels outside the array are
    treated as contributing nothing (p assumed 0 outside the raster).
    """
    p = np.asarray(pred, dtype=np.float64)
    out = np.zeros_like(p)
    for di, dj, _d, k in _kernel_offsets(radius_px):
        shifted = ndimage.shift(p * k, shift=(di, dj), order=0, mode="constant", cval=0.0)
        np.maximum(out, shifted, out=out)
    return out


def distance_to_truth(gt_bool: np.ndarray, radius_px: float = DEFAULT_R_PX) -> np.ndarray:
    """Euclidean distance (px) from every pixel to the nearest ground-truth pixel.

    Distances beyond radius_px are clipped to radius_px + 1 (they all get kernel
    weight 0 and full FP penalty, so exact values are irrelevant and this keeps
    the FP sum numerically identical to the formula).
    """
    g = np.asarray(gt_bool, dtype=bool)
    if not g.any():
        return np.full(g.shape, radius_px + 1.0, dtype=np.float64)
    dist = ndimage.distance_transform_edt(~g).astype(np.float64)
    return np.minimum(dist, radius_px + 1.0)


def dti(
    pred: np.ndarray,
    gt: np.ndarray,
    *,
    radius_px: float = DEFAULT_R_PX,
    alpha: float = DEFAULT_ALPHA,
    beta: float = DEFAULT_BETA,
    eps: float = DEFAULT_EPS,
    eval_mask: np.ndarray | None = None,
    fp_mask: np.ndarray | None = None,
) -> dict:
    """Compute the distance-weighted Tversky index and its components.

    Parameters
    ----------
    pred : float array, values in [0, 1].  NaN is treated as 0.0
        (consistent with "NaN is read as 0.0" in scoring; NaN contributes
        nothing to FP because the FP sum runs over p(x) > 0).
    gt : array of {0, 1} (nonzero treated as 1).
    eval_mask : bool array, optional.  Where False, the pixel is excluded from
        evaluation on BOTH sides (known-fault masking, forum 11516).
    fp_mask : bool array, optional.  Where False, the pixel is excluded from the
        FP term only (kept for sensitivity analysis of the masking ambiguity).

    Returns dict with tp, fp, fn, dti, n_gt, n_pred_pos.
    """
    p = np.array(pred, dtype=np.float64, copy=True)
    if p.ndim != 2:
        raise ValueError(f"pred must be 2-D, got shape {p.shape}")
    if gt.shape != p.shape:
        raise ValueError(f"gt shape {gt.shape} != pred shape {p.shape}")
    p[np.isnan(p)] = 0.0
    if np.nanmin(p) < -1e-9 or np.nanmax(p) > 1.0 + 1e-9:
        raise ValueError("pred values must lie in [0, 1] before scoring (after NaN->0)")

    g = np.asarray(gt) > 0

    if eval_mask is not None:
        em = np.asarray(eval_mask, dtype=bool)
        if em.shape != p.shape:
            raise ValueError("eval_mask shape mismatch")
        p = np.where(em, p, 0.0)
        g = g & em

    # TP_w / FN_w: per ground-truth pixel, best kernel-weighted prediction.
    m = kernel_weighted_max(p, radius_px)
    tp = float(m[g].sum()) if g.any() else 0.0
    fn = float((1.0 - m[g]).sum()) if g.any() else 0.0

    # FP_w: probability mass outside the kernel support of any ground truth.
    dist_g = distance_to_truth(g, radius_px)
    kmax = triangular_kernel(dist_g, radius_px)  # = max_g k(d(x,g))
    fp_map = p * (1.0 - kmax)
    if fp_mask is not None:
        fm = np.asarray(fp_mask, dtype=bool)
        if fm.shape != p.shape:
            raise ValueError("fp_mask shape mismatch")
        fp_map = np.where(fm, fp_map, 0.0)
    fp = float(fp_map.sum())

    denom = tp + alpha * fp + beta * fn + eps
    score = tp / denom if denom > 0 else 0.0

    return {
        "dti": float(score),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "alpha": float(alpha),
        "beta": float(beta),
        "radius_px": float(radius_px),
        "n_gt": int(g.sum()),
        "n_pred_pos": int((p > 0).sum()),
    }


def dti_from_example_values(tp: float, fp: float, fn: float,
                            alpha: float = DEFAULT_ALPHA,
                            beta: float = DEFAULT_BETA,
                            eps: float = DEFAULT_EPS) -> float:
    """DTI from pre-computed weighted counts (used to reproduce the official
    worked example: 3.00, 1.89, 2.00 -> 0.6026... which the page prints as 0.60).
    """
    return float(tp / (tp + alpha * fp + beta * fn + eps))
