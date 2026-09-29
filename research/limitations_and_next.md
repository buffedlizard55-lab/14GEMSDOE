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

*Updated 2026-09-29. The real rasters are in play now (B1 closed — see
`research/real_data_unlock.md`), so the queue below is the real-data queue. **The
sandbox snapshot keeps git-tracked files only: `.venv/`, `data/raw/`,
`data/processed/` and `artifacts/*` (except the three whitelisted JSONs) do NOT
survive a session reset.** Rebuild them first; the whole restore is one command
block (see `README.md` Quickstart).*

1. **Re-run the round-5 real gate to completion** (it was interrupted after 2 of
   4 folds; interim table in `research/results_ledger.md`):
   ```bash
   ./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
     --arms geom geo geom_ramp geom_acc geom_tilt geom_curv geom_gap all \
     --n-pos 20000 --n-neg 40000 --iters 150 --out artifacts/holdout_real.json
   ```
   ~25 min on this box (2 vCPU). Then the emission sweep:
   `./.venv/bin/python scripts/sweep_real.py --gate artifacts/holdout_real.json
   --out artifacts/emission_sweep.json`. Apply the pre-registered promote rule
   (beat `geom` on **sparse AND far** in ≥3 of 4 folds). R5-4/R5-5 are the arms
   to watch; the interim record has R5-4 winning both protocols in both folds
   finished.
2. **Then, and only then, spend one slot** on the winner via
   `scripts/build_real_submission.py` (which selects the arm, averages the four
   fold fields, emits at the CALIB-calibrated budget, and calls
   `scripts/build_submission.py` for clamping/naming/the format gate).
   `scripts/check_submission_uniqueness.py` must exit 0 first; the upload must be
   the finite variant.
3. **Fix `scripts/train_real_full.py`** — it still calls the pre-rewrite
   `validate_real` API (`vr.geo_channels`, `sample_training_pixels`,
   `ARM_EXTRA`, …) and cannot run. Intended purpose: train on the FULL catalogue
   (no hide-out) and dump `artifacts/pred_<arm>.npy` for the submission builder.
   ~1 h.
4. **Swap the site payload to the real field** once a real submission exists:
   `scripts/build_site_payload.py submissions/GEMS_*.tif`, then confirm the DEMO
   banner disappears (`docs/js/payload.js` records `kind=demo|real`). The site
   currently ships the demo payload and says so.
5. **Feed maintenance:** run `scripts/refresh_leaderboard.py` against the live
   leaderboard each session (2 entries in `research/leaderboard_snapshot.json`);
   a scheduled GitHub Action on the team runner would remove the manual step.
6. **U-Net port** (reference notebook) — still the biggest expected jump; needs
   a GPU-class box or a long CPU budget that this sandbox does not have.
7. **External layers** (3DEP 1 m DEM tiles, palaeo-shoreline masks, INGENIOUS
   slip/dilation tendency): the hosts are on the sandbox block list. The named
   free official sources with check dates are in `research/knowledge_base.md` §3;
   bring them in through the team's GitHub runner, exactly as the rasters came in
   (`scripts/bridge_team_mirror.sh` is the template: fetch → split → hash-pin).
8. **R3E prior-overlap test** stays mandatory before any prior-extension
   proposal (the round-3 null stands).

## C. Irregularities flagged for human review
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

## C2b. Session log — 14GEMSDOE (2026-09-28/29, round 5, real data)

* **Pass 1 (implement + verify).** Real rasters recovered through the team's
  GitHub mirror and SHA-256-verified (`research/real_data_unlock.md`); five new
  hypotheses pre-registered (`research/hypotheses_round5.md`); channels
  implemented in `gems/realchannels.py` (+10 unit tests); `scripts/validate_real.py`
  rewritten around a two-view hide-and-recover protocol and a CALIB-chosen
  emission policy; `scripts/sweep_real.py` and `scripts/build_real_submission.py`
  added; `research/artifact_audit.md` rewritten on re-derived hashes.
* **Pass 2 (review, find bugs, fix).** Six real bugs caught and fixed before the
  gate: (a) `np.nan_to_num` missing in `design_matrix` → NaN columns poisoned
  standardisation and produced all-zero scores; (b) float16 overflow in 12
  geometry channels (`dist_endpoint` > 65,504) → per-channel guarded cast;
  (c) the training view leaked the targets (it *included* TEST/HIDE) → split into
  a train view (TEST+HIDE removed) and a prediction view (catalogue minus TEST);
  (d) two full geometry views held simultaneously → ~2× memory → two-phase fold
  loop (train all arms, free, then predict all arms); (e) `np.save` writing
  `fold0_truth.npz.npy` where `np.savez` was meant; (f) NMS `taken` mask
  indexing. Also corrected two documentation errors: the learner is weighted
  logistic regression, *not* "HistGradientBoosting-equivalent"; and
  `scripts/verify_real_data.py` compared affine-order against GDAL-order
  transforms, producing a false FAIL.
* **Pass 3 (re-check against the request).** Re-ran the smoke gate and the
  sweep end-to-end before committing; re-verified the real-data hashes; re-read
  the standing prompt. Result of the full gate rerun: **interrupted at fold 2 by
  an environment reset** (see B.1 and the ledger); nothing promoted, nothing
  killed, no slot spent.
* **Environment reset (2026-09-29).** The workspace came back with tracked files
  only. `data/raw/` (419 MB), `data/processed/`, `.venv/` and the gate fields had
  to be rebuilt. This is now documented in README Quickstart step 0.

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
