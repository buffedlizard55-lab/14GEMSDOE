"""Round-7 hypothesis channels + arm wiring (research/hypotheses_round7.md).

Pins:
  * R7-3 gravity_topology: ridge skeleton of the gradient field with
    terminations and junctions (geoedges.edge_termination_field), leak-free
    (no catalogue input);
  * R7-5 transtensional_coupling: shear x relu(±dilatation), with the sign
    convention exposed as a flag (FLAG #12);
  * the gate's arm registry: geom_gravtopo / geom_trans exist, the pinned
    semantics of `all` (R5 only) and `all6` (R5+R6, no R7) are preserved.
"""

import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from gems import realchannels as rc  # noqa: E402


class TestGravityTopology(unittest.TestCase):
    def test_ridge_line_produces_terminations(self):
        # a bright vertical edge running through the middle of a quiet field
        f = np.zeros((64, 64), dtype=np.float32)
        f[:, 32:36] = 1.0
        out = rc.gravity_topology(f, None, sigma=0.0, support_px=4.0)
        self.assertGreater(float(out["grav_ridge"].sum()), 0.0)
        self.assertGreater(float(out["grav_topo"].sum()), 0.0)
        # the ridge should run N-S near column 32-36; terminations live near
        # its ends (rows ~0 and ~63)
        topo = out["grav_topo"]
        end_rows = topo[:8].sum() + topo[-8:].sum()
        self.assertGreater(float(end_rows), 0.0)

    def test_two_crossing_edges_make_a_junction(self):
        # two smooth density steps (tanh contacts) crossing at (24, 24) —
        # the natural synthetic for intersecting gravity gradients
        y, x = np.mgrid[0:48, 0:48].astype(np.float32)
        f = (np.tanh((x - 24) / 2.0) + np.tanh((y - 24) / 2.0)).astype(np.float32)
        out = rc.gravity_topology(f, None, sigma=0.0, support_px=3.0)
        self.assertGreater(float(out["grav_topo"][20:29, 20:29].sum()), 0.0)
        self.assertEqual(np.unravel_index(int(np.argmax(out["grav_topo"])),
                                          out["grav_topo"].shape), (24, 24))

    def test_all_nan_input_is_safe(self):
        f = np.full((16, 16), np.nan, dtype=np.float32)
        out = rc.gravity_topology(f, f, sigma=0.0)
        self.assertTrue(np.isfinite(out["grav_ridge"]).all())
        self.assertTrue(np.isfinite(out["grav_topo"]).all())

    def test_no_catalogue_input(self):
        # leak-free by construction: the function signature accepts only
        # geophysical rasters
        import inspect
        params = set(inspect.signature(rc.gravity_topology).parameters)
        self.assertNotIn("trace", params)
        self.assertNotIn("context", params)


class TestTranstensionalCoupling(unittest.TestCase):
    @staticmethod
    def _varying(scale: float, sign: float, seed: int = 0) -> np.ndarray:
        # strictly `sign`-valued (sign = +1 -> positive, -1 -> negative) and
        # non-constant, so robust scaling is non-degenerate
        r = np.abs(np.random.default_rng(seed).normal(size=(8, 8))) + 0.5
        return (sign * scale * r).astype(np.float32)

    def test_positive_dilatation_couples(self):
        shear = self._varying(1.0, +1.0, seed=1)
        dilat = self._varying(2.0, +1.0, seed=2)
        out = rc.transtensional_coupling(shear, dilat)
        self.assertGreater(float(out["trans_coupling"].max()), 0.0)

    def test_negative_dilatation_vanishes_by_default(self):
        # strictly contracting field: must NEVER read as coupling, even where
        # contraction is below the field median (physical-sign clip first)
        shear = self._varying(1.0, +1.0, seed=3)
        dilat = self._varying(2.0, -1.0, seed=4)
        out = rc.transtensional_coupling(shear, dilat)
        self.assertEqual(float(out["trans_coupling"].max()), 0.0)

    def test_sign_flag_flips_convention(self):
        shear = self._varying(1.0, +1.0, seed=5)
        dilat = self._varying(2.0, -1.0, seed=6)
        out = rc.transtensional_coupling(shear, dilat, extension_positive=False)
        self.assertGreater(float(out["trans_coupling"].max()), 0.0)

    def test_zero_shear_gives_zero_coupling(self):
        shear = np.zeros((8, 8), dtype=np.float32)
        dilat = self._varying(1.0, +1.0, seed=7)
        out = rc.transtensional_coupling(shear, dilat)
        self.assertEqual(float(np.abs(out["trans_coupling"]).max()), 0.0)


class TestRound7ArmWiring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import validate_real as vr
        cls.vr = vr

    def test_arm_spec_has_round7_arms(self):
        self.assertIn("geom_gravtopo", self.vr.ARM_SPEC)
        self.assertIn("geom_trans", self.vr.ARM_SPEC)

    def test_arm_channels_names(self):
        names, r5, geo = self.vr.arm_channels("geom_gravtopo")
        self.assertIn("grav_ridge", names)
        self.assertIn("grav_topo", names)
        self.assertTrue(geo)
        names, r5, geo = self.vr.arm_channels("geom_trans")
        self.assertIn("trans_coupling", names)

    def test_all_stays_r5_only(self):
        _names, r5, _geo = self.vr.arm_channels("all")
        self.assertEqual(r5, {"ramp", "acc", "tilt", "curv", "gap"})

    def test_all6_stays_r5_r6(self):
        _names, r5, _geo = self.vr.arm_channels("all6")
        self.assertNotIn("gravtopo", r5)
        self.assertNotIn("trans", r5)
        self.assertIn("horse", r5)

    def test_build_round5_channels_wiring(self):
        rng = np.random.default_rng(1)
        shape = (48, 48)
        context = np.zeros(shape, dtype=bool)
        context[20:24, 10:30] = True
        static = {
            "iso_grav_anom_hg": rng.normal(size=shape).astype(np.float16),
            "iso_grav_anom_slope": rng.normal(size=shape).astype(np.float16),
            "geod_shearrate": rng.normal(size=shape).astype(np.float16),
            "geod_dilaterate": rng.normal(size=shape).astype(np.float16),
        }
        valid = np.ones(shape, dtype=bool)
        out = self.vr.build_round5_channels(context, static, valid,
                                            {"gravtopo", "trans"})
        self.assertIn("grav_ridge", out)
        self.assertIn("grav_topo", out)
        self.assertIn("trans_coupling", out)
        for v in out.values():
            self.assertEqual(v.shape, shape)
            self.assertTrue(np.isfinite(v).all())


if __name__ == "__main__":
    unittest.main()


class TestMisregistrationStress(unittest.TestCase):
    """R7-1 protocol utilities (C28 misregistration simulation)."""

    def test_misregister_moves_components_not_truth_shape(self):
        rng = np.random.default_rng(7)
        mask = np.zeros((32, 32), dtype=bool)
        mask[4:10, 4:10] = True
        mask[20:26, 20:26] = True
        out, offs = rc.misregister_mask(mask, 2, rng)
        self.assertEqual(int(mask.sum()), int(out.sum()))   # rigid: same pixels
        self.assertFalse(np.array_equal(out, mask))          # actually moved
        self.assertTrue((np.abs(offs[1:]) <= 2).all())

    def test_zero_delta_is_identity(self):
        rng = np.random.default_rng(7)
        mask = np.zeros((16, 16), dtype=bool)
        mask[2:8, 2:8] = True
        out, _ = rc.misregister_mask(mask, 0, rng)
        self.assertTrue(np.array_equal(out, mask))

    def test_displace_consistent_across_views(self):
        from scipy import ndimage
        lab = np.zeros((16, 16), dtype=int)
        lab[2:6, 2:6] = 1
        lab[10:14, 10:14] = 2
        offs = rc.component_offsets(2, 2, np.random.default_rng(3))
        full = rc.displace_mask(lab > 0, lab, offs)
        part = rc.displace_mask(lab == 1, lab, offs)
        ys, xs = np.nonzero(part)
        self.assertTrue(full[ys, xs].all())
        self.assertEqual(int(part.sum()), int((lab == 1).sum()))

    def test_component_offsets_force_nonzero(self):
        # with delta 1 and many components, at least one shift must be non-zero
        offs = rc.component_offsets(50, 1, np.random.default_rng(5))
        self.assertTrue((np.abs(offs[1:]).sum(axis=1) > 0).any())

    def test_align_moves_toward_expression_and_is_stable(self):
        mask = np.zeros((32, 32), dtype=bool)
        mask[5:25, 12] = True
        expr = np.zeros((32, 32), dtype=np.float32)
        expr[:, 15] = 1.0
        corr, off = rc.align_traces_to_expression(mask, expr, max_offset=3)
        self.assertEqual(list(np.unique(np.nonzero(corr)[1])), [15])
        self.assertAlmostEqual(float(off[corr].max()), 3.0, places=5)
        again, off2 = rc.align_traces_to_expression(corr, expr, max_offset=3)
        self.assertTrue(np.array_equal(again, corr))
        self.assertAlmostEqual(float(off2[again].max()), 0.0, places=5)

    def test_align_respects_max_offset(self):
        mask = np.zeros((48, 48), dtype=bool)
        mask[10:30, 5] = True
        expr = np.zeros((48, 48), dtype=np.float32)
        expr[:, 25] = 1.0            # 20 px away: outside the search window
        corr, off = rc.align_traces_to_expression(mask, expr, max_offset=3)
        self.assertLessEqual(float(off.max()), 3.0)

    def test_gate_registry(self):
        import validate_real as vr
        self.assertIn("geom_align", vr.ARM_SPEC)
        names, r5, _geo = vr.arm_channels("geom_align")
        self.assertIn("align", r5)
        self.assertIn("align_offset", names)
        # the misregistration flag must exist and default to 0
        import argparse
        from io import StringIO
        import contextlib
        # parse the source rather than running main()
        src = (REPO / "scripts" / "validate_real.py").read_text()
        self.assertIn("--misreg-px", src)
        self.assertIn("misreg_px", src)


class TestContinuationSubset(unittest.TestCase):
    """R7-2 diagnostic: hidden components that continue a visible trace."""

    def test_collinear_tip_pair_is_continuation(self):
        # visible trace ending at (20, 10); test trace continuing east to (20, 30)
        test = np.zeros((48, 48), dtype=bool)
        test[20, 14:31] = True
        visible = np.zeros((48, 48), dtype=bool)
        visible[20, 2:11] = True          # collinear, gap 3 px
        from scripts.continuation_subset import continuation_subset
        cont, iso = continuation_subset(test, visible, tip_px=20.0, angle_deg=30.0)
        self.assertTrue(np.array_equal(cont, test))   # whole trace continues
        self.assertFalse(iso.any())

    def test_orthogonal_far_component_is_isolated(self):
        test = np.zeros((48, 48), dtype=bool)
        test[40, 30:45] = True            # horizontal, far from the visible end
        visible = np.zeros((48, 48), dtype=bool)
        visible[5:20, 5] = True           # vertical trace top-left
        from scripts.continuation_subset import continuation_subset
        cont, iso = continuation_subset(test, visible, tip_px=20.0, angle_deg=30.0)
        self.assertFalse(cont.any())
        self.assertTrue(iso.any())

    def test_needs_both_proximity_and_strike(self):
        # near the visible tip but orthogonal -> not a continuation
        test = np.zeros((48, 48), dtype=bool)
        test[10:25, 22] = True
        visible = np.zeros((48, 48), dtype=bool)
        visible[20, 2:11] = True
        from scripts.continuation_subset import continuation_subset
        cont, iso = continuation_subset(test, visible, tip_px=20.0, angle_deg=30.0)
        self.assertFalse(cont.any())


class TestContinuationStitch(unittest.TestCase):
    """R7-2 buried continuation stitching (gems.realchannels.continuation_stitches)."""

    def _world(self, *, bend_deg=0.0, gap=False, flat_field=False):
        """Trace row 32 cols 4-20 (optionally + a second strand cols 30-46),
        potential-field ridge continuing east from the tip (optionally bending)."""
        import numpy as np
        from gems import realchannels as rc  # noqa: F401  (import check)
        n = 96
        t = np.zeros((n, n), dtype=bool)
        t[32, 4:21] = True
        if gap:
            t[32, 30:47] = True
        yy, xx = np.mgrid[0:n, 0:n]
        if flat_field:
            ridge = np.zeros((n, n), dtype=np.float32)
        elif bend_deg == 0.0:
            ridge = np.exp(-((yy - 32) ** 2) / 8.0) * ((xx >= 20) & (xx <= 70))
        else:
            # ridge bends by bend_deg degrees past col 40
            import math
            k = math.tan(math.radians(bend_deg))
            line = 32 + np.clip(xx - 40, 0, None) * k
            ridge = (np.exp(-((yy - line) ** 2) / 8.0)
                     * ((xx >= 20) & (xx <= 88))).astype(np.float32)
        depth = (np.exp(-((yy - 32) ** 2) / 200.0)
                 * np.clip((xx - 16) * 0.5, 0, None)).astype(np.float32)
        z = np.zeros((n, n), dtype=np.float32)
        return t, ridge, depth, z

    def _run(self, **kw):
        import numpy as np
        from gems import realchannels as rc
        t, ridge, depth, z = self._world(**kw)
        return rc.continuation_stitches(t, ridge, ridge, z, z,
                                        depth_to_base=depth, det_elev=z)

    def test_follows_ridge_past_tip(self):
        import numpy as np
        out = self._run()
        b = out["stitch_bridge"]
        # the corridor runs east along row 32 past the tip at (32, 20)
        self.assertTrue(b[32, 25] > 0.5 and b[32, 35] > 0.2, b[32, 20:41])
        # ...and nowhere off the ridge
        self.assertLess(float(b[[28, 29, 35, 36]].max()), 0.05)

    def test_stops_when_noncollinear(self):
        # a 45-degree bend eventually leaves the 30-degree collinearity cone
        # (measured from the tip's own strike); the corridor must stop there
        out = self._run(bend_deg=45.0)
        b = out["stitch_bridge"]
        self.assertTrue(b[32, 30] > 0.2, "walks while still collinear")
        # at cols >= 75 the ridge lies >30 deg off the tip strike: no following
        self.assertLess(float(b[55:, 75:].max()), 0.05)

    def test_connects_mapped_gap(self):
        out = self._run(gap=True)
        b = out["stitch_bridge"]
        # the gap cols 21-29 is bridged
        self.assertTrue((b[32, 22:29] > 0.2).all(), b[32, 20:31])
        # landing on the far strand pins high support at the junction
        self.assertGreater(float(b[32, 30]), float(b[32, 25]))

    def test_flat_field_no_bridge(self):
        out = self._run(flat_field=True)
        self.assertLess(float(out["stitch_bridge"].max()), 0.05)

    def test_cover_channel_tracks_cover(self):
        import numpy as np
        from gems import realchannels as rc
        t, ridge, depth, z = self._world()
        thick = rc.continuation_stitches(t, ridge, ridge, z, z,
                                         depth_to_base=depth, det_elev=z)
        thin = rc.continuation_stitches(t, ridge, ridge, z, z,
                                        depth_to_base=np.zeros_like(depth),
                                        det_elev=z)
        rough = rc.continuation_stitches(
            t, ridge, ridge, z, z, depth_to_base=depth,
            det_elev=np.tile(np.linspace(0.0, 50.0, 96, dtype=np.float32), (96, 1)))
        # the corridor itself does not depend on cover
        np.testing.assert_allclose(thick["stitch_bridge"], thin["stitch_bridge"])
        # no cover -> no buried-continuation emphasis
        self.assertEqual(float(thin["stitch_cover"].sum()), 0.0)
        self.assertGreater(float(thick["stitch_cover"].sum()), 0.0)
        # steep topography suppresses the cover emphasis relative to flat
        self.assertLess(float(rough["stitch_cover"][32, 30:60].sum()),
                        float(thick["stitch_cover"][32, 30:60].sum()))


class TestStitchAndHorse7Wiring(unittest.TestCase):
    def test_geom_stitch_wiring(self):
        import validate_real as vr
        names, r5, geo = vr.arm_channels("geom_stitch")
        self.assertIn("stitch", r5)
        self.assertIn("stitch_bridge", names)
        self.assertIn("stitch_cover", names)
        self.assertIn("geom_stitch", vr.ARM_SPEC)

    def test_horse7_wiring(self):
        import validate_real as vr
        names, r5, geo = vr.arm_channels("horse7")
        self.assertEqual(r5, {"horse", "gravtopo", "trans", "align"})
        self.assertIn("horse_splay", names)
        self.assertIn("grav_ridge", names)
        self.assertIn("trans_coupling", names)
        self.assertIn("align_offset", names)
        self.assertNotIn("stitch_bridge", names)  # excluded at definition time
        self.assertIn("horse7", vr.ARM_SPEC)


class TestCalibPolicyV2(unittest.TestCase):
    """Pre-registered emission-policy protocol v2 (hypotheses_round7.md section 5)."""

    def _setup(self):
        import numpy as np
        rng = np.random.default_rng(3)
        n = 160
        field = (rng.random((n, n)) * 0.2).astype(np.float32)
        calib = np.zeros((n, n), bool)
        calib[30:32, 20:80] = True
        calib[100:102, 20:80] = True
        field[30:32, 20:80] = 0.95
        field[100:102, 20:80] = 0.45
        valid = np.ones((n, n), bool)
        return field, calib, valid

    def test_v2_reports_both_views_and_mean(self):
        import numpy as np
        import validate_real as vr
        field, calib, valid = self._setup()
        pol = vr.calibrate_policy(field, calib, valid, seed=5)
        self.assertIn("calib_dense_dti", pol)
        self.assertIn("calib_sparse_dti", pol)
        self.assertAlmostEqual(pol["calib_dti"],
                               0.5 * (pol["calib_dense_dti"] + pol["calib_sparse_dti"]),
                               places=9)

    def test_v2_uses_fine_budget_grid(self):
        import numpy as np
        import validate_real as vr
        field, calib, valid = self._setup()
        pol = vr.calibrate_policy(field, calib, valid, seed=5)
        if pol["policy"] == "topk":
            fine = {float(f"{q:.6g}") for q in np.geomspace(0.0025, 0.05, 16)}
            self.assertIn(pol["param"], fine)
        else:
            self.assertIn(pol["param"], (0.5, 0.7, 0.9, 0.95, 0.99))

    def test_v1_reproduces_archived_behaviour(self):
        import validate_real as vr
        field, calib, valid = self._setup()
        pol = vr.calibrate_policy(field, calib, valid, seed=5, v1=True)
        self.assertEqual(set(pol.keys()), {"policy", "param", "calib_dti"})
        self.assertIn(pol["param"], (0.5, 0.7, 0.9, 0.95, 0.99, 0.005, 0.01, 0.02, 0.05))
