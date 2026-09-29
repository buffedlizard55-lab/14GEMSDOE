"""Tests for the real-data channel library (gems/realchannels.py).

Focused on the round-5 additions and on the two *performance regressions* found
on 2026-09-28 with py-spy — the full-grid allocations inside the tip-pair loops,
which stalled the real-data gate for >10 minutes.  Both are geometry bugs with
measurable footprints, so they are asserted here rather than left to review.
"""

from __future__ import annotations

import numpy as np
import pytest

from gems import realchannels as rc


def _two_strands(shape=(200, 300), gap=60, offset=0, length=60):
    """Two vertical strands separated by ``gap`` px, optionally offset in rows."""
    t = np.zeros(shape, dtype=bool)
    r0, r1 = 60 + offset, 60 + offset + length
    t[r0:r1, 80:82] = True
    t[60:60 + length, 80 + gap:82 + gap] = True
    return t


def _two_opposed(shape=(300, 300), sep=120, length=80):
    """Two *long* sub-parallel strands with opposed topographic polarity.

    Left strand sits on a west-facing slope, right strand on an east-facing one,
    so the sampled elevation differences across their strike normals have
    opposite signs.
    """
    rows, cols = shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    elev = np.zeros(shape, dtype=np.float32)
    elev[:, :cols // 2] = (xx[:, :cols // 2] * 0.5)          # rises eastward
    elev[:, cols // 2:] = 400.0 - (xx[:, cols // 2:] * 0.5)  # falls eastward
    t = np.zeros(shape, dtype=bool)
    t[100:100 + length, 60:63] = True
    t[120:120 + length, 60 + sep:63 + sep] = True
    return t, elev


def test_knob_helpers_shapes_and_ranges():
    f = np.zeros((50, 50), dtype=np.float32)
    f[10:20, 10] = 1.0
    assert rc.robust_unit(f, symmetric=False).max() <= 1.0
    assert np.isfinite(rc.nan_fill(np.array([np.nan, 1.0]))).all()


def test_elliptical_bridge_patch_matches_wrapper():
    """The patch form must reproduce the full-grid form exactly (regression:
    the full-grid allocation per tip pair stalled the gate)."""
    shape = (200, 300)
    pa, pb = np.array([100.0, 80.0]), np.array([100.0, 140.0])
    full = rc.elliptical_bridge(shape, pa, pb, 60.0, 0.5)
    y0, x0, patch = rc.elliptical_bridge_patch(shape, pa, pb, 60.0, 0.5)
    rebuilt = np.zeros(shape, dtype=np.float32)
    rebuilt[y0:y0 + patch.shape[0], x0:x0 + patch.shape[1]] = patch
    assert np.array_equal(full, rebuilt)
    assert full.max() <= 0.5
    assert rc.elliptical_bridge_patch(shape, pa, pb, 60.0, 0.0) is None


def test_relay_corridors_bridges_two_strands():
    """Overlapping sub-parallel strands (the relay-ramp geometry) are bridged;
    underlapping ones are not — that is the documented difference from R3A."""
    overlapping = _two_strands(gap=60, offset=20)      # hard-linked (overlapping)
    out = rc.relay_corridors(overlapping)
    assert out["n_pairs"] >= 1
    assert out["corridor"].max() > 0
    # the strongest part of the bridge sits in the gap between the strands
    peak = np.unravel_index(np.argmax(out["corridor"]), out["corridor"].shape)
    assert 82 <= peak[1] <= 138, peak
    # exactly parallel, exactly aligned strands are the limiting case
    aligned = _two_strands(gap=60, offset=0)
    assert rc.relay_corridors(aligned)["n_pairs"] >= 1
    # far-apart strands are not bridged
    far = _two_strands(gap=200, offset=0)
    assert rc.relay_corridors(far)["n_pairs"] == 0


def test_ramp_maturity_prefers_overlapping_strands():
    overlapping = _two_strands(gap=20, offset=0)
    far_apart = _two_strands(gap=200, offset=0)
    a = rc.ramp_maturity_field(overlapping, max_gap_px=40)
    b = rc.ramp_maturity_field(far_apart, max_gap_px=40)
    assert a.max() > 0
    assert b.max() == 0 or a.max() > b.max()


def test_fault_polarity_is_opposed_across_two_facing_slopes():
    t, elev = _two_opposed()
    pol = rc.fault_polarity_field(t, elev)
    left = pol[100:180, 60:63]
    right = pol[120:200, 180:183]
    assert np.isfinite(left).any() and np.isfinite(right).any()
    assert np.sign(np.nanmean(left)) != np.sign(np.nanmean(right))


def test_accommodation_corridors_is_selective_and_between_the_strands():
    """Regression: the first version filled 98 % of a test window with a wide
    quad per pair.  The banded form must mark the corridor, not the map."""
    t, elev = _two_opposed()
    field = rc.accommodation_corridors(t, elev)
    assert field.max() > 0
    assert (field > 0).mean() < 0.25, "corridors must not cover the whole window"
    # the painted mass lies in the corridor between the strands (the patch adds a
    # half-width of padding), and nothing is painted on the strands themselves
    ys, xs = np.nonzero(field)
    assert (xs > 60).mean() > 0.9 and (xs < 185).mean() > 0.9
    assert field[t].max() == pytest.approx(0.0)


def test_accommodation_corridors_requires_opposed_polarity():
    t, elev = _two_opposed()
    flat = np.zeros_like(elev)          # no topographic polarity anywhere
    assert rc.accommodation_corridors(t, flat).max() == 0.0


def test_tilt_angle_is_amplitude_independent():
    """Doubling the field amplitude must not change the tilt angle where both
    components are scaled together (the point of a ratio edge detector)."""
    rng = np.random.default_rng(0)
    vg = rng.normal(size=(40, 40)).astype(np.float32)
    hg = rng.normal(size=(40, 40)).astype(np.float32)
    a = rc.tilt_angle(vg, hg)
    b = rc.tilt_angle(10.0 * vg, 10.0 * hg)
    assert np.allclose(a, b, equal_nan=True)


def test_profile_curvature_is_scale_aware():
    rows, cols = 80, 80
    yy, xx = np.mgrid[0:rows, 0:cols]
    ramp = xx.astype(np.float32)
    prof, plan = rc.profile_curvature(ramp, sigma=0.0)
    # a planar ramp has zero curvature everywhere
    assert np.abs(prof).max() < 1e-4
    bowl = (xx - 40.0) ** 2 + (yy - 40.0) ** 2
    prof2, _ = rc.profile_curvature(bowl.astype(np.float32), sigma=0.0)
    assert np.abs(prof2).max() > 0


def test_strike_mismatch_is_angle_wrapped():
    a = np.array([[0.0, 170.0, 90.0]], dtype=np.float32)
    b = np.array([[10.0, 0.0, 90.0]], dtype=np.float32)
    out = rc.strike_mismatch(a, b)
    assert np.allclose(out, [[10.0, 10.0, 0.0]])
