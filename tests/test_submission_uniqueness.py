"""Test exact artifact-identity gates separately from rounded-score warnings.

Published GEMSDOE1 and 5GEMSDOE pages display matching truncated artifact
metadata, while the original uploads are unavailable. Rounded score ties alone
must never be treated as proof of identical predictions.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.check_submission_uniqueness import check, parse_ledger  # noqa: E402

import numpy as np  # noqa: E402


def _write_fake_submission(directory: Path, stem: str, arr: np.ndarray) -> Path:
    """Write a minimal .tif + NOTE + MANIFEST triple (no rasterio needed)."""
    import struct
    import zlib

    raw = arr.astype(np.float32).tobytes()
    path = directory / f"{stem}.tif"
    path.write_bytes(b"FAKETIF" + raw)
    (directory / f"{stem}.NOTE.txt").write_text(f"note for {stem}\n")
    (directory / f"{stem}.MANIFEST.json").write_text(json.dumps({
        "file": path.name,
        "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
        "prediction_sha256": __import__("hashlib").sha256(raw).hexdigest(),
    }))
    return path


LEDGER = """# Results ledger (test fixture)

| # | Entry | Reported score | Description | Artifact id | Unique? | Evidence |
|---|-------|----------------|-------------|-------------|---------|----------|
| 1 | GEMSDOE1 | 0.1563 | ens12 skeleton | `7f00890a` | reference | site |
| 2 | 6GEMSDOE | 0.0286 | divergent probe | - | yes | thread |
| 3 | GEMSDOE3 | 0.1193 | pindrop nodes | f347b70daa | yes | thread |
| 4 | 5GEMSDOE | 0.1563 | same payload as #1 | `7f00890a` | **NO** | site pins identical hash |
| 5 | 12GEMSDOE | 0.1294 | dem10 scarp | 0c9199f14e62 | yes | thread |
"""


class TestLedgerParser(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.ledger = Path(self.tmp) / "ledger.md"
        self.ledger.write_text(LEDGER)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_parses_rows(self):
        rows = parse_ledger(self.ledger)
        self.assertEqual([r["n"] for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual(rows[0]["score"], "0.1563")
        self.assertEqual(rows[3]["artifact"], "`7f00890a`")

    def test_rounded_score_and_truncated_artifact_are_warning_only(self):
        problems, warnings = check(Path(self.tmp), self.ledger,
                                   Path(self.tmp) / "nope.js", strict_ledger=True)
        self.assertEqual(problems, [])
        joined = "\n".join(warnings)
        self.assertIn("0.1563", joined)
        self.assertIn("before claiming identity", joined)
        self.assertIn("cannot establish artifact identity", joined)

    def test_clean_ledger_passes(self):
        clean = self.ledger.read_text().replace(
            "| 4 | 5GEMSDOE | 0.1563 | same payload as #1 | `7f00890a` | **NO** | site pins identical hash |",
            "| 4 | 5GEMSDOE | 0.0712 | distinct run | `aa11bb22` | yes | site |")
        self.ledger.write_text(clean)
        problems, _w = check(Path(self.tmp), self.ledger,
                             Path(self.tmp) / "nope.js", strict_ledger=True)
        self.assertEqual(problems, [])


class TestFileLevelGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.arr = np.arange(64, dtype=np.float32).reshape(8, 8) / 64.0

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_byte_identical_submissions_are_caught(self):
        _write_fake_submission(self.tmp, "GEMS_a_20260928T000000Z_11111111", self.arr)
        _write_fake_submission(self.tmp, "GEMS_b_20260928T000001Z_22222222", self.arr)
        problems, _w = check(self.tmp, self.tmp / "nope.md", self.tmp / "nope.js")
        self.assertTrue(any(p.startswith("F1:") for p in problems), problems)

    def test_same_prediction_hash_is_caught_even_if_tiff_bytes_differ(self):
        _write_fake_submission(self.tmp, "GEMS_a_20260928T000000Z_11111111", self.arr)
        second = _write_fake_submission(self.tmp, "GEMS_b_20260928T000001Z_22222222", self.arr)
        with second.open("ab") as f:
            f.write(b"different-container-metadata")
        manifest_path = self.tmp / f"{second.stem}.MANIFEST.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["sha256"] = __import__("hashlib").sha256(second.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        problems, _warnings = check(self.tmp, self.tmp / "nope.md", self.tmp / "nope.js")
        self.assertTrue(any(p.startswith("F8:") for p in problems), problems)
        self.assertFalse(any(p.startswith("F1:") for p in problems), problems)

    def test_distinct_submissions_pass(self):
        _write_fake_submission(self.tmp, "GEMS_a_20260928T000000Z_11111111", self.arr)
        _write_fake_submission(self.tmp, "GEMS_b_20260928T000001Z_22222222",
                               self.arr[::-1, :].copy())
        problems, _w = check(self.tmp, self.tmp / "nope.md", self.tmp / "nope.js")
        self.assertEqual(problems, [])

    def test_missing_note_or_manifest_is_caught(self):
        p = _write_fake_submission(self.tmp, "GEMS_a_20260928T000000Z_11111111", self.arr)
        (self.tmp / (p.stem + ".NOTE.txt")).unlink()
        problems, _w = check(self.tmp, self.tmp / "nope.md", self.tmp / "nope.js")
        self.assertTrue(any(".NOTE.txt" in x for x in problems), problems)

    def test_tampered_manifest_is_caught(self):
        p = _write_fake_submission(self.tmp, "GEMS_a_20260928T000000Z_11111111", self.arr)
        man = self.tmp / (p.stem + ".MANIFEST.json")
        man.write_text(json.dumps({"sha256": "0" * 64}))
        problems, _w = check(self.tmp, self.tmp / "nope.md", self.tmp / "nope.js")
        self.assertTrue(any(x.startswith("F4:") for x in problems), problems)

    def _pred_hash(self, stem: str) -> str:
        man = json.loads((self.tmp / f"{stem}.MANIFEST.json").read_text())
        return man["prediction_sha256"]

    def _write_payload(self, source_tif: str, pred_hash: str) -> Path:
        js = self.tmp / "payload.js"
        js.write_text(
            "/* Generated by scripts/build_site_payload.py — do not edit by hand. */\n"
            f"/* Source: {source_tif}  kind=real  pixels_sha256={pred_hash} */\n"
            'window.GEMS_PAYLOAD_B64 = "eJwLyk8uyczPS1UIzy/KSQEAGQYF9A==";\n')
        return js

    def test_payload_matching_its_declared_source_passes(self):
        # README step-5 end state: the payload is built from the artifact whose
        # manifest sits in submissions/ — that match is not a duplicate.
        p = _write_fake_submission(self.tmp, "GEMS_a_20260928T000000Z_11111111", self.arr)
        js = self._write_payload(p.name, self._pred_hash(p.stem))
        problems, _w = check(self.tmp, self.tmp / "nope.md", js)
        self.assertEqual(problems, [], problems)

    def test_payload_pinning_another_artifact_fires(self):
        # the historical "site pins identical hash" failure mode: the payload
        # carries the pixels of a built artifact it does not declare as source
        a = _write_fake_submission(self.tmp, "GEMS_a_20260928T000000Z_11111111", self.arr)
        _write_fake_submission(self.tmp, "GEMS_b_20260928T000001Z_22222222",
                               self.arr[::-1, :].copy())
        js = self._write_payload(a.name, self._pred_hash("GEMS_b_20260928T000001Z_22222222"))
        problems, _w = check(self.tmp, self.tmp / "nope.md", js)
        self.assertTrue(any(x.startswith("F7:") for x in problems), problems)


class TestScriptEntryPoint(unittest.TestCase):
    def test_script_runs_on_the_real_repo(self):
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "check_submission_uniqueness.py")],
                           capture_output=True, text=True, cwd=str(REPO), timeout=300)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("uniqueness audit: PASS", r.stdout)
