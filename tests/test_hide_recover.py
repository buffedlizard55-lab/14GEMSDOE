"""Hide-and-recover protocol tests: the anti-leak invariant is the point."""

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gems import hide_recover as hr
from gems.synthesize import make_region


class TestHidePlan(unittest.TestCase):
    def setUp(self):
        self.region = make_region(shape=(128, 128), seed=3)
        self.traces = self.region["traces"]
        self.rng = np.random.default_rng(0)

    def test_whole_components_hidden(self):
        plan = hr.sample_hide_plan(self.traces, 0.35, self.rng)
        lab, n = hr.split_components(self.traces)
        self.assertGreater(n, 3)
        for cid in plan.hidden_ids:
            comp = lab == cid
            # every pixel of the component is hidden, or none is
            hidden_here = self._hidden_mask(plan)
            frac = (comp & hidden_here).sum() / comp.sum()
            self.assertIn(frac, (0.0, 1.0))

    def _hidden_mask(self, plan):
        _c, hidden = hr.apply_plan(self.traces, plan)
        return hidden

    def test_no_leak_invariant(self):
        for _ in range(5):
            plan = hr.sample_hide_plan(self.traces, 0.35, self.rng, buffer_px=2.0)
            context, hidden = hr.apply_plan(self.traces, plan)
            report = hr.assert_no_leak(context, hidden)
            self.assertEqual(report["leaks"], 0)
            # strictly: no hidden pixel within 1 px of the context
            self.assertGreater(report["n_hidden_px"], 0)
            self.assertGreater(report["n_context_px"], 0)

    def test_buffer_hides_neighbours_too(self):
        plan0 = hr.sample_hide_plan(self.traces, 0.2, self.rng, buffer_px=0.0)
        plan2 = hr.sample_hide_plan(self.traces, 0.2, np.random.default_rng(0), buffer_px=6.0)
        self.assertGreaterEqual(len(plan2.hidden_ids), len(plan0.hidden_ids))

    def test_context_distance_positive_on_hidden(self):
        # THE property the prompt demands: hidden traces are not readable as
        # "distance to a known fault = 0"
        from gems.dti import distance_to_truth
        plan = hr.sample_hide_plan(self.traces, 0.4, self.rng, buffer_px=3.0)
        context, hidden = hr.apply_plan(self.traces, plan)
        dist = distance_to_truth(context)
        self.assertTrue((dist[hidden] >= 1.0).all())

    def test_recover_score_prefers_correct_predictions(self):
        plan = hr.sample_hide_plan(self.traces, 0.35, self.rng, buffer_px=2.0)
        _c, hidden = hr.apply_plan(self.traces, plan)
        good = hr.recover_score(hidden.astype(np.float32), hidden)
        bad = hr.recover_score((~hidden).astype(np.float32) * 0.01, hidden)
        self.assertGreater(good["dti"], bad["dti"])
        self.assertAlmostEqual(good["dti"], 1.0, places=6)

    def test_fraction_bounds(self):
        with self.assertRaises(ValueError):
            hr.sample_hide_plan(self.traces, 0.0, self.rng)
        with self.assertRaises(ValueError):
            hr.sample_hide_plan(self.traces, 1.0, self.rng)


class TestTrainingRuns(unittest.TestCase):
    def test_short_training_learns_something(self):
        from scripts.train_hide_recover import train
        region = make_region(shape=(128, 128), seed=9)
        result = train(region, hide_fraction=0.35, epochs=3, seed=9,
                       n_pos_cap=3000, n_neg_cap=3000, verbose=False)
        self.assertEqual(result["pred_full"].shape, region["traces"].shape)
        self.assertTrue(np.isfinite(result["pred_full"]).all())
        # predictions on real trace pixels should beat the field average
        p = result["pred_full"]
        self.assertGreater(p[region["traces"]].mean(), p[~region["traces"]].mean())
        self.assertGreaterEqual(result["mean_recover_dti"], 0.0)
        self.assertLessEqual(result["mean_recover_dti"], 1.0)


if __name__ == "__main__":
    unittest.main()
