"""Leaderboard feed parser tests (HTML and markdown forms)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.refresh_leaderboard import parse_standings

HTML_FIXTURE = """
<html><body><table>
<tr><th>#</th><th>Team</th><th>Score</th></tr>
<tr><td>#1</td><td><a href="https://www.drivendata.org/users/DARD/">DARD</a><br>10h ago</td>
<td>0.3168</td><td></td></tr>
<tr><td>#2</td><td><a href="https://www.drivendata.org/users/alexoktaba/">alexoktaba</a><br>3d</td>
<td>0.2993</td><td></td></tr>
<tr><td>#27</td><td><a href="https://www.drivendata.org/users/SDCF9/">SDCF9</a><br>1d</td>
<td>0.1563</td><td></td></tr>
</table></body></html>
"""

MD_FIXTURE = """
| #1 | [DARD](https://www.drivendata.org/users/DARD/ "View DARD's profile") | 0.3168 |  |
| #2 | [alexoktaba](https://www.drivendata.org/users/alexoktaba/) | 0.2993 |  |
| #27 | [SDCF9](https://www.drivendata.org/users/SDCF9/) | 0.1563 |  |
"""


class TestParser(unittest.TestCase):
    def test_html(self):
        rows = parse_standings(HTML_FIXTURE)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["users"], ["DARD"])
        self.assertAlmostEqual(rows[0]["score"], 0.3168)
        self.assertEqual(rows[2]["users"], ["SDCF9"])
        self.assertAlmostEqual(rows[2]["score"], 0.1563)

    def test_markdown(self):
        rows = parse_standings(MD_FIXTURE)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]["users"], ["alexoktaba"])
        self.assertAlmostEqual(rows[1]["score"], 0.2993)

    def test_empty(self):
        self.assertEqual(parse_standings("<html>nothing here</html>"), [])


if __name__ == "__main__":
    unittest.main()
