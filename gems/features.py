"""Catalogue-geometry features computed from the known-fault catalogue.

Every feature here is computed ONLY from a "context" catalogue (the traces that
are visible to the model).  During hide-and-recover training the context is a
random subset of traces; at inference it is the full USGS/INGENIOUS catalogue.
Because the context is always an explicit input, the protocol can hide traces
completely and the model cannot read "distance to a known fault = 0" as the
answer (research/hypotheses.md, protocol section).

Feature set (as specified in the standing prompt):
  1. distance to the nearest known trace                     -> dist_trace
  2. azimuth to the nearest known trace                      -> az_to_trace
  3. along-strike vs across-strike distance to trace ends    -> across_strike,
                                                                along_strike,
                                                                dist_endpoint
  4. overlapping-tip detection and bridging corridors        -> relay_corridor
  5. intersection density                                    -> junction_density,
                                                                trace_density
  6. angle between a local lineament and known strikes       -> strike_mismatch
  7. slip / dilation tendency (INGENIOUS release)            -> slip_tendency,
                                                                dilation_tendency
                                                                (external rasters)

Vector inputs are optional: if the labels are 1-pixel-wide rasterized polylines
(the normal case for the competition's training_labels.tif), endpoints are
terminal pixels (exactly one 8-connected trace neighbour) and local strike comes
from a neighbourhood inertia tensor of the trace mask.  Both approximations are
measured and reported by tests/test_features.py on synthetic traces with known
geometry, so their error is documented rather than assumed.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


# ---------------------------------------------------------------------------
# 1-2. distance + azimuth to nearest trace
# ---------------------------------------------------------------------------

def distance_and_azimuth(trace_mask: np.ndarray) -> dict:
    """Return dist (px) to nearest trace pixel and azimuth (deg, 0=N, cw) TO it.

    Azimuth is defined as the compass direction from the pixel toward the
    nearest trace pixel, derived from the gradient of the distance field
    (points away from nearest trace, so we negate).
    """
    t = np.asarray(trace_mask, dtype=bool)
    dist = ndimage.distance_transform_edt(~t).astype(np.float32)
    gy, gx = np.gradient(dist.astype(np.float64))
    # gradient points away from the nearest trace; azimuth toward the trace
    az = (np.degrees(np.arctan2(-gx, -gy)) + 360.0) % 360.0
    az = az.astype(np.float32)
    az[t] = 0.0  # direction is meaningless on the trace itself
    return {"dist_trace": dist, "az_to_trace": az}


# ---------------------------------------------------------------------------
# local strike of the catalogue
# ---------------------------------------------------------------------------

def compass_strike(dx_col: float, dy_row: float) -> float:
    """Compass strike (deg in [0,180)) of a direction vector given in image
    coordinates (dx = +east/col, dy = +south/row).  North is -dy.
    A N-S line has strike 0; an E-W line has strike 90.
    """
    return float((np.degrees(np.arctan2(dx_col, -dy_row))) % 180.0)


def strike_field(trace_mask: np.ndarray, window: int = 9) -> tuple[np.ndarray, np.ndarray]:
    """Local strike (deg) of the trace set at every trace pixel, plus a
    confidence measure.

    For each trace pixel, take trace pixels within a (2*window+1)^2 box and
    compute the orientation of the principal axis of their offsets (inertia
    tensor).  Strike is the compass strike of that axis in [0, 180) (0 = N-S).
    Confidence is the normalized eigenvalue gap in [0, 1].
    """
    t = np.asarray(trace_mask, dtype=bool)
    ys, xs = np.nonzero(t)
    n = ys.size
    strike = np.zeros(t.shape, dtype=np.float32)
    conf = np.zeros(t.shape, dtype=np.float32)
    if n == 0:
        return strike, conf

    w = int(window)
    # box-sum helpers for weighted moments
    def box(a: np.ndarray) -> np.ndarray:
        k = np.ones((2 * w + 1, 2 * w + 1), dtype=np.float64)
        return ndimage.convolve(a.astype(np.float64), k, mode="constant", cval=0.0)

    ii, jj = np.meshgrid(np.arange(t.shape[0]), np.arange(t.shape[1]), indexing="ij")
    T = t.astype(np.float64)
    Sx = box(T * jj)   # sum of x over trace pixels in box
    Sy = box(T * ii)   # sum of y
    Sxx = box(T * jj * jj)
    Syy = box(T * ii * ii)
    Sxy = box(T * ij_(ii, jj))
    N = box(T) + 1e-9

    mx, my = Sx / N, Sy / N
    cxx = Sxx / N - mx * mx
    cyy = Syy / N - my * my
    cxy = Sxy / N - mx * my

    # principal axis angle of the 2x2 covariance in (x=col, y=row) space
    theta = 0.5 * np.arctan2(2.0 * cxy, cxx - cyy)  # rad, from +col axis
    # eigenvalue gap as confidence
    tr = cxx + cyy
    det = cxx * cyy - cxy * cxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    l2 = tr / 2.0 - disc
    gap = (l1 - l2) / (l1 + l2 + 1e-12)

    # compass strike of the axis: azimuth = atan2(dx_col, -dy_row) mod 180
    dx = np.cos(theta)
    dy = np.sin(theta)
    strike_deg = (np.degrees(np.arctan2(dx, -dy)) + 360.0) % 180.0

    strike[t] = strike_deg[t].astype(np.float32)
    conf[t] = gap[t].astype(np.float32)
    return strike, conf


def ij_(ii: np.ndarray, jj: np.ndarray) -> np.ndarray:
    return (ii * jj).astype(np.float64)


# ---------------------------------------------------------------------------
# 3. along/across strike + endpoint distance
# ---------------------------------------------------------------------------

def endpoint_mask(trace_mask: np.ndarray) -> np.ndarray:
    """Terminal pixels of 1-px-wide rasterized polylines.

    A trace pixel is terminal when its 8-connected trace neighbourhood
    contains exactly one other trace pixel (excluding itself).  Junction
    pixels (>=3 neighbours) and mid-segment pixels (2 neighbours) are excluded.
    """
    t = np.asarray(trace_mask, dtype=bool)
    k = np.ones((3, 3), dtype=np.uint8)
    neigh = ndimage.convolve(t.astype(np.uint8), k, mode="constant", cval=0) - t.astype(np.uint8)
    return t & (neigh == 1)


def along_across_strike(trace_mask: np.ndarray, window: int = 9) -> dict:
    """Across-strike distance (signed), along-strike position, endpoint distance.

    across_strike : signed shortest distance to the trace, positive on the
        hanging-wall side of the local strike direction (sign convention
        chosen once and kept; magnitude is the physically meaningful part).
    along_strike  : projection of the vector-to-nearest-trace-pixel onto the
        local strike direction (px).
    dist_endpoint : distance to the nearest terminal pixel of the catalogue.
    """
    _da = distance_and_azimuth(trace_mask)
    dist = _da["dist_trace"]
    az = _da["az_to_trace"]
    strike, _conf = strike_field(trace_mask, window=window)

    # direction to nearest trace as a unit vector (dx east, dy south->north)
    az_rad = np.radians(az)
    ux = np.sin(az_rad)              # east component
    uy = np.cos(az_rad)              # north component
    # strike as unit vector (strike deg from north, [0,180))
    s_rad = np.radians(strike)
    sx = np.sin(s_rad)
    sy = np.cos(s_rad)

    # vector from pixel to nearest trace = -u * dist  (u points toward trace)
    vx, vy = -ux * dist, -uy * dist
    across = vx * sy - vy * sx       # perpendicular component (signed)
    along = vx * sx + vy * sy        # parallel component

    ends = endpoint_mask(trace_mask)
    if ends.any():
        dist_end = ndimage.distance_transform_edt(~ends).astype(np.float32)
    else:
        dist_end = np.full(dist.shape, np.float32(1e6))

    return {
        "across_strike": across.astype(np.float32),
        "along_strike": along.astype(np.float32),
        "dist_endpoint": dist_end,
    }


# ---------------------------------------------------------------------------
# 4. overlapping-tip detection and bridging corridors
# ---------------------------------------------------------------------------

def relay_corridors(
    trace_mask: np.ndarray,
    *,
    min_gap_px: float = 2.0,
    max_gap_px: float = 45.0,
    max_strike_diff_deg: float = 35.0,
) -> dict:
    """Detect overlapping/underlapping tip pairs and rasterize bridging corridors.

    Method (approximate, measured on synthetic pairs in tests/test_features.py):
      1. connected components of the trace mask = individual mapped traces.
      2. for each component, endpoints + strike via PCA of its pixels.
      3. pair endpoints of different components whose gap is in
         [min_gap_px, max_gap_px] and whose strikes differ by <= threshold
         (relay ramps link sub-parallel strands).
      4. each qualifying pair draws an elliptical corridor mask between the two
         tips, weighted by how "relay-like" the pair is (closer + more parallel
         = higher weight).  The corridor raster is the max over all pairs.

    Returns dict with:
      corridor      : float32 in [0, 1], the bridging-corridor score
      n_pairs       : number of qualifying tip pairs
      pair_list     : list of (comp_a, comp_b, gap_px, strike_diff_deg, weight)
    """
    t = np.asarray(trace_mask, dtype=bool)
    corridor = np.zeros(t.shape, dtype=np.float32)
    pairs_out: list[tuple] = []

    lab, n = ndimage.label(t, structure=np.ones((3, 3), dtype=int))
    if n < 2:
        return {"corridor": corridor, "n_pairs": 0, "pair_list": []}

    comps: list[dict] = []
    for cid in range(1, n + 1):
        ys, xs = np.nonzero(lab == cid)
        if ys.size < 3:
            continue
        pts = np.stack([ys.astype(np.float64), xs.astype(np.float64)], axis=1)
        mean = pts.mean(axis=0)
        c = np.cov((pts - mean).T)
        evals, evecs = np.linalg.eigh(c)
        axis = evecs[:, np.argmax(evals)]  # principal (strike) direction (row,col)
        # endpoints = farthest points along the principal axis
        proj = (pts - mean) @ axis
        i0, i1 = int(np.argmin(proj)), int(np.argmax(proj))
        comps.append({
            "id": cid,
            "p0": pts[i0],
            "p1": pts[i1],
            "axis": axis,
            "strike": (np.degrees(np.arctan2(axis[1], axis[0])) + 360.0) % 180.0,
        })

    def strike_diff(s1: float, s2: float) -> float:
        d = abs(s1 - s2) % 180.0
        return float(min(d, 180.0 - d))

    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            a, b = comps[i], comps[j]
            sd = strike_diff(a["strike"], b["strike"])
            if sd > max_strike_diff_deg:
                continue
            best = None
            for pa in (a["p0"], a["p1"]):
                for pb in (b["p0"], b["p1"]):
                    gap = float(np.hypot(*(pa - pb)))
                    if min_gap_px <= gap <= max_gap_px:
                        if best is None or gap < best[0]:
                            best = (gap, pa, pb)
            if best is None:
                continue
            gap, pa, pb = best
            w = float((1.0 - gap / max_gap_px) * (1.0 - sd / max_strike_diff_deg))
            w = float(np.clip(w, 0.0, 1.0))
            pairs_out.append((a["id"], b["id"], gap, sd, w))
            corridor = np.maximum(corridor, _elliptical_bridge(t.shape, pa, pb, gap, w))

    return {"corridor": corridor, "n_pairs": len(pairs_out), "pair_list": pairs_out}


def _elliptical_bridge(shape, pa, pb, gap, weight):
    """Elliptical mask centred between two tip points, long axis along the gap."""
    if weight <= 0:
        return np.zeros(shape, dtype=np.float32)
    cy, cx = (pa + pb) / 2.0
    dy, dx = pb - pa
    ang = np.arctan2(dy, dx)
    half_major = max(gap / 2.0 + 1.5, 1.5)   # px
    half_minor = max(gap / 3.0, 1.0)

    r = int(np.ceil(half_major + 2))
    y0, y1 = int(max(cy - r, 0)), int(min(cy + r + 1, shape[0]))
    x0, x1 = int(max(cx - r, 0)), int(min(cx + r + 1, shape[1]))
    if y0 >= y1 or x0 >= x1:
        return np.zeros(shape, dtype=np.float32)

    yy, xx = np.mgrid[y0:y1, x0:x1]
    X = (xx - cx) * np.cos(ang) + (yy - cy) * np.sin(ang)
    Y = -(xx - cx) * np.sin(ang) + (yy - cy) * np.cos(ang)
    val = 1.0 - ((X / half_major) ** 2 + (Y / half_minor) ** 2)
    out = np.zeros(shape, dtype=np.float32)
    patch = np.clip(val, 0.0, 1.0) * weight
    out[y0:y1, x0:x1] = patch.astype(np.float32)
    return out


# ---------------------------------------------------------------------------
# 5. intersection density
# ---------------------------------------------------------------------------

def intersection_density(trace_mask: np.ndarray, radius_px: int = 5) -> dict:
    """Trace density and junction (branch-point) density within radius_px.

    junction: trace pixel with >= 3 trace neighbours in its 8-neighbourhood
    (typical crossing/branching point of a rasterized network).
    """
    t = np.asarray(trace_mask, dtype=bool)
    k = np.ones((3, 3), dtype=np.uint8)
    neigh = ndimage.convolve(t.astype(np.uint8), k, mode="constant", cval=0) - t.astype(np.uint8)
    junctions = (t & (neigh >= 3)).astype(np.float64)

    box = np.ones((2 * radius_px + 1, 2 * radius_px + 1), dtype=np.float64)
    trace_density = ndimage.convolve(t.astype(np.float64), box, mode="constant", cval=0.0)
    junction_density = ndimage.convolve(junctions, box, mode="constant", cval=0.0)

    return {
        "trace_density": trace_density.astype(np.float32),
        "junction_density": junction_density.astype(np.float32),
    }


# ---------------------------------------------------------------------------
# 6. lineament vs known strike
# ---------------------------------------------------------------------------

def structure_tensor_orientation(raster: np.ndarray, sigma: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Local dominant orientation (deg in [0,180)) of any scalar field via the
    structure tensor, plus coherence in [0,1].

    Used on detrended elevation / magnetics / gravity to find local lineaments,
    then compared against the catalogue strike field.
    """
    a = np.asarray(raster, dtype=np.float64)
    a = np.nan_to_num(a, nan=0.0)
    gy, gx = np.gradient(a)
    jxx = ndimage.gaussian_filter(gx * gx, sigma)
    jyy = ndimage.gaussian_filter(gy * gy, sigma)
    jxy = ndimage.gaussian_filter(gx * gy, sigma)

    theta = 0.5 * np.arctan2(2.0 * jxy, jxx - jyy)  # gradient direction (from +col axis)
    # lineament strike is perpendicular to the gradient; use the same compass
    # convention as strike_field: azimuth = atan2(dx_col, -dy_row) mod 180.
    gx_dir, gy_dir = np.cos(theta), np.sin(theta)         # gradient direction
    lx, ly = -gy_dir, gx_dir                               # perpendicular (lineament)
    strike = ((np.degrees(np.arctan2(lx, -ly)) + 360.0) % 180.0).astype(np.float32)
    tr = jxx + jyy
    det = jxx * jyy - jxy * jxy
    disc = np.sqrt(np.maximum(tr * tr / 4.0 - det, 0.0))
    l1 = tr / 2.0 + disc
    l2 = tr / 2.0 - disc
    coherence = ((l1 - l2) / (l1 + l2 + 1e-12)).astype(np.float32)
    return strike.astype(np.float32), coherence


def strike_mismatch(lineament_strike: np.ndarray, catalogue_strike: np.ndarray) -> np.ndarray:
    """Smallest angle between a local lineament orientation and the catalogue
    strike at that pixel, in [0, 90] deg.  0 = parallel to known structures.
    """
    d = np.abs(lineament_strike - catalogue_strike) % 180.0
    return np.minimum(d, 180.0 - d).astype(np.float32)


# ---------------------------------------------------------------------------
# 7. slip / dilation tendency (external INGENIOUS rasters)
# ---------------------------------------------------------------------------

def load_external_raster(path, template_meta: dict) -> np.ndarray:
    """Read an external single-band raster (e.g. slip/dilation tendency from the
    INGENIOUS release, https://doi.org/10.15121/1881483) and, when its grid
    differs from the competition grid, nearest-neighbour resample onto it.

    The INGENIOUS GeoTIFFs are published in their own grids; resampling is an
    approximation whose effect is measured in the holdout, never assumed.
    """
    import rasterio
    from rasterio.warp import Resampling, reproject

    with rasterio.open(path) as src:
        src_arr = src.read(1).astype(np.float32)
        rows, cols = template_meta["rows"], template_meta["cols"]
        dst = np.zeros((rows, cols), dtype=np.float32)
        transform = template_meta.get("transform")
        if transform is None:
            raise ValueError(
                "template_meta has no transform; run scripts/prepare_data.py on the "
                "real template first (grid.json)"
            )
        reproject(
            source=src_arr,
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=rasterio.Affine(*transform) if not isinstance(transform, rasterio.Affine) else transform,
            dst_crs=f"EPSG:{template_meta.get('epsg', 32611)}",
            resampling=Resampling.bilinear,
        )
    return dst


# ---------------------------------------------------------------------------
# stack assembly
# ---------------------------------------------------------------------------

def build_catalogue_feature_stack(context_trace_mask: np.ndarray, window: int = 9) -> dict:
    """Build the full catalogue-geometry feature dict from a context trace mask."""
    out = {}
    out.update(distance_and_azimuth(context_trace_mask))
    out.update(along_across_strike(context_trace_mask, window=window))
    out.update(relay_corridors(context_trace_mask))
    out.update(intersection_density(context_trace_mask))
    strike, conf = strike_field(context_trace_mask, window=window)
    out["catalogue_strike"] = strike
    out["catalogue_strike_conf"] = conf
    # corridor pair count is scalar metadata; keep it out of the raster dict
    meta = {"relay_pairs": out.pop("n_pairs"), "relay_pair_list": out.pop("pair_list")}
    out["_meta"] = meta
    return out
