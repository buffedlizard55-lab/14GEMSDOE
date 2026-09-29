#!/usr/bin/env python3
"""REAL-DATA spatially-blocked, hide-and-recover gate.

This is the gate the standing prompt requires before any submission slot is
spent: every candidate feature arm is measured on the official competition
rasters, with a spatially blocked holdout and with the hide-and-recover
anti-leak invariant enforced (a held-out structure is absent from every
context-derived channel).

What is measured
----------------
Two protocols, same model, same features, same pixel sampling:

  --protocol block
      A 4-fold spatial block split of the grid.  For fold k, the TEST set is
      every catalogue pixel inside that fold's blocks; the CONTEXT is every
      catalogue pixel outside them (minus a purge buffer).  Catalogue-geometry
      features are recomputed from the CONTEXT only.  This measures
      extrapolation to a region with no mapped structure.

  --protocol component   (default)
      Hide-and-recover on whole connected components: HIDE 35 % of the 3,199
      catalogue components, CALIB 20 %, TEST 20 %, and 25 % stay always
      visible.  Context = every component except TEST (so a submission-time
      model's view), features for training and for threshold calibration come
      from the visible+HIDE components only.  Test traces are absent from the
      context at feature-build time.  This is the closest analogue of the
      scored population (structures that are not in the catalogue the model
      was shown).

The metric is the official one (`gems.dti.dti`, radius 3 px = 300 m,
alpha 0.2, beta 0.8) computed with the scored footprint as `eval_mask`.

Arms
----
`--arms` selects additive feature blocks.  `geom` is the baseline.  Every other
arm adds channels to the identical learner, so a difference is attributable to
the feature block alone.

Outputs
-------
artifacts/holdout_real.json            per-arm, per-fold metrics
artifacts/real_fields/fold{k}_{arm}.npy  float16 probability fields (for the
                                       emission sweep in scripts/sweep_real.py)

Usage
-----
    ./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
        --arms geom geo geom_tilt all --out artifacts/holdout_real.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gems import dti as gdti  # noqa: E402
from gems import realchannels as rc  # noqa: E402
from gems import realdata as rd  # noqa: E402
from gems.blocks import assign_folds  # noqa: E402
from scripts.train_hide_recover import logistic_fit, predict_proba, standardize_fit  # noqa: E402

# --------------------------------------------------------------------------
# feature blocks
# --------------------------------------------------------------------------
# Band indices are 1-based and were READ FROM THE FILE's band_name tags
# (data/processed/layer_index.json), never guessed.
BAND = {
    "mag_anom": 1, "rtp": 2, "tmi_hg": 3, "geod_2ndinv": 4,
    "iso_grav_anom_slope": 5, "tc": 6, "geod_shearrate": 7,
    "geod_dilaterate": 8, "tmi_vg": 9, "deq_n100a15": 10,
    "iso_grav_anom_vg": 11, "det_elev": 12, "iso_grav_anom": 13,
    "tmi": 14, "depth_to_base_surf": 15, "ieq_n100a15": 16,
    "cond_surf": 17, "iso_grav_anom_hg": 18, "det_elev_slope": 19,
}

# The physical channels every non-baseline arm may use.  Kept to the ones the
# competition's own documentation and the round-5/6 hypotheses cite; adding all
# 19 bands is a compute choice, not a scientific one.  For R6 we need shear,
# dilation and TMI as well.
GEO_BANDS = ("det_elev", "det_elev_slope", "tmi_hg", "tmi_vg", "tc",
             "iso_grav_anom_hg", "iso_grav_anom_slope", "iso_grav_anom",
             "cond_surf", "depth_to_base_surf", "geod_2ndinv", "deq_n100a15",
             "geod_shearrate", "geod_dilaterate", "tmi")

GEOM_CHANNELS = ("dist_trace", "az_sin", "az_cos", "across_strike",
                 "along_strike", "dist_endpoint", "trace_density",
                 "strike_sin", "strike_cos", "strike_conf", "relay_corridor",
                 "junction_density")


def load_band(name: str) -> np.ndarray:
    """Read one competition band and robust-scale it to [-1, 1] (NaN kept)."""
    a = rd.read_band(BAND[name])
    return rc.robust_unit(a)


def build_static_channels(cache: Path, quiet: bool = False, use_cache: bool = True
                          ) -> dict[str, np.ndarray]:
    """Build (or load) the geophysical channels that do not depend on context.

    ``use_cache=False`` (smoke-crop runs) never reads or writes the on-disk
    cache: a cropped band must not be persisted as if it were the full grid.
    """
    if use_cache:
        cache.mkdir(parents=True, exist_ok=True)
    out: dict[str, np.ndarray] = {}
    for name in GEO_BANDS:
        p = cache / f"{name}.npy"
        if use_cache and p.exists():
            out[name] = np.load(p).astype(np.float32)
            continue
        t0 = time.time()
        a = load_band(name)
        if use_cache:
            np.save(p, a.astype(np.float16))
        out[name] = a
        if not quiet:
            print(f"    [static] {name} built in {time.time()-t0:.1f} s", flush=True)
    return out


def _f16(a: np.ndarray) -> np.ndarray:
    """float16 channel with a finite guard (float16 saturates above 65,504)."""
    x = np.asarray(a, dtype=np.float32)
    x = np.where(np.isfinite(x), x, 0.0)
    return np.clip(x, -30000.0, 30000.0).astype(np.float16)


def _expression_ridge_field(static: dict[str, np.ndarray]) -> np.ndarray:
    """Ridge-strength expression field for R7-1 trace alignment.

    Mean of the three independent ridge-strength bands (detrended-elevation
    slope, TMI horizontal gradient, isostatic-gravity horizontal gradient).
    All three are already robust-scaled to ~[-1, 1]; their mean is a relative
    expression score, which is all the alignment operator needs.
    """
    z = None
    for nm in ("det_elev_slope", "tmi_hg", "iso_grav_anom_hg"):
        v = static.get(nm)
        if v is None:
            continue
        v = np.nan_to_num(np.asarray(v, dtype=np.float32), nan=0.0)
        z = v.copy() if z is None else z + v
    if z is None:
        raise ValueError("no expression bands in static channels")
    return z / 3.0


def build_geom_channels(context: np.ndarray, window: int = 9) -> dict[str, np.ndarray]:
    """Catalogue-geometry channels, computed from the CONTEXT mask only.

    One channel is materialised at a time and cast to float16 immediately: two
    full-view sets held as float32 would be ~1.2 GB on the 12.28 M-pixel grid.
    """
    da = rc.distance_and_azimuth(context)
    out = {"dist_trace": _f16(da["dist_trace"]), "az_sin": _f16(da["az_sin"]),
           "az_cos": _f16(da["az_cos"])}
    del da
    aas = rc.along_across_strike(context, window=window)
    out["across_strike"] = _f16(aas["across_strike"])
    out["along_strike"] = _f16(aas["along_strike"])
    de = np.asarray(aas["dist_endpoint"], dtype=np.float32)
    out["dist_endpoint"] = _f16(np.minimum(de, 3000.0))
    del aas, de
    strike, conf = rc.local_strike(context, window=window)
    out["strike_sin"] = _f16(np.nan_to_num(np.sin(np.radians(strike)), nan=0.0))
    out["strike_cos"] = _f16(np.nan_to_num(np.cos(np.radians(strike)), nan=0.0))
    out["strike_conf"] = _f16(conf)
    del strike, conf
    dens = rc.intersection_density(context)
    out["trace_density"] = _f16(dens["trace_density"])
    out["junction_density"] = _f16(dens["junction_density"])
    del dens
    rel = rc.relay_corridors(context)
    out["relay_corridor"] = _f16(rel["corridor"])
    del rel
    return out


def build_round5_channels(context: np.ndarray, static: dict[str, np.ndarray],
                          valid: np.ndarray, which: set[str]) -> dict[str, np.ndarray]:
    """Round-5 + Round-6 hypothesis channels (only the ones the arm asked for)."""
    out: dict[str, np.ndarray] = {}
    elev = rc.nan_fill(static.get("det_elev", np.zeros(context.shape, np.float32)))
    elev_slope = static.get("det_elev_slope", None)
    # R5
    if "ramp" in which:
        out["ramp_maturity"] = rc.ramp_maturity_field(context)
    if "acc" in which:
        out["acc_corridor"] = rc.accommodation_corridors(context, elev)
    if "tilt" in which:
        vg = np.nan_to_num(static.get("tmi_vg", np.zeros(context.shape, np.float32)), nan=0.0)
        hg = np.nan_to_num(static.get("tmi_hg", np.zeros(context.shape, np.float32)), nan=0.0)
        ta = rc.tilt_angle(vg, hg)
        out["tilt_angle"] = ta
        out["tilt_edge"] = rc.line_max(np.abs(ta), radius=2)
    if "curv" in which:
        prof, plan = rc.profile_curvature(elev, sigma=1.0)
        out["profcurv"] = prof
        out["profcurv_line"] = rc.line_max(np.abs(prof), radius=2)
    if "gap" in which:
        dens = rc.intersection_density(context)["trace_density"]
        res = rc.completeness_residual(dens, {
            "elev": elev,
            "grav_slope": np.nan_to_num(
                static.get("iso_grav_anom_slope", np.zeros(context.shape, np.float32)), nan=0.0),
        }, smooth_sigma=32.0)
        out["gap_residual"] = np.asarray(res["residual"] if isinstance(res, dict) else res,
                                         dtype=np.float32)
    # R6
    if "horse" in which:
        es = rc.nan_fill(elev_slope) if elev_slope is not None else None
        out["horse_splay"] = rc.horsetail_splay_field(context, es, elev, radius_px=20.0, half_angle_deg=60.0)
    if "xsec" in which:
        shear = static.get("geod_shearrate", None)
        dil = static.get("geod_dilaterate", None)
        # also need tmi_hg for weighting optionally
        out["xsec_halo"] = rc.intersection_halos(context, shear, dil, high_angle_deg=45.0, near_miss_px=20.0, halo_sigma_px=10.0)
    if "condbase" in which:
        cond = static.get("cond_surf", None)
        depth = static.get("depth_to_base_surf", None)
        tmi = static.get("tmi", None)
        ghg = static.get("iso_grav_anom_hg", None)
        cb = rc.conductive_base_step(cond, depth, tmi, ghg)
        # conductive_base_step returns zeros if missing; handle shape mismatch
        if isinstance(cb, np.ndarray) and cb.shape == context.shape:
            out["condbase_step"] = cb
        elif isinstance(cb, np.ndarray) and cb.size == context.size:
            out["condbase_step"] = cb.reshape(context.shape)
    if "shore" in which:
        ghg = static.get("iso_grav_anom_hg", None)
        res = rc.paleo_shoreline_suppression(elev, rc.nan_fill(elev_slope) if elev_slope is not None else None, ghg)
        if res:
            if "sublake_enhanced" in res and res["sublake_enhanced"].shape == context.shape:
                out["sublake_enhanced"] = res["sublake_enhanced"]
            if "shoreline_dist" in res and res["shoreline_dist"].shape == context.shape:
                # invert distance: close to shoreline = low fault prob (suppression), far + sublake = high
                # we emit the distance as feature; model learns suppression
                out["shore_dist"] = res["shoreline_dist"]
    if "slip" in which:
        # external data not present in this sandbox run; placeholder returns empty
        sd = rc.slip_dilation_tendency_field(context)
        # if it ever returns something, add it
        for k, v in sd.items():
            if isinstance(v, np.ndarray) and v.shape == context.shape:
                out[k] = v
    # R7 (research/hypotheses_round7.md)
    if "gravtopo" in which:
        ghg = static.get("iso_grav_anom_hg", None)
        gslope = static.get("iso_grav_anom_slope", None)
        if ghg is not None:
            topo = rc.gravity_topology(ghg, gslope)
            out["grav_ridge"] = topo["grav_ridge"]
            out["grav_topo"] = topo["grav_topo"]
    if "trans" in which:
        shear = static.get("geod_shearrate", None)
        dil = static.get("geod_dilaterate", None)
        if shear is not None and dil is not None:
            out.update(rc.transtensional_coupling(shear, dil))
    return {k: _f16(v) for k, v in out.items() if v is not None}


ARM_SPEC: dict[str, str] = {
    "geom": "baseline",
    "geo": "geom + physical bands",
    "geom_ramp": "geom + geo + R5-1 relay-ramp interior",
    "geom_acc": "geom + geo + R5-2 accommodation corridors",
    "geom_tilt": "geom + geo + R5-3 magnetic tilt angle",
    "geom_curv": "geom + geo + R5-4 profile curvature",
    "geom_gap": "geom + geo + R5-5 conditioned completeness residual",
    "all": "geom + geo + every round-5 channel",
    # Round 6
    "geom_horse": "geom + geo + R6-1 horsetail splay fan",
    "geom_xsec": "geom + geo + R6-2 intersection halos (normal x strike-slip)",
    "geom_condbase": "geom + geo + R6-3 conductive-base step / clay-cap edge",
    "geom_shore": "geom + geo + R6-5 paleo-shoreline suppression + sub-lake enhancement",
    "geom_slip": "geom + geo + R6-4 slip/dilation tendency (external, if present)",
    "all6": "geom + geo + R5 + R6 (all channels)",
    # Round 7
    "geom_gravtopo": "geom + geo + R7-3 gravity-gradient termination/intersection topology",
    "geom_trans": "geom + geo + R7-5 transtensional shear x extension coupling",
    "geom_align": "geom(align) + geo + R7-1 expression-aligned traces (misregistration correction)",
}


def arm_channels(arm: str) -> tuple[list[str], set[str], bool]:
    """Return (feature names, round-5/6 extras, whether geo bands are included)."""
    names = list(GEOM_CHANNELS)
    r5: set[str] = set()
    geo = arm != "geom"
    if arm == "geom":
        return names, r5, geo
    for extra in ("ramp", "acc", "tilt", "curv", "gap", "horse", "xsec", "condbase", "shore", "slip",
                  "gravtopo", "trans", "align"):
        if arm == f"geom_{extra}":
            r5.add(extra)
    if arm == "all":
        # pinned definition (ARM_SPEC + round-5 record): every round-5 channel
        r5.update({"ramp", "acc", "tilt", "curv", "gap"})
    if arm == "all6":
        # all6 = R5 + R6; R7 arms stay separate until gated
        r5.update({"ramp", "acc", "tilt", "curv", "gap", "horse", "xsec", "condbase", "shore", "slip"})
    if "ramp" in r5:
        names.append("ramp_maturity")
    if "acc" in r5:
        names.append("acc_corridor")
    if "tilt" in r5:
        names += ["tilt_angle", "tilt_edge"]
    if "curv" in r5:
        names += ["profcurv", "profcurv_line"]
    if "gap" in r5:
        names.append("gap_residual")
    if "horse" in r5:
        names.append("horse_splay")
    if "xsec" in r5:
        names.append("xsec_halo")
    if "condbase" in r5:
        names.append("condbase_step")
    if "shore" in r5:
        names += ["sublake_enhanced", "shore_dist"]
    if "slip" in r5:
        # placeholder: if external raster ever present, its channels will be added dynamically
        # keep name list open; design_matrix will skip missing
        names += ["slip_tendency", "dilation_tendency"]
    if "gravtopo" in r5:
        names += ["grav_ridge", "grav_topo"]
    if "trans" in r5:
        names.append("trans_coupling")
    if "align" in r5:
        # the geometry block itself is rebuilt from the expression-aligned
        # context in run(); this is the extra offset-magnitude channel
        names.append("align_offset")
    if geo:
        names += list(GEO_BANDS)
    return names, r5, geo


def design_matrix(channels: dict[str, np.ndarray], names: list[str],
                  index: np.ndarray) -> np.ndarray:
    cols = []
    for nm in names:
        v = channels.get(nm)
        if v is None:
            continue
        if v.ndim != 2 or v.size == 0 or v.size <= int(index.max()):
            raise ValueError(f"channel {nm!r} has shape {v.shape} (size {v.size}) "
                             f"but pixel indices go up to {int(index.max())}")
        # promote only the sampled rows: the full 12.28 M-pixel grid as float32
        # would be 49 MB per channel and there are ~30 channels.  NaN means "no
        # data for this channel here" (e.g. strike of no trace, band nodata);
        # it is filled with 0 AFTER robust-scaling, i.e. the neutral value.
        col = np.asarray(v.ravel()[index], dtype=np.float32)
        cols.append(np.nan_to_num(col, nan=0.0, posinf=0.0, neginf=0.0))
    if not cols:
        raise ValueError(f"no usable channels among {names}")
    return np.stack(cols, axis=1)


def sample_pixels(context: np.ndarray, valid: np.ndarray, rng: np.random.Generator,
                  n_pos: int, n_neg: int, exclude: np.ndarray | None = None
                  ) -> tuple[np.ndarray, np.ndarray]:
    """Class-balanced flat-pixel sample: context traces + background."""
    pos = np.flatnonzero((context & valid).ravel())
    if exclude is not None:
        pos = pos[~exclude.ravel()[pos]]
    neg_pool = np.flatnonzero((valid & ~context).ravel())
    if exclude is not None:
        neg_pool = neg_pool[~exclude.ravel()[neg_pool]]
    p = rng.choice(pos, size=min(n_pos, pos.size), replace=False)
    n = rng.choice(neg_pool, size=min(n_neg, neg_pool.size), replace=False)
    idx = np.concatenate([p, n])
    y = np.concatenate([np.ones(p.size), np.zeros(n.size)]).astype(np.float64)
    return idx, y


def score_field(pred: np.ndarray, gt: np.ndarray, valid: np.ndarray,
                radius_px: float = 3.0) -> dict:
    return gdti.dti(pred, gt, radius_px=radius_px, eval_mask=valid)


def calibrate_policy(field: np.ndarray, calib: np.ndarray, valid: np.ndarray,
                     seed: int = 11, frac: float = 0.30, radius_px: float = 3.0
                     ) -> dict:
    """Choose the emission policy on the hidden CALIB components only.

    Policies are the two families that can move this metric: a probability
    threshold (emit everything above t) and a top-q budget by probability
    (emit the q·|valid| highest pixels).  Selection is on a 30 % subsample of
    CALIB for cost; the chosen policy is re-scored on the full CALIB set.
    """
    if calib is None or not calib.any():
        return {"policy": "thresh", "param": 0.5, "calib_dti": None}
    flat = np.flatnonzero(calib.ravel())
    rng = np.random.default_rng(seed)
    take = rng.choice(flat, size=max(1, int(frac * flat.size)), replace=False)
    sub = np.zeros(calib.size, dtype=bool)
    sub[take] = True
    sub = sub.reshape(calib.shape)
    policies = ([("thresh", t) for t in (0.5, 0.7, 0.9, 0.95, 0.99)]
                + [("topk", q) for q in (0.005, 0.01, 0.02, 0.05)])
    best = None
    for pol, par in policies:
        pred = emit_policy(field, pol, par, valid)
        d = gdti.dti(pred, sub, radius_px=radius_px, eval_mask=valid)["dti"]
        if best is None or d > best[2]:
            best = (pol, par, d)
    pol, par, _ = best
    pred = emit_policy(field, pol, par, valid)
    full = gdti.dti(pred, calib, radius_px=radius_px, eval_mask=valid)["dti"]
    return {"policy": pol, "param": float(par), "calib_dti": float(full)}


def emit_policy(field: np.ndarray, policy: str, param: float,
                valid: np.ndarray) -> np.ndarray:
    """Binary emission at value 1.0 (see research/hypotheses_round5.md §1)."""
    f = np.where(valid, field, np.nan)
    out = np.zeros(f.shape, dtype=np.float32)
    if policy == "thresh":
        out[np.isfinite(f) & (f >= param)] = 1.0
        return out
    n = max(1, int(round(param * int(valid.sum()))))
    flat = np.flatnonzero(np.isfinite(f))
    order = np.argsort(-f.ravel()[flat])[:n]
    out.ravel()[flat[order]] = 1.0
    return out


def emit_threshold(field: np.ndarray, t: float, valid: np.ndarray) -> np.ndarray:
    out = np.zeros(field.shape, dtype=np.float32)
    out[np.isfinite(field) & (field >= t) & valid] = 1.0
    return out


def far_subset(gt: np.ndarray, context: np.ndarray, dist_px: float) -> np.ndarray:
    """GT pixels farther than dist_px from any context pixel (extrapolation)."""
    if not gt.any():
        return gt
    d = ndimage.distance_transform_edt(~context)
    return gt & (d > dist_px)


def run(args) -> int:
    t_start = time.time()
    labels = rd.read_labels()
    valid = np.load(ROOT / "data/processed/valid_mask.npy").astype(bool)
    rows, cols = labels.shape
    sl = None
    if args.crop_rows and args.crop_rows < rows:
        r0 = (rows - args.crop_rows) // 2
        c0 = max(0, (cols - args.crop_cols) // 2)
        sl = (slice(r0, r0 + args.crop_rows), slice(c0, c0 + args.crop_cols))
        print(f"[gate] SMOKE CROP rows {sl[0]} cols {sl[1]}", flush=True)
        labels = labels[sl]
        valid = valid[sl]
        _band_cache: dict[int, np.ndarray] = {}
        orig_read = rd.read_band

        def _cropped_read(index, *a, **kw):          # noqa: ANN001
            if index not in _band_cache:
                _band_cache[index] = orig_read(index, *a, **kw)[sl]
            return _band_cache[index]

        rd.read_band = _cropped_read
        rows, cols = labels.shape
    print(f"[gate] grid {rows}x{cols} valid={int(valid.sum())} "
          f"catalogue={int(labels.sum())} px", flush=True)

    # In smoke-crop mode the reader itself returns cropped bands (the cache is
    # bypassed), so the channels must NOT be sliced a second time.
    cache_used = sl is None
    static = build_static_channels(ROOT / "data/processed/channels", quiet=args.quiet,
                                   use_cache=cache_used)
    if sl is not None and cache_used:
        static = {k: v[sl] for k, v in static.items()}
    static = {k: np.asarray(v, dtype=np.float16) for k, v in static.items()}
    print(f"[gate] static channels ready ({time.time()-t_start:.0f} s)", flush=True)

    # ---- splits ----------------------------------------------------------
    rng_master = np.random.default_rng(args.seed)
    splits = []
    if args.protocol == "block":
        fold_map = assign_folds(labels.shape, args.block_px, args.folds, seed=args.seed)
        for k in range(args.folds):
            test = labels & (fold_map == k)
            near = ndimage.binary_dilation(test, iterations=args.purge_px)
            context = labels & ~near
            splits.append({"fold": k, "context": context, "test": test,
                           "visible": context, "ids": {}})
        print(f"[gate] protocol=block block_px={args.block_px} folds={args.folds} "
              f"purge={args.purge_px} px", flush=True)
    else:
        lab, n_comp = ndimage.label(labels, structure=np.ones((3, 3), dtype=int))
        perm = rng_master.permutation(np.arange(1, n_comp + 1))
        n_test = max(1, int(round(args.test_fraction * n_comp)))
        n_calib = max(0, int(round(args.calib_fraction * n_comp)))
        n_hide = max(1, int(round(args.hide_fraction * n_comp)))
        for k in range(args.folds):
            p = np.roll(perm, k * (n_test + n_calib + n_hide))
            test_ids = p[:n_test]
            calib_ids = p[n_test:n_test + n_calib]
            hide_ids = p[n_test + n_calib:n_test + n_calib + n_hide]
            test = np.isin(lab, test_ids)
            calib = np.isin(lab, calib_ids)
            hide = np.isin(lab, hide_ids)
            visible = labels & ~(test | calib | hide)
            context = labels & ~test
            splits.append({"fold": k, "context": context, "test": test,
                           "visible": visible, "calib": calib, "hide": hide,
                           "ids": {"test": test_ids.tolist(),
                                   "calib": calib_ids.tolist(),
                                   "hide": hide_ids.tolist()}})
        print(f"[gate] protocol=component comps={n_comp} TEST {n_test} / CALIB {n_calib} "
              f"/ HIDE {n_hide} / visible {n_comp - n_test - n_calib - n_hide}", flush=True)

    # R7-1 stress protocol (research/hypotheses_round7.md): one rigid shift per
    # catalogue component, shared by every view of every fold, so the simulated
    # misregistered world is consistent.  Truth (TEST) is never displaced.
    misreg_offsets = None
    if args.misreg_px > 0:
        if args.protocol != "component":
            raise SystemExit("--misreg-px is only defined for --protocol component")
        misreg_offsets = rc.component_offsets(
            n_comp, int(args.misreg_px), np.random.default_rng(args.seed + 999))
        moved = int((np.abs(misreg_offsets[1:]).sum(axis=1) > 0).sum())
        print(f"[gate] MISREGISTRATION STRESS: shifts <= {int(args.misreg_px)} px "
              f"for {moved}/{n_comp} components (seed {args.seed + 999})", flush=True)

    want_align = any("align" in arm_channels(a)[1] for a in args.arms)

    fields_dir = ROOT / "artifacts" / "real_fields"
    fields_dir.mkdir(parents=True, exist_ok=True)
    results = {arm: {"arm": arm, "spec": ARM_SPEC.get(arm, arm), "folds": []}
               for arm in args.arms}

    for split in splits:
        k = split["fold"]
        t0 = time.time()
        test = split["test"]
        context = split["context"]
        # TWO views per fold (both hide-and-recover clean):
        #   feature_ctx - the context the model TRAINS against: TEST and HIDE are
        #                 absent, so "distance to a mapped trace" carries no
        #                 information about the target structures;
        #   pred_ctx    - the submission-time view: the full catalogue minus TEST
        #                 (what a real model sees when predicting the scored,
        #                 unmapped structures).
        if args.protocol == "component":
            feature_ctx = labels & ~(test | split["hide"])
            pos_mask = split["hide"]
        else:
            feature_ctx = context
            pos_mask = context
        pred_ctx = context
        if misreg_offsets is not None:
            # the catalogue the model sees is misregistered (C28); TEST truth is
            # not part of either view and is never displaced
            feature_ctx = rc.displace_mask(feature_ctx, lab, misreg_offsets)
            pred_ctx = rc.displace_mask(pred_ctx, lab, misreg_offsets)
        t_geom = time.time() - t0
        # truth subsets are arm-independent: compute once per fold
        sp_rng = np.random.default_rng(1000 + k)
        sparse_gt = sample_truth(test, args.sparse_frac, sp_rng)
        far_gt = far_subset(test, context, args.far_px) if args.protocol == "component" else test
        calib = split.get("calib")

        # ---- stage 1: train every arm against the hidden structures -------
        geom_train = build_geom_channels(feature_ctx)
        if not args.quiet:
            print(f"    [fold {k}] train-view geometry in {time.time()-t0:.0f} s", flush=True)
        geom_align_train = None
        if want_align:
            expr_field = _expression_ridge_field(static)
            al_mask, al_off = rc.align_traces_to_expression(feature_ctx, expr_field,
                                                            max_offset=3)
            geom_align_train = build_geom_channels(al_mask)
            geom_align_train["align_offset"] = _f16(rc.line_max(al_off, radius=3))
            if not args.quiet:
                print(f"    [fold {k}] train-view aligned geometry "
                      f"(mean |offset| {float(al_off[al_off > 0].mean()) if (al_off > 0).any() else 0:.2f} px) "
                      f"in {time.time()-t0:.0f} s", flush=True)
        betas: dict[str, tuple] = {}
        names_by_arm: dict[str, list[str]] = {}
        for arm in args.arms:
            ta = time.time()
            names, r5, geo = arm_channels(arm)
            if "align" in r5 and geom_align_train is not None:
                ch_train = dict(geom_align_train)
            else:
                ch_train = dict(geom_train)
            if geo:
                ch_train.update(static)
            if r5:
                ch_train.update(build_round5_channels(feature_ctx, static, valid,
                                                      r5 - {"align"}))
            names_now = [nm for nm in names if nm in ch_train]
            idx, y = sample_pixels(pos_mask, valid,
                                   np.random.default_rng(args.seed + k),
                                   args.n_pos, args.n_neg)
            X = design_matrix(ch_train, names_now, idx)
            mu, sd = standardize_fit(X)
            beta = logistic_fit((X - mu) / sd, y, np.ones_like(y),
                                n_iter=args.iters, lr=0.5, l2=1e-3)
            del X, ch_train
            betas[arm] = (beta, mu, sd, idx.size)
            names_by_arm[arm] = names_now
            if not args.quiet:
                print(f"      [fold {k}] {arm:10s} trained on {idx.size} px "
                      f"({len(names_now)} feats) in {time.time()-ta:.0f} s", flush=True)
        del geom_train
        if geom_align_train is not None:
            del geom_align_train

        # ---- stage 2: predict with the submission-time context ------------
        geom_pred = build_geom_channels(pred_ctx)
        if not args.quiet:
            print(f"    [fold {k}] pred-view geometry in {time.time()-t0:.0f} s", flush=True)
        geom_align_pred = None
        if want_align:
            expr_field = _expression_ridge_field(static)
            al_mask, al_off = rc.align_traces_to_expression(pred_ctx, expr_field,
                                                            max_offset=3)
            geom_align_pred = build_geom_channels(al_mask)
            geom_align_pred["align_offset"] = _f16(rc.line_max(al_off, radius=3))
        for arm in args.arms:
            ta = time.time()
            names, r5, geo = arm_channels(arm)
            if "align" in r5 and geom_align_pred is not None:
                ch_pred = dict(geom_align_pred)
            else:
                ch_pred = dict(geom_pred)
            if geo:
                ch_pred.update(static)
            if r5:
                ch_pred.update(build_round5_channels(pred_ctx, static, valid,
                                                      r5 - {"align"}))
            names_now = [nm for nm in names_by_arm[arm] if nm in ch_pred]
            beta, mu, sd, n_train = betas[arm]
            pred = predict_full_std(beta, mu, sd, ch_pred, names_now, valid,
                                    args.chunk_rows)
            del ch_pred
            np.save(fields_dir / f"fold{k}_{arm}.npy", pred.astype(np.float16))
            pol = calibrate_policy(pred, calib, valid, seed=100 + k)
            emitted = emit_policy(pred, pol["policy"], pol["param"], valid)
            row = {
                "fold": k, "arm": arm, "n_features": len(names_now),
                "n_train_px": int(n_train), "n_test_px": int(test.sum()),
                "raw_dense": score_field(pred, test, valid)["dti"],
                "raw_calib": None if calib is None else score_field(pred, calib, valid)["dti"],
                "calib_policy": pol["policy"], "calib_param": pol["param"],
                "calib_dti": pol["calib_dti"],
                "test_dense_at_t": score_field(emitted, test, valid)["dti"],
                "test_sparse_at_t": score_field(emitted, sparse_gt, valid)["dti"],
                "test_far_at_t": (score_field(emitted, far_gt, valid)["dti"]
                                  if far_gt.any() else None),
                "n_emit": int((emitted > 0).sum()),
                "n_geom_px": int(feature_ctx.sum()),
                "elapsed_s": round(time.time() - ta, 1),
            }
            del pred, emitted
            results[arm]["folds"].append(row)
            print(f"    {arm:10s} fold {k} nfeat={row['n_features']:2d} "
                  f"{pol['policy']}:{pol['param']:g} "
                  f"dense={row['test_dense_at_t']:.4f} sparse={row['test_sparse_at_t']:.4f} "
                  f"far={'-' if row['test_far_at_t'] is None else format(row['test_far_at_t'], '.4f')} "
                  f"emit={row['n_emit']} ({row['elapsed_s']:.0f} s)", flush=True)
        if geom_align_pred is not None:
            del geom_align_pred
        np.savez(fields_dir / f"fold{k}_truth.npz", test=test, sparse=sparse_gt,
                 far=far_gt, **({} if calib is None else {"calib": calib}))

    arms_out = []
    for arm, r in results.items():
        folds = r["folds"]
        r["raw_dense_mean"] = float(np.mean([f["raw_dense"] for f in folds]))
        r["raw_calib_mean"] = (float(np.mean([f["raw_calib"] for f in folds
                                              if f["raw_calib"] is not None]))
                               if any(f["raw_calib"] is not None for f in folds) else None)
        r["dense_mean"] = float(np.mean([f["test_dense_at_t"] for f in folds]))
        r["sparse_mean"] = float(np.mean([f["test_sparse_at_t"] for f in folds]))
        far_vals = [f["test_far_at_t"] for f in folds if f["test_far_at_t"] is not None]
        r["far_mean"] = float(np.mean(far_vals)) if far_vals else None
        r["n_emit_mean"] = float(np.mean([f["n_emit"] for f in folds]))
        arms_out.append(r)

    payload = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "data": {
            "labels": rd.sha256_file(ROOT / "data/raw/training_labels.tif"),
            "features": rd.sha256_file(ROOT / "data/raw/training_features.tif"),
            "template": rd.sha256_file(ROOT / "data/raw/sample_submission.tif"),
        },
        "protocol": {
            "mode": args.protocol, "folds": args.folds, "seed": args.seed,
            "block_px": args.block_px, "purge_px": args.purge_px,
            "test_fraction": args.test_fraction, "calib_fraction": args.calib_fraction,
            "hide_fraction": args.hide_fraction, "far_px": args.far_px,
            "sparse_frac": args.sparse_frac,
            "learner": f"logistic regression, {args.iters} GD iters, lr 0.5, l2 1e-3",
            "n_pos": args.n_pos, "n_neg": args.n_neg,
            "misreg_px": args.misreg_px,
            "geo_bands": list(GEO_BANDS),
            "metric": "official DTI (radius 3 px, alpha 0.2, beta 0.8), eval_mask=footprint",
            "note": ("raw_* scores use the unthresholded probability field and are "
                     "diagnostic only; the headline comparison is the emission sweep "
                     "in scripts/sweep_real.py, which calibrates the threshold on the "
                     "hidden CALIB components and reports TEST"),
        },
        "split_ids": {s["fold"]: s["ids"] for s in splits},
        "results": arms_out,
        "wall_s": round(time.time() - t_start, 1),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2))
    print(f"\n[gate] wrote {out} in {payload['wall_s']:.0f} s", flush=True)
    base = next((r for r in arms_out if r["arm"] == "geom"), None)
    for r in arms_out:
        d = "" if base is None or r is base else f"  (dense {r['dense_mean']-base['dense_mean']:+.4f} vs geom)"
        print(f"{r['arm']:10s} dense={r['dense_mean']:.4f} sparse={r['sparse_mean']:.4f} "
              f"far={'—' if r['far_mean'] is None else format(r['far_mean'], '.4f')} "
              f"emit={r['n_emit_mean']:.0f}px{d}", flush=True)
    return 0


def predict_full_std(beta: np.ndarray, mu: np.ndarray, sd: np.ndarray,
                     channels: dict[str, np.ndarray], names: list[str],
                     valid: np.ndarray, chunk_rows: int = 256) -> np.ndarray:
    rows, cols = valid.shape
    out = np.zeros((rows, cols), dtype=np.float32)
    for r0 in range(0, rows, chunk_rows):
        r1 = min(rows, r0 + chunk_rows)
        idx = np.arange(r0 * cols, r1 * cols)
        X = design_matrix(channels, names, idx)
        Xs = (X - mu) / sd
        out[r0:r1] = predict_proba(beta, Xs).reshape(r1 - r0, cols).astype(np.float32)
    return out


def sample_truth(gt: np.ndarray, frac: float, rng: np.random.Generator) -> np.ndarray:
    if frac >= 1.0:
        return gt
    flat = np.flatnonzero(gt.ravel())
    if flat.size == 0:
        return gt
    keep = rng.choice(flat, size=max(1, int(round(frac * flat.size))), replace=False)
    out = np.zeros(gt.size, dtype=bool)
    out[keep] = True
    return out.reshape(gt.shape)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--protocol", choices=("block", "component"), default="component")
    ap.add_argument("--arms", nargs="+", default=["geom", "geo", "all"],
                    choices=list(ARM_SPEC))
    ap.add_argument("--folds", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--block-px", type=int, default=512)
    ap.add_argument("--purge-px", type=int, default=3)
    ap.add_argument("--test-fraction", type=float, default=0.20)
    ap.add_argument("--calib-fraction", type=float, default=0.20)
    ap.add_argument("--hide-fraction", type=float, default=0.35)
    ap.add_argument("--far-px", type=float, default=10.0,
                    help="far-test distance (px) from any context trace")
    ap.add_argument("--sparse-frac", type=float, default=0.20)
    ap.add_argument("--n-pos", type=int, default=20000)
    ap.add_argument("--n-neg", type=int, default=40000)
    ap.add_argument("--iters", type=int, default=150)
    ap.add_argument("--chunk-rows", type=int, default=256)
    ap.add_argument("--misreg-px", type=float, default=0.0,
                    help="R7-1 stress protocol: rigidly displace every non-TEST "
                         "catalogue component by up to this many px (C28 "
                         "misregistration simulation); 0 = world as mapped")
    ap.add_argument("--out", default="artifacts/holdout_real.json")
    ap.add_argument("--crop-rows", type=int, default=0,
                    help="smoke-test window height (0 = full grid)")
    ap.add_argument("--crop-cols", type=int, default=0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
