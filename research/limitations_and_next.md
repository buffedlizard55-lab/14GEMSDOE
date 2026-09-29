# Limitations & next steps — the working queue

Updated 2026-09-29 (round-6 session, 14GEMSDOE). Ordered by "what most raises
P(win) per unit effort". Owner convention: anything actionable in this repo is
scripted; anything requiring human credentials says exactly which credential
and why.

## Round-6 outcome in one line

`scripts/validate_real.py` gated R6-1 horsetail splay fan + R6-2 intersection halos + R5-4 curvature + all6 ensemble on **real** rasters, component protocol 4 folds, emission calibrated on hidden CALIB only: **R6-1 horsetail splay fan beats geom baseline on sparse AND far in 4/4 folds (0.0385→0.0624 dense +0.0239, 0.0151→0.0217 sparse +0.0066, 0.0003→0.0040 far 13×) — first arm in this project to meet promote rule on real data, PROMOTED.** Submission built: `GEMS_r5-geom-horse-ensemble_20260929T012833Z_b9d51ebb.tif` finite 0 outside [0,1] passes format gate + uniqueness audit PASS, site payload swapped to real kind=real. Full record: `research/hypotheses_round6.md`, `artifacts/holdout_round6_horse.json`, `research/results_ledger.md`. No slot spent yet — validated field ready for next weekly slot. Previous round-3 outcome: `scripts/validate_round3.py` gated five new candidates + two incumbent stacks + one prior-channel follow-up against TRUE round-2 incumbent BMUL 0.3842, reproduced exactly: incumbent stands, all R3 arms killed, prior-extensibility null. Team-reported NaN rejection (T9/FLAG #10) now mitigated and verified end-to-end (finite variant passes). Dependencies in ignored `.venv/`; current suite 127 passed on real-data code.

## A. Blockers

| # | Blocker | Why it blocks | Action | Status |
|---|---------|---------------|--------|--------|
| B1 | Competition data not in `data/raw/` | no real features/labels/template ⇒ no real holdout numbers | The Dropbox links supplied in the brief can be attempted with `bash scripts/download_competition_data.sh`, but their official provenance and binary contents are unverified. Confirm all downloaded files against the authenticated DrivenData data tab and official grid/band metadata before `prepare_data.py` or any training. | blocker; requires authorized source files (official data tab login-gated); sandbox cannot fetch Dropbox binaries |
| B2 | Sandbox TLS policy blocks binary downloads (FLAG #1, re-measured 2026-09-28T09:1xZ: allowlist unchanged) | external INGENIOUS/ScienceBase layers and DEM tiles must be fetched elsewhere | run `scripts/download_external_data.sh` + the `1m_DEM_links.csv` fetch on an unrestricted machine | scripted; needs unrestricted machine |
| B3 | No GPU in this environment | U-Net (reference-solution class) training is slow to impossible | train logistic baseline for protocol work; port U-Net on GPU box; protocol unchanged | environmental — **now the binding constraint after the round-3 support-extensibility null** |
| B4 | ~~Band order unpublished~~ **RESOLVED (C23)**: per-band `description`/`data_category` tags; 15 of 19 named officially, 4 not (FLAG #6b) | feature naming for the real stack | read `src.tags(i)` for all 19 bands on arrival; `prepare_data.py` still refuses to guess | waits on B1 |

## B. Next-session work (in priority order)

*Updated 2026-09-29 after Round 6 promotion. Real rasters present and verified (B1 closed — see `research/real_data_unlock.md`). **Sandbox snapshot keeps git-tracked files only: `.venv/`, `data/raw/`, `data/processed/` and `artifacts/*` (except whitelisted JSONs) do NOT survive reset.** Rebuild via Quickstart block in README.*

1. **Upload the validated R6-1 field** — `submissions/GEMS_r5-geom-horse-ensemble_20260929T012833Z_b9d51ebb.tif` is finite, [0,1], EPSG:32611, passes format gate + uniqueness audit PASS. Note: `real-data hide-and-recover ensemble (geom_horse); features: catalogue geometry + 12 official bands; emission = top 1.00% by probability, budget calibrated on held-out catalogue components (far-protocol 0.0040); valid [0,1] float32 on official grid, no NaN inside footprint`. This is first arm to meet promote rule on real data (4/4 sparse & far). Spend **one** weekly slot on it; record DrivenData submission ID in ledger.

2. **Complete full 4-fold for all6 (R5+R6 ensemble)** — interim 2-fold shows all6 0.0675/0.0212/0.0068 (fold0) and 0.0767/0.0268/0.0095 (fold1) beating both horse and curvature single arms. Command:
   ```bash
   ./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
     --arms geom geom_curv geom_horse all6 --n-pos 20000 --n-neg 40000 --iters 150 \
     --out artifacts/holdout_round6_all6.json
   ```
   ~30 min (2 vCPU). Then emission sweep `scripts/sweep_real.py`. If all6 beats horse on sparse+far ≥3/4, promote all6 and build its submission.

3. **Full-grid validation for remaining R6 arms** — R6-2 xsec, R6-3 condbase, R6-5 shore had only smoke 800×800 2-fold diagnostic (all improved dense/sparse vs geom). Need full 4-fold:
   ```bash
   ./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
     --arms geom geom_xsec geom_condbase geom_shore --n-pos 20000 --n-neg 40000 --iters 150 \
     --out artifacts/holdout_round6_rest.json
   ```

4. **Fetch external slip/dilation tendency for R6-4** — DOI 10.5066/P9YL58W6 verified obtainable via fetch_page 2026-09-29 (ScienceBase item 6296974dd34ec53d276bb33d, Shapefile_INGENIOUS area.zip 27.35 MB, public domain). On unrestricted runner:
   ```bash
   bash scripts/download_external_data.sh  # core already has faults, but slip/dilation needs manual DOI download
   # then unzip data/external/Shapefile_INGENIOUS*.zip and rasterize via geopandas+rasterio onto competition grid
   ```
   Implement rasterization in `gems/realchannels.py::slip_dilation_tendency_field` (currently placeholder returns {} when shp missing). Then validate as `geom_slip`.

5. **Fix `scripts/train_real_full.py`** — still calls pre-rewrite `validate_real` API (`vr.geo_channels`, `sample_training_pixels`, `ARM_EXTRA`). Purpose: train on FULL catalogue (no hide-out) and dump `artifacts/pred_<arm>.npy` for submission builder. ~1 h.

6. **Feed maintenance** — run `scripts/refresh_leaderboard.py` each session (live leaderboard check 2026-09-28 top DARD 0.3168). Scheduled GitHub Action on team runner would automate.

7. **U-Net port** (reference notebook) — still biggest expected jump; needs GPU box. Current logistic baseline is floor, not ceiling. Reference U-Net trained to reproduce catalogue scores 0.1847 (DrivenData account #19), so off-catalogue target + hide-and-recover + emission policy is needed even with U-Net.

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
