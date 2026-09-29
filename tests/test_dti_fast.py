"""Tests for the fast full-grid DTI and the emission policies (gems/dti_fast.py).

Every claim made in the README and in ``research/hypotheses_round5.md`` about the
metric algebra is asserted here numerically, so a strategy statement can never
drift away from the code:

* ``dti_fast`` reproduces the reference ``gems.dti`` transcription;
* the published worked example reproduces (3.00, 1.89, 2.00) -> 0.6026;
* a single-pixel geometry has a hand-computable answer (2/3);
* **the marginal emission rule** ``emit iff k(x) > 0.2 * DTI`` is exactly the
  sign of the change in DTI when one unit of value is added to the field;
* the emitters respect the budget, the validity mask, and float16 inputs.
"""

from __future__ import annotations

import numpy as np
import pytest

from gems import dti as ref
from gems import dti_fast as fast


def _random_case(seed: int, shape=(64, 80)):
    rng = np.random.default_rng(seed)
    gt = rng.random(shape) < 0.01
    pred = (rng.random(shape) < 0.03) * rng.random(shape)
    pred = np.where(rng.random(shape) < 0.1, np.nan, pred)
    eval_mask = rng.random(shape) > 0.15
    return pred.astype(np.float32), gt, eval_mask


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_fast_matches_reference(seed):
    pred, gt, eval_mask = _random_case(seed)
    a = ref.dti(pred, gt, eval_mask=eval_mask)
    b = fast.dti_fast(pred, gt, eval_mask=eval_mask)
    assert b["n_gt"] == a["n_gt"]
    assert b["tp"] == pytest.approx(a["tp"], rel=1e-4, abs=1e-4)
    assert b["fp"] == pytest.approx(a["fp"], rel=1e-4, abs=1e-3)
    assert b["fn"] == pytest.approx(a["fn"], rel=1e-4, abs=1e-4)
    assert b["dti"] == pytest.approx(a["dti"], rel=1e-4)


def test_reference_matches_published_worked_example():
    """The competition page's worked example: TP=3.00, FP=1.89, FN=2.00 -> 0.60."""
    value = ref.dti_from_example_values(3.00, 1.89, 2.00)
    assert value == pytest.approx(0.6026, abs=5e-4)
    assert round(value, 2) == 0.60


def test_single_pixel_geometry_is_hand_computable():
    """Truth at (10, 10); predicting 1.0 one pixel away gives k = 2/3, so
    DTI = (2/3) / (2/3 + 0.2*(1/3) + 0.8*(1/3)) = 2/3 exactly."""
    gt = np.zeros((21, 21), dtype=bool)
    gt[10, 10] = True
    pred = np.zeros((21, 21), dtype=np.float32)
    pred[10, 11] = 1.0
    out = fast.dti_fast(pred, gt)
    assert out["tp"] == pytest.approx(2.0 / 3.0, rel=1e-6)
    assert out["fp"] == pytest.approx(1.0 / 3.0, rel=1e-6)
    assert out["fn"] == pytest.approx(1.0 / 3.0, rel=1e-6)
    assert out["dti"] == pytest.approx(2.0 / 3.0, rel=1e-6)
    # predicting exactly on the truth pixel is perfect
    pred2 = np.zeros_like(pred)
    pred2[10, 10] = 1.0
    assert fast.dti_fast(pred2, gt)["dti"] == pytest.approx(1.0, rel=1e-6)
    # predicting 3 px away earns no credit at all and only pays false positives
    pred3 = np.zeros_like(pred)
    pred3[10, 13] = 1.0
    out3 = fast.dti_fast(pred3, gt)
    assert out3["tp"] == pytest.approx(0.0)
    assert out3["dti"] == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_marginal_emission_rule(seed):
    """The marginal effect of adding one unit of value at pixel x0.

    With ``dTP = sum_g max(0, k_g - m(g))`` (the new pixel steals or improves the
    per-truth maximum), ``dFP = 1 - kmax(x0)`` and ``dFN = -dTP``:

        d(DTI) = [dTP*(Den - 0.2*TP) - 0.2*TP*dFP] / [Den*(Den + dDen)]

    so the *sign* is ``sign(dTP*(1 - 0.2*D) - 0.2*D*dFP)``.  When the new pixel
    becomes the first (and best) prediction near its nearest truth pixel,
    ``dTP = kmax = k`` and the rule collapses to the one the strategy uses:
    **emit iff k > 0.2*D**.  Both the component deltas and the sign rule are
    asserted against the implementation here, so the strategy statement can never
    drift away from the code."""
    rng = np.random.default_rng(seed)
    gt = np.zeros((40, 40), dtype=bool)
    gt[rng.integers(0, 40, 6), rng.integers(0, 40, 6)] = True
    pred = np.zeros((40, 40), dtype=np.float32)
    pred[rng.integers(0, 40, 12), rng.integers(0, 40, 12)] = 1.0
    base = fast.dti_fast(pred, gt)
    den = base["tp"] + 0.2 * base["fp"] + 0.8 * base["fn"] + fast.EPS
    tp, d = base["tp"], base["dti"]
    m_before = fast.kernel_weighted_max(pred).astype(np.float64)
    truth = np.argwhere(gt)
    dist_all = np.hypot(truth[:, 0][None, :] - np.arange(40)[:, None],
                        truth[:, 1][None, :] - np.arange(40)[:, None])
    checked = 0
    checked_rule = 0
    for i in range(40):
        for j in range(40):
            if pred[i, j] > 0:
                continue
            k_g = np.maximum(1.0 - np.hypot(truth[:, 0] - i, truth[:, 1] - j) / 3.0, 0.0)
            kmax = float(k_g.max())
            if kmax == 0.0:
                continue
            m_g = np.array([m_before[a, b] for a, b in truth])
            dtp_formula = float(np.maximum(k_g - m_g, 0.0).sum())
            dfp_formula = 1.0 - kmax
            pred2 = pred.copy()
            pred2[i, j] = 1.0
            after = fast.dti_fast(pred2, gt)
            # 1) the component deltas are exactly the analytic ones
            assert after["tp"] - tp == pytest.approx(dtp_formula, abs=2e-5)
            assert after["fp"] - base["fp"] == pytest.approx(dfp_formula, abs=2e-5)
            assert after["fn"] - base["fn"] == pytest.approx(-dtp_formula, abs=2e-5)
            # 2) the sign of the DTI change follows the exact rule
            rule = dtp_formula * (den - 0.2 * tp) - 0.2 * tp * dfp_formula
            assert np.sign(after["dti"] - d) == np.sign(rule)
            checked += 1
            # 3) the clean case: new pixel is the argmax for its nearest truth
            if abs(dtp_formula - kmax) < 1e-9:
                assert (after["dti"] > d) == (kmax > 0.2 * d)
                checked_rule += 1
    assert checked > 5
    assert checked_rule > 5


def test_scaling_a_support_up_never_lowers_the_score():
    """DTI(c*p) is non-decreasing in c: the metric is scale-monotone, which is why
    the same support should always be emitted at full value 1.0."""
    rng = np.random.default_rng(5)
    gt = np.zeros((30, 30), dtype=bool)
    gt[rng.integers(0, 30, 4), rng.integers(0, 30, 4)] = True
    support = np.zeros((30, 30), dtype=np.float32)
    support[rng.integers(0, 30, 20), rng.integers(0, 30, 20)] = 1.0
    scores = [fast.dti_fast(support * c, gt)["dti"] for c in (0.1, 0.25, 0.5, 0.75, 1.0)]
    assert all(b >= a - 1e-9 for a, b in zip(scores, scores[1:])), scores


def test_emit_thresh_accepts_float16_channels():
    """Regression: channels are stored float16 to fit the memory budget, and a
    float16 array used to break the emitter's -inf sentinel."""
    field = np.zeros((8, 8), dtype=np.float16)
    field[3, 4] = np.float16(0.5)
    valid = np.ones((8, 8), dtype=bool)
    out = fast.emit_thresh(field, valid, 0.2)
    assert out.dtype == np.float32
    assert out[3, 4] == 1.0
    assert out.sum() == 1.0
    empty = fast.emit_thresh(field, valid, 0.9)
    assert empty.sum() == 0.0


def test_emit_budget_and_validity():
    rng = np.random.default_rng(6)
    score = rng.random((50, 60)).astype(np.float32)
    valid = rng.random((50, 60)) > 0.3
    out_topk = fast.emit_topk(score, valid, 200)
    assert int(out_topk.sum()) == 200
    assert not np.any(out_topk[~valid] > 0)
    out_nms = fast.emit_nms(score, valid, 200, 2)
    assert 0 < out_nms.sum() <= 200
    assert not np.any(out_nms[~valid] > 0)
    # every accepted pixel is at least (radius) away from the next accepted one
    ys, xs = np.nonzero(out_nms > 0)
    d = np.hypot(ys[:, None] - ys[None, :], xs[:, None] - xs[None, :])
    np.fill_diagonal(d, np.inf)
    assert (d >= 2).all()
    # an empty budget is legal and produces an all-zero field
    assert fast.emit_nms(score, valid, 0).sum() == 0.0


def test_emit_nms_matches_naive_greedy():
    rng = np.random.default_rng(7)
    score = rng.random((40, 40)).astype(np.float32)
    valid = np.ones((40, 40), dtype=bool)
    budget, radius = 15, 2
    got = fast.emit_nms(score, valid, budget, radius)
    # naive reference implementation
    ref_out = np.zeros_like(score)
    blocked = np.zeros(score.shape, dtype=bool)
    order = np.argsort(-score.ravel(), kind="stable")
    taken = 0
    for idx in order:
        i, j = divmod(int(idx), score.shape[1])
        if blocked[i, j]:
            continue
        ref_out[i, j] = 1.0
        blocked[max(i - radius, 0):i + radius + 1, max(j - radius, 0):j + radius + 1] = True
        taken += 1
        if taken >= budget:
            break
    # the vectorised version accepts local maxima in the same order, so the
    # accepted sets agree whenever no two candidates tie in score
    assert got.sum() == ref_out.sum()
    assert np.array_equal(got > 0, ref_out > 0)


def test_eval_mask_semantics_from_staff_ruling():
    """Forum 11516: pixels of known USGS/INGENIOUS faults are excluded from both
    sides of the metric, so emitting them must be exactly score-neutral."""
    gt = np.zeros((15, 15), dtype=bool)
    gt[2, 2] = True
    pred_clean = np.zeros((15, 15), dtype=np.float32)
    pred_clean[2, 2] = 1.0
    pred_dirty = pred_clean.copy()
    pred_dirty[10:14, 10:14] = 1.0            # mass on "known fault" pixels
    mask = np.ones((15, 15), dtype=bool)
    mask[10:14, 10:14] = False
    a = fast.dti_fast(pred_clean, gt, eval_mask=mask)
    b = fast.dti_fast(pred_dirty, gt, eval_mask=mask)
    assert a["dti"] == pytest.approx(b["dti"])
    assert b["fp"] == pytest.approx(a["fp"])
    # without the mask the same mass is punished, which is the sensitivity the
    # strategy notes in research/scoring_analysis.md
    c = fast.dti_fast(pred_dirty, gt)
    assert c["dti"] < a["dti"]
