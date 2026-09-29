# Results ledger — every submission this group has made (as recorded)

Sources: the project thread (TEAM-REPORTED) and the published run sites
(VERIFIED where noted). Scores appear exactly as reported; blanks stay blank.
This ledger exists so no two entries can silently be the same work again.

| # | Entry / run id | Reported score | Description (per thread/site) | Artifact id | Unique? | Evidence |
|---|----------------|----------------|-------------------------------|-------------|---------|----------|
| 1 | GEMSDOE1 | 0.1563 | ens12-adopted-floor0.1-w0 skeleton; in-browser builder | `7f00890a…` | reference | published site metadata (prefix/payload histogram); original upload binary/ID unavailable |
| 2 | (6GEMSDOE site) | 0.0286 | divergent probe | — | yes | thread |
| 3 | GEMSDOE3 "Pindrop nodes" | 0.1193 | SUBMIT FIRST | f347b70daa | yes | thread (matches LB smrtdoog5 0.1193) |
| 4 | GEMSDOE2 | 0.1560 | near-duplicate family of #1 | — | near-dup | thread |
| 5 | GEMSDOE3 "catalogue-gap target" | 0.0830 | SECOND SYSTEM | 37f9d5b855 | yes | thread |
| 6 | GEMSDOE4 | 0.0343 | divergent probe | — | yes | thread |
| 7 | GEMSDOE3 "dense ridge control" | 0.1152 | CONTROL · UPLOAD LAST | 4e03fc9705 | yes | thread |
| 8 | 5GEMSDOE | 0.1563 | **published builder displays matching artifact-hash prefix and payload metadata as #1** | `7f00890a…` | probable duplicate builder field; upload identity unverified | both live pages fetched; no original upload binary/ID available |
| 9 | 7GEMSDOE | 0.1461 | (matches LB wbg1) | — | yes | thread |
| 10 | 8GEMSDOE | 0.1563 | same rounded score reported | — | unknown | team thread only; score tie does not prove artifact identity |
| 11 | 9GEMSDOE | 0.0107 | divergent probe | — | yes | thread |
| 12 | 10GEMSDOE h16-continuation | 0.0461 | continuation probe | 3431b83c7c | yes | thread |
| 13 | 10GEMSDOE h20-dem10-scarp-thin | (none reported) | DEM-10 scarp thinning | ffc91a1686 | yes | thread |
| 14 | 10GEMSDOE H25-ctx-ridge | (none reported) | context-ridge | 6452ae1d00 | yes | thread |
| 15 | 10GEMSDOE h28-dotted-ridge | (none reported) | dotted-ridge | 6452ae1d00 | yes | thread |
| 16 | 10GEMSDOE wbg1 | 0.1461 (LB) | — | — | yes | LB row #33 |
| 17 | 11GEMSDOE | 0.0202 | divergent probe | — | yes | thread |
| 18 | 12GEMSDOE | 0.1294 | r7-nms3-dem10-scarp | 0c9199f14e62 | yes | thread |
| 19 | 12GEMSDOE _allfinite | (none reported) | NaN-finite variant of #18 | 0c9199f14e62 | variant | thread |
| 20 | SDCF9 | 0.1563 (LB) | identity appears in thread; LB row #27 | — | — | LB snapshot |

## Artifact-fingerprint irregularities

The audit script found repeated short artifact IDs: #1/#8 (`7f00890a…`),
#14/#15 (`6452ae1d00`), and #18/#19 (`0c9199f14e62`). The first pair also has
matching published site metadata. Reuse is **suspected, not proven** for all
three pairs because the ledger stores abbreviated IDs, does not contain the TIFFs,
and lacks the original upload IDs. In particular, the #14/#15 scores are blank
and #18/#19 describe a finite/NaN variant; do not infer they are duplicates from
these records alone. Recover full artifact and prediction-array hashes before
classifying them. Current gate warns on these historical collisions and blocks
only exact hash matches in local files/manifests.

## Cross-checks against the public leaderboard (2026-09-28 snapshot)

* The dated leaderboard snapshot records #26 extradr19 = 0.1563, #27 SDCF9 =
  0.1563, and #28 smashi34 = 0.1563. A four-decimal tie verifies only equal
  displayed scores; it does not establish equal TP/FP/FN components or identical
  rasters. Submission files/IDs for these accounts are not available here.
* #33 wbg1 = 0.1461 and #48 smrtdoog5 = 0.1193 are score matches to team-thread
  entries, not artifact-identity evidence.

## Round-2 gate record (2026-09-28) — no submission slot was spent

`scripts/validate_round2.py`, spatially-blocked holdout (4 folds × 48-px blocks,
3-px purge buffer), 3 region seeds, identical model and protocol per arm.

| Arm | recovery | discovery | combined | Δ combined | Decision |
|---|---|---|---|---|---|
| baseline | 0.3073 | 0.0081 | 0.2863 | — | incumbent |
| N1 gravity-gradient edges | 0.3003 | 0.0087 | 0.2804 | −0.0059 | **killed by gate** |
| N2 seismicity/strain lineaments | 0.3218 | 0.0569 | 0.3352 | +0.0489 | promoted (2nd) |
| N3 alteration-cap margin | 0.3086 | 0.0057 | 0.2855 | −0.0008 | killed |
| N5 range-front step | 0.3214 | 0.0050 | 0.2961 | +0.0097 | promoted (3rd) |
| GEO-ONLY | 0.0822 | 0.0156 | 0.0961 | −0.1903 | killed |
| BLEND (max) | 0.0822 | 0.0156 | 0.0961 | −0.1902 | killed |
| BLEND-ADD | 0.1849 | 0.0289 | 0.2029 | −0.0834 | killed |
| **BLEND-MUL w=0.5** | **0.3673** | **0.0612** | **0.3842** | **+0.0979** | **promoted (1st)** |

Weight sweep (BLEND-MUL): 0.25 → 0.3785, **0.50 → 0.3851**, 1.00 → 0.3746,
2.00 → 0.3394. Interior optimum.

Synthetic forward model only — see `research/hypotheses_round2.md` §Honesty
statement. No slot consumed, no file uploaded.

## Round-3 gate record (2026-09-28, session 14) — no submission slot was spent

`scripts/validate_round3.py`, EXACT round-2 protocol (176 px, seeds 11/12/13,
4 × 48 px blocks, 3 px purge, 5 hide-recover epochs, hide 0.35, w=0.5).
Incumbent corrected this session to the true round-2 emission (classifier over
the ALL block); baseline/BMUL reproduce `holdout_round2.json` to 4 decimals.
Gate run 1 was voided (coordinate-frame bug, caught by the new unit test);
audit trail in `research/hypotheses_round3.md` §2.

| Arm | recovery | discovery | combined | Δ vs incumbent | Decision |
|---|---|---|---|---|---|
| baseline | 0.3073 | 0.0081 | 0.2863 | −0.0979 | reference |
| **BMUL (incumbent)** | **0.3673** | **0.0612** | **0.3842** | — | **stands** |
| R3A tip-continuation cones | 0.2977 | 0.0080 | 0.2772 | −0.1071 | killed |
| R3B completeness residual | 0.3003 | 0.0078 | 0.2796 | −0.1047 | killed |
| R3C magnetic lineaments | 0.3023 | 0.0079 | 0.2815 | −0.1028 | killed |
| R3D scarplet linkage | 0.3322 | 0.0056 | 0.3056 | −0.0787 | killed |
| R3AC cones + magnetics | 0.2930 | 0.0078 | 0.2726 | −0.1116 | killed |
| BMUL-R3A | 0.3624 | 0.0607 | 0.3790 | −0.0052 | killed |
| BMUL-R3AC | 0.3599 | 0.0598 | 0.3758 | −0.0084 | killed |
| BMUL-R3Dp (follow-up, prior channel) | 0.3673 | 0.0612 | 0.3842 | +0.0000 | **null** |

Cumulative gate tally: **11 source-backed arms killed across rounds 2–3, one
promoted blend, zero wasted slots.** The null establishes the
support-extensibility constraint on every future prior idea.

## Round-5 real-data gate record (2026-09-28/29, session 14GEMSDOE) — INTERRUPTED, no slot spent

First gate in this project to run on the **real** competition rasters
(`data/raw/*`, SHA-256-verified; see `research/real_data_unlock.md`).
Command:

```bash
./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
  --arms geom geo geom_ramp geom_acc geom_tilt geom_curv geom_gap all \
  --n-pos 20000 --n-neg 40000 --iters 150 --out artifacts/holdout_real.json
```

Protocol: 3,199 catalogue components; per fold TEST 640 / CALIB 640 / HIDE 1120
components; the model trains on the always-visible 25 % plus HIDE (TEST and HIDE
absent from the *training view*, so "distance to a mapped trace" cannot leak the
target), then predicts with the submission-time context (full catalogue minus
TEST). Emission policy = top-q by probability, q chosen on the hidden CALIB
components; here q = 0.005 (25,837 px ≈ 0.50 % of the 5,167,373-px footprint).
`dense` = all TEST pixels, `sparse` = 20 % subsample, `far` = TEST pixels
> 1,000 m from any context trace.

**The run completed fold 0 and fold 1, was in fold 2, and stopped when the
sandbox was reset** (the workspace snapshot keeps git-tracked files only, so
`data/raw`, `data/processed` and `.venv` were removed mid-run, taking the saved
fields with them). The numbers below are therefore an **interim record of a
2-of-4-fold run**, transcribed from the run log before the reset. They are
*not* a completed gate and no decision is taken on them.

| Arm | f0 dense | f0 sparse | f0 far | f1 dense | f1 sparse | f1 far | sparse wins vs geom | far wins vs geom |
|---|---|---|---|---|---|---|---|---|
| **geom** (baseline, 12 geom features) | 0.0381 | 0.0165 | 0.0006 | 0.0381 | 0.0145 | 0.0006 | — | — |
| geo (+ 12 official bands) | 0.0421 | 0.0186 | 0.0033 | 0.0330 | 0.0132 | 0.0012 | 1/2 | 2/2 |
| geom_ramp (R5-1) | 0.0422 | 0.0186 | 0.0033 | 0.0337 | 0.0135 | 0.0012 | 1/2 | 2/2 |
| geom_acc (R5-2) | 0.0420 | 0.0185 | 0.0034 | 0.0330 | 0.0128 | 0.0010 | 1/2 | 2/2 |
| geom_tilt (R5-3) | 0.0423 | 0.0186 | 0.0033 | 0.0333 | 0.0133 | 0.0010 | 1/2 | 2/2 |
| **geom_curv (R5-4)** | **0.0445** | **0.0196** | **0.0050** | **0.0429** | **0.0179** | **0.0062** | **2/2** | **2/2** |
| geom_gap (R5-5) | 0.0436 | 0.0189 | 0.0023 | 0.0345 | 0.0144 | 0.0012 | 1/2 | 2/2 |
| **all (R5-1…R5-5)** | **0.0450** | **0.0198** | 0.0043 | 0.0422 | 0.0173 | **0.0053** | **2/2** | **2/2** |

Fold 2 (incomplete when the reset hit): geom 0.0333/0.0142/0.0000, geo
0.0335/0.0154/0.0014, geom_ramp 0.0327/0.0149/0.0013, geom_acc
0.0327/0.0150/0.0012.

### What the interim record already says (all of it conditional on 2 folds)

1. **R5-4 profile curvature is the strongest single addition measured in this
   project to date** (+0.0064 dense / +0.0031 sparse / +0.0044 far on fold 0;
   +0.0048 / +0.0034 / +0.0056 on fold 1, all vs the geom baseline at the same
   calibrated budget). It is the only round-5 arm that wins both protocols in
   both completed folds.
2. **Every arm improves the `far` protocol** (2/2 folds) — i.e. all five
   mechanisms do add information about TEST pixels that are >1 km from any other
   catalogue trace, which is the closest available analogue of a genuinely
   unmapped structure. The failures are on `sparse`, where the extra features
   dilute the linear model in fold 1.
3. **The calibrated budget is ~0.5 % of the footprint** (25,837 px), 6× smaller
   than the 155,021 px the group historically shipped. On the real rasters, the
   calibrated top-0.5 % beats everything else the sweep can express — consistent
   with the metric's "quality of support, not mass" behaviour.
4. **Absolute levels are low** (0.033–0.045 dense, ≤0.006 far). These are
   hide-and-recover catalogue numbers on a 20 % component TEST split, not
   leaderboard estimates; the withheld new-fault population is different in kind.

### Gate status (R5)

`artifacts/holdout_real.json` was **not written** in the first attempt (interrupted at fold 2). The rerun after the environment restore is documented below; the promote rule is unchanged (beat geom on both sparse and far in ≥ 3 of 4 folds), and no submission slot was spent on the interim outcome.

## Round-6 real-data gate record (2026-09-29, session 14GEMSDOE) — R6-1 horsetail splay VALIDATED, 4 folds

**Command (full validation of top candidate):**
```bash
./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
  --arms geom geom_horse --n-pos 20000 --n-neg 40000 --iters 150 \
  --out artifacts/holdout_round6_horse.json
```
Grid 3730×3292 valid 5,167,373 catalogue 60,988 px, comps 3,199 TEST 640 / CALIB 640 / HIDE 1120 / visible 799 per fold. Emission calibrated on CALIB only (top-k 0.5% or 1%).

| Fold | geom dense / sparse / far | geom_horse dense / sparse / far | Δ dense | Δ sparse | Δ far | Wins vs geom |
|------|---------------------------|----------------------------------|---------|----------|-------|--------------|
| 0 | 0.0381 / 0.0165 / 0.0006 | 0.0627 / 0.0211 / 0.0041 | +0.0246 | +0.0046 | +0.0035 | 3/3 |
| 1 | 0.0381 / 0.0145 / 0.0006 | 0.0659 / 0.0233 / 0.0041 | +0.0278 | +0.0088 | +0.0035 | 3/3 |
| 2 | 0.0333 / 0.0142 / 0.0000 | 0.0494 / 0.0206 / 0.0019 | +0.0161 | +0.0064 | +0.0019 | 3/3 |
| 3 | 0.0444 / 0.0153 / 0.0002 | 0.0715 / 0.0215 / 0.0059 | +0.0271 | +0.0062 | +0.0057 | 3/3 |
| **Mean** | **0.0385 / 0.0151 / 0.0003** | **0.0624 / 0.0217 / 0.0040** | **+0.0239** | **+0.0066** | **+0.0037** | **4/4 sparse & 4/4 far** |

**Promote rule:** beat geom on both sparse and far in ≥3 of 4 folds. **R6-1 horsetail splay fan meets rule 4/4 and is PROMOTED.** First arm in this project to meet promote rule on real data.

**Comparison vs R5-4 profile curvature (previous best single addition):**
- Fold0: horse 0.0627/0.0211/0.0041 vs curv 0.0446/0.0203/0.0054 → horse +0.0181 dense, +0.0008 sparse, -0.0013 far
- Fold1: horse 0.0659/0.0233/0.0041 vs curv 0.0424/0.0173/0.0059 → horse +0.0235 dense, +0.0060 sparse, -0.0018 far
- Curv wins far by ~0.0015, horse wins dense/sparse. Combination all6 interim (fold0 0.0675/0.0212/0.0068, fold1 0.0767/0.0268/0.0095) beats both single arms, suggesting ensemble best.

**Other R6 arms — smoke 800×800 crop, 2 folds, 20 iters (diagnostic, not gate):**
- geom: dense 0.0142 sparse 0.0078 far 0.0000
- geom_horse: 0.0499 / 0.0225 / 0.0045 (+0.0357/+0.0147/+0.0045)
- geom_xsec: 0.0369 / 0.0143 / 0.0003 (+0.0226/+0.0065/+0.0003)
- geom_condbase: 0.0337 / 0.0172 / 0.0000 (+0.0195/+0.0094/0)
- geom_shore: 0.0353 / 0.0178 / 0.0027 (+0.0211/+0.0100/+0.0027)

All R6 arms improve dense and sparse vs geom in smoke; horse best on all three, shore second on far. Full-grid validation for xsec/condbase/shore interrupted after 1 fold (see /tmp/full4.log); no decision taken yet. File: `artifacts/holdout_round6_horse.json` is the only completed 4-fold gate for R6.

**Block protocol (512 px blocks, purge 3 px):**
All arms ~0.0001 dense — block protocol too harsh (TEST block has no nearby context). Component far protocol (>1 km) is meaningful spatially-blocked metric. File: `/tmp/holdout_round6_block.json`.

**Submission built from validated arm:**
- Averaged 4 fold fields (hide-and-recover ensemble)
- Emission budget median of CALIB-chosen fractions = top 1.00% → 51,674 px (1% of footprint)
- File: `submissions/GEMS_r5-geom-horse-ensemble_20260929T012833Z_b9d51ebb.tif` — float32 [0,1] finite, 0 outside, passes validate_submission.py, uniqueness audit PASS
- Site payload swapped to real: `docs/js/payload.js` kind=real, pixels_sha256 aa966e56…

### Gate status (R6)

`artifacts/holdout_round6_horse.json` **written** (4 folds). R6-1 promoted. R6-2/3/5 pending full-grid rerun. No submission slot spent yet in this session — validated field ready for next weekly slot. Next actions: (1) full 4-fold for all6 (R5+R6) to test ensemble, (2) fetch external slip/dilation shapefile for R6-4, (3) upload promoted horse ensemble.


## Round-6 remaining arms + session-15 gate record (2026-09-29) — R6-3 and R6-5 PROMOTED, 4 folds

**Command (queue item 3, full-grid validation of the remaining R6 arms):**
```bash
./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
  --arms geom geom_xsec geom_condbase geom_shore --n-pos 20000 --n-neg 40000 --iters 150 \
  --out artifacts/holdout_round6_rest.json
```
Wall 1,724 s. The `geom` baseline reproduced the pinned 4-fold means exactly
(0.0385 / 0.0151 / 0.0003 — identical to `holdout_round6_horse.json`), pinning
protocol equivalence across runs.

| Fold | geom dense / sparse / far | xsec | condbase | shore |
|------|---------------------------|------|----------|-------|
| 0 | 0.0381 / 0.0165 / 0.0006 | 0.0427 / 0.0191 / 0.0034 | 0.0431 / 0.0189 / 0.0030 | 0.0497 / 0.0219 / 0.0072 |
| 1 | 0.0381 / 0.0145 / 0.0006 | 0.0318 / 0.0119 / 0.0008 | 0.0323 / 0.0126 / 0.0011 | 0.0433 / 0.0185 / 0.0029 |
| 2 | 0.0333 / 0.0142 / 0.0000 | 0.0281 / 0.0140 / 0.0010 | 0.0348 / 0.0163 / 0.0021 | 0.0375 / 0.0169 / 0.0022 |
| 3 | 0.0444 / 0.0153 / 0.0002 | 0.0444 / 0.0167 / 0.0012 | 0.0486 / 0.0186 / 0.0024 | 0.0502 / 0.0193 / 0.0030 |
| **Mean** | **0.0385 / 0.0151 / 0.0003** | 0.0367 / 0.0154 / 0.0016 | 0.0397 / 0.0166 / 0.0022 | **0.0452 / 0.0191 / 0.0038** |
| Wins vs geom (sparse / far) | — | 2/4 / 4/4 | 3/4 / 4/4 | **4/4 / 4/4** |
| Promote rule (≥3/4 both) | — | **no** (sparse fails) | **PROMOTED** | **PROMOTED** |

* **R6-5 paleo-shoreline (sub-lake enhancement) is the strongest far-protocol
  single arm in the project** (far 0.0038 ≈ 13× the geom baseline, 4/4 wins on
  both protocols; dense +0.0067, sparse +0.0040). It is also the arm with the
  clearest physical story from the label producers (S14: lake sediments obscure
  non-Holocene ruptures).
* **R6-3 conductive-base step** meets the rule (3/4 sparse, 4/4 far; far 7×
  baseline) and is promoted.
* **R6-2 intersection halos does NOT meet the rule** (sparse 2/4; fold-1 and
  fold-2 dense fell below geom). Its smoke-crop improvement did not survive the
  full grid. Recorded as a kill-by-rule, not a crash: the far protocol wins
  4/4 (0.0016 vs 0.0003), so the mechanism is real but too thin on sparse.
* Previous session's smoke numbers (800×800 crop, 2 folds) over-rated xsec and
  under-rated shore; smoke crops are diagnostics only, per their own caveat.

**Session-15 environment record.** The sandbox reset dropped `.venv/`,
`data/raw/`, `data/processed/` and the gate fields; everything was rebuilt from
the Quickstart (bridge retry loop after one transient `gh api` stream error;
all three files SHA-256 verified; `verify_real_data.py` ALL CHECKS PASS).
`scripts/train_real_full.py` (queue item 5) was rewritten against the current
gate API and pinned by `tests/test_train_real_full_api.py` (7 tests). The
leaderboard feed was refreshed (50 rows, DARD 0.3168 top, the 0.1563 cluster
extradr19/SDCF9/smashi34 unchanged at #28–30). The first all6 4-fold attempt
was **OOM-killed (exit 137) at fold 2** after folds 0–1 reproduced the interim
record exactly (all6 0.0675/0.0212/0.0068, 0.0767/0.0268/0.0095); it is being
re-run with 2 arms per process (`artifacts/holdout_round6_all6.json`).

## Reading

Most ≥0.14 scores in this ledger are reported for catalogue-oriented approaches,
but scores alone cannot establish one shared artifact family. The published
GEMSDOE1/5GEMSDOE builders appear to encode the same field; other repeated scores
remain unresolved without artifact hashes or DrivenData IDs. Going forward,
record each generated file's full prediction-array hash, TIFF hash, policy,
validation result and (after upload) platform submission ID. Filenames alone are
not uniqueness evidence; run `scripts/check_submission_uniqueness.py` before
upload and require the real blocked-holdout gate to beat its incumbent.

### Answering the two questions the brief asks directly

**"Why do 5GEMSDOE and GEMSDOE1 have the same score (0.1563)?"** The repo
cannot prove the cause of their uploaded scores. Their published pages display
the same artifact-hash prefix (`7f00890a…`), run-length payload count (259,495),
and histogram. That is strong evidence their *site builders* present the same
prediction field, but the original upload binaries and DrivenData submission IDs
are absent, so upload-level identity remains unverified. If those published
fields were uploaded, identical predictions would necessarily produce identical
scores. 8GEMSDOE's 0.1563 is a rounded-score match only; its artifact is unknown.
Other leaderboard accounts' four-decimal ties likewise do not prove a shared
field.

**"Are we copying the same work over and over?"** The available evidence is
mixed. GEMSDOE1/5GEMSDOE published builders appear to encode the same field;
short IDs also repeat for #14/#15 and #18/#19. We cannot prove which fields were
uploaded without the original artifacts and platform IDs, and rounded scores
alone do not establish reuse. The audit now blocks exact TIFF and prediction-array
hash duplicates among local artifacts, while reporting rounded-score and
truncated-ID collisions for review. Keep a full prediction hash and submission
ID for every future upload; do not use leaderboard scores as uniqueness keys.

---

## Round-7 gates 4 — R7-3 and R7-5 PROMOTED (2026-09-29)

**Command (gate 4, `/tmp/run_gates4.sh`, exit 0, wall ~46 min):**
```bash
./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
  --arms geom geom_gravtopo geom_trans --n-pos 20000 --n-neg 40000 --iters 150 \
  --out artifacts/holdout_round7.json
```
`geom` baseline reproduced the pinned means again (fold rows identical to
`holdout_round6_rest.json`). File: `artifacts/holdout_round7.json`.

| Fold | geom dense / sparse / far | geom_gravtopo (R7-3) | geom_trans (R7-5) |
|------|---------------------------|----------------------|-------------------|
| 0 | 0.0381 / 0.0165 / 0.0006 | 0.0410 / 0.0183 / 0.0033 | 0.0429 / 0.0201 / 0.0038 |
| 1 | 0.0381 / 0.0145 / 0.0006 | 0.0329 / 0.0133 / 0.0014 | 0.0364 / 0.0136 / 0.0017 |
| 2 | 0.0333 / 0.0142 / 0.0000 | 0.0335 / 0.0158 / 0.0020 | 0.0374 / 0.0177 / 0.0034 |
| 3 | 0.0444 / 0.0153 / 0.0002 | 0.0482 / 0.0180 / 0.0024 | 0.0487 / 0.0184 / 0.0032 |
| Wins vs geom (sparse / far) | — | **3/4 / 4/4 → PROMOTED** | **3/4 / 4/4 → PROMOTED** |

Both fail fold 1 on dense/sparse (the 5513-conflict fold); both win far on all
four folds. `geom_trans` is the stronger arm (fold-0 sparse +22 %, far ≈6×
geom). Prior UPDATE: match-scale *cross-aspect gravity-direction coherence*
(`prior_contrast_hits.md` P1, 3/3 matches) was implemented as R7-3's
topology term and PROMOTED here. FLAG #12 (dilatation sign) stands.

## R7-2 continuation subset diagnostic (2026-09-29)

**Command:** `./.venv/bin/python scripts/continuation_subset.py --gate
artifacts/holdout_round6_rest.json --arms geom_shore geom_condbase --out
artifacts/continuation_subset_r6rest.json` (no re-training; split ids + fold
fields). **52.5 % of TEST pixels belong to continuation components** (hidden
component with an endpoint within 20 px of a visible endpoint, strikes within
30°). Recovery of that class is ~2.5× the isolated class (shore: cont 0.0471
vs iso 0.0193; condbase: cont 0.0420 vs 0.0162). The C21 continuation class is
the mass of the truth population; the isolated remainder is where R7-2's
bridge must reach. Suite: 157 tests (3 new).

## Round-7 gates 5–7 + all6 decision (2026-09-29) — R7-1 PROMOTED, all6 ineligible for the slot

**R7-1 `geom_align` decision (pre-registered rule: win δ=2 and not lose δ=0):**
- δ=0 (`artifacts/holdout_round7_align_d0.json`, no --misreg-px → default 0):
  sparse 3/4 (0.0176/0.0132/0.0149/0.0168 vs geom 0.0165/0.0145/0.0142/0.0153),
  far **4/4** (0.0064/0.0016/0.0020/0.0037 — fold-0 far 0.0064 best single far yet).
  Not lost ✓
- δ=2 (`artifacts/holdout_round7_align_d2.json`, `--misreg-px 2` protocol stress:
  one rigid shift per catalogue component, shared by every view of every fold;
  TEST truth never displaced; baseline sees the same misregistered world):
  sparse **4/4** (0.0188/0.0175/0.0170/0.0174), far **4/4** (0.0070/0.0033/0.0040/
  0.0060). Wins ✓
→ **R7-1 PROMOTED.** Interpretation caveat: the stress trains both arms on the
displaced world but only geom_align models/corrects the displacement; a
correction-only-on-the-align-side asymmetry is part of the arm design.

**GATE 7 `all6` vs horse (pre-registered: all6 needs sparse AND far ≥3/4
fold wins; else the slot goes to the rebuilt horse ensemble — §B1):**
`artifacts/holdout_round6_all6.json` (exit 0 — the incremental `_f16` memory
fix held through all 4 folds):

| Fold | all6 dense / sparse / far | horse (pinned, ledger above) | all6 wins? |
|------|---------------------------|------------------------------|------------|
| 0 | 0.0676 / 0.0214 / 0.0068 | 0.0627 / 0.0211 / 0.0041 | S+F |
| 1 | 0.0766 / 0.0268 / 0.0094 | 0.0659 / 0.0233 / 0.0041 | S+F |
| 2 | 0.0594 / 0.0193 / 0.0069 | 0.0494 / 0.0206 / 0.0019 | F only |
| 3 | 0.0680 / 0.0207 / 0.0063 | 0.0715 / 0.0215 / 0.0059 | F only |
| **Mean** | **0.0679 / 0.0221 / 0.0074** | **0.0624 / 0.0217 / 0.0040** | **sparse 2/4, far 4/4** |

**Decision: all6 FAILS the sparse ≥3/4 rule (2/4) despite better means — the
fold-wise rule stands. Submission field = rebuilt `geom_horse` 4-fold ensemble**
(horse gate re-run: `artifacts/holdout_round6_horse.json`, repinning the
pinned rows). If a future all6-class arm adds a sparse-stable term (R7-2
bridge is the candidate), re-test under the same rule.

## Submission artifact rebuilt after the reset (2026-09-29) — horse ensemble, HUMAN upload pending

The round-6 horse TIFF (`GEMS_r5-geom-horse-ensemble_20260929T012833Z_b9d51ebb.tif`)
and its manifest were lost in the workspace reset (`submissions/` is
gitignored); the site payload (`docs/js/payload.js`, committed in PR #8)
survived with `pixels_sha256=aa966e56…`. Rebuilt byte-identically from the
re-pinned gate (`artifacts/holdout_round6_horse.json`, all 4 folds reproduce
the pinned rows exactly):

- **Command:** `./.venv/bin/python scripts/build_real_submission.py --gate
  artifacts/holdout_round6_horse.json --arm geom_horse`
- **Artifact:** `submissions/GEMS_r5-geom-horse-ensemble_20260929T044943Z_b9d51ebb.tif`
  — tif sha256 `b9d51ebbde12…` (identical container hash to the lost file:
  same bytes), prediction sha256 `aa966e5672db…`, 51,674 px emitted
  (top 1.00%, CALIB-median budget), validate_submission PASS, [0,1] finite.
- **Zero uploads of these pixels exist** (leaderboard n=3 unchanged; no slot
  spent). One upload is planned per §B1. "Never re-upload byte-identical"
  protects uploads, not rebuilds after loss — recorded here so the rebuild is
  never mistaken for a second artifact (F8 would have caught two manifests).
- **Uniqueness audit:** `check_submission_uniqueness.py` → **PASS** after the
  F7 design-gap fix (FLAG #13) and the documented payload re-source
  (`build_site_payload.py submissions/GEMS_..._044943Z_b9d51ebb.tif`).
  F5 warnings retained by design (score 0.1563 ties ≠ artifact identity).
- Payload pixels unchanged (aa966e56); only the header `Source:` name moved
  from the lost 01:28 filename to the rebuilt one.

## Round-7 gate 8 (2026-09-29) — R7-2 PROMOTED; horse7 fails the sparse rule, horse artifact stands

**Command (`/tmp/run_gates5.sh`, exit 0, wall ~44 min):**
```bash
./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
  --arms geom geom_stitch geom_horse horse7 --n-pos 20000 --n-neg 40000 --iters 150 \
  --out artifacts/holdout_round7_stitch_horse7.json
```
`geom` and `geom_horse` reproduce the pinned fold rows exactly (protocol
equivalence across the 5th consecutive gate). File:
`artifacts/holdout_round7_stitch_horse7.json`.

| Fold | geom | geom_stitch (R7-2) | geom_horse | horse7 |
|------|------|--------------------|-----------|--------|
| 0 | 0.0381/0.0165/0.0006 | 0.0435/0.0192/0.0037 | 0.0627/0.0211/0.0041 | 0.0681/0.0184/0.0080 |
| 1 | 0.0381/0.0145/0.0006 | 0.0333/0.0131/0.0011 | 0.0659/0.0233/0.0041 | 0.0754/0.0266/0.0073 |
| 2 | 0.0333/0.0142/0.0000 | 0.0359/0.0171/0.0018 | 0.0494/0.0206/0.0019 | 0.0723/0.0192/0.0097 |
| 3 | 0.0444/0.0153/0.0002 | 0.0487/0.0178/0.0019 | 0.0715/0.0215/0.0059 | 0.0748/0.0220/0.0062 |
| **Mean** | 0.0385/0.0151/0.0003 | **0.0403/0.0168/0.0021** | 0.0624/0.0217/0.0040 | **0.0727/0.0215/0.0078** |
| Wins vs bench | — | **sparse 3/4, far 4/4 → R7-2 PROMOTED** | — | **sparse 2/4, far 4/4 → slot rule FAILS** |

**R7-2 pre-registered continuation-subset report** (same gate, split ids + fold
fields, `artifacts/continuation_subset_r7stitch*.json`; subset = TEST
components with an endpoint within 20 px of a visible endpoint and strike
within 30°; 52.5 % of TEST px):

| arm | subset dense | continuation | isolated |
|-----|--------------|--------------|----------|
| geom | 0.0385 | 0.0427 | 0.0138 |
| geom_stitch | 0.0403 | 0.0428 | **0.0164** (+19 %) |
| geom_horse | 0.0623 | 0.0565 | 0.0272 |
| horse7 | 0.0727 | 0.0610 | 0.0294 |

The bridge's gain is in the *isolated* remainder, not the 20-px continuation
window — its 48-px walk reaches past the diagnostic's tip window exactly as the
earlier subset analysis predicted ("the isolated remainder is where R7-2's
bridge must reach"). All five round-7 hypotheses are now decided: R7-1/2/3/5
PROMOTED, R7-4 killed.

**horse7 decision:** mean dense +0.0103 and far nearly double vs horse, but
sparse loses on folds 0 and 2 (−0.0027, −0.0014; CALIB drifted to topk:0.02 on
those folds — the wider budget dilutes sparse-at-t). The pre-registered
fold-wise rule is not bent for better means (same outcome as all6). **The
built horse artifact remains the single upload candidate** (b9d51ebb /
pred aa966e56, uniqueness audit PASS, zero uploads). Next ensemble attempt
should target sparse stability (e.g. a sparse-constrained CALIB policy) rather
than more channels.
