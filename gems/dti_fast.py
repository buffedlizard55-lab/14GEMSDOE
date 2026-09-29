"""Fast float32 implementation of the official DTI, for full-grid evaluation.

Why this module exists
----------------------
``gems/dti.py`` is the reference transcription of the published equations: one
line per published line, float64, easy to audit.  It is also far too slow to run
a *sweep*: every evaluation needs ``M(g) = max_x p(x)k(d(x,g))``, which the
reference computes with 49 ``ndimage.shift`` calls on a 12.3 M-pixel float64
array (≈25 s per evaluation, and the real-data gate evaluates dozens of
emissions per arm).

This module computes the identical quantity in float32 with in-place slice
``np.maximum`` operations instead of shifts, plus a vectorised NMS so a 10 %
budget emission does not take hours.  ``tests/test_dti_fast.py`` asserts
agreement with the reference implementation on random fields.

Definitions transcribed from
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
(alpha = 0.2, beta = 0.8, R = 300 m = 3 px at 100 m):

    TP_w = sum_{g in G}      max_{x : d(x,g) <= R} p(x) k(d(x,g))
    FP_w = sum_{x : p(x) > 0} p(x) [1 - max_{g in G} k(d(x,g))]
    FN_w = sum_{g in G}      [1 - max_{x : d(x,g) <= R} p(x) k(d(x,g))]
    DTI  = TP_w / (TP_w + 0.2 * FP_w + 0.8 * FN_w + 1e-9)
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

ALPHA = 0.2
BETA = 0.8
RADIUS_PX = 3.0
EPS = 1e-9


def _offsets(radius_px: float):
    r = int(np.ceil(radius_px))
    out = []
    for di in range(-r, r + 1):
        for dj in range(-r, r + 1):
            d = float(np.hypot(di, dj))
            k = max(1.0 - d / radius_px, 0.0)
            if k > 0.0:
                out.append((di, dj, k))
    return out


_OFFSETS = _offsets(RADIUS_PX)


def kernel_max(pred: np.ndarray, radius_px: float = RADIUS_PX) -> np.ndarray:
    """M(g) = max_x p(x) * k(d(x, g)) on the whole grid (float32, in place)."""
    p = np.asarray(pred, dtype=np.float32)
    out = np.zeros_like(p, dtype=np.float32)
    for di, dj, k in (_OFFSETS if radius_px == RADIUS_PX else _offsets(radius_px)):
        r0, r1 = max(0, -di), min(p.shape[0], p.shape[0] - di)
        c0, c1 = max(0, -dj), min(p.shape[1], p.shape[1] - dj)
        if r0 >= r1 or c0 >= c1:
            continue
        o = out[r0:r1, c0:c1]
        s = p[r0 + di:r1 + di, c0 + dj:c1 + dj]
        if k == 1.0:
            np.maximum(o, s, out=o)
        else:
            np.maximum(o, s * np.float32(k), out=o)
    return out


# backward-compatible name used by the tests and by earlier sessions
kernel_weighted_max = kernel_max


def subsample_truth(gt: np.ndarray, max_px: int, seed: int = 0, block: int = 128) -> np.ndarray:
    """Truth subset of at most ``max_px`` pixels, drawn in contiguous blocks.

    Used to keep the *dense* protocol's absolute score honest at full precision
    while making a 30-point emission sweep affordable: the labelled traces are
    60 988 pixels against a 5.17 M-pixel footprint, and a sweep evaluates the
    dense protocol 20+ times per arm.  Block sampling (128-px squares, chosen by
    a seeded permutation) keeps whole structures together instead of shattering
    the traces into single pixels, so the subset behaves like a thinner but
    geometrically faithful survey.  With ``max_px`` = 60 988 the function returns
    the input unchanged, i.e. the published headline number stays exact.
    """
    g = np.asarray(gt, bool)
    ys, xs = np.nonzero(g)
    if ys.size <= max_px:
        return g
    rows, cols = g.shape
    nb = cols // block + 1
    bid = (ys // block) * nb + (xs // block)
    uniq = np.unique(bid)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(uniq)
    take = np.zeros(uniq.max() + 1, dtype=bool)
    taken = 0
    for b in perm:
        take[b] = True
        taken += int((bid == b).sum())
        if taken >= max_px:
            break
    out = np.zeros_like(g)
    out[ys[take[bid]], xs[take[bid]]] = True
    return out


def _truth_kmax(gt: np.ndarray, radius_px: float) -> np.ndarray:
    """max_g k(d(x, g)) for every pixel x (0 beyond the radius)."""
    if not gt.any():
        return np.zeros(gt.shape, dtype=np.float32)
    dist = ndimage.distance_transform_edt(~gt).astype(np.float32)
    kmax = 1.0 - np.minimum(dist, np.float32(radius_px)) / np.float32(radius_px)
    return np.maximum(kmax, np.float32(0.0), out=kmax)


def dti_fast(
    pred: np.ndarray,
    gt: np.ndarray,
    *,
    radius_px: float = RADIUS_PX,
    alpha: float = ALPHA,
    beta: float = BETA,
    eps: float = EPS,
    eval_mask: np.ndarray | None = None,
    fp_mask: np.ndarray | None = None,
) -> dict:
    """Same contract and same numbers as ``gems.dti.dti`` (float32 precision)."""
    p = np.nan_to_num(np.asarray(pred, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    g = np.asarray(gt) > 0
    if p.shape != g.shape:
        raise ValueError("pred and gt shapes differ")
    if p.size and (p.min() < -1e-6 or p.max() > 1.0 + 1e-6):
        raise ValueError("pred values must lie in [0, 1]")
    if eval_mask is not None:
        em = np.asarray(eval_mask, dtype=bool)
        p = np.where(em, p, np.float32(0.0))
        g = g & em
    m = kernel_max(p, radius_px)
    tp = float(m[g].sum()) if g.any() else 0.0
    fn = float((1.0 - m[g]).sum()) if g.any() else 0.0
    kmax = _truth_kmax(g, radius_px)
    fp_map = p * (1.0 - kmax)
    if fp_mask is not None:
        fp_map = np.where(np.asarray(fp_mask, dtype=bool), fp_map, np.float32(0.0))
    fp = float(fp_map.sum())
    denom = tp + alpha * fp + beta * fn + eps
    return {
        "dti": float(tp / denom) if denom > 0 else 0.0,
        "tp": tp, "fp": fp, "fn": fn,
        "n_gt": int(g.sum()), "n_pred_pos": int((p > 0).sum()),
    }


def emit_topk(score: np.ndarray, valid: np.ndarray, budget_px: int) -> np.ndarray:
    """Binary field with the ``budget_px`` highest-scoring valid pixels."""
    s = np.where(np.asarray(valid, dtype=bool),
                 np.nan_to_num(np.asarray(score, np.float32), nan=-1.0), -1.0).ravel()
    out = np.zeros(s.size, dtype=np.float32)
    k = int(min(max(budget_px, 0), s.size))
    if k:
        idx = np.argpartition(-s, k - 1)[:k]
        out[idx] = 1.0
    return out.reshape(score.shape)


def emit_thresh(score: np.ndarray, valid: np.ndarray, t: float) -> np.ndarray:
    """Binary field above a probability threshold, inside the valid footprint."""
    s = np.nan_to_num(np.asarray(score, np.float32), nan=0.0)
    return (np.asarray(valid, dtype=bool) & (s >= np.float32(t))).astype(np.float32)


def emit_nms(score: np.ndarray, valid: np.ndarray, budget_px: int, radius: int = 2) -> np.ndarray:
    """Greedy non-maximum suppression, vectorised over the candidate list.

    Emits the strongest pixel, blanks its (2r+1)² neighbourhood, and repeats.
    The candidate set only needs the *local maxima* of the smoothed score field,
    so the greedy loop runs over ~n/(2r+1)² candidates instead of every pixel;
    a pure Python loop over 5 M pixels took hours and was the reason round 7 of
    the sibling register could only afford one NMS arm per run.  Emitting fewer
    than ``budget_px`` pixels is possible when the candidate list is exhausted;
    the caller records the realised pixel count.
    """
    r = int(radius)
    s = np.where(np.asarray(valid, dtype=bool),
                 np.nan_to_num(np.asarray(score, dtype=np.float32), nan=-np.inf),
                 np.float32(-np.inf))
    out = np.zeros(s.shape, dtype=np.float32)
    if budget_px <= 0:
        return out
    pooled = ndimage.maximum_filter(s, size=2 * r + 1, mode="constant", cval=-np.inf)
    cand = np.flatnonzero(np.isfinite(s.ravel()) & (s.ravel() >= pooled.ravel()))
    if cand.size == 0:
        return out
    sflat = s.ravel()
    order = cand[np.argsort(-sflat[cand], kind="stable")]
    blocked = np.zeros(s.shape, dtype=bool)
    oflat = out.ravel()
    bflat = blocked.ravel()
    C = s.shape[1]
    taken = 0
    for idx in order:
        if bflat[idx]:
            continue
        i, j = divmod(int(idx), C)
        oflat[idx] = 1.0
        blocked[max(i - r, 0):i + r + 1, max(j - r, 0):j + r + 1] = True
        taken += 1
        if taken >= budget_px:
            break
    return out
