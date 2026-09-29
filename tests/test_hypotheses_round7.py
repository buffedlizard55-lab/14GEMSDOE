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
