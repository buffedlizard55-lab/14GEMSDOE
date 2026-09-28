"""Spatially-blocked holdout splits.

Neighbouring pixels of the same fault trace are near-duplicates; a random
pixel split overstates generalization.  All model selection in this repo uses
spatial blocks: contiguous squares of the grid are assigned to folds, and a
fold's traces are scored only against models that never saw that block's
context.

Two policies:
  * 'block'  : hold out whole blocks (standard spatial CV).
  * 'buffer' : additionally purge traces that straddle block borders within
               ``buffer_px`` of the held-out blocks (strict; removes the
               near-trace leakage path across block edges).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def make_blocks(shape: tuple[int, int], block_px: int) -> np.ndarray:
    """Assign every pixel a block id (int32 array)."""
    rows, cols = shape
    br = int(np.ceil(rows / block_px))
    bc = int(np.ceil(cols / block_px))
    ii, jj = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
    return (ii // block_px) * bc + (jj // block_px)


def assign_folds(
    shape: tuple[int, int],
    block_px: int,
    n_folds: int,
    seed: int = 0,
) -> np.ndarray:
    """Return per-pixel fold ids in [0, n_folds), block-constant."""
    blocks = make_blocks(shape, block_px)
    n_blocks = int(blocks.max()) + 1
    rng = np.random.default_rng(seed)
    fold_of_block = rng.integers(0, n_folds, size=n_blocks)
    return fold_of_block[blocks]


def holdout_masks(
    trace_mask: np.ndarray,
    fold_map: np.ndarray,
    fold: int,
    *,
    policy: str = "block",
    buffer_px: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (train_mask, test_mask) of trace pixels for one fold.

    test_mask  : trace pixels inside the fold's blocks (policy 'block'), plus —
                 under policy 'buffer' — every trace pixel within buffer_px of
                 them (purged from training).
    train_mask : the remaining trace pixels.
    """
    t = np.asarray(trace_mask, dtype=bool)
    if t.shape != fold_map.shape:
        raise ValueError("trace_mask and fold_map shapes differ")
    in_fold = fold_map == fold
    test = t & in_fold
    if policy == "buffer" and buffer_px > 0:
        near = ndimage.binary_dilation(
            test, structure=np.ones((3, 3), dtype=bool), iterations=int(buffer_px)
        )
        test = test | (t & near)
    elif policy not in ("block", "buffer"):
        raise ValueError(f"unknown policy {policy!r}")
    train = t & ~test
    return train, test
