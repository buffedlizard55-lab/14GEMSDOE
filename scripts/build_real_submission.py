#!/usr/bin/env python3
"""Turn the real-data gate's fields into one uploadable submission.

The gate (`scripts/validate_real.py`) writes, for every fold `k` and arm, the
probability field predicted from the *submission-time* context (the full
catalogue minus that fold's TEST components).  Those four models are trained
against four different hidden subsets, so their average is a hide-and-recover
ensemble: every training run was blind to ~55 % of the catalogue.

This script

  1. selects the arm by the pre-registered rule (beats the baseline on both the
     sparse and the far protocol in >= 3 of 4 folds; ties broken by `far`),
  2. averages the four fold fields,
  3. emits the binary support at the *calibrated* emission budget (the median of
     the per-fold fractions chosen on the hidden CALIB components),
  4. hands the emission to `scripts/build_submission.py`, which clamps, writes
     the GeoTIFF on the template grid, runs the format gate, and names the file
     uniquely (`GEMS_<policy>_<UTC>_<sha8>.tif` + NOTE + MANIFEST).

No slot is spent by this script: it only produces the artifact and its note.

Usage:
    ./.venv/bin/python scripts/build_real_submission.py --arm all
    ./.venv/bin/python scripts/build_real_submission.py            # auto-select
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gems import realdata as rd  # noqa: E402

NOTE_TEMPLATE = (
    "real-data hide-and-recover ensemble ({arm}); features: catalogue geometry + "
    "12 official bands{extra}; emission = top {q:.2%} by probability, budget "
    "calibrated on held-out catalogue components (far-protocol {far}); valid "
    "[0,1] float32 on the official grid, no NaN inside the footprint"
)


def select_arm(gate: dict) -> tuple[str, dict]:
    rows = {r["arm"]: r for r in gate["results"]}
    if "geom" not in rows:
        raise SystemExit("gate JSON has no 'geom' baseline row")
    base = rows["geom"]
    n = len(base["folds"])
    need = max(1, int(np.ceil(0.75 * n)))
    best = None
    for arm, r in rows.items():
        if arm == "geom":
            continue
        wins_sparse = sum(1 for f, b in zip(r["folds"], base["folds"])
                          if f["test_sparse_at_t"] > b["test_sparse_at_t"])
        wins_far = sum(1 for f, b in zip(r["folds"], base["folds"])
                       if (f["test_far_at_t"] or 0.0) > (b["test_far_at_t"] or 0.0))
        eligible = wins_sparse >= need and wins_far >= need
        score = (r.get("far_mean") or 0.0, r.get("sparse_mean") or 0.0)
        cand = {"arm": arm, "wins_sparse": wins_sparse, "wins_far": wins_far,
                "eligible": bool(eligible), "far_mean": r.get("far_mean"),
                "sparse_mean": r.get("sparse_mean"), "n_folds": n}
        if cand["eligible"]:
            if best is None or score > best[1]:
                best = (arm, score, cand)
    if best is None:
        return "geom", {"arm": "geom", "eligible": False,
                        "reason": "no arm beat the baseline on both protocols"}
    return best[0], best[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", default="artifacts/holdout_real.json")
    ap.add_argument("--fields-dir", default="artifacts/real_fields")
    ap.add_argument("--arm", default="")
    ap.add_argument("--outdir", default="submissions")
    ap.add_argument("--emission", default="artifacts/real_emission_ensemble.npy")
    ap.add_argument("--budget", type=float, default=None,
                    help="override the emission budget (fraction of valid px). "
                         "Default: median of the per-fold CALIB-chosen fractions. "
                         "An override must carry its provenance in the note — the "
                         "pre-registered one is the fine-grid CALIB dense-optimal "
                         "(official marginal economics, hypotheses_round7.md §5).")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    gate = json.loads((ROOT / args.gate).read_text())
    rationale = {}
    arm = args.arm
    if not arm:
        arm, rationale = select_arm(gate)
    rows = {r["arm"]: r for r in gate["results"]}
    if arm not in rows:
        raise SystemExit(f"arm {arm!r} not in the gate JSON")
    folds = rows[arm]["folds"]
    valid = np.load(ROOT / "data/processed/valid_mask.npy").astype(bool)

    fields = []
    for f in folds:
        p = ROOT / args.fields_dir / f"fold{f['fold']}_{arm}.npy"
        if not p.exists():
            raise SystemExit(f"missing field {p}: the gate must finish first")
        arr = np.load(p).astype(np.float32)
        if arr.shape != valid.shape:
            raise SystemExit(
                f"field {p} has shape {arr.shape}, expected {valid.shape} — "
                f"a smoke-crop run contaminated the field cache; re-run the "
                f"gate at full grid before building a submission")
        fields.append(arr)
    field = np.mean(fields, axis=0)
    print(f"[submission] arm={arm} folds={len(fields)} "
          f"rationale={rationale or 'caller-specified'}", flush=True)

    # calibrated budget: median of the per-fold fractions chosen on CALIB,
    # unless an explicit --budget override with recorded provenance is given
    fracs = []
    for f in folds:
        if f["calib_policy"] == "topk":
            fracs.append(float(f["calib_param"]))
        else:                                    # threshold policy -> its mass
            n = int(f.get("n_emit", 0))
            fracs.append(n / float(valid.sum()))
    if args.budget is not None:
        q = float(args.budget)
        extra_note = (f"; emission budget {q:.6f} is an explicit override "
                      f"(fine-grid CALIB dense-optimal, median of per-fold "
                      f"optima — official marginal economics)")
    else:
        q = float(np.median(fracs))
        extra_note = ""
    n_emit = max(1, int(round(q * int(valid.sum()))))
    flat = np.flatnonzero(valid & np.isfinite(field))
    order = np.argsort(-field.ravel()[flat])[:n_emit]
    pred = np.zeros(field.shape, dtype=np.float32)
    pred.ravel()[flat[order]] = 1.0
    print(f"[submission] emission budget q={q:.5f} -> {n_emit} px "
          f"({n_emit/valid.sum():.5%} of the footprint)", flush=True)
    out = ROOT / args.emission
    out.parent.mkdir(parents=True, exist_ok=True)
    np.save(out, pred)
    print(f"[submission] wrote {out}", flush=True)

    extra = ""
    if "acc" in arm or arm == "all":
        extra = " + R5-2 accommodation corridors"
    if "tilt" in arm or arm == "all":
        extra += " + R5-3 magnetic tilt angle"
    if "ramp" in arm or arm == "all":
        extra += " + R5-1 relay-ramp interior"
    far_mean = rows[arm].get("far_mean")
    note = NOTE_TEMPLATE.format(arm=arm, extra=extra, q=q,
                                far="n/a" if far_mean is None else f"{far_mean:.4f}")
    note += extra_note
    (ROOT / "artifacts" / "real_submission_note.txt").write_text(note + "\n")
    print(f"[submission] note: {note}", flush=True)

    if args.dry_run:
        return 0
    cmd = [sys.executable, str(ROOT / "scripts" / "build_submission.py"), str(out),
           "--policy", f"r5 real-data ensemble {arm}",
           "--policy-name", f"r5-{arm}-ensemble",
           "--note", note, "--outdir", args.outdir, "--zero-outside"]
    print("[submission] " + " ".join(cmd), flush=True)
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
