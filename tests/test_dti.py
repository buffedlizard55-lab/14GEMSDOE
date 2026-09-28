"""DTI metric tests: analytic vectors derived by hand from the printed equations.

Official source of the equations (verified 2026-09-28):
https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems.dti import (DEFAULT_ALPHA, DEFAULT_BETA, DEFAULT_R_PX, dti,
                      dti_from_example_values, kernel_weighted_max,
                      triangular_kernel)


class TestKernel(unittest.TestCase):
    def test_values(self):
        d = np.array([0.0, 1.0, 2.0, 3.0, 4.0])
        k = triangular_kernel(d, 3.0)
        np.testing.assert_allclose(k, [1.0, 2 / 3, 1 / 3, 0.0, 0.0])

    def test_nonnegative(self):
        d = np.linspace(-5, 10, 100)
        self.assertTrue((triangular_kernel(d, 3.0) >= 0).all())


class TestOfficialWorkedExample(unittest.TestCase):
    def test_printed_result(self):
        # page prints TIw(0.2, 0.8) = 3.00 / (3.00 + 0.2*1.89 + 0.8*2.00) = 0.60
        v = dti_from_example_values(3.00, 1.89, 2.00)
        self.assertAlmostEqual(v, 3.00 / (3.00 + 0.378 + 1.600 + 1e-9), places=12)
        self.assertEqual(round(v, 2), 0.60)  # matches the printed 0.60


class TestDTIAnalyticVectors(unittest.TestCase):
    def test_perfect_single_pixel(self):
        # 1 predicted px exactly on 1 GT px, nothing else: TP=1, FN=0, FP=0
        g = np.zeros((7, 7)); g[3, 3] = 1
        p = np.zeros((7, 7)); p[3, 3] = 1.0
        r = dti(p, g)
        self.assertAlmostEqual(r["tp"], 1.0, places=9)
        self.assertAlmostEqual(r["fn"], 0.0, places=9)
        self.assertAlmostEqual(r["fp"], 0.0, places=9)
        self.assertAlmostEqual(r["dti"], 1.0 / (1.0 + 1e-9), places=12)

    def test_all_missed(self):
        g = np.zeros((7, 7)); g[3, 3] = 1
        p = np.zeros((7, 7))
        r = dti(p, g)
        self.assertAlmostEqual(r["tp"], 0.0, places=9)
        self.assertAlmostEqual(r["fn"], 1.0, places=9)
        self.assertAlmostEqual(r["dti"], 0.0, places=9)

    def test_offset_by_one_px(self):
        # prediction 1 px from the GT: TP = k(1) = 2/3, FN = 1/3
        # FP: the predicted px is at distance 1 -> kmax = 2/3 -> FP = 1 * (1-2/3) = 1/3
        g = np.zeros((7, 7)); g[3, 3] = 1
        p = np.zeros((7, 7)); p[3, 4] = 1.0
        r = dti(p, g)
        self.assertAlmostEqual(r["tp"], 2 / 3, places=9)
        self.assertAlmostEqual(r["fn"], 1 / 3, places=9)
        self.assertAlmostEqual(r["fp"], 1 / 3, places=9)
        expect = (2 / 3) / (2 / 3 + 0.2 * (1 / 3) + 0.8 * (1 / 3) + 1e-9)
        self.assertAlmostEqual(r["dti"], expect, places=12)

    def test_offset_beyond_support(self):
        # prediction 5 px away: no TP credit, full FN, full FP
        g = np.zeros((11, 11)); g[5, 5] = 1
        p = np.zeros((11, 11)); p[5, 0] = 1.0
        r = dti(p, g)
        self.assertAlmostEqual(r["tp"], 0.0, places=9)
        self.assertAlmostEqual(r["fn"], 1.0, places=9)
        self.assertAlmostEqual(r["fp"], 1.0, places=9)  # kmax=0 at that distance

    def test_recall_penalty_dominates(self):
        # equal-magnitude error: one FN hurts 4x as much as one FP (beta/alpha=4)
        self.assertAlmostEqual(DEFAULT_BETA / DEFAULT_ALPHA, 4.0, places=12)

    def test_probability_mass_at_distance_zero(self):
        # fractional p on the GT pixel: TP = p, FN = 1-p, FP = 0
        g = np.zeros((5, 5)); g[2, 2] = 1
        p = np.zeros((5, 5)); p[2, 2] = 0.4
        r = dti(p, g)
        self.assertAlmostEqual(r["tp"], 0.4, places=9)
        self.assertAlmostEqual(r["fn"], 0.6, places=9)
        self.assertAlmostEqual(r["fp"], 0.0, places=9)

    def test_two_gt_best_prediction_wins(self):
        # two GT pixels; one well predicted, one missed entirely
        g = np.zeros((9, 9)); g[4, 2] = 1; g[4, 6] = 1
        p = np.zeros((9, 9)); p[4, 2] = 1.0
        r = dti(p, g)
        self.assertAlmostEqual(r["tp"], 1.0, places=9)
        self.assertAlmostEqual(r["fn"], 1.0, places=9)

    def test_nan_treated_as_zero(self):
        g = np.zeros((5, 5)); g[2, 2] = 1
        p = np.full((5, 5), np.nan); p[2, 2] = 1.0
        r = dti(p, g)
        self.assertAlmostEqual(r["dti"], 1.0 / (1.0 + 1e-9), places=12)

    def test_out_of_range_rejected(self):
        g = np.zeros((5, 5)); g[2, 2] = 1
        p = np.zeros((5, 5)); p[2, 2] = 2.0  # logits-like
        with self.assertRaises(ValueError):
            dti(p, g)


class TestMasking(unittest.TestCase):
    def test_known_fault_mask_makes_catalogue_free(self):
        # staff ruling (forum 11516): known-fault pixels are excluded from
        # evaluation; including or omitting catalogue predictions must not
        # change the score.  Under eval_mask semantics this holds exactly.
        g = np.zeros((11, 11)); g[5, 5] = 1          # hidden fault pixel
        known = np.zeros((11, 11), dtype=bool); known[5, 2] = True  # catalogue px
        p_with = np.zeros((11, 11)); p_with[5, 5] = 0.9; p_with[5, 2] = 1.0
        p_without = np.zeros((11, 11)); p_without[5, 5] = 0.9
        em = ~known
        r1 = dti(p_with, g, eval_mask=em)
        r2 = dti(p_without, g, eval_mask=em)
        self.assertAlmostEqual(r1["dti"], r2["dti"], places=12)

    def test_masked_ground_truth_removed(self):
        g = np.zeros((7, 7)); g[3, 3] = 1
        known = np.zeros((7, 7), dtype=bool); known[3, 3] = True
        p = np.zeros((7, 7))
        r = dti(p, g, eval_mask=~known)
        self.assertEqual(r["n_gt"], 0)
        self.assertAlmostEqual(r["dti"], 0.0, places=9)


class TestKernelWeightedMax(unittest.TestCase):
    def test_identity_when_on_pixel(self):
        p = np.zeros((5, 5)); p[2, 2] = 0.7
        m = kernel_weighted_max(p, 3.0)
        self.assertAlmostEqual(m[2, 2], 0.7, places=9)

    def test_decay_with_distance(self):
        p = np.zeros((9, 9)); p[4, 4] = 1.0
        m = kernel_weighted_max(p, 3.0)
        self.assertAlmostEqual(m[4, 5], 2 / 3, places=9)
        self.assertAlmostEqual(m[4, 6], 1 / 3, places=9)
        self.assertAlmostEqual(m[4, 7], 0.0, places=9)


if __name__ == "__main__":
    unittest.main()
