# Results ledger — every submission this group has made (as recorded)

Sources: the project thread (TEAM-REPORTED) and the published run sites
(VERIFIED where noted). Scores appear exactly as reported; blanks stay blank.
This ledger exists so no two entries can silently be the same work again.

| # | Entry / run id | Reported score | Description (per thread/site) | Artifact id | Unique? | Evidence |
|---|----------------|----------------|-------------------------------|-------------|---------|----------|
| 1 | GEMSDOE1 | 0.1563 | ens12-adopted-floor0.1-w0 skeleton; in-browser builder | `7f00890a…` | reference | site pins hash (VERIFIED 2026-09-28) |
| 2 | (6GEMSDOE site) | 0.0286 | divergent probe | — | yes | thread |
| 3 | GEMSDOE3 "Pindrop nodes" | 0.1193 | SUBMIT FIRST | f347b70daa | yes | thread (matches LB smrtdoog5 0.1193) |
| 4 | GEMSDOE2 | 0.1560 | near-duplicate family of #1 | — | near-dup | thread |
| 5 | GEMSDOE3 "catalogue-gap target" | 0.0830 | SECOND SYSTEM | 37f9d5b855 | yes | thread |
| 6 | GEMSDOE4 | 0.0343 | divergent probe | — | yes | thread |
| 7 | GEMSDOE3 "dense ridge control" | 0.1152 | CONTROL · UPLOAD LAST | 4e03fc9705 | yes | thread |
| 8 | 5GEMSDOE | 0.1563 | **same payload as #1** | `7f00890a…` | **NO** | site pins identical hash (VERIFIED) |
| 9 | 7GEMSDOE | 0.1461 | (matches LB wbg1) | — | yes | thread |
| 10 | 8GEMSDOE | 0.1563 | score-identical to #1 family | — | **likely NO** | thread |
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

## Cross-checks against the public leaderboard (2026-09-28 snapshot)

* #26 extradr19 = 0.1563, #27 SDCF9 = 0.1563, #28 smashi34 = 0.1563 —
  three-way exact tie; ties to 4 decimals mean equal TP_w/FP_w/FN_w, i.e.
  effectively equal prediction fields (VERIFIED rows, inference recorded).
* #33 wbg1 = 0.1461 matches entry 9 (VERIFIED row).
* #48 smrtdoog5 = 0.1193 matches entry 3 (VERIFIED row).

## Reading

Scores ≥ 0.14 in this ledger are all the catalogue-skeleton family (#1/#4/#8/#10
and their thin variants). The divergent ideas (#2, #6, #11, #12, #17, and the
0.03–0.05 probes) were never developed past a first upload — each is an idea
that could have been validated off-line first. Going forward: entries are only
created by `scripts/build_submission.py` (unique name + sha8 + note), and the
slot log on `docs/leaderboard.html` must show a holdout delta before upload.
