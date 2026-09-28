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

The synthetic generator deliberately contains TWO fault populations, because the
competition does:

  * ``traces``      — the *catalogue*: what USGS/INGENIOUS publish. This is what
                      hide-and-recover hides components of, and what the blocked
                      holdout scores recovery of.
  * ``blind_traces``— real faults that are **absent from the catalogue** and are
                      expressed only in the geophysical rasters. These are never
                      training labels: they are the local analogue of the
                      sponsor's private test set, and they are kept >=
                      ``blind_min_sep_px`` from every catalogue trace so that the
                      "distance to a known fault = 0" shortcut cannot score them.

Feature rasters carry a real, but noisy, signal on and near the structures:
  * ``f_elev``  detrended-elevation analogue (scarp at every catalogue trace)
  * ``f_mag``   magnetic analogue
  * ``f_grav``  gravity analogue whose *horizontal-gradient ridge* follows the
                TRUE fault network (catalogue + blind) and dies out at the
                tips — the signature Faulds et al. 2026 say defined fault
                terminations and intersections
  * ``f_seis``  seismicity-density analogue, strongest on blind strands under
                modelled basin fill
  * ``f_cond``  surface-conductance analogue (clay cap above blind strands)
  * ``f_maglo`` magnetic-low analogue over the same caps
  * ``strain``  background strain-rate analogue
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


def _fault_edge_field(shape, segments, sigma: float = 2.0, taper: bool = True):
    """Scalar field whose horizontal-gradient ridge follows ``segments``.

    Physical model: a near-vertical density (or magnetisation) contrast across a
    fault produces a step in the potential field; the *gradient magnitude* of
    that step is a ridge running along the fault, and it vanishes where the
    contrast dies — i.e. at the fault tip.  We build the field as a sum of
    tapered Gaussian tubes oriented along each segment, so |grad| ridges lie on
    the segments and terminate at their ends.
    """
    rows, cols = shape
    yy, xx = np.mgrid[0:rows, 0:cols].astype(np.float64)
    field = np.zeros((rows, cols), dtype=np.float64)
    for (y0, x0), (y1, x1) in segments:
        dy, dx = float(y1 - y0), float(x1 - x0)
        L = float(np.hypot(dy, dx))
        if L < 1e-6:
            continue
        uy, ux = dy / L, dx / L          # along-strike unit vector
        # perpendicular offset of every pixel from the segment line
        rx, ry = xx - x0, yy - y0
        perp = rx * uy - ry * ux
        along = rx * ux + ry * uy
        if taper:
            t = np.clip(along / L, 0.0, 1.0)
            w = np.sin(np.pi * t)        # 0 at both tips, 1 at mid-segment
        else:
            w = np.ones_like(along)
        field += w * np.exp(-(perp ** 2) / (2.0 * sigma * sigma))
    return field


def _segments_from_mask(mask: np.ndarray, min_px: int = 6) -> list:
    """Approximate each connected component of a mask by its PCA long axis."""
    from scipy import ndimage as _ndi
    lab, n = _ndi.label(np.asarray(mask, dtype=bool), structure=np.ones((3, 3), dtype=int))
    segs = []
    for cid in range(1, n + 1):
        ys, xs = np.nonzero(lab == cid)
        if ys.size < min_px:
            continue
        pts = np.stack([ys.astype(np.float64), xs.astype(np.float64)], axis=1)
        mean = pts.mean(axis=0)
        c = np.cov((pts - mean).T)
        evals, evecs = np.linalg.eigh(c)
        axis = evecs[:, int(np.argmax(evals))]
        proj = (pts - mean) @ axis
        i0, i1 = int(np.argmin(proj)), int(np.argmax(proj))
        segs.append((tuple(pts[i0]), tuple(pts[i1])))
    return segs


def make_region(
    shape: tuple[int, int] = (256, 256),
    n_normal: int = 14,
    n_strike_slip: int = 4,
    n_relay_pairs: int = 4,
    n_horsetails: int = 6,
    seed: int = 20260928,
    n_blind: int = 6,
    blind_min_sep_px: int = 22,
    include_geophysics: bool = True,
) -> dict:
    """Generate a synthetic region dict.

    Returns
    -------
    dict with keys:
      traces            : bool (rows, cols) catalogue of visible traces
      blind_traces      : bool (rows, cols) faults absent from the catalogue
      family            : int8 (rows, cols) 0 none, 1 normal, 2 strike-slip
      comp_meta         : per-component metadata list
      f_elev, f_mag     : float32 feature rasters with structure signal
      f_grav            : float32 gravity analogue (gradient ridges on truth)
      f_seis            : float32 seismicity-density analogue
      f_cond            : float32 conductance analogue (clay caps)
      f_maglo           : float32 magnetic-low analogue
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

    # --- blind faults: real, in the geophysics, absent from the catalogue -----
    blind = np.zeros(shape, dtype=bool)
    if n_blind > 0:
        from scipy import ndimage as _ndi
        # keep every blind trace >= blind_min_sep_px from any catalogue trace
        far = _ndi.distance_transform_edt(~traces) >= blind_min_sep_px
        tries = 0
        placed = 0
        while placed < n_blind and tries < 400:
            tries += 1
            strike_deg = float(rng.normal(10.0, 14.0)) if placed % 2 == 0 \
                else float(rng.normal(135.0, 10.0))
            rad = np.radians(strike_deg)
            length = rng.uniform(rows * 0.12, rows * 0.34)
            y0 = rng.uniform(rows * 0.15, rows * 0.85)
            x0 = rng.uniform(cols * 0.15, cols * 0.85)
            y1 = y0 + length * np.cos(rad)
            x1 = x0 + length * np.sin(rad)
            cand = _rasterize_segment(shape, (y0, x0), (y1, x1))
            if not (cand & far).any():
                continue
            new = cand & far
            if new.sum() < 5:
                continue
            blind |= new
            placed += 1

    # --- geophysical analogues built on the TRUE fault network --------------
    true_faults = traces | blind
    if include_geophysics:
        segs = _segments_from_mask(true_faults)

        # gravity: regional tilt + the tapered-tube edge field (|grad| ridges on
        # the true network, terminating at the tips)
        edge = _fault_edge_field(shape, segs, sigma=2.2)
        edge = edge / (np.abs(edge).max() + 1e-9)
        gnoise = ndimage.gaussian_filter(
            rng.normal(0, 1, size=shape).astype(np.float32), 4.0)
        gnoise /= (np.abs(gnoise).max() + 1e-9)
        f_grav = (0.25 * (yy / rows) + 0.9 * edge + 0.30 * gnoise).astype(np.float32)

        # seismicity: blobs on the true network, weighted toward blind strands
        # (a buried fault under basin fill slips and is not in the catalogue)
        if blind.any():
            d_blind = ndimage.distance_transform_edt(~blind).astype(np.float32)
        else:
            d_blind = np.full(shape, 1e6, dtype=np.float32)
        d_true = ndimage.distance_transform_edt(~true_faults).astype(np.float32)
        f_seis = (np.exp(-d_true / 5.0) + 1.6 * np.exp(-d_blind / 3.5)).astype(np.float32)
        f_seis = f_seis * (0.6 + 0.8 * rng.random(shape).astype(np.float32))

        # clay cap above blind strands: high conductance + magnetic low
        cap = np.exp(-d_blind / 9.0).astype(np.float32)
        cnoise = ndimage.gaussian_filter(
            rng.normal(0, 1, size=shape).astype(np.float32), 5.0)
        cnoise /= (np.abs(cnoise).max() + 1e-9)
        f_cond = (0.7 * cap + 0.35 * cnoise + 0.2).astype(np.float32)
        f_maglo = (-0.8 * cap + 0.45 * cnoise + 0.5).astype(np.float32)
    else:
        f_grav = f_seis = f_cond = f_maglo = None

    return {
        "traces": traces,
        "blind_traces": blind,
        "family": family,
        "comp_meta": comp_meta,
        "n_components_total": len(comp_meta),
        "n_normal_px": n_existing,
        "f_elev": f_elev,
        "f_mag": f_mag,
        "f_grav": f_grav,
        "f_seis": f_seis,
        "f_cond": f_cond,
        "f_maglo": f_maglo,
        "strain": strain,
        "dist_true": dist,
        "footprint": footprint,
    }
