"""Submission format gate tests.

These reproduce, mechanically, the two real failure modes behind the team's
submission-form rejection ("Predicted values must be in range [0, 1]") and
prove the gate catches both before a file is ever uploaded.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from gems import raster as gr  # noqa: E402


def write_tif(path, arr, *, nodata=float("nan"), dtype="float32"):
    import rasterio
    from rasterio.transform import Affine
    arr = arr.astype(dtype)
    with rasterio.open(
        path, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1],
        count=1, dtype=dtype, crs="EPSG:32611",
        transform=Affine(100.0, 0, 500000.0, 0, -100.0, 4500000.0),
        nodata=nodata,
    ) as ds:
        ds.write(arr, 1)


class TestGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.tmeta = {
            "rows": 32, "cols": 32, "epsg": 32611, "res": 100.0,
            "transform": [100.0, 0.0, 500000.0, 0.0, -100.0, 4500000.0],
        }
        self.valid = np.ones((32, 32), dtype=bool)
        self.valid[0, 0] = False
        self.valid_path = self.dir / "valid_mask.npy"
        np.save(self.valid_path, self.valid)

    def tearDown(self):
        self.tmp.cleanup()

    def _tm(self):
        t = dict(self.tmeta)
        t["valid_mask_path"] = str(self.valid_path)
        return t

    def test_good_file_passes(self):
        arr = np.full((32, 32), 0.5, dtype=np.float32)
        arr[~self.valid] = np.nan
        p = self.dir / "good.tif"
        write_tif(p, arr)
        rep = gr.check_submission(p, self._tm())
        self.assertTrue(rep["ok"])

    def test_nan_inside_valid_rejected(self):
        # THE observed failure: NaN inside the scored region
        arr = np.full((32, 32), 0.5, dtype=np.float32)
        arr[5, 5] = np.nan          # inside the valid footprint
        arr[~self.valid] = np.nan   # legal outside
        p = self.dir / "nan_inside.tif"
        write_tif(p, arr)
        with self.assertRaises(gr.SubmissionValidationError) as cm:
            gr.check_submission(p, self._tm())
        self.assertIn("range [0, 1]", str(cm.exception))

    def test_values_above_one_rejected(self):
        arr = np.full((32, 32), 1.7, dtype=np.float32)  # logits-like output
        arr[~self.valid] = np.nan
        p = self.dir / "logits.tif"
        write_tif(p, arr)
        with self.assertRaises(gr.SubmissionValidationError) as cm:
            gr.check_submission(p, self._tm())
        self.assertIn("outside [0, 1]", str(cm.exception))

    def test_negative_values_rejected(self):
        arr = np.full((32, 32), -0.2, dtype=np.float32)
        p = self.dir / "neg.tif"
        write_tif(p, arr)
        with self.assertRaises(gr.SubmissionValidationError):
            gr.check_submission(p, self._tm())

    def test_float64_rejected(self):
        arr = np.full((32, 32), 0.5, dtype=np.float64)
        p = self.dir / "f64.tif"
        write_tif(p, arr, dtype="float64")
        with self.assertRaises(gr.SubmissionValidationError) as cm:
            gr.check_submission(p, self._tm())
        self.assertIn("float32", str(cm.exception))

    def test_wrong_shape_rejected(self):
        arr = np.full((16, 16), 0.5, dtype=np.float32)
        p = self.dir / "small.tif"
        write_tif(p, arr)
        with self.assertRaises(gr.SubmissionValidationError):
            gr.check_submission(p, self._tm())

    def test_zero_outside_variant_accepted_only_when_allowed(self):
        arr = np.full((32, 32), 0.5, dtype=np.float32)
        p = self.dir / "zero_out.tif"
        write_tif(p, arr, nodata=None)
        gr.check_submission(p, self._tm(), allow_zero_outside=True)
        gr.check_submission(p, self._tm(), allow_zero_outside=False)  # no NaN at all: fine


class TestBuildSubmissionCLI(unittest.TestCase):
    """End-to-end: pred.npy -> validated submission with unique name + note."""

    def test_build_and_validate(self):
        with tempfile.TemporaryDirectory() as td:
            wdir = Path(td)
            (wdir / "data" / "processed").mkdir(parents=True)
            (wdir / "data" / "demo").mkdir(parents=True)
            (wdir / "artifacts").mkdir()
            (wdir / "scripts").symlink_to(REPO / "scripts")
            (wdir / "gems").symlink_to(REPO / "gems")

            # synthetic template + grid
            valid = np.ones((48, 48), dtype=bool)
            valid[:4, :4] = False
            np.save(wdir / "data" / "processed" / "valid_mask.npy", valid)
            (wdir / "data" / "processed" / "grid.json").write_text(json.dumps({
                "rows": 48, "cols": 48, "epsg": 32611, "res": 100.0,
                "transform": [100.0, 0.0, 500000.0, 0.0, -100.0, 4500000.0],
                "source": "test",
            }))
            arr_t = np.where(valid, np.float32(0.0), np.float32("nan"))
            write_tif(wdir / "data" / "demo" / "sample_submission.tif", arr_t)

            # a nasty prediction: out-of-range values AND NaN inside the footprint
            pred = np.full((48, 48), 2.5, dtype=np.float32)
            pred[10, 10] = np.nan
            np.save(wdir / "artifacts" / "pred.npy", pred)

            env = {"PYTHONPATH": str(REPO)}
            # first attempt must be refused without --fix-nan
            rc = subprocess.call(
                [sys.executable, "scripts/build_submission.py", "artifacts/pred.npy",
                 "--policy", "gate-test", "--template",
                 "data/demo/sample_submission.tif"],
                cwd=wdir, env={**dict(**__import__("os").environ), **env},
            )
            self.assertEqual(rc, 1)

            # with --fix-nan it must succeed and clamp 2.5 -> 1.0
            rc = subprocess.call(
                [sys.executable, "scripts/build_submission.py", "artifacts/pred.npy",
                 "--policy", "gate-test", "--template",
                 "data/demo/sample_submission.tif", "--fix-nan"],
                cwd=wdir, env={**dict(**__import__("os").environ), **env},
            )
            self.assertEqual(rc, 0)
            outs = sorted((wdir / "submissions").glob("GEMS_gate-test_*.tif"))
            self.assertEqual(len(outs), 1)
            self.assertTrue((wdir / "submissions" / (outs[0].stem + ".NOTE.txt")).exists())
            manifest_path = wdir / "submissions" / (outs[0].stem + ".MANIFEST.json")
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text())
            self.assertEqual(len(manifest["prediction_sha256"]), 64)
            self.assertEqual(
                manifest["prediction_hash_scope"],
                "full float32 array in C order after output/nodata policy",
            )

            # validate the produced file with the CLI gate too
            rc = subprocess.call(
                [sys.executable, "scripts/validate_submission.py", str(outs[0]),
                 "--template", "data/demo/sample_submission.tif"],
                cwd=wdir, env={**dict(**__import__("os").environ), **env},
            )
            self.assertEqual(rc, 0)

            # name uniqueness: second build at a later stamp must differ
            import time
            time.sleep(1)
            rc = subprocess.call(
                [sys.executable, "scripts/build_submission.py", "artifacts/pred.npy",
                 "--policy", "gate-test", "--template",
                 "data/demo/sample_submission.tif", "--fix-nan"],
                cwd=wdir, env={**dict(**__import__("os").environ), **env},
            )
            self.assertEqual(rc, 0)
            outs2 = sorted((wdir / "submissions").glob("GEMS_gate-test_*.tif"))
            self.assertEqual(len(outs2), 2)
            self.assertNotEqual(outs2[0].name, outs2[1].name)


if __name__ == "__main__":
    unittest.main()
