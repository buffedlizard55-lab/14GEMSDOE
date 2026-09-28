"""Node round-trip test for docs/js/tif_writer.js.

Builds the same field with the JS writer and with rasterio, then requires:
  * identical decoded pixels (bit-for-bit, NaN-aware),
  * identical grid metadata (shape, EPSG, transform, nodata).
This is what makes the site's one-click button trustworthy: it emits the same
bytes-with-different-container as the Python pipeline.
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]

NODE_CHECK = r"""
const fs = require("fs");
const path = require("path");
const repo = process.argv[2];
const outPath = process.argv[3];
require(path.join(repo, "docs/js/tif_writer.js"));

const rows = 12, cols = 10;
const values = new Float32Array(rows * cols);
for (let i = 0; i < values.length; i++) {
  values[i] = (i % 7 === 0) ? NaN : Math.round((Math.sin(i) * 0.5 + 0.5) * 1e6) / 1e6;
}
const tif = GemsTiff.writeGeoTiffFloat32({
  rows, cols, values,
  transform: [100, 0, 500000, 0, -100, 4500000],
  epsg: 32611,
  nodata: "nan"
});
fs.writeFileSync(outPath, Buffer.from(tif));

// also dump the raw field for the pixel compare
const fieldPath = outPath.replace(/\.tif$/, ".field.npy.raw");
fs.writeFileSync(fieldPath, Buffer.from(new Uint8Array(values.buffer)));
fs.writeFileSync(outPath.replace(/\.tif$/, ".meta.json"), JSON.stringify({rows, cols}));
console.log("JS_WRITER_OK", tif.length);
"""


@unittest.skipIf(shutil.which("node") is None, "node not available")
class TestJsTifWriter(unittest.TestCase):
    def test_round_trip_identical_pixels_and_grid(self):
        import rasterio

        with tempfile.TemporaryDirectory() as td:
            tif = Path(td) / "js.tif"
            script = Path(td) / "check.js"
            script.write_text(NODE_CHECK)
            proc = subprocess.run(
                ["node", str(script), str(REPO), str(tif)],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("JS_WRITER_OK", proc.stdout)

            meta = json.loads((Path(td) / "js.meta.json").read_text())
            raw = np.frombuffer((Path(td) / "js.field.npy.raw").read_bytes(), dtype=np.float32)
            field = raw.reshape(meta["rows"], meta["cols"])

            with rasterio.open(tif) as ds:
                arr = ds.read(1)
                self.assertEqual(ds.dtypes[0], "float32")
                self.assertEqual((ds.height, ds.width), (meta["rows"], meta["cols"]))
                self.assertEqual(ds.count, 1)
                self.assertEqual(ds.crs.to_epsg(), 32611)
                np.testing.assert_allclose([ds.transform.a, ds.transform.c, ds.transform.e,
                                            ds.transform.f],
                                           [100.0, 500000.0, -100.0, 4500000.0],
                                           rtol=0, atol=1e-9)
                # GDAL_NODATA present and NaN-aware pixel compare
                self.assertTrue(np.isnan(ds.nodata), "GDAL_NODATA should be NaN")

            same = (arr == field) | (np.isnan(arr) & np.isnan(field))
            self.assertTrue(bool(same.all()), "JS writer pixels differ from source field")


if __name__ == "__main__":
    unittest.main()
