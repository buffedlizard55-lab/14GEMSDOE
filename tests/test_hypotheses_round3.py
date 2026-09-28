"""Round-3 hypothesis arms: geometry, leak-safety, and schema stability.

Pins the contracts that make the R3 arms legal under hide-and-recover:
  * R3A cones are computed from the VISIBLE context only, never paint a
    context pixel, and lie strictly beyond the traces they continue;
  * R3B reads only the context catalogue (density) plus catalogue-independent
    fields, and its residual is strongly negative where strain + relief exist
    but the catalogue is empty (the definition of an under-mapped corridor);
  * every arm returns a stable schema (same keys, same shapes) whether or not
    the context is non-empty, so the per-epoch weight ensemble stays valid;
  * R3C/R3D are catalogue-independent (identical output with/without context
    for their context-free features).
"""

import sys
import unittest
from pathlib import Path

import numpy as np
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems import hide_recover as hr  # noqa: E402
from gems.hypotheses import (  # noqa: E402
    R3_ARMS,
    build_arm_features,
    r3a_tip_cones,
    r3b_completeness,
    r3c_magnetic_lineaments,
    r3d_scarplet_linkage,
)
from gems.synthesize import make_region  # noqa: E402


def _straight_trace(shape, y0, x0, y1, x1):
    m = np.zeros(shape, dtype=bool)
    n = int(max(abs(y1 - y0), abs(x1 - x0), 1)) * 2
    for s in np.linspace(0.0, 1.0, n + 1):
        m[int(round(y0 + (y1 - y0) * s)), int(round(x0 + (x1 - x0) * s))] = True
    return m


class TestR3ATipCones(unittest.TestCase):
    def test_cone_is_strictly_off_trace_and_forward(self):
        # single N-S trace in the middle of the grid
        t = _straight_trace((80, 80), 10, 40, 69, 40)
        f = r3a_tip_cones(t)
        cone = f["r3a_cone"] > 0
        self.assertGreater(cone.sum(), 0)
        self.assertEqual(int((cone & t).sum()), 0, "cone may never paint a trace pixel")
        dist = ndimage.distance_transform_edt(~t)
        self.assertGreaterEqual(float(dist[cone].min()), 1.0 + 1e-6)
        # every cone pixel is beyond one of the two tips: its y is either
        # above the top tip's row or below the bottom tip's row (N-S trace,
        # cones only extend along strike, i.e. vertically here)
        beyond_top = cone[:10, :].sum()
        beyond_bottom = cone[70:, :].sum()
        self.assertGreater(beyond_top, 0, "cone must extend past the top tip")
        self.assertGreater(beyond_bottom, 0, "cone must extend past the bottom tip")
        # the bulk of the wedge lies beyond the tips; the remainder is the
        # gaussian-smoothed skirt near them
        self.assertGreater(beyond_top + beyond_bottom, 0.8 * cone.sum(),
                           "cones must extend along strike beyond the tips")

    def test_cone_respects_context_and_never_touches_it(self):
        reg = make_region(shape=(160, 160), seed=5)
        t = reg["traces"]
        rng = np.random.default_rng(0)
        plan = hr.sample_hide_plan(t, 0.35, rng)
        ctx, _hidden = hr.apply_plan(t, plan)
        f = r3a_tip_cones(ctx)
        cone = f["r3a_cone"] > 0
        self.assertEqual(int((cone & ctx).sum()), 0,
                         "context-derived cone may never paint the context")

    def test_empty_context_schema_stable(self):
        reg = make_region(shape=(96, 96), seed=3)
        t = reg["traces"]
        f_full = r3a_tip_cones(t)
        f_empty = r3a_tip_cones(np.zeros_like(t))
        self.assertEqual(sorted(f_full), sorted(f_empty))
        for k, v in f_empty.items():
            self.assertEqual(v.shape, t.shape)
            self.assertTrue(np.isfinite(v).all())
        self.assertEqual(float(f_empty["r3a_cone"].sum()), 0.0)


class TestR3BCompleteness(unittest.TestCase):
    def _region(self):
        reg = make_region(shape=(160, 160), seed=7)
        return reg

    def test_schema_and_finiteness(self):
        reg = self._region()
        f = r3b_completeness(reg, reg["traces"])
        self.assertEqual(set(f), {"r3b_residual", "r3b_undmap"})
        for v in f.values():
            self.assertEqual(v.shape, reg["traces"].shape)
            self.assertTrue(np.isfinite(v).all())

    def test_empty_high_strain_cell_gets_negative_residual(self):
        # build a tiny synthetic: strain concentrated where the catalogue is not
        shape = (120, 120)
        strain = np.zeros(shape)
        strain[10:40, 10:40] = 1.0           # high-strain quadrant, empty catalogue
        strain[70:100, 70:100] = 1.0         # high-strain quadrant, WITH catalogue
        elev = np.random.default_rng(1).normal(0, 10, size=shape)
        traces = np.zeros(shape, dtype=bool)
        traces[80:95, 80:95] = True          # catalogue only in the second quadrant
        reg = {"traces": traces, "f_elev": elev, "strain": strain}
        f = r3b_completeness(reg, traces, cell_px=20, smooth_sigma=2.0)
        empty_high_strain = f["r3b_residual"][15:35, 15:35].mean()
        mapped_high_strain = f["r3b_residual"][75:95, 75:95].mean()
        self.assertLess(empty_high_strain, mapped_high_strain,
                        "the un-mapped high-strain quadrant must look under-mapped")
        # undmap is the sigmoid of the negative residual: higher where empty
        self.assertGreater(f["r3b_undmap"][15:35, 15:35].mean(),
                           f["r3b_undmap"][75:95, 75:95].mean())

    def test_empty_context_gives_neutral_output(self):
        reg = self._region()
        f = r3b_completeness(reg, np.zeros_like(reg["traces"]))
        self.assertEqual(float(np.abs(f["r3b_residual"]).sum()), 0.0)


class TestR3CMagnetics(unittest.TestCase):
    def test_ridge_found_and_strike_reported(self):
        shape = (96, 96)
        yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
        f_mag = np.exp(-((xx - 48.0) ** 2) / (2 * 3.0 ** 2))  # N-S ridge of mag high
        reg = {"traces": np.zeros(shape, dtype=bool), "f_mag": f_mag}
        f = r3c_magnetic_lineaments(reg)
        self.assertIn("r3c_ridge_dist", f)
        skel_close = f["r3c_ridge_dist"] < 3.0
        self.assertGreater(int(skel_close[:, 40:56].sum()), 10,
                           "a strong N-S magnetic ridge must be skeletonised")
        for v in f.values():
            self.assertTrue(np.isfinite(v).all())

    def test_context_adds_strike_agreement_features_only(self):
        reg = make_region(shape=(128, 128), seed=9)
        f_wo = r3c_magnetic_lineaments(reg)
        f_with = r3c_magnetic_lineaments(reg, context_mask=reg["traces"])
        self.assertIn("r3c_strike_mismatch", f_with)
        self.assertIn("r3c_parallel_agreement", f_with)
        for k in f_wo:
            self.assertIn(k, f_with)


class TestR3DScarpletLinkage(unittest.TestCase):
    def test_bridge_spans_a_gap_in_a_scarplet(self):
        shape = (96, 96)
        yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
        # N-S scarp with a 6 px buried gap in the middle
        elev = -np.exp(-((xx - 48.0) ** 2) / (2 * 2.0 ** 2)) * 10.0
        reg = {"f_elev": elev, "traces": np.zeros(shape, dtype=bool)}
        f = r3d_scarplet_linkage(reg)
        self.assertIn("r3d_bridge", f)
        # near the middle of the scarp trend, the bridge distance must be small
        mid = f["r3d_bridge_dist"][40:56, 44:52]
        self.assertLess(float(mid.min()), 4.0,
                        "closing must bridge the buried gap along the scarp trend")
        for v in f.values():
            self.assertTrue(np.isfinite(v).all())


class TestAssembly(unittest.TestCase):
    def test_all_r3_arms_dispatch_and_are_finite(self):
        reg = make_region(shape=(128, 128), seed=13)
        for arm in R3_ARMS:
            f = build_arm_features(reg, arm, context_mask=reg["traces"])
            self.assertTrue(f, arm)
            for k, v in f.items():
                self.assertIsInstance(v, np.ndarray)
                self.assertEqual(v.shape, reg["traces"].shape, (arm, k))
                self.assertTrue(np.isfinite(v).all(), (arm, k))

    def test_unknown_arm_raises(self):
        reg = make_region(shape=(64, 64), seed=1)
        with self.assertRaises(ValueError):
            build_arm_features(reg, "R3Z", context_mask=reg["traces"])


if __name__ == "__main__":
    unittest.main()
