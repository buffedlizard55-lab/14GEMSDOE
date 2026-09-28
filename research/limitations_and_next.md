# Limitations & next steps — the working queue

Updated 2026-09-28. Ordered by "what most raises P(win) per unit effort".
Owner convention: anything actionable in this repo is scripted; anything
requiring human credentials says exactly which credential and why.

## A. Blockers

| # | Blocker | Why it blocks | Action | Status |
|---|---------|---------------|--------|--------|
| B1 | Competition data not in `data/raw/` (DrivenData login required, C18) | no real features/labels/template ⇒ no real holdout numbers | run `scripts/download_competition_data.sh` on a machine with a DrivenData account, then `python3 scripts/prepare_data.py` | **needs human credential** (one-time) |
| B2 | Sandbox TLS policy blocks binary downloads (FLAG #1) | external INGENIOUS/ScienceBase layers and DEM tiles must be fetched elsewhere | run `scripts/download_external_data.sh` + the `1m_DEM_links.csv` fetch on an unrestricted machine | scripted; needs unrestricted machine |
| B3 | No GPU in this environment | U-Net (reference-solution class) training is slow to impossible | train logistic baseline for protocol work; port U-Net on GPU box; protocol unchanged | environmental |
| B4 | Band order of the 19-layer stack unpublished (FLAG #6) | feature naming for the real stack | read the data dictionary shipped in the download; `prepare_data.py` refuses to guess | waits on B1 |

## B. Next-session work (in priority order)

1. **Land the data (B1/B2), then run the H1 gate.** Structural completion is the
   top-ranked hypothesis and needs no external data. Deliverable: blocked
   holdout DTI of H1-geometry model vs the catalogue-emission baseline on real
   labels. Only then assign it slot #1.
2. **Scale `strike_field` and `relay_corridors` to the full grid** (tiled
   convolutions; KD-tree pruning for component pairs). Currently correct but
   tuned for ≤1k-component synthetic regions.
3. **H2 (magnetic lineaments) behind the same gate.** Structure-tensor stack on
   the RTP magnetics + TMI-slope bands; strike-mismatch feature; A/B vs H1.
4. **External layers (H3/H4)** once B2 completes: rasterize springs/sinter/vents
   and the slip/dilation tendency onto the template grid; enrichment statistic
   on hidden traces before any emission change.
5. **U-Net port** (reference notebook) with hide-and-recover batches: hide
   components per sample rather than per epoch for stochasticity; keep the same
   hidden-recovery scoring.
6. **Masking diagnostic slot** (S5-style catalogue-hedge probe) — only when the
   slot budget is otherwise unused; interpretation written *before* upload.
7. **Site payload swap:** after the first real validated submission,
   `build_site_payload.py submissions/GEMS_….tif` and confirm the banner flips
   from DEMO to the real artifact hash.
8. **Leaderboard feed:** schedule `scripts/refresh_leaderboard.py` (locally or
   via GitHub Action on a runner with network) so the site's snapshot stays
   current; the snapshot timestamp always shows on the Leaderboard page.

## C. Irregularities flagged for human review

1. **FLAG #1 — sandbox network policy.** dropbox.com, gdr.openei.org/*files*,
   sciencebase.gov, docs.nlr.gov binaries: TLS handshake closed from the Arena
   sandbox (curl exit 35 / Python SSLError). Pages are fetchable. The team's
   Dropbox mirrors of `example_submission.tif` / `existing_faults.tif` were
   therefore NOT re-hashed here; the download scripts hash whatever they fetch.
2. **FLAG #2 — Faulds percentage vintage drift** (32/22/22/8 in 2012 vs
   25/20/18/7 later). Brief numbers kept as primary; hypotheses robust to both.
3. **FLAG #3 — stale brief figure "0.3049 is the highest score"**: live top on
   2026-09-28 is 0.3168 (DARD). 0.3049 not in the top 50.
4. **FLAG #4 — "geothermal vents" wording**: the scored target is faults.
   Vents (GDR volcanics layer) are used only as an independent structure proxy.
5. **FLAG #5 — masking semantics ambiguity** (C11): both-sides exclusion chosen;
   sensitivity switch documented in `gems/dti.py`.
6. **FLAG #6 — 19-band order unpublished.**
7. **FLAG #7 — thread scores without values**: h20-dem10-scarp-thin,
   H25-ctx-ridge, h28-dotted-ridge, r7-nms3 entries have no reported score in
   the project thread; ledger leaves them blank rather than guessing.
8. **FLAG #8 — identical-score submissions across accounts** (three LB accounts
   at 0.1563): if those are ours, note that multiple identical uploads waste
   slots and produce no information; the hash-unique naming + slot log exist to
   prevent a repeat.

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
   template (confirm or correct the pinned 3,292 × 3,730).
2. H1 holdout number recorded on real labels.
3. At least one idea beaten on holdout and either promoted or killed — with the
   numbers written down.
4. Zero submissions from this repo whose file hash matches any prior upload.
