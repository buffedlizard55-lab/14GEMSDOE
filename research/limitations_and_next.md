# Limitations & next steps — the working queue

Updated 2026-09-28 (round-2 session). Ordered by "what most raises P(win) per
unit effort". Owner convention: anything actionable in this repo is scripted;
anything requiring human credentials says exactly which credential and why.

## Round-2 outcome in one line

`scripts/validate_round2.py` gated nine arms on the spatially-blocked holdout:
**BLEND-MUL (classifier × (1 + 0.5·geophysical prior)) won with +0.0979
combined DTI and improved recovery AND discovery; the literature-ranked top
candidate N1 (gravity-gradient edge terminations) was killed at −0.0059.** No
submission slot was spent. Full record: `research/hypotheses_round2.md`.

## A. Blockers

| # | Blocker | Why it blocks | Action | Status |
|---|---------|---------------|--------|--------|
| B1 | Competition data not in `data/raw/` (DrivenData login required, C18) | no real features/labels/template ⇒ no real holdout numbers | run `scripts/download_competition_data.sh` on a machine with a DrivenData account, then `python3 scripts/prepare_data.py` | **needs human credential** (one-time) |
| B2 | Sandbox TLS policy blocks binary downloads (FLAG #1) | external INGENIOUS/ScienceBase layers and DEM tiles must be fetched elsewhere | run `scripts/download_external_data.sh` + the `1m_DEM_links.csv` fetch on an unrestricted machine | scripted; needs unrestricted machine |
| B3 | No GPU in this environment | U-Net (reference-solution class) training is slow to impossible | train logistic baseline for protocol work; port U-Net on GPU box; protocol unchanged | environmental |
| B4 | ~~Band order of the 19-layer stack unpublished~~ **RESOLVED (C23)**: the order is in the GeoTIFF band tags (`description`, `data_category`); the reference notebook reads them. 15 of 19 layers are named in the official provided-features list; the remaining 4 are not enumerated publicly (FLAG #6b) | feature naming for the real stack | read `src.tags(i)` for all 19 bands on arrival; `prepare_data.py` still refuses to guess | waits on B1 |

## B. Next-session work (in priority order)

1. **Land the data (B1), then re-run the round-2 gate on the real rasters.**
   `scripts/validate_round2.py` runs unchanged once `data/processed/` exists.
   Deliverable: the same nine-arm table computed on real labels. BLEND-MUL is
   the incumbent to beat; nothing may be uploaded until it does.
2. **Only then spend a weekly slot**, with
   `scripts/build_submission.py --policy "blend-mul w0.5 holdout<VALUE>"` and
   `scripts/check_submission_uniqueness.py` run first (exit 0 required).
3. **Scale `strike_field` and `relay_corridors` to the full grid** (tiled
   convolutions; KD-tree pruning for component pairs). Currently correct but
   tuned for ≤1k-component synthetic regions.
4. **H2 (magnetic lineaments) behind the same gate.** Structure-tensor stack on
   the RTP magnetics + TMI-slope bands; strike-mismatch feature; A/B vs H1.
5. **External layers (H3/H4)** once B2 completes: rasterize springs/sinter/vents
   and the slip/dilation tendency onto the template grid; enrichment statistic
   on hidden traces before any emission change.
6. **U-Net port** (reference notebook) with hide-and-recover batches: hide
   components per sample rather than per epoch for stochasticity; keep the same
   hidden-recovery scoring. Note the reference's hyperparameters are now recorded
   (C24) so the port is a like-for-like comparison; note also that the reference
   trains on the known-fault population and has no masking (C25), so it is a
   floor to beat, not a target to match.
7. **Masking diagnostic slot** (S5-style catalogue-hedge probe) — only when the
   slot budget is otherwise unused; interpretation written *before* upload.
8. **Site payload swap:** after the first real validated submission,
   `build_site_payload.py submissions/GEMS_….tif` and confirm the banner flips
   from DEMO to the real artifact hash.
9. **Leaderboard feed:** schedule `scripts/refresh_leaderboard.py` (locally or
   via GitHub Action on a runner with network) so the site's snapshot stays
   current; the snapshot timestamp always shows on the Leaderboard page.

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
2. **FLAG #2 — Faulds percentage vintage drift** (32/22/22/8 in 2012 vs
   25/20/18/7 later). Brief numbers kept as primary; hypotheses robust to both.
5. **FLAG #3 — stale brief figure "0.3049 is the highest score"**: live top on
   2026-09-28 is 0.3168 (DARD); live top 5 recorded in T7. 0.3049 not in the
   top 50.
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
11. **FLAG #8 — identical-score submissions across accounts** (three LB accounts
    at 0.1563, VERIFIED T6): if those are ours, note that multiple identical
    uploads waste slots and produce no information. The mechanical prevention is
    now in place: `scripts/check_submission_uniqueness.py` (hash-identity,
    name-identity, NOTE/MANIFEST provenance, manifest integrity, ledger
    score+artifact collisions) is wired into `tests/test_submission_uniqueness.py`
    and must exit 0 before any upload.
12. **FLAG #9 — staff will not disclose the provenance of the hidden test
    faults** (C12, forum 11527). Every hypothesis about *which* fault types are
    in the test set is therefore inference. This is why `validate_round2.py`
    scores three targets (recovery / discovery / combined) instead of one, and
    why the promotion gate uses the union.

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
