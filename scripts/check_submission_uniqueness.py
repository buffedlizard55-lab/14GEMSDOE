#!/usr/bin/env python3
"""Audit submission artifacts and prevent exact prediction re-uploads.

A leaderboard score rounded to four decimals does NOT prove identical
predictions. The published GEMSDOE1 and 5GEMSDOE pages show matching truncated
artifact/payload metadata, but this repo lacks their original upload files and
DrivenData submission IDs. Treat score collisions as provenance-review prompts,
not duplicate-file findings.

Checks:
  F1  no byte-identical GeoTIFF files
  F2  no filename collisions
  F3  each GeoTIFF has its NOTE and MANIFEST
  F4  manifest file sha256 matches actual bytes
  F5  warns on repeated rounded scores / ledger fingerprints (not a hard error)
  F6  warns on an unexplained ledger `NO` marker
  F7  compares exact prediction-array hashes in manifests with the current site
      payload hash (when both are present)
  F8  no two manifests share the same prediction-array hash

Exit code 0 means no proven artifact duplication or integrity failure was
found. Missing historical upload records remain an audit limitation.
""

Usage:
    python3 scripts/check_submission_uniqueness.py
    python3 scripts/check_submission_uniqueness.py --submissions submissions \\
            --ledger research/results_ledger.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


LEDGER_ROW = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")


def parse_ledger(path: Path) -> list[dict]:
    """Parse the results-ledger table into rows (score + artifact + unique flag)."""
    rows = []
    for line in path.read_text().splitlines():
        m = LEDGER_ROW.match(line)
        if not m:
            continue
        num, entry, score, desc, artifact, unique, evidence = (g.strip() for g in m.groups())
        if not num.isdigit():
            continue
        if score.strip().lower() in {"none reported", "(none reported)", "n/a"}:
            score = ""
        rows.append({
            "n": int(num), "entry": entry, "score": score, "desc": desc,
            "artifact": artifact, "unique": unique, "evidence": evidence,
        })
    return rows


def check(submissions: Path, ledger: Path, payload_js: Path,
          strict_ledger: bool = False) -> tuple[list[str], list[str]]:
    """Return (hard_problems, ledger_warnings)."""
    problems: list[str] = []
    warnings: list[str] = []

    # ---- F1/F2/F3/F4: file-level ------------------------------------------
    tifs = sorted(submissions.glob("*.tif"))
    by_hash: dict[str, list[str]] = {}
    by_prediction_hash: dict[str, list[str]] = {}
    names: dict[str, int] = {}
    for t in tifs:
        names[t.name] = names.get(t.name, 0) + 1
        by_hash.setdefault(sha256_file(t), []).append(t.name)
        note = submissions / (t.stem + ".NOTE.txt")
        man = submissions / (t.stem + ".MANIFEST.json")
        if not note.exists():
            problems.append(f"F3: {t.name} has no sibling .NOTE.txt")
        if not man.exists():
            problems.append(f"F3: {t.name} has no sibling .MANIFEST.json")
        else:
            try:
                meta = json.loads(man.read_text())
            except json.JSONDecodeError as e:
                problems.append(f"F4: {man.name} is not valid JSON ({e})")
                continue
            actual = sha256_file(t)
            if meta.get("sha256") and meta["sha256"] != actual:
                problems.append(
                    f"F4: {t.name} manifest sha256 {meta['sha256'][:12]}... != actual "
                    f"{actual[:12]}...")
            prediction_hash = meta.get("prediction_sha256")
            if prediction_hash:
                by_prediction_hash.setdefault(str(prediction_hash), []).append(t.name)
    for h, group in by_hash.items():
        if len(group) > 1:
            problems.append(
                f"F1: {len(group)} byte-identical submissions share sha256 {h[:12]}...: "
                + ", ".join(group))
    for h, group in by_prediction_hash.items():
        if len(group) > 1:
            problems.append(
                f"F8: {len(group)} submissions share the same prediction-array hash "
                f"{h[:12]}...: " + ", ".join(group))
    for name, count in names.items():
        if count > 1:
            problems.append(f"F2: filename {name!r} appears {count} times")

    # ---- F5/F6: ledger-level ----------------------------------------------
    if ledger.exists():
        rows = parse_ledger(ledger)
        seen_artifacts: dict[str, int] = {}
        for r in rows:
            artifact = r["artifact"].strip().strip("`* ")
            if artifact in ("", "-", "—", "–"):
                continue
            if artifact in seen_artifacts:
                warnings.append(
                    f"F5: ledger rows {seen_artifacts[artifact]} and {r['n']} share "
                    f"artifact fingerprint {artifact!r}; it may be a truncated hash "
                    "or a reused output ID. Compare full TIFF and prediction-array "
                    "hashes before claiming identity.")
            else:
                seen_artifacts[artifact] = r["n"]
        # a repeated score with a DIFFERENT (or absent) artifact is suspicious
        by_score: dict[str, list[int]] = {}
        for r in rows:
            s = r["score"]
            if s in ("", "-", "none reported"):
                continue
            by_score.setdefault(s, []).append(r["n"])
        for s, ns in by_score.items():
            if len(ns) > 1:
                warnings.append(
                    f"F5(note): rounded score {s!r} appears in ledger rows {ns}; "
                    "a score match alone cannot establish artifact identity. Compare "
                    "full prediction-array hashes where available.")
        for r in rows:
            if r["unique"].upper().startswith("NO") and "same payload" not in r["desc"].lower():
                msg = (f"F6: ledger row {r['n']} is marked Unique?=NO without an "
                       "explanation in its description")
                (problems if strict_ledger else warnings).append(msg)
    else:
        warnings.append(f"F5: ledger not found at {ledger}")

    # ---- F7: compare like-for-like array hashes, never TIFF hashes ----------
    if payload_js.exists():
        text = payload_js.read_text()
        m = re.search(r"pixels_sha256=([0-9a-f]{16,64})", text)
        if m:
            short = m.group(1)
            dup = [name for h, group in by_prediction_hash.items()
                   if h.startswith(short) for name in group]
            if dup:
                problems.append(
                    f"F7: site payload pixel hash {short}... matches prediction-array "
                    f"hash in {len(dup)} submission manifest(s): {', '.join(dup)}")
    return problems, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--submissions", default="submissions")
    ap.add_argument("--ledger", default="research/results_ledger.md")
    ap.add_argument("--payload", default="docs/js/payload.js")
    ap.add_argument("--strict-ledger", action="store_true",
                    help="treat ledger duplicates (F5/F6) as hard failures")
    args = ap.parse_args()

    problems, warnings = check(Path(args.submissions), Path(args.ledger),
                               Path(args.payload), strict_ledger=args.strict_ledger)
    if warnings:
        print("ledger warnings (history, not the current build):")
        for w in warnings:
            print("  ! " + w)
        print()
    if problems:
        print("UNIQUENESS GATE FAILED - do not upload anything from this state:\n")
        for p in problems:
            print("  - " + p)
        return 1
    print("uniqueness audit: PASS (no proven duplicate TIFF/prediction arrays or "
          "manifest-integrity failures; score ties are review warnings only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
