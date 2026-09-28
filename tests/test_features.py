"""Catalogue-geometry feature tests on synthetic traces with known geometry."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems.features import (along_across_strike, distance_and_azimuth,
                           endpoint_mask, intersection_density,
                           relay_corridors, strike_mismatch, strike_field,
                           structure_tensor_orientation)


def vertical_line(n=32, col=16):
    m = np.zeros((n, n), dtype=bool)
    m[:, col] = True
    return m


def horizontal_line(n=32, row=16):
    m = np.zeros((n, n), dtype=bool)
    m[row, :] = True
    return m


class TestDistanceAzimuth(unittest.TestCase):
    def test_distance_to_vertical_line(self):
        m = vertical_line(32, 16)
        d = distance_and_azimuth(m)
        self.assertEqual(d["dist_trace"][20, 16], 0.0)
        self.assertEqual(d["dist_trace"][20, 19], 3.0)
        self.assertEqual(d["dist_trace"][20, 10], 6.0)

    def test_azimuth_toward_trace(self):
        m = vertical_line(32, 16)
        d = distance_and_azimuth(m)
        # pixel east of the line must look WEST (270 deg) toward the trace
        self.assertAlmostEqual(d["az_to_trace"][20, 22], 270.0, places=3)
        # pixel west of the line must look EAST (90 deg)
        self.assertAlmostEqual(d["az_to_trace"][20, 10], 90.0, places=3)


class TestEndpoints(unittest.TestCase):
    def test_line_has_two_endpoints(self):
        m = vertical_line(32, 16)
        ends = endpoint_mask(m)
        self.assertEqual(int(ends.sum()), 2)
        self.assertTrue(ends[0, 16])
        self.assertTrue(ends[31, 16])

    def test_loop_has_no_endpoints(self):
        m = np.zeros((16, 16), dtype=bool)
        m[4, 4:12] = True; m[11, 4:12] = True
        m[4:12, 4] = True; m[4:12, 11] = True
        ends = endpoint_mask(m)
        self.assertEqual(int(ends.sum()), 0)


class TestAlongAcross(unittest.TestCase):
    def test_across_is_perpendicular_distance(self):
        m = vertical_line(32, 16)
        f = along_across_strike(m, window=7)
        # for a pixel 4 px east of the line, across-strike magnitude = 4
        self.assertAlmostEqual(abs(f["across_strike"][20, 20]), 4.0, delta=0.5)

    def test_endpoint_distance(self):
        m = vertical_line(32, 16)
        f = along_across_strike(m, window=7)
        # midpoint of the line is ~16 px from both ends
        self.assertAlmostEqual(float(f["dist_endpoint"][16, 16]), 16.0, delta=1.5)


class TestRelayCorridors(unittest.TestCase):
    def test_parallel_gap_pair_detected(self):
        # two parallel vertical strands with a 4 px gap between tips
        m = np.zeros((32, 32), dtype=bool)
        m[0:14, 10] = True    # strand A ends at row 13
        m[18:32, 12] = True   # strand B starts at row 18 (gap ~4 px)
        r = relay_corridors(m, min_gap_px=2, max_gap_px=10, max_strike_diff_deg=35)
        self.assertGreaterEqual(r["n_pairs"], 1)
        self.assertGreater(float(r["corridor"].max()), 0.0)
        # corridor peak lies between the tips
        peak = np.unravel_index(int(np.argmax(r["corridor"])), r["corridor"].shape)
        self.assertTrue(12 <= peak[0] <= 20)

    def test_orthogonal_pair_not_relay(self):
        m = np.zeros((32, 32), dtype=bool)
        m[6, 0:12] = True     # horizontal
        m[24, 20:32] = True   # horizontal far away AND orthogonal-ish case
        m2 = np.zeros((32, 32), dtype=bool)
        m2[0:12, 6] = True    # vertical
        m2[20:28, 8] = True
        both = m2  # vertical pair is fine
        r_strict = relay_corridors(m, min_gap_px=2, max_gap_px=40, max_strike_diff_deg=5)
        # the two horizontal segments are parallel but far; use strike filter on
        # a deliberately orthogonal close pair instead:
        mo = np.zeros((32, 32), dtype=bool)
        mo[0:12, 10] = True       # vertical strand
        mo[14:16, 12:24] = True   # horizontal strand 2 px below its tip
        r_ortho = relay_corridors(mo, min_gap_px=1, max_gap_px=8, max_strike_diff_deg=10)
        self.assertEqual(r_ortho["n_pairs"], 0)

    def test_empty_and_single(self):
        m = np.zeros((16, 16), dtype=bool)
        self.assertEqual(relay_corridors(m)["n_pairs"], 0)
        m[8, 2:8] = True
        self.assertEqual(relay_corridors(m)["n_pairs"], 0)


class TestIntersectionDensity(unittest.TestCase):
    def test_crossing_produces_junction(self):
        m = np.zeros((21, 21), dtype=bool)
        m[10, :] = True
        m[:, 10] = True
        d = intersection_density(m, radius_px=3)
        self.assertGreater(float(d["junction_density"][10, 10]), 0.0)
        self.assertGreater(float(d["trace_density"][10, 10]),
                           float(d["trace_density"][0, 0]))


class TestStrike(unittest.TestCase):
    def test_strike_field_vertical(self):
        m = vertical_line(32, 16)
        s, conf = strike_field(m, window=7)
        vals = s[m]
        # a vertical line in (row, col) has principal axis along rows -> strike
        # consistent with ~0 or ~180 mapped into [0,180)
        self.assertTrue(np.all((vals < 15) | (vals > 165)))
        self.assertGreater(float(conf[m].mean()), 0.5)

    def test_strike_mismatch_range(self):
        a = np.full((4, 4), 10.0, dtype=np.float32)
        b = np.full((4, 4), 170.0, dtype=np.float32)
        mm = strike_mismatch(a, b)
        self.assertAlmostEqual(float(mm[0, 0]), 20.0, places=4)  # 170 vs 10 -> 20 deg
        self.assertTrue((mm >= 0).all() and (mm <= 90).all())

    def test_structure_tensor_on_edge(self):
        img = np.zeros((32, 32), dtype=np.float32)
        img[:, 16:] = 1.0
        strike, coh = structure_tensor_orientation(img, sigma=1.5)
        self.assertTrue((coh >= 0).all() and (coh <= 1).all())
        # the step edge is vertical; lineament strike should be near-vertical
        interior = strike[8:24, 14:18].ravel()
        self.assertTrue(np.all((interior < 20) | (interior > 160)))


if __name__ == "__main__":
    unittest.main()
