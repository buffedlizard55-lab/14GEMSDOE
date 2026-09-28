# Limitations & next steps — the working queue

Updated 2026-09-28 (round-3 session, 14GEMSDOE). Ordered by "what most raises
P(win) per unit effort". Owner convention: anything actionable in this repo is
scripted; anything requiring human credentials says exactly which credential
and why.

## Round-3 outcome in one line

`scripts/validate_round3.py` gated five new candidates + two incumbent stacks +
one prior-channel follow-up against the TRUE round-2 incumbent (BMUL 0.3842,
reproduced exactly): **the incumbent stands; all R3 arms were killed; the
prior-extensibility test was exactly null, establishing that the multiplicative
prior cannot extend the classifier's support.** No submission slot was spent.
Full record: `research/hypotheses_round3.md`. This session's corrections:
team-reported submission-form NaN rejection (T9/FLAG #10) remains unverified
end-to-end here; Dropbox data links are reclassified as team-provided, unverified
shares, not official mirrors; four Round-4 candidates were pre-registered without
claiming holdout validation. Leaderboard checked live 2026-09-28. Dependencies
were installed into ignored `.venv/`; current suite result is 102 passed. No
real competition data was present, so these tests do not validate leaderboard
performance.

## A. Blockers

| # | Blocker | Why it blocks | Action | Status |
|---|---------|---------------|--------|--------|
| B1 | Competition data not in `data/raw/` | no real features/labels/template ⇒ no real holdout numbers | The Dropbox links supplied in the brief can be attempted with `bash scripts/download_competition_data.sh`, but their official provenance and binary contents are unverified. Confirm all downloaded files against the authenticated DrivenData data tab and official grid/band metadata before `prepare_data.py` or any training. | blocker; requires authorized source files (official data tab login-gated); sandbox cannot fetch Dropbox binaries |
| B2 | Sandbox TLS policy blocks binary downloads (FLAG #1, re-measured 2026-09-28T09:1xZ: allowlist unchanged) | external INGENIOUS/ScienceBase layers and DEM tiles must be fetched elsewhere | run `scripts/download_external_data.sh` + the `1m_DEM_links.csv` fetch on an unrestricted machine | scripted; needs unrestricted machine |
| B3 | No GPU in this environment | U-Net (reference-solution class) training is slow to impossible | train logistic baseline for protocol work; port U-Net on GPU box; protocol unchanged | environmental — **now the binding constraint after the round-3 support-extensibility null** |
| B4 | ~~Band order unpublished~~ **RESOLVED (C23)**: per-band `description`/`data_category` tags; 15 of 19 named officially, 4 not (FLAG #6b) | feature naming for the real stack | read `src.tags(i)` for all 19 bands on arrival; `prepare_data.py` still refuses to guess | waits on B1 |

## B. Next-session work (in priority order)

1. **Land the data (B1), then re-run BOTH gates on the real rasters**
   (`scripts/validate_round2.py` and `scripts/validate_round3.py` run unchanged
   once `data/processed/` exists). Deliverable: the arm tables computed on real
   labels, BLEND-MUL re-measured as the incumbent; nothing may be uploaded
   until it does.
2. **Only then spend a weekly slot**, with
   `scripts/build_submission.py --policy "bmul w0.5 holdout<VALUE>"` and
   `scripts/check_submission_uniqueness.py` run first (exit 0 required).
   **Upload the FINITE (0.0-outside) file** — the NaN variant is known-rejected
   (T9/FLAG #10).
3. **R3E prior-overlap test first**: when the INGENIOUS slip/dilation raster
   lands, compute the pixel-level overlap between the tendency field and the
   classifier's confident support BEFORE any gate run (the round-3 null makes
   this the mandatory first step for every prior-extension proposal).
4. **Scale `strike_field` and `relay_corridors` to the full grid** (tiled
   convolutions; KD-tree pruning). Currently correct but tuned for ≤1k-component
   synthetic regions.
5. **U-Net port** (reference notebook) with hide-and-recover batches: hide
   components per sample rather than per epoch; keep the same hidden-recovery
   scoring; reference hyperparameters recorded (C24); the reference trains on
   the known-fault population with no masking (C25) — a floor to beat.
6. **Masking diagnostic slot** (S5-style catalogue-hedge probe) — only when the
   slot budget is otherwise unused; interpretation written *before* upload.
7. **Site payload swap:** after the first real validated submission,
   `build_site_payload.py submissions/GEMS_….tif` and confirm the banner flips
   from DEMO to the real artifact hash.
8. **Leaderboard feed:** schedule `scripts/refresh_leaderboard.py` (locally or
   via GitHub Action on a runner with network) so the snapshot stays current.

## C. Irregularities flagged for human review

1. **FLAG #1 — sandbox network policy, RE-MEASURED (T8).** From bash, only
   pypi.org, files.pythonhosted.org, github.com, api.github.com,
   codeload.github.com and registry.npmjs.org complete a TLS handshake.
   drivendata.org, gdr.openei.org, sciencebase.gov, usgs.gov, doi.org,
   dropbox.com, zenodo.org, raw.githubusercontent.com all fail with
   `SSL_ERROR_SYSCALL`. The Arena `fetch_page` / `web_search` tools DO reach
   them, so all external pages cited in `knowledge_base.md` were verified
   through those tools. Consequence: **the official reference-solution repo is
   now obtainable in-sandbox** (cloned via codeload, tarball sha256
   `05a32550365aef3…`) — that is how C24/C25 were verified. Binary data files
   (Dropbox mirrors of `example_submission.tif` / `existing_faults.tif`, GDR
   file downloads, DEM tiles) still cannot be fetched here and were NOT
   re-hashed; the download scripts hash whatever they fetch.
2. **FLAG #1b — no free official paleo-shoreline dataset has been sourced yet.**
   This blocks hypothesis N4 (lidar scarp + shoreline suppression). Named
   candidates to check: USGS ScienceBase GeoDAWN item 657e1d85d34e23d3533209f7
   (DOI 10.5066/P93LGLVQ) and NBMG lake-level publications. **N4 must not be
   promoted to a slot until a verified source exists.**
3. **FLAG #1c — the competition's 19-band stack has 4 bands whose names are not
   published** (15 are enumerated officially, C27). The figure caption mentions
   total radiometric counts, so radiometrics are in the stack. Read the band tags
   on arrival; do not guess.
4. **FLAG #2 — Faulds percentage vintage drift** (32/22/22/8 in 2012 vs
   25/20/18/7 later). Brief numbers kept as primary; hypotheses robust to both.
   **Round-2 adds the 2026 vintage (S8–S10): 39.6/26.1/16.7/6.8 for FSS counts,
   27.5/22.1/16.6/5.7 for the 403 known systems — all VERIFIED.**
5. **FLAG #3 — stale brief figure "0.3049 is the highest score"**: live top on
   2026-09-28 is 0.3168 (DARD); live top 5 recorded in T7 and re-verified in
   T11 (09:22Z). 0.3049 not in the top 50.
6. **FLAG #4 — "geothermal vents" wording**: the scored target is faults.
   Vents (GDR volcanics layer) are used only as an independent structure proxy.
7. **FLAG #5 — masking semantics ambiguity** (C11). Staff wrote: "Pixels
   corresponding to known USGS/INGENIOUS faults are masked / excluded from
   evaluation, so they do not count towards penalty terms" and "it should not
   matter whether these known faults are included with predictions or not".
   That sentence is satisfied by FP-side-only masking as well as by both-sides
   masking, so the ambiguity is **not** resolved by the ruling. `gems/dti.py`
   keeps both implementations (`eval_mask` and `fp_mask`) and the S5-style
   catalogue-hedge probe measures which one the platform uses. **Recommendation:
   run that diagnostic before spending the third slot of any week.**
8. **FLAG #6 — 19-band order**: RESOLVED, see C23.
9. **FLAG #6b — 4 of the 19 bands unnamed publicly** (see FLAG #1c).
10. **FLAG #7 — thread scores without values**: h20-dem10-scarp-thin,
    H25-ctx-ridge, h28-dotted-ridge, r7-nms3 entries have no reported score in
    the project thread; ledger leaves them blank rather than guessing.
11. **FLAG #8 — score ties are not artifact proof.** The public leaderboard's
    three-way displayed 0.1563 tie was observed, but four-decimal scores cannot
    establish identical prediction arrays. The ledger also contains repeated
    abbreviated artifact IDs (#1/#8, #14/#15, #18/#19); these are flagged for
    reconciliation, not called duplicates without full hashes. The audit now
    blocks exact TIFF or manifest prediction-array hash repeats and reports
    rounded score/fingerprint collisions as warnings. This checkout has no
    historic submission TIFFs or DrivenData submission IDs.
12. **FLAG #9 — staff will not disclose the provenance of the hidden test
    faults** (C12, forum 11527). Every hypothesis about *which* fault types are
    in the test set is therefore inference. This is why the gates score three
    targets (recovery / discovery / combined) instead of one.
13. **FLAG #10 — the form's range check rejects NaN** anywhere in the raster,
    including the format page's permitted "null or NaN" outside the footprint
    (T9: real upload bounced 2026-09-28 with exactly "Predicted values must be
    in range [0, 1]"). Mechanism inferred, not disclosed. Mitigated: finite
    default emission in the site builder and `build_submission.py`. Needs one
    real finite-file upload to confirm the fix end-to-end.

## C2. Session log — 14GEMSDOE (2026-09-28, round 3)

* **Pass 1 (implement + verify).** R3 arms implemented
  (`gems/hypotheses.py`, context-threaded through `train_hide_recover.py`),
  `scripts/validate_round3.py` written with the round-2 protocol, tests added
  (`tests/test_hypotheses_round3.py`, `tests/test_data_path.py`), site finite
  default + value gate, mirror download script, KB/ledger/docs updated.
* **Pass 2 (review, find bugs, fix).** Found and fixed:
  (a) `_outward_direction` coordinate-frame bug (cones empty on axis-aligned
  traces) — caught by the new unit test after gate run 1 had started; run 1
  voided and re-run; (b) the round-3 incumbent initially reproduced round 2
  with the WRONG classifier block (baseline instead of ALL) — corrected so
  baseline/BMUL reproduce round-2 numbers exactly (0.3073/0.3842), pinning
  protocol equivalence; (c) R3D linkage scale parameterised after measuring
  real flank spacing (5×5 closing bridged nothing: flanks 7 px apart → 9×9);
  (d) a URL typo in the knowledge base fixed on proofread; (e) nav link missing
  on the round-2 page.
* **Pass 3 (round-3 session historical record).** That session reported 101/101
  tests and a synthetic end-to-end demo. For this review, the dependency
  environment was recreated in ignored `.venv/`; the current full suite passed
  **102/102**, including exact prediction-hash and score-tie-warning tests.
  This does not validate competition performance because real rasters/labels are
  still absent.

## D. Standing decisions (do not relitigate without new evidence)

* Metric constants and equations: from the official page (C2); tests pin them.
* Masked-pixel policy: both-sides exclusion (C11 + "should not matter" clause).
* Slot rule: blocked hide-and-recover DTI is the only currency; nothing else
  may spend a weekly submission.
* Emission style: thin high-confidence traces; the prior width measurement
  (w=0 optimal at floor 0.1 on their ensembles) is team-reported but consistent
  with the per-g max arithmetic; re-measure width on our own holdout once real
  data lands, do not assume.

## E. Success criteria for the next session

1. `data/raw/` populated; `prepare_data.py` grid.json measured from the real
   template (confirm or correct the pinned 3,292 × 3,730); all 19 band names read
   from `src.tags(i)` and written into `data/processed/band_names.json`.
2. `scripts/validate_round2.py` re-run on real rasters; BLEND-MUL either beaten
   or promoted, with the numbers written into `artifacts/holdout_round2.json`.
3. At least one new idea beaten on the real holdout and either promoted or
   killed — with the numbers written down. (Round-2 already did this on the
   synthetic forward model: N1 killed, BLEND-MUL promoted.)
4. Zero submissions from this repo whose file hash matches any prior upload —
   enforced by `scripts/check_submission_uniqueness.py` exiting 0.
5. A verified free official paleo-shoreline source, or N4 formally shelved.
