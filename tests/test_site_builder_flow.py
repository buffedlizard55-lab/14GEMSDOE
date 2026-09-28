"""Headless test of the site builder's critical path (docs/js/site.js logic).

Reproduces, under node, exactly what the browser does on "Build submission.tif":
decode payload → value gate (refuse anything outside [0,1]) → write the PRIMARY
finite build (0.0 outside, no GDAL_NODATA) → header self-check.  This is the
regression guard for FLAG #10 (the platform rejects NaN-nodata files), so the
default download can never silently regress to the rejected variant.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio

REPO = Path(__file__).resolve().parents[1]

NODE_FLOW = r"""
const fs = require("fs");
const path = require("path");
// works both as `node file.js repo out` (argv 2,3) and `node -e script repo out` (argv 1,2)
const repo = process.argv[process.argv.length - 2];
const outPath = process.argv[process.argv.length - 1];
require(path.join(repo, "docs/js/tif_writer.js"));
require(path.join(repo, "docs/js/payload.js"));
const json = JSON.parse(
  require("zlib").inflateSync(Buffer.from(globalThis.GEMS_PAYLOAD_B64, "base64")).toString("utf8"));
const valsDV = new DataView(new Uint8Array(Buffer.from(json.rle.values_b64, "base64")).buffer);
const lensDV = new DataView(new Uint8Array(Buffer.from(json.rle.lengths_b64, "base64")).buffer);
const field = new Float32Array(json.rows * json.cols);
let o = 0;
for (let r = 0; r < json.rle.n_runs; r++) {
  const v = valsDV.getFloat32(r * 4, true);
  const len = Number(lensDV.getBigInt64(r * 8, true));
  for (let k = 0; k < len; k++) field[o++] = v;
}
if (o !== field.length) throw new Error("field length mismatch");
// value gate (site.js)
let nBad = 0;
const finite = new Float32Array(field.length);
for (let i = 0; i < field.length; i++) {
  finite[i] = isNaN(field[i]) ? 0.0 : field[i];
  if (finite[i] < 0.0 || finite[i] > 1.0) nBad++;
}
if (nBad > 0) throw new Error(nBad + " values outside [0,1]");
const tif = GemsTiff.writeGeoTiffFloat32({
  rows: json.rows, cols: json.cols, values: finite,
  transform: json.transform, epsg: json.epsg, nodata: null
});
fs.writeFileSync(outPath, Buffer.from(tif));
const dv = new DataView(tif.buffer, tif.byteOffset, tif.byteLength);
if (dv.getUint16(0, true) !== 0x4949 || dv.getUint16(2, true) !== 42) throw new Error("not LE TIFF");
const ifdOff = dv.getUint32(4, true);
const nTags = dv.getUint16(ifdOff, true);
const seen = {};
for (let i = 0; i < nTags; i++) seen[dv.getUint16(ifdOff + 2 + i * 12, true)] = true;
[256, 257, 258, 273, 33550, 33922, 34735].forEach(function (t) {
  if (!seen[t]) throw new Error("missing TIFF tag " + t);
});
if (seen[42113]) throw new Error("primary build unexpectedly carries GDAL_NODATA");
console.log("FLOW_OK");
"""


@unittest.skipIf(shutil.which("node") is None, "node not available")
class TestSiteBuilderFlow(unittest.TestCase):
    def test_primary_build_is_finite_and_passes_range_check(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "primary.tif"
            p = subprocess.run(["node", "-e", NODE_FLOW, str(REPO), str(out)],
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(p.returncode, 0,
                             f"node flow failed:\n{p.stdout}\n{p.stderr}")
            self.assertIn("FLOW_OK", p.stdout)
            with rasterio.open(out) as ds:
                self.assertEqual(ds.dtypes[0], "float32")
                self.assertEqual(ds.crs.to_epsg(), 32611)
                self.assertIsNone(ds.nodata)          # no GDAL_NODATA on primary
                a = ds.read(1)
            self.assertTrue(np.isfinite(a).all(),
                            "primary build must contain no NaN anywhere")
            self.assertTrue(bool(np.all((a >= 0.0) & (a <= 1.0))),
                            "primary build must pass the platform range check")


if __name__ == "__main__":
    unittest.main()
