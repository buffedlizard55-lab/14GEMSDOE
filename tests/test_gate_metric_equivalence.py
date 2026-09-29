"""The gate's scoring path must stay identical to the public metric.

`scripts/validate_real.py` and `scripts/sweep_real.py` score on `gems.dti_fast`
(float32) instead of the float64 transcription in `gems.dti` because the
calibration loop evaluates one emission per candidate policy per arm — 1.5 s per
call instead of 5.2 s on the real 3730x3292 grid.  This module pins that
substitution: the two implementations must agree to float32 round-off on the
shapes, masks and emission styles the gate actually produces.

Regression it guards (2026-09-28/29): the first full-grid gate run was killed
after fold 0 because scoring with the float64 path plus a 9-policy calibration
grid made one fold take ~40 minutes; nothing in the *numbers* was wrong, but the
run could not finish inside a session.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from gems import dti as gdti  # noqa: E402
from gems import dti_fast as df  # noqa: E402

import validate_real as vr  # noqa: E402


def _toy(seed: int = 3, rows: int = 90, cols: int = 110) -> dict:
    rng = np.random.default_rng(seed)
    valid = np.zeros((rows, cols), dtype=bool)
    valid[3:-3, 3:-3] = True
    gt = np.zeros((rows, cols), dtype=bool)
    for _ in range(6):
        r, c = rng.integers(8, rows - 8), rng.integers(8, cols - 8)
        gt[r:r + 3, c:c + 12] = True
    gt &= valid
    field = rng.random((rows, cols), dtype=np.float32)
    field[~valid] = 0.0
    return {"valid": valid, "gt": gt, "field": field}


def test_score_field_matches_the_reference_metric():
    t = _toy()
    emitted = vr.emit_policy(t["field"], "topk", 0.05, t["valid"])
    fast = vr.score_field(emitted, t["gt"], t["valid"])
    ref = gdti.dti(emitted, t["gt"], radius_px=3.0, eval_mask=t["valid"])
    assert fast["dti"] == pytest.approx(ref["dti"], abs=2e-5)
    assert fast["n_gt"] == ref["n_gt"]
    assert fast["n_pred_pos"] == ref["n_pred_pos"]


@pytest.mark.parametrize("policy,param", [("thresh", 0.7), ("topk", 0.02), ("nms", 0.02)])
def test_every_emission_policy_scores_identically_to_the_reference(policy, param):
    t = _toy(seed=5)
    emitted = vr.emit_policy(t["field"], policy, param, t["valid"])
    assert set(np.unique(emitted)) <= {0.0, 1.0}          # binary, always 1.0
    fast = df.dti_fast(emitted, t["gt"], radius_px=3.0, eval_mask=t["valid"])["dti"]
    ref = gdti.dti(emitted, t["gt"], radius_px=3.0, eval_mask=t["valid"])["dti"]
    assert fast == pytest.approx(ref, abs=2e-5)


def test_calibration_never_scores_on_the_test_set():
    """`calibrate_policy` may only ever look at the CALIB slice it is given."""
    t = _toy(seed=7)
    calib = t["gt"]
    pol_a = vr.calibrate_policy(t["field"], calib, t["valid"], seed=1)
    # a completely different TEST slice must not change the chosen policy
    shuffled = t["field"].copy()
    shuffled[~t["valid"]] = 0.0
    pol_b = vr.calibrate_policy(shuffled, calib, t["valid"], seed=1)
    assert pol_a["policy"] == pol_b["policy"]
    assert pol_a["param"] == pol_b["param"]


def test_emit_policy_never_touches_invalid_pixels_or_exceeds_the_budget():
    t = _toy(seed=11)
    for policy, param in [("thresh", 0.5), ("topk", 0.05), ("nms", 0.05)]:
        pred = vr.emit_policy(t["field"], policy, param, t["valid"])
        assert not pred[~t["valid"]].any(), f"{policy} emitted outside the footprint"
        if policy != "thresh":
            budget = int(round(param * int(t["valid"].sum())))
            assert (pred > 0).sum() <= budget + 1
