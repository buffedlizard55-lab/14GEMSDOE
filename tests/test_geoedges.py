"""Geophysical edge/lineament detector tests.

The detectors must (a) recover a known edge geometry from a clean field,
(b) report the edge's END and its INTERSECTIONS, and (c) be blind to the
catalogue - i.e. they must not take a trace mask as input at all.
"""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems import geoedges as ge  # noqa: E402
from gems.synthesize import make_region  # noqa: E402


def step_field(shape=(64, 64), col=32, amp=10.0):
    """A full-height vertical density step at column ``col``.

    Full height matters: a partial step would also produce horizontal ridges
    along its top and bottom, which is correct behaviour but not what these
    unit tests are about.
    """
    a = np.zeros(shape, dtype=np.float64)
    a[:, col:] = amp
    return a


def partial_step_field(shape=(64, 64), col=32, amp=10.0, y0=8, y1=56):
    """A vertical step that starts and stops: its |grad| ridge has ENDS."""
    a = np.zeros(shape, dtype=np.float64)
    a[y0:y1, col:] = amp
    return a


class TestGradient(unittest.TestCase):
    def test_gradient_of_step_is_peaked_on_the_step(self):
        f = step_field()
        mag, gx, gy = ge.gradient_magnitude(f, sigma=0.0)
        self.assertGreater(mag[20, 32], mag[20, 20])
        self.assertGreater(mag[20, 32], mag[20, 44])
        self.assertAlmostEqual(float(gy.max()), 0.0, places=6)

    def test_nan_is_not_propagated(self):
        f = step_field()
        f[0, 0] = np.nan
        mag, _gx, _gy = ge.gradient_magnitude(f, sigma=0.0)
        self.assertTrue(np.isfinite(mag).all())


class TestRidgeSkeleton(unittest.TestCase):
    def test_vertical_step_gives_vertical_ridge(self):
        f = step_field()
        skel = ge.ridge_skeleton(f, sigma=0.0, min_length_px=4)
        self.assertTrue(skel.any())
        rows, cols = np.nonzero(skel)
        # the ridge must sit on (or within 1 px of) the step column
        self.assertLessEqual(int(np.abs(cols - 32).max()), 1)
        # and it must be ~vertical: the column spread is much smaller than rows
        self.assertLess(int(cols.max() - cols.min()), int(rows.max() - rows.min()))

    def test_skeleton_is_one_pixel_wide(self):
        f = step_field()
        skel = ge.ridge_skeleton(f, sigma=0.0, min_length_px=4)
        # no 2x2 block of skeleton pixels
        blocks = skel[:-1, :-1] & skel[:-1, 1:] & skel[1:, :-1] & skel[1:, 1:]
        self.assertEqual(int(blocks.sum()), 0)

    def test_flat_field_has_no_ridge(self):
        skel = ge.ridge_skeleton(np.zeros((32, 32)), sigma=0.0)
        self.assertFalse(skel.any())


class TestTerminationsAndJunctions(unittest.TestCase):
    def test_open_line_has_two_terminations(self):
        skel = np.zeros((32, 32), dtype=bool)
        skel[10, 8:24] = True
        term = ge.edge_terminations(skel)
        self.assertEqual(int(term.sum()), 2)
        self.assertTrue(term[10, 8])
        self.assertTrue(term[10, 23])

    def test_loop_has_no_terminations(self):
        skel = np.zeros((32, 32), dtype=bool)
        skel[8, 8:24] = True
        skel[23, 8:24] = True
        skel[8:24, 8] = True
        skel[8:24, 23] = True
        self.assertEqual(int(ge.edge_terminations(skel).sum()), 0)

    def test_three_arms_meeting_give_one_junction(self):
        skel = np.zeros((32, 32), dtype=bool)
        skel[16, 16:32] = True          # east arm
        skel[8:17, 16] = True           # north arm
        for i in range(1, 15):          # south-east diagonal arm
            skel[16 + i, 16 + i] = True
        junc = ge.edge_junctions(skel)
        # a rasterised 3-arm junction is a small CLUSTER of branch-like pixels
        # (the arm pixels flanking the true node also see 3 neighbours); the
        # detector reports the cluster, and the true node is in it
        self.assertTrue(junc[16, 16])
        self.assertLessEqual(int(junc.sum()), 9)
        self.assertGreaterEqual(int(junc.sum()), 1)

    def test_cross_has_a_junction_at_the_centre(self):
        skel = np.zeros((32, 32), dtype=bool)
        skel[16, :] = True
        skel[:, 16] = True
        junc = ge.edge_junctions(skel)
        self.assertTrue(junc[16, 16])
        self.assertLessEqual(int(junc.sum()), 9)


class TestTerminationField(unittest.TestCase):
    def test_field_is_peaked_where_the_edge_ends(self):
        # a single tapered tube: the |grad| ridge follows it and dies at the
        # ends, which is exactly the "fault tip seen only in gravity" case
        from gems.synthesize import _fault_edge_field
        f = _fault_edge_field((96, 96), [((20, 20), (70, 70))], sigma=2.2)
        out = ge.edge_termination_field(f, sigma=0.0, support_px=8.0)
        tf = out["term_field"]
        self.assertGreater(int(out["terminations"].sum()), 0)
        # the maximum of the termination field sits ON a detected termination
        arg = np.unravel_index(int(np.argmax(tf)), tf.shape)
        self.assertTrue(out["terminations"][arg])
        # mid-segment of the tube carries no termination weight
        self.assertLess(float(tf[45, 45]), 0.05 * float(tf.max()))
        # the detected ends are near (but not exactly at) the geometric tips:
        # the taper means the density contrast dies out before the tip line
        rows, cols = np.nonzero(out["terminations"])
        d0 = float(np.min(np.hypot(rows - 20, cols - 20)))
        d1 = float(np.min(np.hypot(rows - 70, cols - 70)))
        self.assertLess(d0, 25.0)
        self.assertLess(d1, 25.0)
        self.assertLessEqual(float(tf.max()), 1.0)
        self.assertGreaterEqual(float(tf.min()), 0.0)

    def test_full_height_step_terminates_only_at_the_image_border(self):
        out = ge.edge_termination_field(step_field(), sigma=0.0)
        term = out["terminations"]
        self.assertLessEqual(int(term.sum()), 2)
        if term.any():
            # Zhang-Suen skeletonisation trims the two end rows of a 2-px-wide
            # bar, so the ends land within 2 px of the image border
            rows, cols = np.nonzero(term)
            self.assertTrue(np.all((rows <= 2) | (rows >= term.shape[0] - 3)))
            self.assertTrue(np.all(np.abs(cols - 32) <= 1))


class TestCapMargin(unittest.TestCase):
    def test_cap_mask_requires_conjunction(self):
        cond = np.zeros((32, 32))
        cond[10:20, 10:20] = 1.0
        mag = np.zeros((32, 32))
        mag[12:18, 12:18] = -1.0     # magnetic low only inside the cap
        cap = ge.cap_mask_from_anomalies(conductance=cond, magnetic=mag,
                                         cond_thresh=0.5, mag_thresh=-0.5)
        self.assertTrue(cap[15, 15])
        self.assertFalse(cap[10, 10])   # high conductance but not a magnetic low
        m = ge.cap_margin(cap, support_px=4.0)
        self.assertGreater(float(m[12, 15]), float(m[15, 15]))


class TestSyntheticGeophysics(unittest.TestCase):
    """The forward model must put the gravity ridge on the TRUE fault network."""

    def test_blind_traces_are_separated_from_the_catalogue(self):
        r = make_region(shape=(160, 160), seed=21)
        from scipy import ndimage
        if r["blind_traces"].any():
            d = ndimage.distance_transform_edt(~r["traces"])
            self.assertGreaterEqual(float(d[r["blind_traces"]].min()), 20.0)

    def test_gravity_termination_field_localises_blind_faults(self):
        r = make_region(shape=(160, 160), seed=21)
        out = ge.edge_termination_field(r["f_grav"])
        tf = out["term_field"]
        self.assertGreater(float(tf[r["blind_traces"]].mean()),
                           3.0 * float(tf.mean()))
