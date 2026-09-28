"""Guard the competition-data placement script.

The standing prompt demands official, verified sources and no hallucinated
links.  The Dropbox mirror URLs in scripts/download_competition_data.sh were
captured verbatim from the project thread (TEAM-REPORTED-OFFICIAL-MIRROR:
they are the data tab's own share links).  This test pins:

  * every mirror row parses and points at https dropbox.com with an rlkey;
  * the canonical target names are exactly the ones prepare_data.py expects;
  * the sandbox-failure path is handled (exit != 0 only AFTER the manual
    instructions print, never a crash).
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "download_competition_data.sh"

CANONICAL = ("sample_submission.tif", "training_labels.tif",
             "training_features.tif", "1m_DEM_links.pdf", "GEMS_96647_rules.pdf")


class TestMirrorList(unittest.TestCase):
    def rows(self):
        text = SCRIPT.read_text()
        block = re.search(r"MIRRORS=\(\n(.*?)\n\)", text, re.S).group(1)
        rows = []
        for line in block.strip().splitlines():
            line = line.strip().strip('"')
            name, url = line.split("|", 1)
            rows.append((name, url))
        return rows

    def test_all_mirrors_parse(self):
        rows = self.rows()
        self.assertEqual([r[0] for r in rows], list(CANONICAL))
        for name, url in rows:
            self.assertTrue(url.startswith("https://www.dropbox.com/"),
                            f"{name}: not an https dropbox URL")
            self.assertIn("rlkey=", url, f"{name}: missing rlkey (share link)")
            self.assertIn("dl=1", url, f"{name}: must force download (dl=1)")

    def test_prepare_data_expected_names_covered(self):
        prep = (REPO / "scripts" / "prepare_data.py").read_text()
        for expected in ("training_features.tif", "training_labels.tif",
                         "sample_submission.tif"):
            self.assertIn(expected, prep,
                          f"prepare_data.py does not reference {expected}")

    def test_script_runs_and_fails_cleanly_without_data(self):
        # In the sandbox the mirrors are TLS-blocked, so the script must print
        # the manual instructions and exit non-zero — not crash.
        p = subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True,
                           timeout=600, cwd=str(REPO))
        combined = p.stdout + p.stderr
        self.assertIn("place the files by hand", combined,
                      "manual fallback instructions must print")
        self.assertNotEqual(p.returncode, 0,
                            "without the data the script must not report success")


if __name__ == "__main__":
    unittest.main()
