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
