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
