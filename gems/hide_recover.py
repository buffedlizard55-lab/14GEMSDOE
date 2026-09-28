"""Hide-and-recover training protocol.

Why this exists (standing prompt):  "Train these only through hide-and-recover,
hiding a random share of known traces from the context inputs each epoch and
scoring recovery of the hidden ones. That way the model cannot read 'distance to
a known fault = 0' as the answer."

Unit of hiding
--------------
Whole connected trace components are hidden, never random pixels of every
trace.  Hiding pixels still leaves the trace's neighbours in the context and
the distance field collapses to ~0 on the hidden pixel — the model would learn
the trivial answer.  Hiding whole components is the smallest unit at which
"the catalogue does not contain this structure" is actually true, which is the
condition the prize test set imposes (forum 11516: known-fault pixels are
masked from scoring; the scored population is exactly the traces that are NOT
in the catalogue).

Anti-leak invariant (asserted every epoch, tested in tests/test_hide_recover.py)
------------------------------------------------------------------------------
For every hidden component pixel h:  context_distance(h) > 0.  In fact, with
whole-component hiding, context_distance(h) >= 1 px by construction, and we
additionally support a ``buffer_px`` that also hides components within a
distance of the hidden ones (optional, stricter).

Recovery score
--------------
DTI restricted to the hidden components' pixels as ground truth (with the same
300 m kernel), computed on the model's prediction given the masked context.
This is the number that selects models and hyperparameters — never a score
computed with the full catalogue visible.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from .dti import dti


def split_components(trace_mask: np.ndarray) -> tuple[np.ndarray, int]:
    """Label 8-connected trace components."""
    lab, n = ndimage.label(np.asarray(trace_mask, dtype=bool), structure=np.ones((3, 3), dtype=int))
    return lab, n


class HidePlan:
    """A per-epoch hiding plan: which components are hidden."""

    def __init__(self, n_components: int, hidden_ids: np.ndarray):
        self.n_components = int(n_components)
        self.hidden_ids = np.asarray(sorted(hidden_ids.tolist()), dtype=int)

    @property
    def fraction(self) -> float:
        return len(self.hidden_ids) / max(self.n_components, 1)


def sample_hide_plan(
    trace_mask: np.ndarray,
    hide_fraction: float,
    rng: np.random.Generator,
    buffer_px: float = 0.0,
) -> HidePlan:
    """Randomly hide ``hide_fraction`` of connected trace components.

    If buffer_px > 0, any component whose pixels come within buffer_px of a
    hidden component is hidden as well (stricter: the hidden structure is
    invisible even at its tips' near-neighbourhood).
    """
    if not 0.0 < hide_fraction < 1.0:
        raise ValueError(f"hide_fraction must be in (0,1), got {hide_fraction}")
    lab, n = split_components(trace_mask)
    if n == 0:
        raise ValueError("trace_mask has no components to hide")
    ids = np.arange(1, n + 1)
    n_hide = max(1, int(round(hide_fraction * n)))
    hidden = set(rng.choice(ids, size=n_hide, replace=False).tolist())

    if buffer_px > 0:
        hidden_mask = np.isin(lab, list(hidden))
        buf = ndimage.binary_dilation(hidden_mask, iterations=int(np.ceil(buffer_px)))
        for cid in ids:
            if cid in hidden:
                continue
            if (buf & (lab == cid)).any():
                hidden.add(int(cid))

    return HidePlan(n, np.array(sorted(hidden), dtype=int))


def apply_plan(trace_mask: np.ndarray, plan: HidePlan) -> tuple[np.ndarray, np.ndarray]:
    """Return (context_mask, hidden_mask) for a hide plan."""
    lab, _n = split_components(trace_mask)
    hidden = np.isin(lab, plan.hidden_ids)
    context = np.asarray(trace_mask, dtype=bool) & ~hidden
    return context, hidden


def assert_no_leak(context_mask: np.ndarray, hidden_mask: np.ndarray) -> dict:
    """Enforce the anti-leak invariant: no hidden pixel may touch the context.

    Returns a small report dict; raises AssertionError on violation.
    """
    if hidden_mask.any():
        # any hidden pixel with a context pixel in its 8-neighbourhood?
        near = ndimage.binary_dilation(context_mask, structure=np.ones((3, 3), dtype=bool))
        leaks = int((hidden_mask & near).sum())
        if leaks:
            raise AssertionError(
                f"hide-and-recover leak: {leaks} hidden pixel(s) touch the context "
                "(distance-0 information still visible)"
            )
    return {"leaks": 0, "n_hidden_px": int(hidden_mask.sum()), "n_context_px": int(context_mask.sum())}


def recover_score(pred: np.ndarray, hidden_mask: np.ndarray, *, radius_px: float = 3.0) -> dict:
    """DTI of the prediction against the hidden traces only.

    eval_mask = dilate(hidden, radius) — evaluation is restricted to the
    neighbourhood of hidden traces so that the model is scored on recovery,
    not on re-predicting visible catalogue geometry.
    """
    near = ndimage.binary_dilation(
        hidden_mask, structure=np.ones((3, 3), dtype=bool), iterations=int(np.ceil(radius_px))
    )
    return dti(pred, hidden_mask, radius_px=radius_px, eval_mask=near)
