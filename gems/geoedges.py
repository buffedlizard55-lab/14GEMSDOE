"""Geophysical edge / lineament detectors for faults the catalogue omits.

Motivation (VERIFIED sources, see research/knowledge_base.md S9-S12):

* Faulds et al. (2026, Stanford Geothermal Workshop) state, of their own
  INGENIOUS compilation of >1,430 favourable structural settings: *"Isostatic
  residual and horizontal gradient gravity data were the most useful. For
  example, terminating and intersecting gravity gradients respectively defined
  many of the fault terminations and fault intersections. This was especially
  important in defining FSS in the many basins of the region, where basin-fill
  sediments obscure the subsurface architecture and primary basin-bounding
  and/or intrabasinal faults."*
  (https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2026/Faulds.pdf)

* The same paper: *"magnetic lows and low resistivity anomalies may
  respectively indicate altered rocks and clay caps at depth induced by
  geothermal activity."*

* The same paper: much of the Great Basin was inundated by late Pleistocene
  lakes, so faults that have not ruptured in the Holocene are obscured by lake
  sediments and shoreline features; some favourable settings are minor faults
  with minimal surface rupture, hard to see even in lidar.

These three statements define a class of faults that are (a) real, (b) expressed
in geophysics, and (c) *absent* from a catalogue compiled from surface scarps
and lineaments: the tip-line of a fault that continues under basin fill, the
intersection of two strands under a playa, and the strand feeding a clay cap.

What this module computes (all from a scalar raster, no catalogue input, so it
is leak-free under hide-and-recover by construction):

  1. ``gradient_magnitude``      - first horizontal derivative magnitude; the
                                   competition stack supplies the "slope of the
                                   isostatic gravity anomaly" band, which IS
                                   this quantity for gravity.
  2. ``ridge_skeleton``          - 1-px ridges of the gradient magnitude
                                   (non-maximum suppression across the ridge +
                                   hysteresis + morphological skeletonisation).
  3. ``edge_terminations``       - skeleton pixels with exactly one skeleton
                                   neighbour: where a geophysical edge STOPS.
  4. ``edge_junctions``          - skeleton pixels with >= 3 skeleton neighbours.
  5. ``edge_termination_field``  - a [0,1] candidate field peaked at terminating
                                   edges, weighted by the gradient magnitude
                                   that dies out there.
  6. ``cap_margin``              - level-set boundary of a boolean "cap" mask
                                   (used for the magnetic-low + high-conductance
                                   hydrothermal alteration-cap hypothesis).

Every function is pure array maths on numpy/scipy/scikit-image; nothing here
needs the competition data to exist.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize

_EIGHT = np.ones((3, 3), dtype=bool)


# ---------------------------------------------------------------------------
# 1. first horizontal derivative
# ---------------------------------------------------------------------------

def gradient_magnitude(field: np.ndarray, sigma: float = 1.0):
    """Return (magnitude, gx, gy) of the horizontal gradient of ``field``.

    ``gx`` is the derivative along columns (east), ``gy`` along rows (south).
    ``sigma`` pre-smooths the field so single-pixel noise does not dominate the
    derivative.  NaN is treated as 0 and reported through ``valid`` so callers
    can respect the footprint.
    """
    a = np.asarray(field, dtype=np.float64)
    nan = np.isnan(a)
    if nan.any():
        a = np.where(nan, 0.0, a)
    if sigma and sigma > 0:
        a = ndimage.gaussian_filter(a, sigma)
    gy, gx = np.gradient(a)
    mag = np.hypot(gx, gy)
    return mag, gx, gy


# ---------------------------------------------------------------------------
# 2. ridge extraction from the gradient magnitude
# ---------------------------------------------------------------------------

def _non_max_suppression(mag: np.ndarray, gx: np.ndarray, gy: np.ndarray) -> np.ndarray:
    """Keep only local maxima of ``mag`` measured ACROSS the ridge.

    The gradient of ``mag`` points along the gradient direction (perpendicular
    to the ridge), so a ridge pixel must be >= both of its neighbours along
    +/- (gx, gy).  Pixels with zero gradient magnitude carry no orientation and
    are never ridge candidates.
    """
    m = np.asarray(mag, dtype=np.float64)
    # quantise the gradient direction into 4 sectors; compare along the axis
    # perpendicular to the ridge (i.e. the gradient direction itself).
    ax = np.abs(gx)
    ay = np.abs(gy)
    east_west = ax >= ay  # gradient mostly +/- x -> ridge runs N-S
    out = np.zeros_like(m, dtype=bool)
    live = m > 0.0

    def shifted(dr, dc):
        return ndimage.shift(m, shift=(dr, dc), order=1, mode="nearest")

    # gradient along +x/-x -> compare with (0,+1) and (0,-1)
    sel = east_west & live
    if sel.any():
        out |= sel & (m >= shifted(0, 1)) & (m >= shifted(0, -1))
    # gradient along +y/-y -> compare with (+1,0) and (-1,0)
    sel = (~east_west) & live
    if sel.any():
        out |= sel & (m >= shifted(1, 0)) & (m >= shifted(-1, 0))
    return out


def ridge_skeleton(field: np.ndarray, *, sigma: float = 1.0,
                   low_quantile: float = 60.0, high_quantile: float = 90.0,
                   min_length_px: int = 4) -> np.ndarray:
    """1-pixel-wide ridges of the gradient magnitude of ``field``.

    Steps: gradient -> non-maximum suppression across the ridge -> hysteresis
    threshold (percentiles of the surviving magnitudes) -> connected-component
    filtering by length -> morphological skeletonisation to 1 px.
    """
    shape = np.asarray(field).shape
    mag, gx, gy = gradient_magnitude(field, sigma=sigma)
    nms = _non_max_suppression(mag, gx, gy)
    cand = mag[nms]
    if cand.size == 0 or float(cand.max()) <= 0.0:
        return np.zeros(shape, dtype=bool)
    lo = np.percentile(cand, low_quantile)
    hi = np.percentile(cand, high_quantile)
    if hi <= lo:                      # degenerate (near-constant) gradient
        hi = float(cand.max())
        lo = 0.5 * hi
    strong = nms & (mag >= hi)
    weak = nms & (mag >= lo)
    if not strong.any():
        strong = nms & (mag >= float(cand.max()))
    lab, n = ndimage.label(weak, structure=_EIGHT)
    keep = np.zeros_like(weak)
    for cid in range(1, n + 1):
        comp = lab == cid
        if comp.sum() < min_length_px:
            continue
        if (comp & strong).any():
            keep |= comp
    if not keep.any():
        return np.zeros(shape, dtype=bool)
    return skeletonize(keep).astype(bool)


# ---------------------------------------------------------------------------
# 3-4. terminations and junctions of a skeleton
# ---------------------------------------------------------------------------

def skeleton_neighbour_count(skel: np.ndarray) -> np.ndarray:
    """Number of 8-connected skeleton neighbours per skeleton pixel."""
    s = np.asarray(skel, dtype=bool)
    neigh = ndimage.convolve(s.astype(np.uint8), np.ones((3, 3), dtype=np.uint8),
                             mode="constant", cval=0) - s.astype(np.uint8)
    return neigh


def edge_terminations(skel: np.ndarray) -> np.ndarray:
    """Skeleton pixels with exactly one skeleton neighbour (a ridge that ends)."""
    s = np.asarray(skel, dtype=bool)
    return s & (skeleton_neighbour_count(s) == 1)


def edge_junctions(skel: np.ndarray) -> np.ndarray:
    """Skeleton pixels with >= 3 skeleton neighbours (ridges that meet)."""
    s = np.asarray(skel, dtype=bool)
    return s & (skeleton_neighbour_count(s) >= 3)


# ---------------------------------------------------------------------------
# 5. the candidate field
# ---------------------------------------------------------------------------

def edge_termination_field(field: np.ndarray, *, sigma: float = 1.0,
                           support_px: float = 6.0) -> dict:
    """Candidate field for faults that the geophysics shows but the catalogue omits.

    Returns
    -------
    dict with
      skeleton      : the extracted ridge network
      terminations  : mask of ridge endpoints
      junctions     : mask of ridge branch points
      term_field    : float32 in [0,1]; decays linearly from each termination
                      over ``support_px`` and is scaled by the gradient
                      magnitude at that termination
      junction_field: float32 in [0,1]; linear decay from each junction
      edge_mag      : the gradient magnitude (handy as a plain feature)
    """
    mag, _gx, _gy = gradient_magnitude(field, sigma=sigma)
    skel = ridge_skeleton(field, sigma=sigma)
    if not skel.any():
        z = np.zeros(np.asarray(field).shape, dtype=np.float32)
        return {"skeleton": skel, "terminations": z.astype(bool),
                "junctions": z.astype(bool), "term_field": z,
                "junction_field": z, "edge_mag": mag.astype(np.float32)}

    term = edge_terminations(skel)
    junc = edge_junctions(skel)

    # weight each termination by the gradient magnitude that dies out there
    w_term = np.where(term, mag, 0.0)
    w_junc = np.where(junc, mag, 0.0)
    mx = float(mag[skel].max()) if skel.any() else 1.0
    if mx <= 0:
        mx = 1.0

    def decay(weights: np.ndarray) -> np.ndarray:
        if not weights.any():
            return np.zeros(weights.shape, dtype=np.float32)
        # distance to the nearest weighted pixel, then linear decay
        d = ndimage.distance_transform_edt(~(weights > 0))
        val = np.clip(1.0 - d / support_px, 0.0, 1.0)
        # scale by the weight of the nearest source pixel (nearest-neighbour
        # resample of the weight field through the distance-transform labels)
        _idx, ind = ndimage.distance_transform_edt(~(weights > 0),
                                                   return_indices=True)
        w_at = weights[tuple(ind)]
        return (val * (w_at / mx)).astype(np.float32)

    return {
        "skeleton": skel,
        "terminations": term,
        "junctions": junc,
        "term_field": decay(w_term),
        "junction_field": decay(w_junc),
        "edge_mag": mag.astype(np.float32),
    }


# ---------------------------------------------------------------------------
# 6. cap / anomaly margin (hydrothermal alteration cap -> fault placement)
# ---------------------------------------------------------------------------

def cap_margin(cap_mask: np.ndarray, *, support_px: float = 4.0,
               inside_weight: float = 1.0, outside_weight: float = 0.6) -> np.ndarray:
    """Level-set boundary strength of a boolean anomaly mask.

    The fault that feeds a hydrothermal clay cap lies at the cap's margin, so we
    return a field peaked on the mask boundary that decays both inward and
    outward (asymmetric: alteration is more likely to sit above its own fault
    than the fault is to sit outside the cap).
    """
    m = np.asarray(cap_mask, dtype=bool)
    if not m.any():
        return np.zeros(m.shape, dtype=np.float32)
    d_in = ndimage.distance_transform_edt(m)            # >0 inside
    d_out = ndimage.distance_transform_edt(~m)          # >0 outside
    f_in = np.clip(1.0 - d_in / support_px, 0.0, 1.0) * inside_weight
    f_out = np.clip(1.0 - d_out / support_px, 0.0, 1.0) * outside_weight
    return np.maximum(f_in, f_out).astype(np.float32)


def cap_mask_from_anomalies(*, conductance=None, cond_thresh=None,
                            magnetic=None, mag_thresh=None,
                            conductive_base=None, base_thresh=None) -> np.ndarray:
    """Boolean hydrothermal-alteration-cap mask.

    Follows Faulds et al. 2026 verbatim: low resistivity (high conductance /
    shallow conductive base) AND a magnetic low indicate altered rock and clay
    caps at depth.  Any subset of the three inputs may be supplied; the mask is
    the conjunction of whatever was given.  Thresholds are quantiles of the
    supplied raster unless explicit values are passed.
    """
    parts = []
    for arr, thresh, high_is_cap in ((conductance, cond_thresh, True),
                                     (conductive_base, base_thresh, False),
                                     (magnetic, mag_thresh, False)):
        if arr is None:
            continue
        a = np.asarray(arr, dtype=np.float64)
        a = np.where(np.isfinite(a), a, np.nan)
        if thresh is None:
            thresh = float(np.nanpercentile(a, 75.0))
        parts.append((a >= thresh) if high_is_cap else (a <= thresh))
    if not parts:
        raise ValueError("supply at least one anomaly raster")
    out = parts[0]
    for p in parts[1:]:
        out = out & p
    return out


# ---------------------------------------------------------------------------
# convenience: lineament strike of a geophysical field
# ---------------------------------------------------------------------------

def lineament_strike(field: np.ndarray, sigma: float = 2.0):
    """Local lineament orientation (deg, [0,180)) and coherence of a scalar field.

    Thin wrapper around the structure tensor, kept here so the geophysical
    hypotheses import one module.
    """
    from gems.features import structure_tensor_orientation
    return structure_tensor_orientation(field, sigma=sigma)
