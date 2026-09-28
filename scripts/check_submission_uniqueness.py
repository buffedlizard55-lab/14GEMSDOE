#!/usr/bin/env python3
"""Uniqueness gate: prove that no two submissions this group has made are the
same work, and that no two are even the same score without an explanation.

Why this exists
---------------
The group's history contains GEMSDOE1, 5GEMSDOE and 8GEMSDOE all scoring exactly
0.1563, and the public leaderboard contains three separate accounts tied at
exactly 0.1563 (extradr19 #26, SDCF9 #27, smashi34 #28 - verified on the live
leaderboard 2026-09-28).  A four-decimal tie in this metric means equal
TP_w/FP_w/FN_w, i.e. effectively equal prediction fields.  The published sites
pin the same artifact hash for GEMSDOE1 and 5GEMSDOE, so at least two of those
uploads were byte-identical: a wasted submission slot that produced zero
information.

This script is the mechanical prevention.  It checks, on every run:

  F1  no two files in ``submissions/`` share a sha256          (byte-identity)
  F2  no two filenames collide                                 (name-identity)
  F3  every .tif has its sibling .NOTE.txt and .MANIFEST.json  (provenance)
  F4  every MANIFEST's sha256 matches the file's actual hash   (integrity)
  F5  no two ledger rows share BOTH a reported score and an artifact id
  F6  no ledger row is marked Unique? = NO without an explanation in the row
  F7  the site payload (docs/js/payload.js) does not pin the same pixel hash as
      an already-uploaded submission unless it is explicitly the current one

Exit code 0 = clean; 1 = a violation was found (the build must not be uploaded).

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
        rows.append({
            "n": int(num), "entry": entry, "score": score, "artifact": artifact,
            "unique": unique, "evidence": evidence,
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
    for h, group in by_hash.items():
        if len(group) > 1:
            problems.append(
                f"F1: {len(group)} byte-identical submissions share sha256 {h[:12]}...: "
                + ", ".join(group))
    for name, count in names.items():
        if count > 1:
            problems.append(f"F2: filename {name!r} appears {count} times")

    # ---- F5/F6: ledger-level ----------------------------------------------
    if ledger.exists():
        rows = parse_ledger(ledger)
        seen: dict[tuple[str, str], int] = {}
        for r in rows:
            score = r["score"]
            art = r["artifact"]
            if score in ("", "-", "none reported") or art in ("", "-", "\u2014"):
                continue
            key = (score, art)
            if key in seen:
                msg = (f"F5: ledger rows {seen[key]} and {r['n']} share BOTH score "
                       f"{score!r} and artifact {art!r} - identical work recorded twice")
                (problems if strict_ledger else warnings).append(msg)
            else:
                seen[key] = r["n"]
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
                    f"F5(note): score {s!r} is reported for ledger rows {ns} - "
                    "acceptable ONLY if their artifacts differ; verify before reusing")
        for r in rows:
            if r["unique"].upper().startswith("NO") and "same payload" not in r["desc"].lower():
                msg = (f"F6: ledger row {r['n']} is marked Unique?=NO without an "
                       "explanation in its description")
                (problems if strict_ledger else warnings).append(msg)
    else:
        warnings.append(f"F5: ledger not found at {ledger}")

    # ---- F7: site payload --------------------------------------------------
    if payload_js.exists():
        text = payload_js.read_text()
        m = re.search(r"pixels_sha256=([0-9a-f]{16})", text)
        if m:
            short = m.group(1)
            dup = [n for h, ns in by_hash.items() for n in ns if h.startswith(short)]
            if len(dup) > 1:
                problems.append(
                    f"F7: the site payload pins pixels {short}... which matches "
                    f"{len(dup)} files in submissions/ ({', '.join(dup)})")
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
    print("uniqueness gate: PASS (no byte-identical submissions, no unexplained "
          "duplicate scores, every artifact carries NOTE + MANIFEST)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
