"""Pin the API contract between scripts/train_real_full.py and the gate.

Queue item 5 (research/limitations_and_next.md): ``train_real_full.py`` was
left calling the pre-rewrite ``validate_real`` API (``geo_channels``,
``context_channels``, ``ARM_EXTRA``, ``stack_matrix``, ``fit_model``,
``predict_full``, ``dilate_valid``) and crashed on first use after the round-5
rewrite.  It has been rewritten against the current API; this test is the
regression guard so that any future gate-side rename breaks *here*, not
silently in the deployment path.

Checks (no raster data required):
  * every ``vr.<name>`` the deployment script references exists on the gate
    module; every ``df.<name>`` exists on gems.dti_fast;
  * the learner helpers it imports from scripts/train_hide_recover exist;
  * the CLI rejects unknown arm names before touching any data files.
"""

import ast
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))   # gate + learner are plain modules

SCRIPT = REPO / "scripts" / "train_real_full.py"


def _attr_uses(tree: ast.AST, root_name: str) -> set[str]:
    """Attribute names accessed as ``root_name.<attr>`` anywhere in the tree."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == root_name):
            out.add(node.attr)
    return out


class TestTrainRealFullApiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = SCRIPT.read_text()
        cls.tree = ast.parse(cls.src)

    def test_script_parses(self):
        ast.parse(self.src)  # syntax guard

    def test_vr_attrs_exist_on_gate_module(self):
        import validate_real  # noqa: F401  (importable: deps present)
        mod = sys.modules["validate_real"]
        missing = sorted(a for a in _attr_uses(self.tree, "vr")
                         if not hasattr(mod, a))
        self.assertEqual(missing, [],
                         f"train_real_full.py references stale validate_real "
                         f"API: {missing}")

    def test_df_attrs_exist_on_dti_fast(self):
        from gems import dti_fast
        missing = sorted(a for a in _attr_uses(self.tree, "df")
                         if not hasattr(dti_fast, a))
        self.assertEqual(missing, [],
                         f"train_real_full.py references stale dti_fast "
                         f"API: {missing}")

    def test_learner_helpers_exist(self):
        m = re.search(r"from train_hide_recover import ([^\n]+)", self.src)
        self.assertIsNotNone(m, "learner helpers must come from train_hide_recover")
        self.assertIn("logistic_fit", m.group(1))
        self.assertIn("standardize_fit", m.group(1))
        from train_hide_recover import logistic_fit, standardize_fit  # noqa: F401
        self.assertTrue(callable(logistic_fit) and callable(standardize_fit))

    def test_stale_api_is_gone(self):
        for stale in ("geo_channels", "context_channels", "sample_training_pixels",
                      "ARM_EXTRA", "BASE_NAMES", "stack_matrix", "fit_model",
                      "dilate_valid"):
            self.assertNotIn(f"vr.{stale}", self.src,
                             f"stale gate API call vr.{stale} still present")

    def test_cli_rejects_unknown_arm_without_touching_data(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--arms", "not_an_arm"],
            capture_output=True, text=True, timeout=120, cwd=str(REPO))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unknown arm", proc.stderr)

    def test_hide_and_recover_views_are_documented(self):
        # The deployment view must be the FULL catalogue; the training view must
        # hide the positive components.  Pin the two expressions.
        self.assertIn("labels & ~hide", self.src)
        self.assertIn("vr.build_geom_channels(labels)", self.src)


if __name__ == "__main__":
    unittest.main()
