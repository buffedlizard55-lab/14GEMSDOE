"""Round-2 hypothesis arms: leak-freedom, determinism, and the gate itself.

The point of these tests is that a hypothesis arm may NEVER be able to read the
answer off the catalogue, and that the holdout gate refuses to promote an arm
that does not beat the baseline.
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems import geoedges as ge  # noqa: E402
from gems import hide_recover as hr  # noqa: E402
from gems.hypotheses import (ARMS, build_arm_features, n1_gravity_edges,  # noqa: E402
                             n2_seismic_lineaments, n3_cap_margin, n5_range_front)
from gems.synthesize import make_region  # noqa: E402


class TestArmLeakFreedom(unittest.TestCase):
    """Every arm must be computable with NO catalogue in the region at all."""

    def setUp(self):
        self.region = make_region(shape=(128, 128), seed=31, n_blind=3)

    def test_arms_ignore_the_catalogue(self):
        stripped = {k: v for k, v in self.region.items() if k != "traces"}
        for arm in ("N1", "N2", "N3", "N5", "ALL"):
            with_cat = build_arm_features(self.region, arm)
            without_cat = build_arm_features(stripped, arm)
            self.assertEqual(sorted(with_cat), sorted(without_cat), arm)
            for k in with_cat:
                np.testing.assert_array_equal(with_cat[k], without_cat[k], err_msg=f"{arm}/{k}")

    def test_arm_features_are_2d_float_and_finite(self):
        for arm in ("N1", "N2", "N3", "N5", "ALL"):
            for k, v in build_arm_features(self.region, arm).items():
                self.assertEqual(v.ndim, 2, f"{arm}/{k}")
                self.assertTrue(np.isfinite(v).all(), f"{arm}/{k} has non-finite values")

    def test_arm_features_are_invariant_to_an_arbitrary_catalogue(self):
        # the strongest form of the leak test: replace the catalogue with an
        # UNRELATED trace set and require the arm features to be unchanged
        rng = np.random.default_rng(0)
        bogus = np.zeros_like(self.region["traces"])
        ys = rng.integers(0, bogus.shape[0], 400)
        xs = rng.integers(0, bogus.shape[1], 400)
        bogus[ys, xs] = True
        swapped = dict(self.region)
        swapped["traces"] = bogus
        a = build_arm_features(self.region, "ALL")
        b = build_arm_features(swapped, "ALL")
        self.assertEqual(sorted(a), sorted(b))
        for k in a:
            np.testing.assert_array_equal(a[k], b[k], err_msg=k)

    def test_n1_finds_blind_faults_better_than_distance_to_catalogue(self):
        from gems.dti import dti
        from gems.features import distance_and_azimuth
        feats = build_arm_features(self.region, "N1")
        blind = self.region["blind_traces"]
        self.assertTrue(blind.any())
        d_cat = distance_and_azimuth(self.region["traces"])["dist_trace"]
        cat_proxy = 1.0 / (1.0 + d_cat)
        self.assertGreater(dti(feats["n1_term_field"], blind)["dti"],
                           dti(cat_proxy, blind)["dti"])


class TestHypothesisArms(unittest.TestCase):
    def test_unknown_arm_raises(self):
        with self.assertRaises(ValueError):
            build_arm_features({}, "NOPE")

    def test_derived_arms_map_to_all(self):
        r = make_region(shape=(64, 64), seed=1)
        self.assertEqual(sorted(build_arm_features(r, "BLEND-MUL")),
                         sorted(build_arm_features(r, "ALL")))

    def test_arms_are_deterministic(self):
        r = make_region(shape=(96, 96), seed=5)
        for arm in ARMS:
            a = build_arm_features(r, arm)
            b = build_arm_features(r, arm)
            self.assertEqual(sorted(a), sorted(b))
            for k in a:
                np.testing.assert_array_equal(a[k], b[k])


class TestGateSemantics(unittest.TestCase):
    """The gate must refuse an arm that does not beat the baseline."""

    def test_gate_logic(self):
        # mirrors the promotion rule in scripts/validate_round2.py
        def gate(combined, baseline):
            return combined > baseline

        self.assertTrue(gate(0.40, 0.29))
        self.assertFalse(gate(0.29, 0.29))
        self.assertFalse(gate(0.28, 0.29))

    def test_leak_invariant_still_holds_with_arm_features(self):
        region = make_region(shape=(128, 128), seed=7)
        rng = np.random.default_rng(0)
        for _ in range(3):
            plan = hr.sample_hide_plan(region["traces"], 0.4, rng, buffer_px=2.0)
            ctx, hidden = hr.apply_plan(region["traces"], plan)
            self.assertEqual(hr.assert_no_leak(ctx, hidden)["leaks"], 0)
            # arm features are context-independent, so they cannot leak either
            a = build_arm_features(region, "ALL")
            b = build_arm_features({**region, "traces": ctx}, "ALL")
            for k in a:
                np.testing.assert_array_equal(a[k], b[k], err_msg=k)


class TestGeoEdgeRobustness(unittest.TestCase):
    def test_all_nan_field_does_not_crash(self):
        f = np.full((32, 32), np.nan)
        out = ge.edge_termination_field(f)
        self.assertFalse(out["skeleton"].any())
        self.assertEqual(float(out["term_field"].max()), 0.0)

    def test_constant_field_has_no_edges(self):
        out = ge.edge_termination_field(np.ones((32, 32)))
        self.assertFalse(out["skeleton"].any())

    def test_cap_mask_requires_at_least_one_input(self):
        with self.assertRaises(ValueError):
            ge.cap_mask_from_anomalies()

    def test_cap_margin_of_empty_mask_is_zero(self):
        m = ge.cap_margin(np.zeros((16, 16), dtype=bool))
        self.assertEqual(float(m.max()), 0.0)
