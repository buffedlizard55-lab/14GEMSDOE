"""Feature blocks for the round-2 geological hypotheses (N1-N5).

Each arm returns a dict of 2-D float32 rasters that can be concatenated onto the
catalogue-geometry feature matrix.  Arms are additive so an A/B on the blocked
holdout is a pure feature-set comparison with the same model, the same seeds and
the same hide-and-recover protocol.

Arms (see research/hypotheses_round2.md for the sourcing and the "why this
catches a MISSING fault" argument):

  N1  gravity-gradient edge terminations & junctions   (f_grav / gravity slope)
  N2  seismicity-density + strain-invariant lineaments (f_seis)
  N3  alteration-cap margin (conductance AND magnetic low)  (f_cond, f_maglo)
  N5  range-front / interbasinal-high topographic step  (f_elev)

Round-3 arms (see research/hypotheses_round3.md):

  R3A tip-continuation cones (catalogue geometry; needs ``context_mask``)
  R3B completeness-angle residual: catalogue density regressed on relief,
      strain and range-front geometry; strongly negative residuals mark
      under-mapped corridors (needs ``context_mask``)
  R3C magnetic-basement lineaments (f_mag): structure-tensor strike,
      coherence-weighted ridge skeleton, strike agreement with the catalogue
  R3D scarplet curvature-linkage (f_elev): negative-curvature scarplets
      morphologically linked across small gaps into candidate traces

None of the N-arms reads the catalogue, so every one of them is leak-free under
hide-and-recover by construction - they are equally available at training time
(when components are hidden) and at inference time.  R3A and R3B DO read the
catalogue and therefore take ``context_mask``: callers must pass the visible
context (never the full catalogue) so the hide-and-recover contract holds;
tests/test_hypotheses_round3.py pins this.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from gems import geoedges as ge
from gems.features import structure_tensor_orientation

ARMS = ("baseline", "N1", "N2", "N3", "N5", "ALL")
# arms consumed by scripts/validate_round2.py that reuse the ALL feature block
DERIVED_ARMS = ("GEO-ONLY", "BLEND", "BLEND-ADD", "BLEND-MUL")

# round-3 arms (research/hypotheses_round3.md).  R3A/R3B need the visible
# catalogue context; R3C/R3D are catalogue-independent.
R3_ARMS = ("R3A", "R3B", "R3C", "R3D", "R3AC")
# composites used by scripts/validate_round3.py: the round-2 ALL block plus
# round-3 blocks.  BMUL (the round-2 promoted incumbent) trains its classifier
# on "ALL" and then multiplies by the geophysical prior - exactly the round-2
# emission (validate_round2.py mapped its BLEND-* arms onto the ALL block).
COMPOSITE_ARMS = ("ALLR3A", "ALLR3AC")


# ---------------------------------------------------------------------------
# N1 - gravity horizontal-gradient edge terminations and intersections
# ---------------------------------------------------------------------------

def n1_gravity_edges(region: dict, *, sigma: float = 1.0) -> dict:
    """Terminating / intersecting edges of the horizontal gravity gradient.

    Faulds et al. 2026 (INGENIOUS compilation): "terminating and intersecting
    gravity gradients respectively defined many of the fault terminations and
    fault intersections ... especially important in defining FSS in the many
    basins of the region, where basin-fill sediments obscure the subsurface
    architecture".  The competition stack supplies the isostatic gravity anomaly
    and its slope; if only the slope is present it is used directly, otherwise
    the gradient is computed from the anomaly.
    """
    f = region.get("f_grav")
    if f is None:
        return {}
    out = ge.edge_termination_field(f, sigma=sigma)
    feats = {
        "n1_term_field": out["term_field"],
        "n1_junction_field": out["junction_field"],
        "n1_edge_mag": out["edge_mag"],
    }
    # distance to the nearest edge termination: lets the model learn "just past
    # the end of the geophysical edge" rather than only "on it"
    term = out["terminations"]
    if term.any():
        feats["n1_term_dist"] = ndimage.distance_transform_edt(~term).astype(np.float32)
    else:
        feats["n1_term_dist"] = np.full(f.shape, 1e6, dtype=np.float32)
    return feats


# ---------------------------------------------------------------------------
# N2 - seismicity-density and strain-invariant lineaments (blind faults)
# ---------------------------------------------------------------------------

def n2_seismic_lineaments(region: dict, *, sigma: float = 2.0) -> dict:
    """Lineaments of the seismicity-density field and of the strain invariant.

    Basin-fill-covered faults still produce microseismicity; the epicentre cloud
    therefore delineates a fault that has no surface scarp and hence no catalogue
    trace.  Faulds et al. 2026: basin-fill sediments obscure the subsurface
    architecture and primary basin-bounding and/or intrabasinal faults.
    """
    feats: dict = {}
    f = region.get("f_seis")
    if f is not None:
        strike, coh = structure_tensor_orientation(f, sigma=sigma)
        feats["n2_seis_strike"] = strike
        feats["n2_seis_coherence"] = coh
        feats["n2_seis_value"] = np.asarray(f, dtype=np.float32)
        # local maxima of the density = the active strand itself
        a = np.asarray(f, dtype=np.float64)
        mx = ndimage.maximum_filter(a, size=5)
        feats["n2_seis_ridge"] = ((a >= mx - 1e-9) & (a > 0)).astype(np.float32)
    s = region.get("strain")
    if s is not None:
        feats["n2_strain_value"] = np.asarray(s, dtype=np.float32)
    return feats


# ---------------------------------------------------------------------------
# N3 - hydrothermal alteration-cap margin
# ---------------------------------------------------------------------------

def n3_cap_margin(region: dict, *, support_px: float = 4.0,
                  cond_key: str = "f_cond", mag_key: str = "f_maglo",
                  base_key: str = "f_cbase") -> dict:
    """Level-set margin of the (high conductance AND magnetic low) clay cap.

    Faulds et al. 2026: "magnetic lows and low resistivity anomalies may
    respectively indicate altered rocks and clay caps at depth induced by
    geothermal activity".  The fault that feeds a cap is not necessarily mapped,
    and the cap is invisible to scarp-based catalogue compilation.
    """
    cond = region.get(cond_key)
    mag = region.get(mag_key)
    base = region.get(base_key)
    if cond is None and mag is None and base is None:
        return {}
    try:
        cap = ge.cap_mask_from_anomalies(conductance=cond, magnetic=mag,
                                         conductive_base=base)
    except ValueError:
        return {}
    if not cap.any():
        return {}
    return {
        "n3_cap_margin": ge.cap_margin(cap, support_px=support_px),
        "n3_cap_mask": cap.astype(np.float32),
    }


# ---------------------------------------------------------------------------
# N5 - range-front topographic step / interbasinal high
# ---------------------------------------------------------------------------

def n5_range_front(region: dict, *, sigma: float = 2.0) -> dict:
    """Topographic step along range fronts and interbasinal highs.

    Faulds et al. 2026: "Topographic steps along the fronts of mountain
    ranges/fault blocks may delineate step-overs or relay ramps. Interbasinal
    highs commonly correspond to accommodation zones between oppositely dipping
    Quaternary fault systems."
    """
    f = region.get("f_elev")
    if f is None:
        return {}
    a = np.asarray(f, dtype=np.float64)
    gy, gx = np.gradient(a)
    slope = np.hypot(gx, gy)
    strike, coh = structure_tensor_orientation(a, sigma=sigma)
    return {
        "n5_slope": slope.astype(np.float32),
        "n5_strike": strike,
        "n5_coherence": coh,
        "n5_step_dist": ndimage.distance_transform_edt(
            ~(slope > np.percentile(slope, 90.0))).astype(np.float32),
    }


# ---------------------------------------------------------------------------
# R3A - tip-continuation cones (catalogue geometry; needs the CONTEXT traces)
# ---------------------------------------------------------------------------

def r3a_tip_cones(context_mask: np.ndarray, *, cone_len_px: float = 20.0,
                  half_angle_deg: float = 25.0, min_align: float = 0.3) -> dict:
    """Decaying probability wedge continuing each catalogue trace past its tip.

    Why this can be scoreable while the trace itself is not: the sponsor ruled
    that "new fault" means any fault pixel not already captured by USGS /
    INGENIOUS and that this *can include newly mapped geometry of an existing
    fault system* - explicitly "a continuation past a mapped tip" (forum 11536,
    VERIFIED, knowledge base C21).  The cone is computed ONLY from the visible
    context, extends strictly beyond tip pixels, and never touches a trace
    pixel, so under hide-and-recover it is exactly the "where would this
    truncated trace continue?" signal.

    Differs from everything already in the repo: ``relay_corridors`` needs an
    OVERLAPPING partner pair (a subset of tips); ``along_across_strike`` is an
    unsigned per-pixel distance without direction; nothing else in the repo
    emits an oriented continuation prior from trace endpoints.
    """
    t = np.asarray(context_mask, dtype=bool)
    zero = np.zeros(t.shape, dtype=np.float32)
    if not t.any():
        return {"r3a_cone": zero, "r3a_cone_dist": np.full(t.shape, 1e6, dtype=np.float32)}

    strike, conf = strike_field_cached(t)
    ends = _endpoint_pixels(t)
    cone = np.zeros(t.shape, dtype=np.float32)
    if ends.size:
        # distance to the context, so cones never paint on or adjacent to a trace
        dist = ndimage.distance_transform_edt(~t)
        half = np.radians(half_angle_deg)
        cos_half = float(np.cos(half))
        L = float(cone_len_px)
        r = int(np.ceil(L))
        sy, sx = t.shape
        for ey, ex in ends:
            s = strike[ey, ex]
            if not np.isfinite(s) or conf[ey, ex] < 0.2:
                continue
            rad = np.radians(s)
            sv = np.array([np.sin(rad), -np.cos(rad)])   # (dx_east, dy_south->north)
            if not np.isfinite(sv).all():
                continue
            outward = _outward_direction(t, ey, ex)
            if outward is None:
                continue
            align = float(sv @ outward)
            if abs(align) < min_align:
                continue
            u = sv if align > 0 else -sv
            y0, y1 = max(ey - r, 0), min(ey + r + 1, sy)
            x0, x1 = max(ex - r, 0), min(ex + r + 1, sx)
            if y1 <= y0 or x1 <= x0:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1]
            vy = yy - ey
            vx = xx - ex
            d = np.hypot(vy, vx)
            with np.errstate(invalid="ignore", divide="ignore"):
                cosang = (vx * u[0] + vy * u[1]) / np.where(d > 0, d, 1.0)
            wedge = (d > 1.0) & (d <= L) & (cosang >= cos_half)
            if not wedge.any():
                continue
            val = np.clip(1.0 - d / L, 0.0, 1.0).astype(np.float32)
            sub = cone[y0:y1, x0:x1]
            np.maximum(sub, np.where(wedge, val, np.float32(0.0)), out=sub)
            cone[y0:y1, x0:x1] = sub
        cone[dist <= 1.0] = 0.0     # strictly off-trace: no "distance = 0" answer
        cone = ndimage.gaussian_filter(cone, sigma=1.0)
        cone[dist <= 1.0] = 0.0
    cone_dist = (ndimage.distance_transform_edt(cone <= 1e-6)
                 if (cone > 1e-6).any() else np.full(t.shape, 1e6, dtype=np.float32))
    return {"r3a_cone": cone.astype(np.float32), "r3a_cone_dist": cone_dist.astype(np.float32)}


def structure_tensor_is_strike_field(trace_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Wrapper kept for readability: local strike + confidence of the traces."""
    return strike_field_cached(trace_mask)


def strike_field_cached(trace_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    from gems.features import strike_field
    return strike_field(trace_mask, window=9)


def _endpoint_pixels(trace_mask: np.ndarray) -> np.ndarray:
    """(n, 2) array of terminal-pixel coordinates (row, col)."""
    from gems.features import endpoint_mask
    ys, xs = np.nonzero(endpoint_mask(trace_mask))
    return np.stack([ys, xs], axis=1)


def _outward_direction(trace_mask: np.ndarray, ey: int, ex: int):
    """Unit vector pointing from the trace body out through the tip."""
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dy == 0 and dx == 0:
                continue
            yy, xx = ey + dy, ex + dx
            if 0 <= yy < trace_mask.shape[0] and 0 <= xx < trace_mask.shape[1] \
                    and trace_mask[yy, xx]:
                n = float(np.hypot(dy, dx))
                # outward in the (east, south) frame: the neighbour sits at
                # (south=dy, east=dx) inside the trace, so outward = (-dx, -dy)
                return np.array([-dx / n, -dy / n])
    return None


# ---------------------------------------------------------------------------
# R3B - completeness-angle residual (catalogue density vs strain/relief)
# ---------------------------------------------------------------------------

def r3b_completeness(region: dict, context_mask: np.ndarray, *,
                     cell_px: int = 24, smooth_sigma: float = 6.0) -> dict:
    """Where should the catalogue be full but is empty?  The completeness angle.

    Observed catalogue density per coarse cell is regressed (ridge OLS in log
    space) on what geology says should support faults: relief (std of the
    detrended-elevation analogue), strain rate (second-invariant analogue) and
    range-front proximity.  The RESIDUAL raster is the feature: strongly
    negative residuals = strain + relief present but catalogue empty = the
    corridor a mapper never reached (Hermant et al. 2025, knowledge base M5:
    Qfault density is partly a map of who mapped what).

    Reads the CONTEXT catalogue only, so hiding components really does change
    what the feature can see (hide-and-recover safe).
    """
    traces = np.asarray(region["traces"], dtype=bool)
    shape = traces.shape
    zero = np.zeros(shape, dtype=np.float32)
    out = {"r3b_residual": zero, "r3b_undmap": np.full(shape, 0.5, dtype=np.float32)}
    t = np.asarray(context_mask, dtype=bool)

    elev = region.get("f_elev")
    strain = region.get("strain")
    if elev is None or strain is None or not t.any():
        return out

    rows, cols = shape
    nr, nc = int(np.ceil(rows / cell_px)), int(np.ceil(cols / cell_px))
    cid = (np.arange(rows)[:, None] // cell_px) * nc + (np.arange(cols)[None, :] // cell_px)
    n_cells = nr * nc
    flat_cid = cid.ravel().astype(np.int64)

    def cell_sum(a: np.ndarray) -> np.ndarray:
        return np.bincount(flat_cid, weights=np.asarray(a, dtype=np.float64).ravel(),
                           minlength=n_cells)

    obs = cell_sum(t) / float(cell_px * cell_px)
    e = np.asarray(elev, dtype=np.float64)
    e0 = np.nan_to_num(e, nan=0.0)
    n_px = cell_sum(np.ones(shape))
    mean_e = cell_sum(e0) / np.maximum(n_px, 1)
    mean_e2 = cell_sum(e0 * e0) / np.maximum(n_px, 1)
    relief = np.sqrt(np.maximum(mean_e2 - mean_e ** 2, 0.0))
    strain_m = cell_sum(np.nan_to_num(np.asarray(strain, dtype=np.float64), nan=0.0)) \
        / np.maximum(n_px, 1)
    gy, gx = np.gradient(e0)
    slope = np.hypot(gx, gy)
    front = (slope > np.percentile(slope, 90.0)).astype(np.float64)
    front_frac = cell_sum(front) / np.maximum(n_px, 1)

    def z(v: np.ndarray) -> np.ndarray:
        sd = v.std()
        return (v - v.mean()) / (sd + 1e-9)

    X = np.stack([np.ones(n_cells), z(relief), z(strain_m), z(front_frac)], axis=1)
    y = np.log1p(obs * 1000.0)
    lam = 1.0
    A = X.T @ X + lam * np.eye(X.shape[1])
    A[0, 0] -= lam                     # do not penalise the intercept
    beta = np.linalg.solve(A, X.T @ y)
    resid = y - X @ beta
    rz = (resid - resid.mean()) / (resid.std() + 1e-9)

    res_raster = rz[cid].astype(np.float32)
    res_raster = ndimage.gaussian_filter(res_raster, sigma=smooth_sigma)
    undmap = (1.0 / (1.0 + np.exp(np.clip(2.0 * res_raster, -30, 30)))).astype(np.float32)
    return {"r3b_residual": res_raster.astype(np.float32), "r3b_undmap": undmap}


# ---------------------------------------------------------------------------
# R3C - magnetic-basement lineaments (catalogue-independent)
# ---------------------------------------------------------------------------

def r3c_magnetic_lineaments(region: dict, context_mask: np.ndarray | None = None, *,
                            sigma: float = 2.0) -> dict:
    """Lineaments of the magnetic field and their agreement with the catalogue.

    Basin- and lake-fill hide faults from geomorphic mapping, but a
    basement-rooted fault that offsets magnetised crystalline basement still
    produces a magnetic lineament (the GeoDAWN RTP/TMI layers exist precisely
    because of this; knowledge base C17/C19).  Unlike N1 (gravity horizontal-
    gradient terminations) this arm reads the MAGNETIC field, and unlike N1 it
    does not feed raw edge terminations to the classifier: its features are the
    orientation-coherent ridge skeleton's distance, the lineament strike, the
    coherence, and the strike AGREEMENT with the visible catalogue - the model
    learns "magnetic fabric parallel to nearby known strikes", which is the
    step-over/intersection geometry of the Faulds inventory (S1/S8-S10).
    """
    f = region.get("f_mag")
    if f is None:
        return {}
    strike_l, coh = structure_tensor_orientation(f, sigma=sigma)
    skel = ge.ridge_skeleton(np.asarray(f, dtype=np.float64), sigma=sigma)
    ridge_dist = (ndimage.distance_transform_edt(~skel).astype(np.float32)
                  if skel.any() else np.full(np.shape(f), 1e6, dtype=np.float32))
    feats = {
        "r3c_ridge_dist": ridge_dist,
        "r3c_strike": strike_l.astype(np.float32),
        "r3c_coherence": coh.astype(np.float32),
    }
    if context_mask is not None and np.asarray(context_mask).any():
        from gems.features import strike_mismatch
        t = np.asarray(context_mask, dtype=bool)
        strike_c, _conf = strike_field_cached(t)
        dist, (iy, ix) = ndimage.distance_transform_edt(~t, return_indices=True)
        strike_c_off = strike_c[iy, ix]          # nearest-trace strike off trace
        mismatch = strike_mismatch(strike_l, strike_c_off)
        feats["r3c_strike_mismatch"] = mismatch
        # parallel agreement in [0,1]: 1 when magnetic fabric is parallel to the
        # nearby catalogue strike AND the fabric is coherent
        feats["r3c_parallel_agreement"] = (np.cos(np.radians(mismatch)) *
                                           coh).astype(np.float32)
    return feats


# ---------------------------------------------------------------------------
# R3D - scarplet curvature-linkage (catalogue-independent)
# ---------------------------------------------------------------------------

def r3d_scarplet_linkage(region: dict, *, sigma_smooth: float = 1.5,
                         curv_percentile: float = 8.0,
                         close_size: int = 9, min_scarp_px: int = 4) -> dict:
    """Low-amplitude scarplets found by curvature, then LINKED across gaps.

    The most recent slips inside basins leave decimetre scarplets whose slope
    amplitude sits below the range-front threshold N5 uses; in curvature
    (second derivative) they are sharp negative lineaments.  Morphological
    closing along their trend bridges the 2-5 px gaps where the scarp is
    buried, producing candidate LINKED traces - the connectivity transform
    turns scattered noise into continuity, which is what a catalogue mapper
    needed to accept a trace.  Differs from N5 (range-front slope magnitude at
    the 90th percentile, no curvature, no linkage) and from N4-adjacent ideas
    in that the scored signal is the BRIDGE, not the scarp amplitude.
    """
    f = region.get("f_elev")
    if f is None:
        return {}
    a = ndimage.gaussian_filter(np.nan_to_num(np.asarray(f, dtype=np.float64), nan=0.0),
                                sigma_smooth)
    curv = ndimage.laplace(a)
    thresh = np.percentile(curv, curv_percentile)
    scarps = curv < thresh
    # drop tiny isolated speckle so "linkage" is not pure noise
    lab, n = ndimage.label(scarps, structure=np.ones((3, 3), dtype=int))
    if n:
        counts = np.bincount(lab.ravel())
        small = counts < min_scarp_px
        scarps = scarps & ~small[lab]
    closed = ndimage.binary_closing(scarps, structure=np.ones((close_size, close_size),
                                                              dtype=bool))
    bridges = closed & ~scarps
    feats = {
        "r3d_curv": np.clip(curv / (curv.std() + 1e-9), -5, 5).astype(np.float32),
        "r3d_scarp_dist": (ndimage.distance_transform_edt(~scarps).astype(np.float32)
                           if scarps.any() else np.full(np.shape(f), 1e6, dtype=np.float32)),
        "r3d_bridge": bridges.astype(np.float32),
        "r3d_bridge_dist": (ndimage.distance_transform_edt(~bridges).astype(np.float32)
                            if bridges.any() else np.full(np.shape(f), 1e6, dtype=np.float32)),
    }
    return feats


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------

def build_arm_features(region: dict, arm: str, *, sigma_geo: float = 1.0,
                       context_mask: np.ndarray | None = None) -> dict:
    """Return the extra (non-baseline) feature block for one hypothesis arm.

    ``context_mask`` is the VISIBLE catalogue context (post-hide).  Round-3
    arms R3A/R3B read it (they are catalogue-geometry features and must obey
    the hide-and-recover contract); R3C uses it optionally for the strike-
    agreement feature; everything else ignores it.
    """
    arm = arm.upper()
    if arm in DERIVED_ARMS:
        arm = "ALL"
    if arm == "BASELINE":
        return {}
    if arm == "ALL":
        out = {}
        out.update(n1_gravity_edges(region, sigma=sigma_geo))
        out.update(n2_seismic_lineaments(region))
        out.update(n3_cap_margin(region))
        out.update(n5_range_front(region))
        return out
    if arm == "N1":
        return n1_gravity_edges(region, sigma=sigma_geo)
    if arm == "N2":
        return n2_seismic_lineaments(region)
    if arm == "N3":
        return n3_cap_margin(region)
    if arm == "N5":
        return n5_range_front(region)
    if arm == "R3A":
        if context_mask is None:
            context_mask = region.get("traces")
        return r3a_tip_cones(context_mask)
    if arm == "R3B":
        if context_mask is None:
            context_mask = region.get("traces")
        return r3b_completeness(region, context_mask)
    if arm == "R3C":
        return r3c_magnetic_lineaments(region, context_mask=context_mask)
    if arm == "R3D":
        return r3d_scarplet_linkage(region)
    if arm == "R3AC":
        if context_mask is None:
            context_mask = region.get("traces")
        out = r3a_tip_cones(context_mask)
        out.update(r3c_magnetic_lineaments(region, context_mask=context_mask))
        return out
    if arm == "ALLR3A":
        out = build_arm_features(region, "ALL", sigma_geo=sigma_geo)
        if context_mask is None:
            context_mask = region.get("traces")
        out.update(r3a_tip_cones(context_mask))
        return out
    if arm == "ALLR3AC":
        out = build_arm_features(region, "ALL", sigma_geo=sigma_geo)
        if context_mask is None:
            context_mask = region.get("traces")
        out.update(r3a_tip_cones(context_mask))
        out.update(r3c_magnetic_lineaments(region, context_mask=context_mask))
        return out
    raise ValueError(f"unknown arm {arm!r}; expected one of "
                     f"{ARMS + R3_ARMS + COMPOSITE_ARMS}")


def arm_feature_names(region: dict, arm: str, **kw) -> list:
    return sorted(build_arm_features(region, arm, **kw).keys())
