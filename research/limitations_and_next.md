# Limitations & next steps — the working queue

Updated 2026-09-29 (session-15 continuation). Ordered by "what most raises
P(win) per unit effort". Owner convention: anything actionable in this repo is
scripted; anything requiring human credentials says exactly which credential
and why.

## Current outcome in one line

Session 15 rebuilt the reset environment (hash-verified), fixed the deployment
path (`train_real_full.py` + tests), refreshed the leaderboard feed, completed
the round-6 full-grid gate: **R6-3 condbase and R6-5 shore PROMOTED** (shore
4/4 sparse & far, far 13× baseline; condbase 3/4 & 4/4) and **R6-2 xsec
killed-by-rule** (sparse 2/4); the **all6 ensemble 4-fold gate is re-running**
(folds 0–1: all6 0.0675/0.0212/0.0068, 0.0767/0.0268/0.0095, beating horse and
curv on all three protocols — first attempt OOM-killed at fold 2). Round-7
hypotheses pre-registered (`research/hypotheses_round7.md`), R7-3/R7-5 channels
implemented + 20 unit tests, R7-1 misregistration operator + `--misreg-px`
stress protocol implemented (amendment: 0.02/px displacement penalty, recorded
before gate numbers). Records: `artifacts/holdout_round6_rest.json`,
`research/results_ledger.md`. Suite 154 passed.

## A. Blockers

| # | Blocker | Why it blocks | Action | Status |
|---|---------|---------------|--------|--------|
| B1 | Competition data not in `data/raw/` | no real features/labels/template ⇒ no real holdout numbers | The Dropbox links supplied in the brief can be attempted with `bash scripts/download_competition_data.sh`, but their official provenance and binary contents are unverified. Confirm all downloaded files against the authenticated DrivenData data tab and official grid/band metadata before `prepare_data.py` or any training. | blocker; requires authorized source files (official data tab login-gated); sandbox cannot fetch Dropbox binaries |
| B2 | Sandbox TLS policy blocks binary downloads (FLAG #1, re-measured 2026-09-28T09:1xZ: allowlist unchanged) | external INGENIOUS/ScienceBase layers and DEM tiles must be fetched elsewhere | run `scripts/download_external_data.sh` + the `1m_DEM_links.csv` fetch on an unrestricted machine | scripted; needs unrestricted machine |
| B3 | No GPU in this environment | U-Net (reference-solution class) training is slow to impossible | train logistic baseline for protocol work; port U-Net on GPU box; protocol unchanged | environmental — **now the binding constraint after the round-3 support-extensibility null** |
| B4 | ~~Band order unpublished~~ **RESOLVED (C23)**: per-band `description`/`data_category` tags; 15 of 19 named officially, 4 not (FLAG #6b) | feature naming for the real stack | read `src.tags(i)` for all 19 bands on arrival; `prepare_data.py` still refuses to guess | waits on B1 |

## B. Next-session work (in priority order)

*Updated 2026-09-29 after Round 6 promotion. Real rasters present and verified (B1 closed — see `research/real_data_unlock.md`). **Sandbox snapshot keeps git-tracked files only: `.venv/`, `data/raw/`, `data/processed/` and `artifacts/*` (except whitelisted JSONs) do NOT survive reset.** Rebuild via Quickstart block in README.*

1. **Upload the validated artifact — HUMAN ACTION (DrivenData login).**
   **READY:** `submissions/GEMS_r5-geom-horse-ensemble_20260929T154852Z_ccbe1de0.tif`
   (recovered prediction-exactly from the merged site payload after the second
   reset; prediction `e96e942f…` identical to the recorded artifact — see the
   ledger's recovery entry; container hash differs by GDAL serialization only).
   The original build was `submissions/GEMS_r5-geom-horse-ensemble_20260929T080858Z_76116a29.tif`
   (horse 4-fold ensemble, official-economics budget q 0.0225, TEST dense
   0.0699; uniqueness audit PASS; zero uploads of these pixels). All ensemble
   alternatives (all6, horse7 v1, horse7 v2) were decided by the pre-registered
   fold-wise sparse rule and lost; the artifact is the single upload candidate.
   Spend **one** weekly slot (C8: one submission per entity is scored across
   both rounds). Record the DrivenData submission ID in the ledger.

2. ~~Complete full 4-fold for all6~~ **DONE (2026-09-29):** all6 4-fold
   0.0679/0.0221/0.0074 vs horse 0.0624/0.0217/0.0040 — sparse wins 2/4 →
   all6 NOT eligible (fold-wise rule). horse7 (horse + R7-1/3/5) then failed
   the same rule twice (v1 2/4, protocol-v2 2/4). Recorded failure mode:
   fold-wise sparse consistency on budget-drift folds. See
   `research/results_ledger.md` gates 7 and 9.

3. ~~Full-grid validation for remaining R6 arms~~ **DONE (2026-09-29):**
   `artifacts/holdout_round6_rest.json`. R6-5 shore PROMOTED (4/4 sparse & far),
   R6-3 condbase PROMOTED (3/4 sparse, 4/4 far), R6-2 xsec killed-by-rule
   (sparse 2/4; far 4/4 but thin). Full table in `research/results_ledger.md`.

4. **Fetch external slip/dilation tendency for R6-4** — DOI 10.5066/P9YL58W6
   verified obtainable (ScienceBase item 6296974dd34ec53d276bb33d,
   Shapefile_INGENIOUS area.zip 27.35 MB, public domain). Still needs an
   unrestricted runner (sandbox TLS blocks sciencebase.gov — FLAG #1):
   ```bash
   bash scripts/download_external_data.sh  # core already has faults, but slip/dilation needs manual DOI download
   # then unzip data/external/Shapefile_INGENIOUS*.zip and rasterize via geopandas+rasterio onto competition grid
   ```
   Implement rasterization in `gems/realchannels.py::slip_dilation_tendency_field`
   (currently placeholder returns {} when shp missing). Then validate as
   `geom_slip`.

5. ~~Fix `scripts/train_real_full.py`~~ **DONE (2026-09-29):** rewritten against
   the post-rewrite gate API (hide-and-recover train view
   `labels & ~hide`, deploy view = full catalogue, CALIB-calibrated emission);
   `tests/test_train_real_full_api.py` (7 tests) pins the API contract so a
   future gate-side rename breaks tests, not the deployment path. Smoke it on
   the real grid once the gates free the CPU:
   `./.venv/bin/python scripts/train_real_full.py --arms all6 geom_horse`.

6. ~~Feed maintenance~~ **DONE (2026-09-29):** 50 rows refreshed via the Arena
   fetch tool (FLAG #1 path: `refresh_leaderboard.py --html-file`). Top DARD
   0.3168; the 0.1563 cluster (extradr19/SDCF9/smashi34) unchanged at #28–30;
   joeyfezster 0.2872 new #3. Snapshot `research/leaderboard_snapshot.json`
   history n=3.

6b. **Round-7 gate (in progress).** Pre-registration:
   `research/hypotheses_round7.md`. Commands queued behind the all6 re-run:
   ```bash
   ./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
     --arms geom geom_gravtopo geom_trans --n-pos 20000 --n-neg 40000 --iters 150 \
     --out artifacts/holdout_round7.json
   ./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
     --arms geom geom_align --n-pos 20000 --n-neg 40000 --iters 150 \
     --out artifacts/holdout_round7_align_d0.json
   ./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
     --arms geom geom_align --n-pos 20000 --n-neg 40000 --iters 150 \
     --misreg-px 2 --out artifacts/holdout_round7_align_d2.json
   ```
   Promote rule unchanged (≥3/4 wins on sparse AND far vs same-run geom); for
   R7-1 additionally the δ=2 stress condition must pass and δ=0 must not lose.
   R7-2 stitching and R7-4 strain-deficit channels are not yet implemented
   (queue item 6c). R7-3 is N1's physics re-tested on real data (the round-2
   synthetic kill is void as evidence, directive 4).

7. **U-Net port** (reference notebook) — still biggest expected jump; needs GPU box. Current logistic baseline is floor, not ceiling. Reference U-Net trained to reproduce catalogue scores 0.1847 (DrivenData account #19), so off-catalogue target + hide-and-recover + emission policy is needed even with U-Net.

8. **R8 pre-registration candidates (2026-09-29, for the next session's
   3–5 hypotheses):** (a) **band-6 depth feature** — FLAG #11 resolution shows
   `tc` is the top-of-crustal magnetic source depth estimate (km, smooth
   regional structure), not an edge raster; use it as a long-wavelength
   structural-level feature (and its edges stay available). (b) **budget-matched
   sparse comparison for ensembles** — the three ensemble misses are all
   budget-drift artifacts; a pre-registered rule comparing arms at matched
   CALIB budgets would isolate channel value from emission drift (do NOT
   retro-fit the old rule). (c) **sparse-stable ensemble emission** — a
   constrained CALIB policy (maximize dense subject to sparse ≥ bench) tested
   as a NEW policy family. (d) R6-4 slip/dilation (blocked on external data —
   see item 4).
9. **GitHub push + PR #9 update** — blocked on an invalid `GH_TOKEN`
   (2026-09-29, mid-session expiry: the session's commits are local; push
   `arena/01a0eae6-14gemsdoe` and sync the PR once GitHub is reconnected).

8. **R3E prior-overlap test** stays mandatory before any prior-extension proposal (round-3 null stands: multiplicative prior cannot extend classifier support).

9. **Leaderboard analysis** — why 0.1563 plateau? Audit shows GEMSDOE1 and 5GEMSDOE published byte-identical files (git blob SHA-1 812e61b7… same SHA-256 7f00890a…), identical score from identical pixels. Other 0.1563 accounts (SDCF9, extradr19, smashi34) are score ties only, not proven artifact identity. Group historically shipped 155,021 px budget (2% footprint) but calibrated budget on real rasters is 0.5–1% (25,837–51,674 px) — selection, not budget, moves score (three pindrop submissions same budget scored 0.083/0.1152/0.1193, Δ0.036). Emission policy derived from metric: add pixel when ΔTP/ΔFP >0.2·D/(1-0.2·D)=0.0323 at D=0.1563, scaling support up never lowers score — binary 1.0 emission optimal given support.

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
14. **FLAG #11 — `tc` band tag conflict — RESOLVED 2026-09-29 (data-driven).**
    The file's per-band `description` tag says "Tilt angle or total curvature"
    while the official provided-features list (C27, [provided
    features](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#provided-features))
    names "top-of-crustal magnetic source depth estimate" and no other tag
    matches it. Measurements on the actual band (index 6, `gems.realdata.
    read_band(6)`): min 2.953, max 88.567, median 18.482, std 4.418,
    **fraction of pixels < 0 = 0.000**, pct1..99 = 7.7..29.1. A tilt-angle
    response is bounded at exactly ±90° and MUST change sign over a dipolar
    magnetic survey; total curvature sign-changes at contacts. A depth
    estimate is strictly positive — and 3–89 km with median ~18.5 km is the
    published range of top-of-crustal magnetic-source / Curie-style depths for
    the Great Basin. Supporting checks: corr(band6, band15 basement depth) =
    0.21 (weak — band 6 is NOT a re-skinned sediment thickness, which would
    correlate ~1 after unit scaling); RMS|∇|/std = 0.107 vs 0.021 for band 15
    (local-wavenumber depth maps are speckled — expected). **Conclusion: band
    6 is the top-of-crustal magnetic source depth estimate in km; the GDAL
    description is a mistaken generic fallback.** Current usage (`tc` as an
    edge-strength raster) remains valid under either reading and is unchanged;
    using band 6 as a *depth* feature is now a pre-registrable R8 candidate.
    (Note: the official figure asset `gems_tc_tmi.png` uses "tc" for total
    radiometric counts — the figure caption's 16th named GeoDAWN product, not
    necessarily inside `training_features.tif`; no band tag mentions
    radiometrics. That naming coincidence is not evidence about band 6.)
15. **FLAG #12 — `geod_dilaterate` sign convention is not stated.** The tag
    says "rate of volumetric strain (expansion/contraction)" without declaring
    which sign is extension. R7-5 defaults to the geodetic convention
    (positive = extension) and exposes `extension_positive=False` for the
    ablation; a strictly contracting field must never read as coupling
    (tests pin this).

16. **FLAG #13 — uniqueness-gate F7 design gap (found by executing the
    documented flow, fixed 2026-09-29).** The README step-5 order is
    build → `check_submission_uniqueness.py` (exit 0) →
    `build_site_payload.py <the built tif>`; the site payload therefore
    *necessarily* ends up carrying the pixels of the artifact whose manifest
    sits in `submissions/`. The original F7 hard-failed on any payload↔manifest
    pixel-hash match — including the payload's own source — so the documented
    end state could never pass, and `tests/test_submission_uniqueness.py::
    test_script_runs_on_the_real_repo` (exit 0 on the real repo) only held
    while `submissions/` was empty (a reset artifact). Fixed on principle, not
    convenience: F7 now permits exactly one match — the manifest of the tif the
    payload header declares as its `Source:` — and still hard-fails when the
    payload pins the pixels of any *other* built artifact (the historical
    "site pins identical hash" failure mode, 5GEMSDOE row). F1/F8 are
    untouched: two artifacts with identical prediction arrays can never be
    built at all. Two unit tests pin both sides (payload-sourced match passes;
    foreign match fires). Cross-team scored-artifact identity remains the job
    of `scripts/audit_scored_artifacts.py --fetch-scored` (README step 4).

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

## C2c. Session log — 14GEMSDOE (2026-09-29, session 15, continuation)

* **Pass 1 (rebuild + verify).** Environment and data rebuilt from the
  Quickstart after the sandbox reset; one transient `gh api` stream error
  handled by a retry loop; all three rasters SHA-256 verified;
  `verify_real_data.py` ALL CHECKS PASS (incl. the GDAL-order transform
  comparison fix from session 14). Suite 127/127 on the restored checkout.
* **Pass 2 (queue items).** `train_real_full.py` rewritten against the current
  gate API (the stale calls `vr.geo_channels`/`ARM_EXTRA`/`stack_matrix`/
  `fit_model`/`predict_full`/`dilate_valid` were a crash waiting to happen)
  with the two-view hide-and-recover design; 7 regression tests pin the
  contract. Leaderboard feed refreshed (Arena fetch path). The all6 4-fold gate
  reproduced the interim record exactly on folds 0–1 and was OOM-killed at
  fold 2 (exit 137) — re-queued as a 2-arm process. Round-6 remaining-arms gate
  completed: R6-5 shore and R6-3 condbase PROMOTED, R6-2 xsec killed-by-rule.
* **Pass 3 (round 7 + review pass).** R7 pre-registration written from the two
  unused official statements (C28 misregistration-as-target, C21
  continuations-as-truth) plus the label producers' own basin playbook (S11);
  R7-3/R7-5 implemented in `realchannels` + gate registry with 13 tests; R7-1
  alignment operator + `--misreg-px` stress protocol implemented with 7 tests.
  The first R7-1 smoke exposed over-sliding (mean |offset| 3.57 px on an
  injected 2 px misregistration); the operator was amended with a fixed
  0.02/px displacement penalty BEFORE any gate numbers, and the amendment is
  recorded in the pre-registration. A latent bug in `transtensional_coupling`
  (standardisation forgetting the physical dilatation sign — below-median
  contraction read as coupling) was caught by unit tests and fixed by clipping
  on physical sign before scaling. `all`/`all6` arm definitions were pinned
  back to their recorded semantics (protocol-drift fix). Suite 154/154.

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
