"""Regression tests for the site's submission-file path.

The 2026-09-29 failure: docs/js/site.js assigned `tifBytesNan` without
declaring it.  Inside the strict-mode IIFE that is a ReferenceError, `.catch()`
swallowed it, every download button stayed disabled and the published site had
**no submission file to download** — while the Python test suite stayed green
because nothing here ran the site's JavaScript.

These tests close that hole from both ends:

  * the in-browser route   — scripts/check_site_build.mjs drives the real
                             payload.js / tif_writer.js / site.js under a DOM
                             shim and must reach READY and hand over a
                             format-valid GeoTIFF;
  * the no-JavaScript route — docs/downloads/*.tif must exist, match the
                             shipped payload pixel-for-pixel, and be linked
                             from docs/index.html.

Both routes are additionally checked against the repository's own format gate
(gems.raster.check_submission), so a file that would be rejected with
"Predicted values must be in range [0, 1]" cannot pass these tests.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

PAYLOAD_JS = REPO / "docs" / "js" / "payload.js"
INDEX_HTML = REPO / "docs" / "index.html"
DOWNLOADS = REPO / "docs" / "downloads"


def decode_payload_field() -> tuple[np.ndarray, dict]:
    """Decode docs/js/payload.js exactly as the browser does."""
    src = PAYLOAD_JS.read_text()
    m = re.search(r'GEMS_PAYLOAD_B64\s*=\s*"([^"]+)"', src)
    assert m, "docs/js/payload.js does not define GEMS_PAYLOAD_B64"
    blob = json.loads(zlib.decompress(base64.b64decode(m.group(1))).decode("utf-8"))
    rle = blob["rle"]
    values = np.frombuffer(base64.b64decode(rle["values_b64"]), dtype="<f4")
    lengths = np.frombuffer(base64.b64decode(rle["lengths_b64"]), dtype="<i8")
    field = np.ascontiguousarray(
        np.repeat(values, lengths).reshape(int(blob["rows"]), int(blob["cols"])),
        dtype=np.float32)
    return field, blob


def expected_template_meta(blob: dict) -> dict:
    return {
        "rows": int(blob["rows"]),
        "cols": int(blob["cols"]),
        "epsg": int(blob["epsg"]),
        "res": float(blob["res"]),
        "transform": list(blob["transform"]),
        "valid_mask_path": "data/processed/valid_mask.npy",
    }


class SitePayloadTest(unittest.TestCase):
    """The payload is the single source of truth both routes are judged against."""

    @classmethod
    def setUpClass(cls):
        cls.field, cls.blob = decode_payload_field()

    def test_payload_hash_matches_shipped_field(self):
        got = hashlib.sha256(self.field.astype("<f4").tobytes()).hexdigest()
        self.assertEqual(got, self.blob["pixels_sha256"],
                         "docs/js/payload.js's pinned pixels_sha256 is not the hash of "
                         "the field it actually ships — the site would refuse to build")

    def test_payload_values_are_submittable(self):
        self.assertTrue(np.isfinite(self.field).all(), "payload contains NaN/Inf")
        self.assertGreaterEqual(float(self.field.min()), 0.0)
        self.assertLessEqual(float(self.field.max()), 1.0)

    def test_payload_grid_matches_repo_grid_constants(self):
        from gems import raster as gr
        self.assertEqual(self.field.shape, gr.PINNED_SHAPE)
        self.assertEqual(int(self.blob["epsg"]), gr.PINNED_EPSG)
        self.assertAlmostEqual(float(self.blob["res"]), gr.PINNED_RES_M)


@unittest.skipIf(shutil.which("node") is None, "node not available")
class HeadlessSiteBuildTest(unittest.TestCase):
    """Drive docs/js/site.js the way a browser does and judge what it produces."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out_tif = Path(cls.tmp.name) / "site_build.tif"
        proc = subprocess.run(
            ["node", str(REPO / "scripts" / "check_site_build.mjs"),
             "--json", "--out", str(cls.out_tif)],
            capture_output=True, text=True, cwd=str(REPO), timeout=600)
        cls.stdout, cls.stderr, cls.returncode = proc.stdout, proc.stderr, proc.returncode
        try:
            cls.report = json.loads(proc.stdout[proc.stdout.index("{"):])
        except (ValueError, json.JSONDecodeError):
            cls.report = None

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_harness_step_passes(self):
        self.assertIsNotNone(
            self.report,
            f"could not parse the harness report.\nstdout:\n{self.stdout}\nstderr:\n{self.stderr}")
        failed = [s for s in self.report["steps"] if not s["ok"]]
        self.assertEqual(
            [], failed,
            "the in-browser builder failed: "
            + "; ".join(f"{s['name']} -> {s['detail']}" for s in failed)
            + "\n(2026-09-29 regression: an undeclared variable left every download "
              "button disabled and the site with no submission file)")
        self.assertEqual(self.report["verdict"], "PASS")
        self.assertEqual(self.returncode, 0)

    def test_harness_reports_ready_and_offers_the_download(self):
        names = [s["name"] for s in self.report["steps"]]
        self.assertTrue(any("reaches READY and enables all three buttons" in n for n in names),
                        names)
        self.assertTrue(any("pressing 'Build submission.tif' produces a download" in n
                            for n in names), names)

    def test_both_writer_paths_are_exercised(self):
        """Current browsers deflate the build; older ones must still get a file."""
        names = [s["name"] for s in self.report["steps"]]
        self.assertTrue(any(n.startswith("[deflate]") for n in names), names)
        self.assertTrue(any(n.startswith("[no-compression]") for n in names), names)
        self.assertTrue(any("deflate-compressed (Compression=8)" in n for n in names), names)
        self.assertTrue(any("fallback still produces a usable file" in n for n in names), names)

    def test_generated_filename_and_note_are_unique_to_this_build(self):
        fname, note = self.report["filename"], self.report["note"]
        self.assertRegex(fname, r"^gems-submission-\d{8}T\d{6}Z-[0-9a-f]{8}\.tif$")
        self.assertIn(self.report["file_sha256"][:8], fname)
        # the Note must identify the build, never be a constant
        self.assertIn("sha8=" + self.report["file_sha256"][:8], note)
        self.assertIn("pixels sha8=" + self.report["pixels_sha256"][:8], note)
        self.assertIn("px > 0", note)

    def test_built_file_passes_the_repository_format_gate(self):
        import rasterio
        from gems import raster as gr

        field, blob = decode_payload_field()
        self.assertTrue(self.out_tif.exists(), "the harness wrote no GeoTIFF")
        with rasterio.open(self.out_tif) as ds:
            arr = ds.read(1)
            self.assertEqual(arr.shape, field.shape)
            self.assertEqual(ds.count, 1)
            self.assertEqual(ds.dtypes[0], "float32")
            self.assertEqual(ds.crs.to_string(), f"EPSG:{int(blob['epsg'])}")
            for a, b in zip(list(ds.transform)[:6], blob["transform"]):
                self.assertAlmostEqual(a, b, places=9)
        self.assertTrue(np.isfinite(arr).all())
        self.assertGreaterEqual(float(arr.min()), 0.0)
        self.assertLessEqual(float(arr.max()), 1.0)
        # bit-for-bit identical predictions to the shipped payload
        self.assertEqual(arr.astype("<f4").tobytes(), field.astype("<f4").tobytes(),
                         "the browser build does not carry the shipped payload's pixels")
        report = gr.check_submission(self.out_tif, expected_template_meta(blob),
                                     allow_zero_outside=True)
        self.assertTrue(report.get("ok"), report.get("problems"))


class DirectDownloadTest(unittest.TestCase):
    """The JavaScript-free route: a real file in docs/downloads/ that is linked."""

    @classmethod
    def setUpClass(cls):
        cls.field, cls.blob = decode_payload_field()
        cls.manifest_path = DOWNLOADS / "manifest.json"
        cls.manifest = (json.loads(cls.manifest_path.read_text())
                        if cls.manifest_path.exists() else None)

    def test_manifest_and_tif_exist(self):
        self.assertIsNotNone(self.manifest, "docs/downloads/manifest.json is missing — "
                                            "run scripts/build_site_download.py")
        self.assertTrue((DOWNLOADS / self.manifest["file"]).exists(),
                        f"{self.manifest['file']} is listed but not present")

    def test_direct_download_carries_the_shipped_pixels(self):
        with (DOWNLOADS / self.manifest["file"]).open("rb") as fh:
            actual = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(actual, self.manifest["sha256"], "file on disk != manifest hash")
        self.assertEqual(self.manifest["prediction_sha256"], self.blob["pixels_sha256"])

        import rasterio
        with rasterio.open(DOWNLOADS / self.manifest["file"]) as ds:
            arr = ds.read(1)
            crs = ds.crs.to_string()
            transform = list(ds.transform)[:6]
        self.assertTrue(np.isfinite(arr).all())
        self.assertGreaterEqual(float(arr.min()), 0.0)
        self.assertLessEqual(float(arr.max()), 1.0)
        self.assertEqual(arr.astype("<f4").tobytes(), self.field.astype("<f4").tobytes(),
                         "the direct download does not carry the shipped payload's pixels")
        self.assertEqual(crs, f"EPSG:{int(self.blob['epsg'])}")
        for a, b in zip(transform, self.blob["transform"]):
            self.assertAlmostEqual(a, b, places=9)

    def test_direct_download_passes_the_repository_format_gate(self):
        from gems import raster as gr
        report = gr.check_submission(DOWNLOADS / self.manifest["file"],
                                     expected_template_meta(self.blob),
                                     allow_zero_outside=True)
        self.assertTrue(report.get("ok"), report.get("problems"))

    def test_index_links_the_direct_download(self):
        html = INDEX_HTML.read_text()
        href = f'downloads/{self.manifest["file"]}'
        self.assertIn(href, html,
                      "docs/index.html does not link the directly downloadable file — "
                      "a visitor with JavaScript disabled would have nothing to submit")
        self.assertIn("DIRECT-DOWNLOAD:BEGIN", html)
        self.assertIn("DIRECT-DOWNLOAD:END", html)

    def test_builder_check_mode_agrees(self):
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "build_site_download.py"), "--check"],
            capture_output=True, text=True, cwd=str(REPO), timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class SiteClaimsTest(unittest.TestCase):
    """Numbers the site shows must come from the shipped payload, not memory."""

    def test_no_stale_payload_hash_is_advertised(self):
        html = INDEX_HTML.read_text()
        _, blob = decode_payload_field()
        shipped = str(blob["pixels_sha256"])[:8]
        for stale in re.findall(r"pixels_sha256 ([0-9a-f]{8})", html):
            self.assertEqual(stale, shipped,
                             f"docs/index.html advertises pixels_sha256 {stale}… but the "
                             f"shipped payload is {shipped}…")

    def test_hero_offers_a_file_before_anything_else(self):
        """The hero card must offer the file first — before any tooling talk.

        Scoped to the hero card, because the navigation bar (which every page
        carries) links to how-to-submit.html far earlier in the document.
        """
        html = INDEX_HTML.read_text()
        hero_start = html.index('class="card hero"')
        hero = html[hero_start:html.index("</main>", hero_start)]
        direct = hero.index("DIRECT-DOWNLOAD:BEGIN")
        self.assertIn("Download the finished submission file", hero)
        self.assertLess(direct, hero.index("Build submission.tif"),
                        "the direct download must precede the JS builder")
        self.assertLess(direct, hero.index("how-to-submit.html"))
        self.assertLess(direct, hero.index("Paste the Note"),
                        "the file offer must come before the note/upload steps")

    def test_empty_nan_footprint_is_not_advertised_as_the_default(self):
        html = INDEX_HTML.read_text()
        hero = html[:html.index("Why the team kept scoring")]
        self.assertNotIn("GDAL_NODATA=nan", hero,
                         "the default download carries no GDAL_NODATA tag")


if __name__ == "__main__":
    unittest.main()
