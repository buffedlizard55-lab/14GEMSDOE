"""Synthetic GeoDAWN-like test region.

The real competition data sits behind a DrivenData login and cannot be fetched
from this sandbox (verified 2026-09-28: the data tab redirects to the login
page).  Everything in this repo that executes is therefore exercised on this
generator, which reproduces the structural statistics the hypotheses target:

  * a N- to NNE-striking normal-fault family (Basin and Range),
  * a NW-striking dextral strike-slip family (Walker Lane analogue),
  * step-overs / relay ramps between overlapping sub-parallel strands,
  * horsetail splays at fault tips,
  * cross-family intersections,

with feature rasters (detrended-elevation analogue, magnetic analogue) that
carry a real signal on and near the hidden structures, so recovery is possible
but not trivial.  Shapes match the pinned competition grid scale-down factor so
tests run in seconds.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def _rasterize_segment(shape, p0, p1, width=1):
    """Rasterize a line segment (inclusive) with a square brush of given width."""
    mask = np.zeros(shape, dtype=bool)
    y0, x0 = p0
    y1, x1 = p1
    n = int(max(abs(y1 - y0), abs(x1 - x0), 1)) * 2
    for s in np.linspace(0.0, 1.0, n + 1):
        y = int(round(y0 + (y1 - y0) * s))
        x = int(round(x0 + (x1 - x0) * s))
        r = max(0, width // 2)
        y0b, y1b = max(y - r, 0), min(y + r + 1, shape[0])
        x0b, x1b = max(x - r, 0), min(x + r + 1, shape[1])
        mask[y0b:y1b, x0b:x1b] = True
    return mask


def make_region(
    shape: tuple[int, int] = (256, 256),
    n_normal: int = 14,
    n_strike_slip: int = 4,
    n_relay_pairs: int = 4,
    n_horsetails: int = 6,
    seed: int = 20260928,
) -> dict:
    """Generate a synthetic region dict.

    Returns
    -------
    dict with keys:
      traces            : bool (rows, cols) full catalogue of visible traces
      family            : int8 (rows, cols) 0 none, 1 normal, 2 strike-slip
      hidden_is_relay   : bool per-component (metadata list)
      f_elev, f_mag     : float32 feature rasters with structure signal
      strain            : float32 background strain-rate analogue
      footprint         : bool valid-region mask
    """
    rng = np.random.default_rng(seed)
    rows, cols = shape
    traces = np.zeros(shape, dtype=bool)
    family = np.zeros(shape, dtype=np.int8)
    comp_meta: list[dict] = []

    def add(mask, fam, kind):
        nonlocal traces, family
        new = mask & ~traces
        if new.any():
            traces |= new
            family[new] = fam
            comp_meta.append({"kind": kind, "px": int(new.sum())})

    # --- family 1: N- to NNE-striking normal faults (Basin and Range) ---
    for _ in range(n_normal):
        x0 = rng.uniform(cols * 0.05, cols * 0.95)
        y0 = rng.uniform(0, rows * 0.4)
        length = rng.uniform(rows * 0.25, rows * 0.7)
        strike_deg = rng.normal(10.0, 12.0)  # ~N10E
        rad = np.radians(strike_deg)
        y1 = y0 + length * np.cos(rad)
        x1 = x0 + length * np.sin(rad)
        add(_rasterize_segment(shape, (y0, x0), (y1, x1)), 1, "normal")

    # --- family 2: NW-striking dextral faults (Walker Lane analogue) ---
    for _ in range(n_strike_slip):
        y0 = rng.uniform(rows * 0.1, rows * 0.9)
        x0 = rng.uniform(0, cols * 0.3)
        length = rng.uniform(cols * 0.35, cols * 0.8)
        strike_deg = rng.normal(135.0, 8.0)  # ~NW
        rad = np.radians(strike_deg)
        y1 = y0 - length * np.cos(rad) * 0.5
        x1 = x0 + length * np.sin(rad) * 0.7
        add(_rasterize_segment(shape, (y0, x0), (y1, x1)), 2, "strike-slip")

    # --- relay pairs: two sub-parallel overlapping strands with a gap ---
    for _ in range(n_relay_pairs):
        xc = rng.uniform(cols * 0.15, cols * 0.85)
        yc = rng.uniform(rows * 0.15, rows * 0.85)
        length = rng.uniform(rows * 0.18, rows * 0.32)
        strike_deg = rng.normal(10.0, 8.0)
        rad = np.radians(strike_deg)
        off = rng.uniform(6, 14) * rng.choice([-1, 1])
        gap = rng.uniform(2, 9)
        s0, s1 = rng.uniform(0.1, 0.4), rng.uniform(0.6, 0.9)
        a0 = (yc + length * (s0 - 0.5) * np.cos(rad) - off * np.sin(rad),
              xc + length * (s0 - 0.5) * np.sin(rad) + off * np.cos(rad))
        a1 = (yc + length * (0.55 - 0.5) * np.cos(rad) - off * np.sin(rad),
              xc + length * (0.55 - 0.5) * np.sin(rad) + off * np.cos(rad))
        b0 = (yc + length * (s1 - 0.5) * np.cos(rad) + off * np.sin(rad) * 0 + off * np.sin(rad),
              xc + length * (s1 - 0.5) * np.sin(rad) - off * np.cos(rad) + gap * np.cos(rad))
        b1 = (yc + length * (1.45 - 0.5) * np.cos(rad) + off * np.sin(rad),
              xc + length * (1.45 - 0.5) * np.sin(rad) - off * np.cos(rad))
        add(_rasterize_segment(shape, a0, a1), 1, "relay-strand")
        add(_rasterize_segment(shape, b0, b1), 1, "relay-strand")

    # --- horsetail splays at tips of some normal faults ---
    n_existing = int(traces.sum())
    for _ in range(n_horsetails):
        ys, xs = np.nonzero(traces)
        if ys.size == 0:
            break
        i = rng.integers(0, ys.size)
        y0, x0 = float(ys[i]), float(xs[i])
        for _s in range(rng.integers(2, 5)):
            length = rng.uniform(6, 18)
            ang = rng.uniform(0, 2 * np.pi)
            y1 = y0 + length * np.cos(ang)
            x1 = x0 + length * np.sin(ang)
            add(_rasterize_segment(shape, (y0, x0), (y1, x1)), 1, "horsetail")

    # --- feature rasters carrying structure signal ---
    dist = ndimage.distance_transform_edt(~traces).astype(np.float32)
    noise = rng.normal(0, 1, size=shape).astype(np.float32)
    noise = ndimage.gaussian_filter(noise, 3.0)
    noise /= (np.abs(noise).max() + 1e-9)

    # elevation analogue: smooth regional tilt + ridge noise + scarp at traces
    yy, xx = np.mgrid[0:rows, 0:cols]
    regional = (0.4 * yy / rows + 0.2 * xx / cols).astype(np.float32)
    scarp = np.exp(-dist / 2.5).astype(np.float32)
    f_elev = (regional + 0.25 * noise + 0.55 * scarp).astype(np.float32)

    # magnetic analogue: different phase noise + edge response at traces
    noise2 = ndimage.gaussian_filter(rng.normal(0, 1, size=shape).astype(np.float32), 2.0)
    noise2 /= (np.abs(noise2).max() + 1e-9)
    f_mag = (noise2 + 0.45 * np.exp(-dist / 1.8)).astype(np.float32)

    strain = np.exp(-dist / 40.0).astype(np.float32) * 1e-9

    footprint = np.ones(shape, dtype=bool)
    # carve an invalid corner to exercise the NaN-outside-footprint path
    footprint[: rows // 16, : cols // 16] = False

    return {
        "traces": traces,
        "family": family,
        "comp_meta": comp_meta,
        "n_components_total": len(comp_meta),
        "n_normal_px": n_existing,
        "f_elev": f_elev,
        "f_mag": f_mag,
        "strain": strain,
        "dist_true": dist,
        "footprint": footprint,
    }
