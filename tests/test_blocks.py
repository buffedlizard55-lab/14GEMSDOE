"""Spatial block-split tests."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems.blocks import assign_folds, holdout_masks, make_blocks


class TestBlocks(unittest.TestCase):
    def test_block_ids_cover_grid(self):
        b = make_blocks((100, 90), 32)
        self.assertEqual(b.shape, (100, 90))
        self.assertEqual(int(b.min()), 0)
        # block-constant
        self.assertEqual(b[0, 0], b[0, 31])
        self.assertNotEqual(b[0, 0], b[0, 32])

    def test_folds_partition_traces(self):
        rng = np.random.default_rng(0)
        t = rng.random((96, 96)) < 0.01
        fm = assign_folds((96, 96), 24, 4, seed=1)
        for k in range(4):
            train, test = holdout_masks(t, fm, k, policy="block")
            self.assertEqual(int((train & test).sum()), 0)
            self.assertEqual(int((train | test).sum()), int(t.sum()))
        # every trace pixel lands in exactly one fold's test set
        seen = np.zeros_like(t)
        for k in range(4):
            _tr, te = holdout_masks(t, fm, k, policy="block")
            seen |= te
        self.assertTrue((seen == t).all())

    def test_buffer_purges_border_traces(self):
        t = np.zeros((48, 48), dtype=bool)
        t[20, 10:40] = True  # straddles the block border at col 24
        fm = assign_folds((48, 48), 24, 2, seed=2)
        train_b, test_b = holdout_masks(t, fm, 0, policy="block")
        train_p, test_p = holdout_masks(t, fm, 0, policy="buffer", buffer_px=4)
        self.assertGreaterEqual(int(test_p.sum()), int(test_b.sum()))
        self.assertEqual(int((train_p & test_p).sum()), 0)


if __name__ == "__main__":
    unittest.main()
