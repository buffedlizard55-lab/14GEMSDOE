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

None of these arms reads the catalogue, so every one of them is leak-free under
hide-and-recover by construction - they are equally available at training time
(when components are hidden) and at inference time.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from gems import geoedges as ge
from gems.features import structure_tensor_orientation

ARMS = ("baseline", "N1", "N2", "N3", "N5", "ALL")
# arms consumed by scripts/validate_round2.py that reuse the ALL feature block
DERIVED_ARMS = ("GEO-ONLY", "BLEND", "BLEND-ADD", "BLEND-MUL")


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
# assembly
# ---------------------------------------------------------------------------

def build_arm_features(region: dict, arm: str, *, sigma_geo: float = 1.0) -> dict:
    """Return the extra (non-catalogue) feature block for one hypothesis arm."""
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
    raise ValueError(f"unknown arm {arm!r}; expected one of {ARMS}")


def arm_feature_names(region: dict, arm: str, **kw) -> list:
    return sorted(build_arm_features(region, arm, **kw).keys())
