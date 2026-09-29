"""Real-data channels: catalogue geometry, geophysics, curvature and completeness.

Everything here is computed from (a) the visible *context* catalogue mask and
(b) the official 19-band feature stack.  No channel reads a hidden label, and no
channel is a function of the held-out truth.  Two consequences the gate relies
on:

  * geometry channels are computed from the context mask, so hiding a trace
    hides it from every geometry channel as well (anti-leak by construction);
  * geophysics channels are context-independent, which is the point — they are
    the only evidence available where the catalogue says nothing.

Channel groups
--------------
``geometry``    standing-prompt feature list: distance/azimuth to the nearest
                trace, along- vs across-strike distance to endpoints,
                overlapping-tip (relay) corridors, intersection density, and the
                angle between the local lineament and neighbouring known strikes.
``geophys``     the 19 official bands, robust-scaled, plus edge/curvature
                transforms (horizontal-gradient magnitude, tilt angle, profile
                curvature, ridge/valley response).
``completeness`` catalogue density regressed on the predictors that should set
                it (strain rate, relief, range-front position); the signed
                residual is the completeness angle.
``round5``      the round-5 candidate arms (R5-1 … R5-5), each documented in
                research/hypotheses_round5.md with layers, signature, why it
                should catch a *missing* fault, and its difference from every
                arm this repo and the sibling registers have already run.

Scaling convention: every channel is returned as float32, robust-scaled to
roughly [-1, 1] with percentile-2/98 clipping (``robust_unit``) unless it is a
non-negative intensity where [0, 1] is used.  NaN (outside the survey footprint)
is preserved as NaN and imputed by the learner, never by the feature builder.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def nan_fill(a: np.ndarray, value: float = 0.0) -> np.ndarray:
    return np.where(np.isfinite(a), a, value).astype(np.float32)


def robust_unit(a: np.ndarray, lo: float = 2.0, hi: float = 98.0, symmetric: bool = True) -> np.ndarray:
    """Percentile-clipped robust scaling to [-1, 1] (symmetric) or [0, 1].

    NaN is preserved.  Percentiles are taken over finite values only.
    """
    x = np.asarray(a, dtype=np.float32)
    finite = np.isfinite(x)
    if not finite.any():
        return np.full(x.shape, np.nan, dtype=np.float32)
    v = x[finite]
    p_lo, p_hi = np.percentile(v, [lo, hi])
    if p_hi <= p_lo:
        out = np.where(finite, 0.0, np.nan).astype(np.float32)
        return out
    out = (x - p_lo) / (p_hi - p_lo)
    out = np.clip(out, 0.0, 1.0)
    if symmetric:
        out = out * 2.0 - 1.0
    out = np.where(finite, out, np.nan).astype(np.float32)
    return out


def hgm(a: np.ndarray) -> np.ndarray:
    """Horizontal gradient magnitude of a scalar field (NaN-aware input)."""
    x = np.asarray(a, dtype=np.float32)
    gy, gx = np.gradient(np.nan_to_num(x, nan=0.0))
    finite = np.isfinite(x)
    out = np.hypot(gx, gy).astype(np.float32)
    return np.where(finite, out, np.nan).astype(np.float32)


def laplacian(a: np.ndarray) -> np.ndarray:
    x = np.asarray(a, dtype=np.float32)
    out = ndimage.laplace(np.nan_to_num(x, nan=0.0)).astype(np.float32)
    return np.where(np.isfinite(x), out, np.nan).astype(np.float32)


def _finite_gradient(arr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Gradient of a NaN-bearing field, computed on the NaN-filled field
    (float32, for memory: the full grid is 3,730 x 3,292)."""
    x = np.nan_to_num(np.asarray(arr, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    gy, gx = np.gradient(x)
    return gy.astype(np.float32, copy=False), gx.astype(np.float32, copy=False)


def line_max(response: np.ndarray, radius: int = 3) -> np.ndarray:
    """Spatial maximum of a response field over a (2r+1) square.

    Used to build "credit-aware" channels: a lineament response measured 1–3
    pixels away is still evidence for a fault at this pixel, because the metric
    itself credits a hit within 300 m (3 px).  NaN stays NaN.
    """
    r = int(radius)
    # scipy's maximum_filter has no float16 kernel; channels are stored as
    # float16 to fit the memory budget, so cast explicitly here.
    resp = np.asarray(response, dtype=np.float32)
    pooled = ndimage.maximum_filter(np.nan_to_num(resp, nan=-np.inf), size=2 * r + 1)
    pooled = np.where(np.isfinite(pooled), pooled, np.nan)
    return pooled.astype(np.float32)


# ---------------------------------------------------------------------------
# 1. catalogue-geometry channels (context mask only)
# ---------------------------------------------------------------------------


def distance_and_azimuth(trace: np.ndarray) -> dict:
    t = np.asarray(trace, dtype=bool)
    dist = ndimage.distance_transform_edt(~t).astype(np.float32)
    gy, gx = _finite_gradient(dist)
    az = (np.degrees(np.arctan2(-gx, -gy)) + 360.0) % 360.0
    return {
        "dist_trace": dist,
        "az_sin": (np.sin(np.radians(az)) * (dist > 0)).astype(np.float32),
        "az_cos": (np.cos(np.radians(az)) * (dist > 0)).astype(np.float32),
    }


def endpoint_mask(trace: np.ndarray) -> np.ndarray:
    t = np.asarray(trace, dtype=bool)
    k = np.ones((3, 3), dtype=np.uint8)
    neigh = ndimage.convolve(t.astype(np.uint8), k, mode="constant", cval=0) - t.astype(np.uint8)
    return t & (neigh == 1)


def local_strike(trace: np.ndarray, window: int = 9) -> tuple[np.ndarray, np.ndarray]:
    """Local strike of the catalogue (deg, clockwise from north, [0,180))."""
    t = np.asarray(trace, dtype=bool)
    w = int(window)
    T = t.astype(np.float32)
    ii, jj = np.meshgrid(np.arange(t.shape[0], dtype=np.float32),
                         np.arange(t.shape[1], dtype=np.float32), indexing="ij")
    size = 2 * w + 1
    area = float(size * size)
    conv = lambda a: ndimage.uniform_filter(a, size=size, mode="constant", cval=0.0) * area  # noqa: E731
    N = conv(T) + 1e-9
    mx = conv(T * jj) / N
    my = conv(T * ii) / N
    cxx = conv(T * jj * jj) / N - mx * mx
    cyy = conv(T * ii * ii) / N - my * my
    cxy = conv(T * ii * jj) / N - mx * my
    theta = 0.5 * np.arctan2(2.0 * cxy, cxx - cyy)
    tr = cxx + cyy
    det = cxx * cyy - cxy * cxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1, l2 = tr / 2.0 + disc, tr / 2.0 - disc
    gap = (l1 - l2) / (l1 + l2 + 1e-12)
    dx, dy = np.cos(theta), np.sin(theta)
    strike = ((np.degrees(np.arctan2(dx, -dy)) + 360.0) % 180.0).astype(np.float32)
    conf = np.where(t, gap, 0.0).astype(np.float32)
    strike = np.where(t, strike, np.nan).astype(np.float32)
    return strike, conf


def strike_field_dilated(strike: np.ndarray, conf: np.ndarray | None = None,
                         radius: int = 60) -> np.ndarray:
    """Nearest-trace strike propagated outward (needed for strike mismatch).

    One Euclidean-distance transform with ``return_indices=True`` gives the
    nearest trace pixel for every pixel in the grid, so the propagated strike is
    the strike of the closest catalogue pixel rather than of a dilation front
    (equivalent for a 1-px-wide catalogue, and ~100x faster than 60 dilations on
    a 12.3 M-pixel grid).
    """
    st = np.asarray(strike, dtype=np.float32)
    known = np.isfinite(st)
    if not known.any():
        return np.full(st.shape, np.nan, dtype=np.float32)
    _d, (iy, ix) = ndimage.distance_transform_edt(~known, return_indices=True)
    out = st[iy, ix]
    far = _d > float(radius)
    out = np.where(far, np.nan, out).astype(np.float32)
    return out


def along_across_strike(trace: np.ndarray, window: int = 9) -> dict:
    t = np.asarray(trace, dtype=bool)
    d = distance_and_azimuth(t)
    dist = d["dist_trace"]
    strike, _ = local_strike(t, window=window)
    st = strike_field_dilated(strike, None, radius=60)
    az = np.arctan2(d["az_sin"], d["az_cos"])
    ux, uy = np.sin(az), np.cos(az)
    vx, vy = -ux * dist, -uy * dist
    s_rad = np.radians(np.nan_to_num(st, nan=0.0))
    sx, sy = np.sin(s_rad), np.cos(s_rad)
    across = (vx * sy - vy * sx).astype(np.float32)
    along = (vx * sx + vy * sy).astype(np.float32)
    ends = endpoint_mask(t)
    dist_end = (ndimage.distance_transform_edt(~ends).astype(np.float32)
                if ends.any() else np.full(t.shape, np.float32(1e6), dtype=np.float32))
    return {"across_strike": across, "along_strike": along, "dist_endpoint": dist_end}


def relay_corridors(
    trace: np.ndarray,
    *,
    min_gap_px: float = 2.0,
    max_gap_px: float = 60.0,
    max_strike_diff_deg: float = 40.0,
) -> dict:
    """Overlapping/underlapping tip pairs -> bridging-corridor field (KD-tree).

    Components are the connected catalogue traces.  For every ordered pair
    within ``max_gap_px`` the four tip-to-tip gaps are tested; a pair qualifies
    when the smallest gap is in range, the strikes differ by no more than the
    threshold, and every other tip-to-tip gap is also within range (that is what
    makes the pair *overlapping* rather than an isolated continuation).  Weight
    scales with parallelity and proximity, following the published ramp-width
    distribution (Giddens & Faulds 2025: 0.1–14.6 km, mean 2.8 km).
    """
    t = np.asarray(trace, dtype=bool)
    lab, n = ndimage.label(t, structure=np.ones((3, 3), dtype=int))
    corr = np.zeros(t.shape, dtype=np.float32)
    if n < 2:
        return {"corridor": corr, "n_pairs": 0, "tip_table": None}

    objs = ndimage.find_objects(lab)
    tips = []
    for cid in range(1, n + 1):
        sl = objs[cid - 1]
        if sl is None:
            continue
        yy, xx = np.nonzero(lab[sl] == cid)
        yy = yy + sl[0].start
        xx = xx + sl[1].start
        if yy.size < 2:
            continue
        # tips: the two pixels farthest apart (exact for short traces, close
        # enough for longer ones at 100 m resolution)
        pts = np.stack([yy, xx], axis=1).astype(np.float32)
        # principal axis + extreme projections (O(n) per component)
        c = pts.mean(axis=0)
        q = pts - c
        cov = q.T @ q
        evals, evecs = np.linalg.eigh(cov)
        axis = evecs[:, int(np.argmax(evals))]
        proj = q @ axis
        i0, i1 = int(np.argmin(proj)), int(np.argmax(proj))
        length = float(proj[i1] - proj[i0])
        strike = float((np.degrees(np.arctan2(axis[1], axis[0])) + 360.0) % 180.0)
        tips.append((cid, pts[i0], pts[i1], strike, length, pts.size // 2))

    if len(tips) < 2:
        return {"corridor": corr, "n_pairs": 0, "tip_table": None}

    tip_pts = np.array([p for _c, a, b, *_ in tips for p in (a, b)], dtype=np.float32)
    # candidate pairs: tips within 1.5x the gap limit.  The *nearest tip* distance
    # can exceed the true strand-to-strand gap when long strands are offset along
    # strike (the tips are then not the closest points), so the candidate radius is
    # relaxed here and the exact minimum point-to-point distance between the two
    # strand point sets is evaluated below.
    tree = cKDTree(tip_pts)
    pairs = tree.query_pairs(r=float(1.5 * max_gap_px), output_type="ndarray")
    comp_pts = {}
    for _c, a, b, _st, _ln, _n in tips:
        pass
    pts_by_comp = {}
    for cid in range(1, n + 1):
        sl = objs[cid - 1]
        if sl is None:
            continue
        yy, xx = np.nonzero(lab[sl] == cid)
        if yy.size == 0:
            continue
        pts_by_comp[cid] = np.stack([yy + sl[0].start, xx + sl[1].start], axis=1).astype(np.float32)
    out_pairs = []
    for i, j in pairs:
        ca, cb = i // 2, j // 2
        if ca == cb:
            continue
        ia, ib = tips[ca], tips[cb]
        sd = abs(ia[3] - ib[3]) % 180.0
        sd = min(sd, 180.0 - sd)
        if sd > max_strike_diff_deg:
            continue
        A_pts, B_pts = pts_by_comp.get(ia[0]), pts_by_comp.get(ib[0])
        if A_pts is None or B_pts is None:
            continue
        # exact strand-to-strand gap = minimum point-to-point distance
        if A_pts.shape[0] > B_pts.shape[0]:
            A_pts, B_pts = B_pts, A_pts
        gmin = float(cKDTree(A_pts).query(B_pts, k=1)[0].min())
        if gmin < min_gap_px or gmin > max_gap_px:
            continue
        # "Genuine overlap" is an *along-strike* property, not a diagonal one: the
        # two strands' projections on the mean strike must overlap.  The earlier
        # test (every one of the four tip-to-tip gaps < max_gap) silently rejected
        # real relay ramps whose strands are longer than the step-over width
        # (units: the along-strike overlap is the published hard-link criterion,
        # Giddens & Faulds 2025 — ~70 % of higher-T step-overs are hard-linked).
        # Found by tests/test_realchannels.py::test_relay_corridors_bridges_two_strands.
        theta = np.radians(0.5 * (ia[3] + ib[3]))
        u = np.array([np.cos(theta), np.sin(theta)], dtype=np.float32)
        p_a = [float(np.dot(P - ia[1], u)) for P in (ia[1], ia[2])]
        p_b = [float(np.dot(P - ib[1], u)) for P in (ib[1], ib[2])]
        overlap = min(max(p_a), max(p_b)) - max(min(p_a), min(p_b))
        if overlap <= 0:
            continue
        w = float((1.0 - gmin / max_gap_px) * (1.0 - sd / max_strike_diff_deg))
        w = float(np.clip(w, 0.0, 1.0))
        # bridge the two *nearest* tips
        best = None
        for pa in (ia[1], ia[2]):
            for pb in (ib[1], ib[2]):
                g = float(np.hypot(*(pa - pb)))
                if best is None or g < best[0]:
                    best = (g, pa, pb)
        _g, pa, pb = best
        out_pairs.append((ia[0], ib[0], gmin, sd, w))
        patch = elliptical_bridge_patch(t.shape, pa, pb, gmin, w)
        if patch is not None:
            y0, x0, arr = patch
            np.maximum(corr[y0:y0 + arr.shape[0], x0:x0 + arr.shape[1]], arr,
                       out=corr[y0:y0 + arr.shape[0], x0:x0 + arr.shape[1]])
    return {"corridor": corr, "n_pairs": len(out_pairs), "tip_table": np.array(tips, dtype=object)}


def elliptical_bridge(shape, pa, pb, gap, weight) -> np.ndarray:
    """Elliptical bridge between two tips, painted into a full-grid array.

    Thin wrapper around :func:`elliptical_bridge_patch` kept for the callers
    that want a full grid (``gems.hypotheses`` / round-2 tooling)."""
    out = np.zeros(shape, dtype=np.float32)
    patch = elliptical_bridge_patch(shape, pa, pb, gap, weight)
    if patch is not None:
        y0, x0, arr = patch
        np.maximum(out[y0:y0 + arr.shape[0], x0:x0 + arr.shape[1]], arr,
                   out=out[y0:y0 + arr.shape[0], x0:x0 + arr.shape[1]])
    return out


def elliptical_bridge_patch(shape, pa, pb, gap, weight):
    """(y0, x0, patch) for the bridge ellipse — the memory-cheap form.

    Regression: the original version allocated a fresh 12.3 M-pixel float32
    array *per tip pair*.  With thousands of pairs that is thousands of 49 MB
    allocations and it dominated the runtime of the real-data gate (found with
    py-spy on 2026-09-28).  Returning the bounding-box patch instead is exact and
    ~10^4 times cheaper in allocation."""
    if weight <= 0:
        return None
    cy, cx = (pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0
    dy, dx = pb[0] - pa[0], pb[1] - pa[1]
    ang = np.arctan2(dy, dx)
    half_major = max(gap / 2.0 + 1.5, 1.5)
    half_minor = max(gap / 3.0, 1.0)
    r = int(np.ceil(half_major + 2))
    y0, y1 = int(max(cy - r, 0)), int(min(cy + r + 1, shape[0]))
    x0, x1 = int(max(cx - r, 0)), int(min(cx + r + 1, shape[1]))
    if y0 >= y1 or x0 >= x1:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1]
    X = (xx - cx) * np.cos(ang) + (yy - cy) * np.sin(ang)
    Y = -(xx - cx) * np.sin(ang) + (yy - cy) * np.cos(ang)
    val = 1.0 - ((X / half_major) ** 2 + (Y / half_minor) ** 2)
    patch = (np.clip(val, 0.0, 1.0) * weight).astype(np.float32)
    return y0, x0, patch


def intersection_density(trace: np.ndarray, radius_px: int = 12) -> dict:
    t = np.asarray(trace, dtype=bool)
    k = np.ones((3, 3), dtype=np.uint8)
    neigh = ndimage.convolve(t.astype(np.uint8), k, mode="constant", cval=0) - t.astype(np.uint8)
    junctions = (t & (neigh >= 3)).astype(np.float32)
    size = 2 * int(radius_px) + 1
    # separable box sums: a dense (2r+1)^2 convolution is ~625 multiply-adds per
    # pixel at r=12 on a 12.3 M-pixel grid; uniform_filter is the same operator
    # scaled by the window area and costs O(1) per pixel per axis.
    area = float(size * size)
    return {
        "trace_density": (ndimage.uniform_filter(t.astype(np.float32), size=size,
                                                 mode="constant", cval=0.0) * area),
        "junction_density": (ndimage.uniform_filter(junctions, size=size,
                                                    mode="constant", cval=0.0) * area),
        "junction_mask": junctions,
    }


def structure_tensor(field: np.ndarray, sigma: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(strike, coherence, energy) of a scalar field via the structure tensor."""
    x = np.nan_to_num(np.asarray(field, dtype=np.float32), nan=0.0)
    gy, gx = np.gradient(x.astype(np.float64))
    jxx = ndimage.gaussian_filter(gx * gx, sigma)
    jyy = ndimage.gaussian_filter(gy * gy, sigma)
    jxy = ndimage.gaussian_filter(gx * gy, sigma)
    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)
    gxd, gyd = np.cos(theta), np.sin(theta)
    lx, ly = -gyd, gxd
    strike = ((np.degrees(np.arctan2(lx, -ly)) + 360.0) % 180.0).astype(np.float32)
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1, l2 = tr / 2.0 + disc, tr / 2.0 - disc
    coh = ((l1 - l2) / (l1 + l2 + 1e-12)).astype(np.float32)
    return strike, coh, np.sqrt(np.maximum(tr, 0.0)).astype(np.float32)


def strike_mismatch(lineament_strike: np.ndarray, cat_strike: np.ndarray) -> np.ndarray:
    d = np.abs(np.asarray(lineament_strike, np.float32) - np.asarray(cat_strike, np.float32)) % 180.0
    return np.minimum(d, 180.0 - d).astype(np.float32)


# ---------------------------------------------------------------------------
# 2. completeness angle
# ---------------------------------------------------------------------------


def completeness_residual(
    density: np.ndarray,
    predictors: dict[str, np.ndarray],
    *,
    smooth_sigma: float = 32.0,
    mask: np.ndarray | None = None,
) -> dict:
    """Signed residual of catalogue density against its expected predictors.

    Ordinary least squares of smoothed catalogue density on smoothed
    strain-rate, relief and range-front predictors (all variables are supplied
    already smoothed by the caller's grid).  Positive residual = the catalogue
    is denser than the physical setting predicts (mapped thoroughly); strongly
    negative = the setting should host faults that the catalogue does not show.

    ``mask`` (e.g. the training-fold footprint) restricts the fit so the
    residual never sees held-out blocks.
    """
    y = np.nan_to_num(ndimage.gaussian_filter(np.nan_to_num(density, nan=0.0), smooth_sigma), nan=0.0)
    cols = [y]
    names = []
    for name, arr in predictors.items():
        v = np.nan_to_num(ndimage.gaussian_filter(np.nan_to_num(np.asarray(arr, np.float32), nan=0.0), smooth_sigma), nan=0.0)
        # standardise each predictor over the fit mask
        m = v[mask] if mask is not None else v.ravel()
        sd = float(np.std(m)) or 1.0
        cols.append((v - float(np.mean(m))) / sd)
        names.append(name)
    X = np.stack(cols[1:], axis=-1).reshape(-1, len(cols) - 1)
    yy = cols[0].ravel()
    if mask is not None:
        sel = np.asarray(mask, dtype=bool).ravel()
        Xf, yf = X[sel], yy[sel]
    else:
        Xf, yf = X, yy
    # the fit uses a random subsample of the fit mask: the model has 4 free
    # parameters, so 200 k pixels estimate them to far better precision than the
    # residual's own accuracy, while a full-grid lstsq would need >1 GB.
    n_fit = int(Xf.shape[0])
    if n_fit > 120_000:
        sel = np.random.default_rng(0).choice(n_fit, size=120_000, replace=False)
        Xs, ys = Xf[sel], yf[sel]
    else:
        Xs, ys = Xf, yf
    A = np.concatenate([Xs, np.ones((Xs.shape[0], 1), dtype=np.float32)], axis=1)
    coef, *_ = np.linalg.lstsq(A.astype(np.float64), ys.astype(np.float64), rcond=None)
    pred = np.concatenate([X, np.ones((X.shape[0], 1), dtype=np.float32)], axis=1) @ coef
    resid = (yy - pred).reshape(density.shape).astype(np.float32)
    return {
        "residual": resid,
        "coef": {n: float(c) for n, c in zip(names, coef[:-1])},
        "intercept": float(coef[-1]),
    }


# ---------------------------------------------------------------------------
# 3. round-5 candidate channels
# ---------------------------------------------------------------------------


def ramp_maturity_field(
    trace: np.ndarray,
    *,
    max_gap_px: float = 60.0,
    max_strike_diff_deg: float = 40.0,
    overlap_penalty_km: float = 2.8,
    pixel_m: float = 100.0,
) -> np.ndarray:
    """R5-1: relay-ramp *interior* maturity (see hypotheses_round5.md).

    For every overlapping tip pair found by :func:`relay_corridors`, weight the
    ramp by three published geometric controls instead of one:

      * across-strike separation scaled by the observed ramp-width distribution
        (Giddens & Faulds 2025: 0.1–14.6 km, mean 2.8 km),
      * along-strike overlap relative to separation (hard-linked ramps, ~70% of
        higher-temperature step-overs, are those whose strands overlap rather
        than underlap),
      * strike parallelity.

    The field is the *interior* of each ramp — the sub-region between the
    overlapping strands — not the tip-to-tip line, because that interior is
    where the connecting small faults are mapped in the field and where they are
    most often absent from a regional catalogue.
    """
    t = np.asarray(trace, dtype=bool)
    lab, n = ndimage.label(t, structure=np.ones((3, 3), dtype=int))
    field = np.zeros(t.shape, dtype=np.float32)
    if n < 2:
        return field
    tips = []
    objs = ndimage.find_objects(lab)
    for cid in range(1, n + 1):
        sl = objs[cid - 1]
        if sl is None:
            continue
        yy, xx = np.nonzero(lab[sl] == cid)
        yy = yy + sl[0].start
        xx = xx + sl[1].start
        if yy.size < 2:
            continue
        pts = np.stack([yy, xx], axis=1).astype(np.float32)
        c = pts.mean(axis=0)
        q = pts - c
        evals, evecs = np.linalg.eigh(q.T @ q)
        axis = evecs[:, int(np.argmax(evals))]
        proj = q @ axis
        i0, i1 = int(np.argmin(proj)), int(np.argmax(proj))
        tips.append((pts[i0], pts[i1], float((np.degrees(np.arctan2(axis[1], axis[0])) + 360.0) % 180.0)))
    if len(tips) < 2:
        return field

    tip_pts = np.array([p for a, b, _s in tips for p in (a, b)], dtype=np.float32)
    tree = cKDTree(tip_pts)
    pairs = tree.query_pairs(r=float(max_gap_px), output_type="ndarray")
    for i, j in pairs:
        ca, cb = i // 2, j // 2
        if ca == cb:
            continue
        (a0, a1, sa), (b0, b1, sb) = tips[ca], tips[cb]
        sd = abs(sa - sb) % 180.0
        sd = min(sd, 180.0 - sd)
        if sd > max_strike_diff_deg:
            continue
        # tips are given in (row, col); use (col, row) as (x, y) for the ramp frame
        A0, A1 = np.array([a0[1], a0[0]]), np.array([a1[1], a1[0]])
        B0, B1 = np.array([b0[1], b0[0]]), np.array([b1[1], b1[0]])
        d_a = A1 - A0
        u = d_a / (np.linalg.norm(d_a) + 1e-9)             # strike direction (A)
        n_hat = np.array([-u[1], u[0]])                    # across-strike
        sep = abs(float(np.dot(B0 - A0, n_hat)))           # across-strike separation (px)
        # along-strike overlap of the two strands, projected on A's strike
        pa = [float(np.dot(P - A0, u)) for P in (A0, A1)]
        pb = [float(np.dot(P - A0, u)) for P in (B0, B1)]
        overlap = max(0.0, min(max(pa), max(pb)) - max(min(pa), min(pb)))
        sep_km = sep * pixel_m / 1000.0
        if sep_km > 14.6:                                   # outside the published range
            continue
        w_width = float(np.exp(-0.5 * (sep_km / overlap_penalty_km) ** 2))
        w_overlap = overlap / (overlap + sep + 1e-6)         # hard-link tendency, in [0,1)
        w_par = 1.0 - sd / max_strike_diff_deg
        weight = float(np.clip(w_width * w_overlap * w_par, 0.0, 1.0))
        if weight <= 0:
            continue
        # paint the ramp interior: the quad between the two strands
        centre = (A0 + A1 + B0 + B1) / 4.0
        half_len = max(1.0, overlap / 2.0 + 2.0)
        half_w = max(1.0, sep / 2.0 + 1.0)
        r = int(np.ceil(max(half_len, half_w) + 2))
        y0, y1 = int(max(centre[1] - r, 0)), int(min(centre[1] + r + 1, t.shape[0]))
        x0, x1 = int(max(centre[0] - r, 0)), int(min(centre[0] + r + 1, t.shape[1]))
        if y0 >= y1 or x0 >= x1:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        X = xx - centre[0]
        Y = yy - centre[1]
        U = X * u[0] + Y * u[1]
        V = X * n_hat[0] + Y * n_hat[1]
        val = (1.0 - (U / half_len) ** 2) * (1.0 - (V / half_w) ** 2)
        patch = np.clip(val, 0.0, 1.0) * weight
        field[y0:y1, x0:x1] = np.maximum(field[y0:y1, x0:x1], patch.astype(np.float32))
    return field


def tilt_angle(vg: np.ndarray, hg: np.ndarray) -> np.ndarray:
    """R5-3: amplitude-normalised magnetic tilt angle atan2(dV/dz, |dH/dx,dy|).

    Independent of magnetisation amplitude, so buried edges stay visible where
    a strength threshold fails (Salem et al. 2007 tilt-depth method).  Because
    the shipped band units are not documented, the ratio is used as a shape
    descriptor only — the gate decides whether it carries information.
    """
    v = np.nan_to_num(np.asarray(vg, dtype=np.float32), nan=0.0).astype(np.float64)
    h = np.abs(np.nan_to_num(np.asarray(hg, dtype=np.float32), nan=0.0)).astype(np.float64)
    theta = np.arctan2(v, h + 1e-12)
    valid = np.isfinite(vg) & np.isfinite(hg)
    return np.where(valid, theta, np.nan).astype(np.float32)


def profile_curvature(elev: np.ndarray, sigma: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """R5-4: plan and profile curvature of a topographic field.

    Profile curvature is the curvature in the direction of steepest descent; it
    marks the convex breaks in slope where a range front steps or where an
    alluvial fan has buried the fault trace (Faulds: fans and lake sediments
    mask faults).  Returned as (profile, plan).
    """
    e = np.nan_to_num(np.asarray(elev, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    if sigma > 0:
        e = ndimage.gaussian_filter(e, sigma)
    gy, gx = np.gradient(e)
    gyy, gyx = np.gradient(gy)
    gxy, gxx = np.gradient(gx)
    p = gx * gx + gy * gy + 1e-12
    # profile curvature (negative = convex in the downslope direction)
    prof = (gxx * gx * gx + 2.0 * gxy * gx * gy + gyy * gy * gy) / (p ** 1.5)
    plan = (gxx * gy * gy - 2.0 * gxy * gx * gy + gyy * gx * gx) / (p ** 1.5)
    return prof.astype(np.float32), plan.astype(np.float32)


def fault_polarity_field(trace: np.ndarray, elev: np.ndarray, *, sample_px: int = 4) -> np.ndarray:
    """R5-2: local dip polarity of each catalogue trace from topography.

    For every trace pixel, sample the elevation a few pixels to either side along
    the local strike normal and take the sign of the difference: +1 when the
    right-hand side of the strike direction is lower, -1 when the left-hand side
    is.  That is a *proxy* for the throw direction of the fault (the down-thrown
    side is lower), valid only where the topography still records the scarp; it
    is deliberately coarse, and the corridor weighting uses the sign of a whole
    trace, never a single pixel.

    Regression (2026-09-28): the first version built two full-grid ``np.mgrid``
    index arrays (0.6 GB of temporaries) and gathered 4 × 12.3 M elevations; it
    is now O(number of trace pixels) and identical in meaning.
    """
    t = np.asarray(trace, dtype=bool)
    e = np.nan_to_num(np.asarray(elev, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    out = np.full(t.shape, np.nan, dtype=np.float32)
    ys, xs = np.nonzero(t)
    if ys.size == 0:
        return out
    strike, _conf = local_strike(t)
    s = np.radians(np.nan_to_num(strike[ys, xs], nan=0.0))
    # normal to the strike direction (x = col, y = row): (cos s, -sin s)
    nx, ny = np.cos(s), -np.sin(s)
    o = int(sample_px)
    dx = np.round(nx * o).astype(np.int32)
    dy = np.round(ny * o).astype(np.int32)
    c1 = np.clip(xs + dx, 0, t.shape[1] - 1); r1 = np.clip(ys + dy, 0, t.shape[0] - 1)
    c2 = np.clip(xs - dx, 0, t.shape[1] - 1); r2 = np.clip(ys - dy, 0, t.shape[0] - 1)
    diff = e[r1, c1] - e[r2, c2]
    out[ys, xs] = np.sign(diff).astype(np.float32)
    return out


def _band_patch(shape, pa, pb, half_width, weight):
    """(y0, x0, patch): a thin band of half-width ``half_width`` px between two
    tips, tapered as ``weight * (1 - d/half_width)`` in point-to-segment
    distance.  Patch form keeps the allocation independent of grid size."""
    hw = float(half_width)
    if hw <= 0 or weight <= 0:
        return None
    y0 = int(max(min(pa[0], pb[0]) - hw - 2, 0))
    y1 = int(min(max(pa[0], pb[0]) + hw + 3, shape[0]))
    x0 = int(max(min(pa[1], pb[1]) - hw - 2, 0))
    x1 = int(min(max(pa[1], pb[1]) + hw + 3, shape[1]))
    if y0 >= y1 or x0 >= x1:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dy = float(pb[0] - pa[0]); dx = float(pb[1] - pa[1])
    l2 = dy * dy + dx * dx
    if l2 <= 0:
        t = np.zeros_like(yy, dtype=np.float32)
    else:
        t = np.clip(((yy - pa[0]) * dy + (xx - pa[1]) * dx) / l2, 0.0, 1.0)
    py = pa[0] + t * dy
    px = pa[1] + t * dx
    d = np.hypot(yy - py, xx - px)
    patch = (weight * np.clip(1.0 - d / hw, 0.0, 1.0)).astype(np.float32)
    return y0, x0, patch


def accommodation_corridors(
    trace: np.ndarray,
    elev: np.ndarray,
    *,
    min_sep_px: float = 50.0,
    max_sep_px: float = 250.0,
    max_strike_diff_deg: float = 50.0,
    min_len_px: float = 20.0,
    max_pairs: int = 400,
    pixel_m: float = 100.0,
) -> np.ndarray:
    """R5-2: accommodation-zone / transfer-corridor field between opposed-dip strands.

    Faulds et al. (2026) report accommodation zones as 19.3 % of favourable
    structural-setting *area* (2nd largest by area, 5.7-6.8 % by count):
    spatially extensive, structurally diffuse settings where two fault systems
    with opposed polarity hand over displacement.  Such transfer zones are
    bounded by mapped faults but their interior is typically unmapped.

    Rule used here
    --------------
    1. components of the context catalogue longer than ``min_len_px`` (2 km) —
       a transfer zone is a *system-scale* feature, not a 2-pixel speckle;
    2. per-component topographic polarity proxy (:func:`fault_polarity_field`),
       strike and tips from the principal axis;
    3. keep tip pairs 5-25 km apart, strike difference <= 50 deg, **opposed
       polarity**, weight = parallelity x separation kernel (peaking at the 2.8 km
       relay-ramp mean of Giddens & Faulds 2025) x length term;
    4. sort by weight and paint at most ``max_pairs`` thin bands (half-width
       ``clip(sep/10, 3, 12)`` px = 0.3-1.2 km) along the facing-tip segment.

    Regression (2026-09-28): the first version painted a wide quadratic quad per
    pair, which on an 800 x 800 test window marked 98 % of all pixels and took
    28 s; the selective banded form marks the corridor itself (a few per cent of
    the window) and is ~100x cheaper.
    """
    t = np.asarray(trace, dtype=bool)
    lab, n = ndimage.label(t, structure=np.ones((3, 3), dtype=int))
    field = np.zeros(t.shape, dtype=np.float32)
    if n < 2:
        return field
    pol = fault_polarity_field(t, elev)
    objs = ndimage.find_objects(lab)
    comps = []
    for cid in range(1, n + 1):
        sl = objs[cid - 1]
        if sl is None:
            continue
        yy, xx = np.nonzero(lab[sl] == cid)
        yy, xx = yy + sl[0].start, xx + sl[1].start
        if yy.size < 2:
            continue
        p = pol[yy, xx]
        p = p[np.isfinite(p)]
        if p.size == 0:
            continue
        pts = np.stack([yy, xx], axis=1).astype(np.float32)
        c = pts.mean(axis=0)
        q = pts - c
        evals, evecs = np.linalg.eigh(q.T @ q)
        axis = evecs[:, int(np.argmax(evals))]
        proj = q @ axis
        i0, i1 = int(np.argmin(proj)), int(np.argmax(proj))
        length = float(proj[i1] - proj[i0])
        if length < min_len_px:
            continue
        strike = float((np.degrees(np.arctan2(axis[1], axis[0])) + 360.0) % 180.0)
        comps.append({"id": cid, "p0": pts[i0], "p1": pts[i1], "strike": strike,
                      "polarity": 1.0 if float(np.mean(p)) >= 0 else -1.0,
                      "length": length})
    if len(comps) < 2:
        return field
    tips = []
    for c in comps:
        tips.append((c["p0"], c))
        tips.append((c["p1"], c))
    pts = np.array([tp[0] for tp in tips], dtype=np.float32)
    tree = cKDTree(pts)
    pairs = tree.query_pairs(r=float(max_sep_px), output_type="ndarray")
    cand = []
    for i, j in pairs:
        (pa, ca), (pb, cb) = tips[i], tips[j]
        if ca["id"] == cb["id"]:
            continue
        sep = float(np.hypot(*(pa - pb)))
        if sep < min_sep_px:
            continue
        sd = abs(ca["strike"] - cb["strike"]) % 180.0
        sd = min(sd, 180.0 - sd)
        if sd > max_strike_diff_deg:
            continue
        if ca["polarity"] == cb["polarity"]:
            continue                      # opposed polarity is the defining property
        sep_km = sep * pixel_m / 1000.0
        len_term = min(1.0, 0.5 * (ca["length"] + cb["length"]) / 200.0)
        w = float(np.clip((1.0 - sd / max_strike_diff_deg) * len_term *
                          np.exp(-0.5 * ((sep_km - 2.8) / 8.0) ** 2), 0.0, 1.0))
        if w <= 0:
            continue
        cand.append((w, sep, pa, pb))
    cand.sort(key=lambda x: -x[0])
    for w, sep, pa, pb in cand[:max_pairs]:
        patch = _band_patch(t.shape, pa, pb, float(np.clip(sep / 10.0, 3.0, 12.0)), w)
        if patch is not None:
            y0, x0, arr = patch
            np.maximum(field[y0:y0 + arr.shape[0], x0:x0 + arr.shape[1]], arr,
                       out=field[y0:y0 + arr.shape[0], x0:x0 + arr.shape[1]])
    field[t] = 0.0            # the hypothesis is about the *unmapped* corridor interior
    return field


# ---------------------------------------------------------------------------
# Round 6 — new hypotheses (see research/hypotheses_round6.md)
# ---------------------------------------------------------------------------

def _outward_direction_tip(trace: np.ndarray, ey: int, ex: int):
    """Unit outward vector (east, south) from trace interior through tip."""
    t = np.asarray(trace, dtype=bool)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            yy, xx = ey + dy, ex + dx
            if 0 <= yy < t.shape[0] and 0 <= xx < t.shape[1] and t[yy, xx]:
                n = float(np.hypot(dy, dx))
                if n == 0:
                    continue
                # outward = - interior direction
                return np.array([-dx / n, -dy / n], dtype=np.float32)  # (east, south)
    return None


def horsetail_splay_field(
    trace: np.ndarray,
    elev_slope: np.ndarray | None = None,
    det_elev: np.ndarray | None = None,
    *,
    radius_px: float = 20.0,
    half_angle_deg: float = 60.0,
    sigma_angle_deg: float = 35.0,
) -> np.ndarray:
    """R6-1: horsetail splay fan at fault terminations.

    For each endpoint pixel, emit a 120° fan (half-angle 60°) of radius
    radius_px outward from the tip. Weight decays linearly with distance and
    with angular deviation from the outward direction (Gaussian in angle).
    The fan marks where distributed horsetail splays would occur — minor faults
    with minimal surface rupture that are difficult to recognize even with lidar
    (Faulds et al. 2026, S14) and that the catalogue omits.
    """
    t = np.asarray(trace, dtype=bool)
    field = np.zeros(t.shape, dtype=np.float32)
    if not t.any():
        return field
    ends = endpoint_mask(t)
    ys, xs = np.nonzero(ends)
    if ys.size == 0:
        return field
    strike, _conf = local_strike(t, window=9)
    R = float(radius_px)
    half_rad = np.radians(float(half_angle_deg))
    cos_half = float(np.cos(half_rad))
    sigma_rad = np.radians(float(sigma_angle_deg))
    # optional modulation by slope magnitude
    slope_mod = None
    if elev_slope is not None:
        s = np.nan_to_num(np.asarray(elev_slope, dtype=np.float32), nan=0.0)
        # normalize to [0,1] via percentile
        lo, hi = np.percentile(s[np.isfinite(s)], [10, 90]) if np.isfinite(s).any() else (0.0, 1.0)
        if hi > lo:
            slope_mod = np.clip((s - lo) / (hi - lo + 1e-9), 0.0, 1.0)
    for ey, ex in zip(ys, xs):
        outward = _outward_direction_tip(t, int(ey), int(ex))
        if outward is None:
            continue
        # outward is (east, south) = (dx_col, dy_row)
        # ensure we have a finite strike at tip, else use outward as strike proxy
        # (no additional filtering on strike confidence for now)
        r = int(np.ceil(R))
        y0, y1 = max(int(ey) - r, 0), min(int(ey) + r + 1, t.shape[0])
        x0, x1 = max(int(ex) - r, 0), min(int(ex) + r + 1, t.shape[1])
        if y1 <= y0 or x1 <= x0:
            continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        vy = yy - int(ey)  # south
        vx = xx - int(ex)  # east
        d = np.hypot(vy, vx).astype(np.float32)
        # avoid division by zero at tip itself
        with np.errstate(invalid="ignore", divide="ignore"):
            cosang = (vx * outward[0] + vy * outward[1]) / np.where(d > 0, d, 1.0)
        wedge = (d > 1.0) & (d <= R) & (cosang >= cos_half)
        if not wedge.any():
            continue
        # distance decay
        w_dist = np.clip(1.0 - d / R, 0.0, 1.0)
        # angular decay: Gaussian in angle difference
        # angle = arccos(cosang), weight = exp(-0.5*(angle/sigma)^2)
        ang = np.arccos(np.clip(cosang, -1.0, 1.0))
        w_ang = np.exp(-0.5 * (ang / (sigma_rad + 1e-9)) ** 2)
        val = (w_dist * w_ang).astype(np.float32)
        if slope_mod is not None:
            # modulate by local slope magnitude (scarplet presence)
            patch_mod = slope_mod[y0:y1, x0:x1]
            # keep at least 0.3 even where slope low (horsetails are low amplitude)
            val = val * (0.3 + 0.7 * patch_mod)
        patch = np.where(wedge, val, 0.0).astype(np.float32)
        # max over all tips
        field[y0:y1, x0:x1] = np.maximum(field[y0:y1, x0:x1], patch)
    # strictly off-trace
    field[t] = 0.0
    # light smoothing so fan is continuous
    field = ndimage.gaussian_filter(field, sigma=1.0).astype(np.float32)
    field[t] = 0.0
    return field


def intersection_halos(
    trace: np.ndarray,
    shear: np.ndarray | None = None,
    dilation: np.ndarray | None = None,
    *,
    strike_window: int = 9,
    high_angle_deg: float = 45.0,
    near_miss_px: float = 20.0,
    halo_sigma_px: float = 10.0,
    max_pairs: int = 500,
) -> np.ndarray:
    """R6-2: normal × strike-slip intersection halos.

    Detects (a) true junctions where strike variance > high_angle_deg and
    (b) near-miss tip pairs within near_miss_px whose strikes differ by > high_angle_deg.
    Emits Gaussian halos weighted by shear × dilation (geodetic strain).
    """
    t = np.asarray(trace, dtype=bool)
    field = np.zeros(t.shape, dtype=np.float32)
    if not t.any():
        return field
    # --- (a) junction-based high-angle intersections ---
    k = np.ones((3, 3), dtype=np.uint8)
    neigh = ndimage.convolve(t.astype(np.uint8), k, mode="constant", cval=0) - t.astype(np.uint8)
    junctions = t & (neigh >= 3)
    candidate = np.zeros(t.shape, dtype=bool)
    if junctions.any():
        strike, _conf = local_strike(t, window=strike_window)
        # strike is NaN off-trace; we sample in a window around each junction
        # for efficiency, compute circular variance via structure tensor of strike?
        # Simple: for each junction, collect strikes of trace pixels in 5x5 window
        ys, xs = np.nonzero(junctions)
        # precompute strike as unit vectors double angle (mod 180 -> mod 360)
        st_rad = np.radians(np.nan_to_num(strike, nan=0.0) * 2.0)
        # for each junction, look at window
        for y, x in zip(ys, xs):
            y0, y1 = max(y - 2, 0), min(y + 3, t.shape[0])
            x0, x1 = max(x - 2, 0), min(x + 3, t.shape[1])
            window_traces = t[y0:y1, x0:x1]
            if window_traces.sum() < 3:
                continue
            vals = strike[y0:y1, x0:x1][window_traces]
            vals = vals[np.isfinite(vals)]
            if vals.size < 2:
                continue
            # circular difference max
            # compute max pairwise difference mod 180
            diffs = []
            for i in range(len(vals)):
                for j in range(i + 1, len(vals)):
                    d = abs(float(vals[i] - vals[j])) % 180.0
                    d = min(d, 180.0 - d)
                    diffs.append(d)
            if not diffs:
                continue
            if max(diffs) >= high_angle_deg:
                candidate[y, x] = True
    # --- (b) near-miss high-angle tip pairs ---
    # reuse relay_corridors logic but inverted strike condition
    lab, n = ndimage.label(t, structure=np.ones((3, 3), dtype=int))
    if n >= 2:
        objs = ndimage.find_objects(lab)
        tips = []
        for cid in range(1, n + 1):
            sl = objs[cid - 1]
            if sl is None:
                continue
            yy, xx = np.nonzero(lab[sl] == cid)
            yy = yy + sl[0].start
            xx = xx + sl[1].start
            if yy.size < 2:
                continue
            pts = np.stack([yy, xx], axis=1).astype(np.float32)
            c = pts.mean(axis=0)
            q = pts - c
            evals, evecs = np.linalg.eigh(q.T @ q)
            axis = evecs[:, int(np.argmax(evals))]
            strike = float((np.degrees(np.arctan2(axis[1], axis[0])) + 360.0) % 180.0)
            # tips = extremes
            proj = q @ axis
            i0, i1 = int(np.argmin(proj)), int(np.argmax(proj))
            tips.append((pts[i0], pts[i1], strike, cid))
        if len(tips) >= 2:
            tip_pts = np.array([p for a, b, _s, _c in tips for p in (a, b)], dtype=np.float32)
            tree = cKDTree(tip_pts)
            pairs = tree.query_pairs(r=float(near_miss_px), output_type="ndarray")
            for i, j in pairs:
                ca, cb = i // 2, j // 2
                if ca == cb:
                    continue
                (a0, a1, sa, _), (b0, b1, sb, _) = tips[ca], tips[cb]
                sd = abs(sa - sb) % 180.0
                sd = min(sd, 180.0 - sd)
                if sd < high_angle_deg:
                    continue
                # mark both tips as candidate intersections
                for pt in (a0, a1, b0, b1):
                    y, x = int(pt[0]), int(pt[1])
                    if 0 <= y < t.shape[0] and 0 <= x < t.shape[1]:
                        # check if tips are within near_miss_px of each other
                        # (we already know at least one pair is, but mark all)
                        candidate[y, x] = True
    # --- halo emission ---
    if not candidate.any():
        return field
    # Gaussian blur of candidate points
    halo = ndimage.gaussian_filter(candidate.astype(np.float32), sigma=halo_sigma_px)
    # geodetic weighting
    weight = np.ones(t.shape, dtype=np.float32)
    if shear is not None:
        s = np.nan_to_num(np.asarray(shear, dtype=np.float32), nan=0.0)
        # robust to [0,1]
        if np.isfinite(s).any():
            lo, hi = np.percentile(s[np.isfinite(s)], [5, 95])
            if hi > lo:
                sn = np.clip((s - lo) / (hi - lo + 1e-9), 0.0, 1.0)
                weight = weight * (0.3 + 0.7 * sn)
    if dilation is not None:
        d = np.nan_to_num(np.asarray(dilation, dtype=np.float32), nan=0.0)
        if np.isfinite(d).any():
            lo, hi = np.percentile(d[np.isfinite(d)], [5, 95])
            if hi > lo:
                dn = np.clip((d - lo) / (hi - lo + 1e-9), 0.0, 1.0)
                weight = weight * (0.3 + 0.7 * dn)
    field = (halo * weight).astype(np.float32)
    field[t] = 0.0
    return field


def conductive_base_step(
    cond_surf: np.ndarray | None,
    depth_to_base: np.ndarray | None,
    tmi: np.ndarray | None = None,
    grav_hg: np.ndarray | None = None,
    *,
    hgm_percentile: float = 90.0,
    cond_percentile: float = 80.0,
    mag_low_percentile: float = 20.0,
) -> np.ndarray:
    """R6-3: conductive-base step / clay-cap edge."""
    # need at least cond and depth
    if cond_surf is None or depth_to_base is None:
        # return zeros shaped like whichever is available, or empty
        if cond_surf is not None:
            return np.zeros(np.shape(cond_surf), dtype=np.float32)
        if depth_to_base is not None:
            return np.zeros(np.shape(depth_to_base), dtype=np.float32)
        return np.zeros((1, 1), dtype=np.float32)
    # work with finite-filled arrays
    cond = np.nan_to_num(np.asarray(cond_surf, dtype=np.float32), nan=0.0)
    depth = np.nan_to_num(np.asarray(depth_to_base, dtype=np.float32), nan=0.0)
    shape = cond.shape
    # HGM of depth_to_base
    gy, gx = np.gradient(depth)
    hgm_depth = np.hypot(gx, gy).astype(np.float32)
    if not np.isfinite(hgm_depth).any():
        return np.zeros(shape, dtype=np.float32)
    thresh_hgm = np.percentile(hgm_depth[np.isfinite(hgm_depth)], hgm_percentile)
    hgm_high = hgm_depth >= thresh_hgm
    thresh_cond = np.percentile(cond[np.isfinite(cond)], cond_percentile)
    cond_high = cond >= thresh_cond
    mag_low = None
    if tmi is not None:
        mag = np.nan_to_num(np.asarray(tmi, dtype=np.float32), nan=0.0)
        if np.isfinite(mag).any():
            thresh_mag = np.percentile(mag[np.isfinite(mag)], mag_low_percentile)
            mag_low = mag <= thresh_mag
    # coincidence: HGM ridge near cond high (and mag low if available)
    # dilate cond_high by 5 px to allow near coincidence
    cond_dil = ndimage.binary_dilation(cond_high, iterations=5)
    if mag_low is not None:
        mag_dil = ndimage.binary_dilation(mag_low, iterations=5)
        coincidence = hgm_high & cond_dil & mag_dil
    else:
        coincidence = hgm_high & cond_dil
    if not coincidence.any():
        return np.zeros(shape, dtype=np.float32)
    # distance decay from coincidence
    dist = ndimage.distance_transform_edt(~coincidence).astype(np.float32)
    # Gaussian-like decay: exp(-dist^2 / (2*sigma^2)), sigma=5 px
    sigma = 5.0
    field = np.exp(-0.5 * (dist / sigma) ** 2).astype(np.float32)
    field[~np.isfinite(cond)] = 0.0
    # weight by cond magnitude
    cond_norm = np.clip((cond - thresh_cond) / (np.percentile(cond, 95) - thresh_cond + 1e-9), 0.0, 1.0) if np.isfinite(cond).any() else 0.0
    field = field * (0.5 + 0.5 * cond_norm)
    return field.astype(np.float32)


def paleo_shoreline_suppression(
    det_elev: np.ndarray | None,
    det_elev_slope: np.ndarray | None,
    grav_hg: np.ndarray | None = None,
    *,
    coherence_thresh: float = 0.65,
    slope_low_percentile: float = 30.0,
) -> dict:
    """R6-5: paleo-lake shoreline mask + sub-lake fault enhancement.

    Returns dict with 'shoreline_mask' and 'sublake_enhanced'.
    """
    if det_elev is None:
        return {}
    elev = np.nan_to_num(np.asarray(det_elev, dtype=np.float32), nan=0.0)
    shape = elev.shape
    # structure tensor for coherence
    try:
        strike, coh, _energy = structure_tensor(elev, sigma=2.0)
    except Exception:
        coh = np.zeros(shape, dtype=np.float32)
        strike = np.zeros(shape, dtype=np.float32)
    # slope low
    if det_elev_slope is not None:
        slope = np.nan_to_num(np.asarray(det_elev_slope, dtype=np.float32), nan=0.0)
        if np.isfinite(slope).any():
            thresh_slope = np.percentile(slope[np.isfinite(slope)], slope_low_percentile)
            slope_low = slope <= thresh_slope
        else:
            slope_low = np.ones(shape, dtype=bool)
    else:
        slope_low = np.ones(shape, dtype=bool)
    shoreline = (coh >= coherence_thresh) & slope_low
    # sub-lake: detrended elev < 0 (valley bottom) and grav_hg high
    sublake = np.zeros(shape, dtype=np.float32)
    if grav_hg is not None:
        gh = np.nan_to_num(np.asarray(grav_hg, dtype=np.float32), nan=0.0)
        if np.isfinite(gh).any():
            thresh_gh = np.percentile(gh[np.isfinite(gh)], 90.0)
            gh_high = gh >= thresh_gh
            # valley bottom: elev < 0 (detrended)
            valley = elev < 0
            sublake_mask = valley & gh_high
            # distance from shoreline: enhance where not near shoreline?
            if shoreline.any():
                dist_shore = ndimage.distance_transform_edt(~shoreline).astype(np.float32)
                # weight decays near shoreline (shoreline itself is FP, not fault)
                w = 1.0 - np.exp(-0.5 * (dist_shore / 10.0) ** 2)
                sublake = np.where(sublake_mask, w, 0.0).astype(np.float32)
            else:
                sublake = sublake_mask.astype(np.float32)
    return {
        "shoreline_mask": shoreline.astype(np.float32),
        "sublake_enhanced": sublake.astype(np.float32),
        "shoreline_dist": ndimage.distance_transform_edt(~shoreline).astype(np.float32) if shoreline.any() else np.full(shape, 1e6, dtype=np.float32),
    }


def slip_dilation_tendency_field(
    trace: np.ndarray,
    slip_path: str | None = None,
    dilation_path: str | None = None,
    shapefile_dir: str = "data/external",
) -> dict:
    """R6-4: slip & dilation tendency from external INGENIOUS release.

    If the external shapefile is not present, returns empty dict and logs FLAG.
    The shapefile is expected at data/external/Shapefile_INGENIOUS area/...
    with fields slip_tendency and dilation_tendency (0-1).
    This function is a placeholder for the real rasterization which requires
    geopandas + rasterio on an unrestricted machine.
    """
    # check if external files exist
    import os
    from pathlib import Path
    base = Path(shapefile_dir)
    # look for any .shp containing slip
    shp_candidates = list(base.rglob("*.shp"))
    if not shp_candidates:
        return {}  # external data not present — caller should FLAG
    # if present, we would rasterize here; for now return empty to avoid heavy dep
    # Real implementation would:
    #   gdf = geopandas.read_file(shp)
    #   rasterize with rasterio.features.rasterize onto competition grid
    #   then compute field = dilation * slip * (1 - catalogue_proximity)
    return {}


# ---------------------------------------------------------------------------
# Round-7 hypothesis channels (research/hypotheses_round7.md)
# ---------------------------------------------------------------------------

def gravity_topology(
    grav_hg: np.ndarray,
    grav_slope: np.ndarray | None = None,
    *,
    sigma: float = 1.0,
    support_px: float = 6.0,
) -> dict:
    """R7-3: gravity-gradient termination & intersection topology.

    Faulds et al. 2026 (KB S11, VERIFIED): *"terminating and intersecting
    gravity gradients respectively defined many of the fault terminations and
    fault intersections. This was especially important in defining FSS in the
    many basins of the region, where basin-fill sediments obscure the
    subsurface architecture"* — the label producers' own basin playbook.

    The operator is ``gems.geoedges.edge_termination_field`` (ridge skeleton of
    the gradient magnitude, weighted terminations and junctions).  Pure
    geophysics — no catalogue input, so leak-free under hide-and-recover by
    construction.

    Returns
    -------
    dict with
      grav_ridge : gradient magnitude along the ridge skeleton (edge strength
                   where a real geophysical edge exists)
      grav_topo  : termination field + junction field in [0, 2] (compact
                   topology maps of where edges stop and cross)

    The caller decides which of these an arm uses.
    """
    from gems import geoedges as ge

    base = np.nan_to_num(np.asarray(grav_hg, dtype=np.float32),
                         nan=0.0, posinf=0.0, neginf=0.0)
    if grav_slope is not None:
        base = base + np.nan_to_num(np.asarray(grav_slope, dtype=np.float32),
                                    nan=0.0, posinf=0.0, neginf=0.0)
    out = ge.edge_termination_field(base, sigma=sigma, support_px=support_px)
    skel = out["skeleton"]
    ridge = np.where(skel, out["edge_mag"], 0.0).astype(np.float32)
    topo = (out["term_field"] + out["junction_field"]).astype(np.float32)
    return {"grav_ridge": ridge, "grav_topo": topo}


def transtensional_coupling(
    shear: np.ndarray,
    dilat: np.ndarray,
    *,
    extension_positive: bool = True,
) -> dict:
    """R7-5: shear x extension (transtensional) coupling field.

    KB S1/S4/S7 (VERIFIED): systems concentrate in transtensional areas of
    highest strain rate; step-overs and horsetail terminations show the largest
    modelled dilatation and Coulomb shear-traction increases.

    ``coupling = relu(unit(shear)) * relu(unit(max(±dilatation, 0)))`` — the
    *interaction* of excess shear with excess *physical* extension, not either
    rate alone.  The extension/contraction clip is applied to the physical sign
    BEFORE scaling, so a below-median contraction can never read as coupling.

    The band tag ("rate of volumetric strain (expansion/contraction)") does not
    state the sign convention; the default follows the geodetic convention
    (positive = expansion/extension).  The flag exists so the opposite
    convention can be ablated without a code change (FLAG #12,
    hypotheses_round7.md).
    """
    s = np.nan_to_num(np.asarray(shear, dtype=np.float32),
                      nan=0.0, posinf=0.0, neginf=0.0)
    d = np.nan_to_num(np.asarray(dilat, dtype=np.float32),
                      nan=0.0, posinf=0.0, neginf=0.0)
    if not extension_positive:
        d = -d
    d_ext = np.maximum(d, 0.0)                    # physical extension only
    s_rel = np.maximum(robust_unit(s), 0.0)       # excess shear
    d_rel = np.maximum(robust_unit(d_ext), 0.0)   # excess extension
    coupling = s_rel * d_rel
    return {"trans_coupling": coupling.astype(np.float32)}


def misregister_mask(mask: np.ndarray, delta_px: int, rng: np.random.Generator
                     ) -> tuple[np.ndarray, np.ndarray]:
    """R7-1 stress protocol: rigidly translate each component by <= delta_px.

    Simulates the C28 condition ("portions of the existing fault data may be
    misaligned from the true location of the surface fault"): every mapped
    component is displaced by a random integer vector (uniform direction,
    magnitude in [1, delta_px]; a redraw forces a non-zero shift).

    Returns (shifted_mask, offsets) where offsets is an (n+1, 2) int array of
    (dy, dx) per component id (id 0 unused).
    """
    m = int(delta_px)
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    if n == 0 or m <= 0:
        return mask.copy(), np.zeros((n + 1, 2), dtype=int)
    ys, xs = np.nonzero(mask)
    cids = lab[ys, xs]
    dy = rng.integers(-m, m + 1, size=n + 1)
    dx = rng.integers(-m, m + 1, size=n + 1)
    zero = (dy == 0) & (dx == 0)
    zero[0] = False
    if zero.any():                       # one redraw; if still zero, accept
        dy[zero] = rng.integers(-m, m + 1, size=int(zero.sum()))
        dx[zero] = rng.integers(-m, m + 1, size=int(zero.sum()))
    ny, nx = mask.shape
    nys = np.clip(ys + dy[cids], 0, ny - 1)
    nxs = np.clip(xs + dx[cids], 0, nx - 1)
    out = np.zeros(mask.shape, dtype=bool)
    out[nys, nxs] = True
    offsets = np.stack([dy, dx], axis=1)
    return out, offsets


def align_traces_to_expression(
    context: np.ndarray,
    expression: np.ndarray,
    *,
    max_offset: int = 3,
    penalty_per_px: float = 0.02,
) -> tuple[np.ndarray, np.ndarray]:
    """R7-1: per-component rigid alignment of catalogue traces to expression.

    C28 (VERIFIED problem description): *"portions of the existing fault data
    may be misaligned from the true location of the surface fault, which is the
    prediction target."*  For every connected component of ``context``, search
    integer shifts in [-max_offset, max_offset]^2 (the metric kernel is 3 px)
    and pick the shift maximising ``mean expression under the trace``
    − ``penalty_per_px`` · |shift|.  The (0, 0) shift competes on equal terms,
    so a well-registered trace is left alone.

    The displacement penalty (amended 2026-09-29 after a crop smoke showed
    mean |offset| exceeding the injected misregistration on noisy expression —
    recorded BEFORE any gate numbers, not tuned on results) keeps the operator
    from sliding traces to expression noise: a 3 px move must buy > 0.06 mean
    expression (bands are robust-scaled to ~[−1, 1]).

    Leak-free under hide-and-recover: only the (visible) context mask and
    geophysical expression are read; hidden components are not in ``context``.

    Returns (corrected_mask, offset_mag) with offset_mag the per-pixel shift
    magnitude of the owning component (0 off-trace), *before* any credit
    pooling — the caller pools it (e.g. via line_max) for the metric kernel.
    """
    mask = np.asarray(context, dtype=bool)
    expr = np.nan_to_num(np.asarray(expression, dtype=np.float32),
                         nan=0.0, posinf=0.0, neginf=0.0)
    lab, n = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    offset_mag = np.zeros(mask.shape, dtype=np.float32)
    if n == 0:
        return mask.copy(), offset_mag
    ys, xs = np.nonzero(mask)
    cids = lab[ys, xs]
    ny, nx = mask.shape
    m = int(max_offset)
    shifts = [(dy, dx) for dy in range(-m, m + 1) for dx in range(-m, m + 1)]
    counts = np.bincount(cids, minlength=n + 1).astype(np.float64)
    # score[component, shift] = mean expression under the shifted component
    scores = np.full((n + 1, len(shifts)), -np.inf, dtype=np.float64)
    for k, (dy, dx) in enumerate(shifts):
        sy = np.clip(ys + dy, 0, ny - 1)
        sx = np.clip(xs + dx, 0, nx - 1)
        sums = np.bincount(cids, weights=expr[sy, sx], minlength=n + 1)
        scores[:, k] = sums / np.maximum(counts, 1.0)
    # penalised objective; the extra 1e-6/px makes exact ties resolve toward
    # the smallest displacement (expression ridges are commonly invariant along
    # strike, and an arbitrary along-strike slide would displace trace ends)
    dist = np.hypot([s[0] for s in shifts], [s[1] for s in shifts])
    objective = scores - (float(penalty_per_px) + 1e-6) * dist[None, :]
    pick = np.argmax(objective, axis=1)
    best_dy = np.array([shifts[p][0] for p in pick], dtype=np.int64)
    best_dx = np.array([shifts[p][1] for p in pick], dtype=np.int64)
    nys = np.clip(ys + best_dy[cids], 0, ny - 1)
    nxs = np.clip(xs + best_dx[cids], 0, nx - 1)
    corrected = np.zeros(mask.shape, dtype=bool)
    corrected[nys, nxs] = True
    mag = np.hypot(best_dy[cids], best_dx[cids]).astype(np.float32)
    offset_mag[nys, nxs] = mag
    return corrected, offset_mag


def component_offsets(n_comp: int, delta_px: int, rng: np.random.Generator
                      ) -> np.ndarray:
    """One rigid (dy, dx) shift per component id in 1..n_comp, |shift| <= delta.

    Shared by every view of the same fold so the simulated misregistered world
    is consistent (a component is displaced identically in the training and
    prediction contexts).  Non-zero shifts are forced when possible.
    """
    m = int(delta_px)
    dy = rng.integers(-m, m + 1, size=n_comp + 1)
    dx = rng.integers(-m, m + 1, size=n_comp + 1)
    zero = (dy == 0) & (dx == 0)
    zero[0] = False
    if zero.any():
        dy[zero] = rng.integers(-m, m + 1, size=int(zero.sum()))
        dx[zero] = rng.integers(-m, m + 1, size=int(zero.sum()))
    return np.stack([dy, dx], axis=1)


def displace_mask(mask: np.ndarray, lab: np.ndarray,
                  offsets: np.ndarray) -> np.ndarray:
    """Move every masked pixel by its component's offset (see component_offsets).

    ``lab`` is the component label array of the FULL catalogue, so any subset
    (training view, prediction view) is displaced consistently.
    """
    ys, xs = np.nonzero(mask)
    if ys.size == 0:
        return mask.copy()
    o = offsets[lab[ys, xs]]
    ny, nx = mask.shape
    out = np.zeros(mask.shape, dtype=bool)
    out[np.clip(ys + o[:, 0], 0, ny - 1), np.clip(xs + o[:, 1], 0, nx - 1)] = True
    return out


def _trace_endpoints(trace: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Endpoint pixels of a trace mask with outward unit vectors in (dy, dx).

    An endpoint has at most one 8-connected trace neighbour (isolated single
    pixels have no strike and are skipped).  Same definition as
    ``scripts/continuation_subset.py`` so the diagnostic and the operator agree.
    """
    from scipy.ndimage import convolve

    t = np.asarray(trace, dtype=bool)
    if not t.any():
        return (np.zeros(0, np.int64), np.zeros(0, np.int64),
                np.zeros((0, 2), np.float32))
    nbr = convolve(t.astype(np.uint8), np.ones((3, 3), np.uint8),
                   mode="constant", cval=0) - t.astype(np.uint8)
    ys, xs = np.nonzero(t & (nbr <= 1))
    keep_y, keep_x, dirs = [], [], []
    for y, x in zip(ys.tolist(), xs.tolist()):
        d = _outward_direction_tip(t, int(y), int(x))   # (east, south)
        if d is None or float(d[0]) == 0.0 and float(d[1]) == 0.0:
            continue
        keep_y.append(y)
        keep_x.append(x)
        dirs.append((float(d[1]), float(d[0])))         # (dy, dx)
    return (np.asarray(keep_y, np.int64), np.asarray(keep_x, np.int64),
            np.asarray(dirs, np.float32).reshape(-1, 2))


def _robust_z(a: np.ndarray) -> np.ndarray:
    """(a - median) / (1.4826 * MAD), NaN-safe; constant fields map to 0."""
    v = np.nan_to_num(np.asarray(a, dtype=np.float32),
                      nan=0.0, posinf=0.0, neginf=0.0)
    finite = v[np.isfinite(v)]
    if finite.size == 0:
        return np.zeros_like(v)
    med = float(np.median(finite))
    mad = float(np.median(np.abs(finite - med)))
    scale = 1.4826 * mad
    if scale <= 1e-12:
        # sparse-ridge case (mostly-constant field): fall back to std, then 0
        scale = float(np.std(finite))
    if scale <= 1e-12:
        return np.zeros_like(v)
    return (v - med) / scale


def continuation_stitches(
    trace: np.ndarray,
    rtp: np.ndarray,
    tmi: np.ndarray,
    tmi_hg: np.ndarray,
    grav_hg: np.ndarray,
    depth_to_base: np.ndarray | None = None,
    det_elev: np.ndarray | None = None,
    *,
    max_len_px: float = 48.0,
    collinearity_deg: float = 30.0,
    corridor_halfwidth: int = 3,
    min_crest: float = 0.10,
) -> dict:
    """R7-2: buried continuation stitching through cover.

    ``research/hypotheses_round7.md``: *a potential-field ridge corridor that
    continues a catalogued trace along strike past its mapped tip or across a
    mapped gap, especially where basin fill or lake sediments cover the
    connection (``depth_to_base_surf`` thick, ``det_elev`` flat).  Collinearity
    tolerance 30°, corridor width ≤ 3 px.*  C21 — continuations past mapped
    tips are scoring truth; S14 — faults obscured by lake sediments end where
    expression ends, not where the fault ends.

    Algorithm: from every catalogue tip, walk the crest of the combined
    potential-field ridge expression (robust-z mean of ``rtp``, ``tmi``,
    ``tmi_hg``, ``grav_hg``) outward along the tip's own strike.  A step is
    accepted when the across-corridor crest score (crest minus the flank mean
    at ±``corridor_halfwidth``) clears ``min_crest`` and the heading stays
    within ``collinearity_deg`` of the tip's outward direction.  Support decays
    linearly to ``max_len_px``; landing on another strand (a mapped gap
    crossing) pins support at 1.  Leak-free under hide-and-recover: the walk
    starts only at *visible* tips.

    Returns
    -------
    dict with
      stitch_bridge : corridor crest support in [0, 1]
      stitch_cover  : the same corridor re-weighted by a cover factor
                      (``depth_to_base_surf`` thick and ``det_elev`` flat —
                      the "hidden by cover" emphasis of the signature)
    """
    ys, xs, dirs = _trace_endpoints(trace)
    ny, nx = np.asarray(trace, bool).shape
    bridge = np.zeros((ny, nx), np.float32)
    cover_out = np.zeros((ny, nx), np.float32)
    if ys.size == 0:
        return {"stitch_bridge": bridge, "stitch_cover": cover_out}

    expr = 0.25 * (_robust_z(rtp) + _robust_z(tmi)
                   + _robust_z(tmi_hg) + _robust_z(grav_hg))

    # cover factor: thick basin fill x flat topography, in [0, 1]
    if depth_to_base is not None:
        depth_z = np.clip(_robust_z(depth_to_base), 0.0, 2.0) / 2.0
    else:
        depth_z = np.zeros((ny, nx), np.float32)
    if det_elev is not None:
        elev = np.nan_to_num(np.asarray(det_elev, np.float32),
                             nan=0.0, posinf=0.0, neginf=0.0)
        gy, gx = np.gradient(elev)
        slope = np.hypot(gy, gx)
        med = float(np.median(slope[slope > 0])) if (slope > 0).any() else 1.0
        flat = np.exp(-slope / max(med, 1e-6)).astype(np.float32)
    else:
        flat = np.ones((ny, nx), np.float32)
    cover = depth_z * flat

    cos_lim = float(np.cos(np.deg2rad(collinearity_deg)))
    half = int(corridor_halfwidth)
    tmask = np.asarray(trace, bool)

    def crest_at(qy: int, qx: int, hy: float, hx: float) -> float:
        # across-corridor normal (rotate heading 90 deg); flank samples at +-half
        nyn, nxn = -hx, hy
        f1y = int(round(qy + nyn * half)); f1x = int(round(qx + nxn * half))
        f2y = int(round(qy - nyn * half)); f2x = int(round(qx - nxn * half))
        if not (0 <= f1y < ny and 0 <= f1x < nx and 0 <= f2y < ny and 0 <= f2x < nx):
            return -1.0
        return float(expr[qy, qx] - 0.5 * (expr[f1y, f1x] + expr[f2y, f2x]))

    for ty, tx, d in zip(ys.tolist(), xs.tolist(), dirs.tolist()):
        oy, ox = float(d[0]), float(d[1])
        hy, hx = oy, ox
        py, px = float(ty), float(tx)
        walked = 0.0
        for _ in range(int(max_len_px) + 4):
            if walked >= max_len_px:
                break
            cy, cx = int(round(py)), int(round(px))
            best = None
            best_s = min_crest
            for dy in (-2, -1, 0, 1, 2):
                for dx in (-2, -1, 0, 1, 2):
                    qy, qx = cy + dy, cx + dx
                    if not (0 <= qy < ny and 0 <= qx < nx):
                        continue
                    vy, vx = qy - ty, qx - tx          # vs the TIP: total
                    n = float(np.hypot(vy, vx))        # deviation is bounded
                    if n < 1.0 or n <= walked + 0.49:  # must advance outward
                        continue
                    if (vy * oy + vx * ox) / n < cos_lim:   # collinearity cone
                        continue
                    s = crest_at(qy, qx, hy, hx)
                    if s > best_s:
                        best_s = s
                        best = (qy, qx, vy / n, vx / n)
            if best is None:
                break
            qy, qx, hy, hx = best
            walked = float(np.hypot(qy - ty, qx - tx))
            decay = max(0.0, 1.0 - walked / max_len_px)
            support = float(np.clip(best_s, 0.0, 1.0)) * decay
            if tmask[qy, qx] and walked > 3.0:
                support = max(support, 1.0)           # gap connected: pin at 1
            if support > bridge[qy, qx]:
                bridge[qy, qx] = support
                cover_out[qy, qx] = support * float(cover[qy, qx])
            if tmask[qy, qx] and walked > 3.0:
                break
            py, px = float(qy), float(qx)

    return {"stitch_bridge": bridge, "stitch_cover": cover_out}
