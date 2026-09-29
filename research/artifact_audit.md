# Artifact audit — why 0.1563 kept appearing, and whether it was duplicated work

**Session:** 14GEMSDOE, 2026-09-28. **Status:** every claim below was re-derived in
this sandbox from the group's own public repositories and from the eight scored
prediction rasters vendored in `buffedlizard55-lab/7GEMSDOE/external/scored/`.
Nothing here is inferred from a file *name*; every identity claim is a content
hash.

Reproduce:

```bash
# 1. content hashes + prediction hashes + catalogue overlap of the eight scored files
./.venv/bin/python scripts/audit_scored_artifacts.py \
    /tmp/g7/external/scored/*.tif --json artifacts/scored_artifact_audit.json

# 2. the duplicate-blob check (needs gh with repo read access)
gh api "repos/buffedlizard55-lab/GEMSDOE/git/trees/HEAD?recursive=1"   > /tmp/tree_GEMSDOE.json
gh api "repos/buffedlizard55-lab/5GEMSDOE/git/trees/HEAD?recursive=1" > /tmp/tree_5GEMSDOE.json
python3 - <<'PY'
import json
for r in ("GEMSDOE", "5GEMSDOE"):
    t = json.load(open(f"/tmp/tree_{r}.json"))["tree"]
    for x in t:
        if x["path"].endswith("submission.tif") and x.get("size") == 570890:
            print(r, x["path"], x["sha"], x["size"])
PY
```

## 1. The direct answer: yes, two of the published artifacts are the same bytes

| Evidence | Value |
|---|---|
| `data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif` in **GEMSDOE** | git blob `812e61b74050d1350cc2bde1fab0c76ead32e0c4`, 570,890 B |
| the **same path** in **5GEMSDOE** | identical blob `812e61b74050d1350cc2bde1fab0c76ead32e0c4`, 570,890 B |
| 5GEMSDOE also keeps it as `data/evidence/leaderboard_anchor/gemsdoe-ens12-adopted-7f00890a.tif` | same blob |
| SHA-256 of the file, re-downloaded from GEMSDOE `HEAD` in this session | `7f00890a62878d612fb5eef67a9a364a2df819433dde74b6762ce4fc0fc4fe15` |
| SHA-256 of the vendored scored copy in 7GEMSDOE (`gemsdoe1-ens12-7f00890a.tif`) | identical |
| `docs/submission_field.bin` (the payload **both websites** ship) | identical blob `6a89b64e01a7c11b8235449c538390ac3435605d`, 532,072 B in both |
| `data/evidence/baseline/submission.tif` (and `baseline_rerun/`) | identical blob `6926b76f24e8846238b7cdfd2276d1c723d44cfd`, 545,798 B in both |

A git blob SHA-1 is a content hash, so identical values mean identical bytes
regardless of commit dates or branch names. **Repositories duplicated; bytes
duplicated.**

What is *not* verifiable here, and is therefore not claimed: which account
uploaded which file. DrivenData submission IDs and the uploaded binaries appear
nowhere in the group's repositories. The group's own record
(`7GEMSDOE/external/scored/manifest.json`) attributes the 570,890-byte file to
account **GEMSDOE1 / extradr19** with public score **0.1563**, and notes that
**SDCF9 later showed 0.1563 on the leaderboard from an unrecorded file**. The
live leaderboard (fetched 2026-09-28) shows exactly three accounts on 0.1563:
#27 extradr19, #28 SDCF9, #29 smashi34 — no other top-50 row shares that score.

## 2. Are the eight scored artifacts different work? Mostly yes — see the table

| File | Score | Bytes | Prediction-array SHA-256 (prefix) | Positive px | On catalogue | Within 300 m of catalogue |
|---|---|---|---|---|---|---|
| `gems6-hgb88-topk03-33cec71ff0.tif` | 0.0286 | 1,652,883 | `74e1bd986d23a37d…` | 155,021 | 23,605 | 73.1 % |
| `gemsdoe1-ens12-7f00890a.tif` | **0.1563** | 570,890 | `cc063e629aec10ea…` | 172,974 | 6,455 | 21.6 % |
| `gemsdoe2-dual-union-f68e590f.tif` | 0.156 | 568,065 | `e6483ccef108bfe8…` | 183,642 | 7,693 | 23.2 % |
| `gemsdoe3-pindrop-discovery-37f9d5b855.tif` | 0.083 | 777,446 | `73ac14d815b4c206…` | 155,021 | 0 | 8.5 % |
| `gemsdoe3-pindrop-nodes-f347b70daa.tif` | 0.1193 | 777,822 | `9e0084c3ed3da5b3…` | 155,021 | 0 | 8.8 % |
| `gemsdoe3-pindrop-ridge-4e03fc9705.tif` | 0.1152 | 651,948 | `e45fc88ed2d69059…` | 155,021 | 0 | 19.5 % |
| `gemsdoe3-sgmc-gap-7251c22bb4.tif` *(never uploaded)* | — | 426,346 | `b21d53e97e6df340…` | 61,664 | 0 | 0.0 % |
| `gemsdoe4-combined-237f0063.tif` | 0.0343 | 505,882 | `b7f8d297a5f2cb3a…` | 264,247 | 5,924 | 14.7 % |

Eight files, **eight distinct prediction arrays** (pairwise Jaccard ≤ 0.11 except
one pair). So the group was not re-uploading one raster — with two qualifications:

1. **`ens12` and `dual-union` are near-duplicate supports:** Jaccard 0.94,
   scores 0.1563 vs 0.1560 — different bytes, same idea, 0.0003 apart. That is a
   *repeated strategy*, not a repeated file.
2. **Every field is binary and thin** (`mass == n_pos`, 1.2–5.1 % of the
   5,167,373-pixel footprint). The whole submission history is a search over
   *supports* at a frozen emission style; the metric algebra in
   `research/hypotheses_round5.md` §1 shows binary emission is correct *given* a
   support, so the search was in the right space — it just never left the
   catalogue's neighbourhood.

## 3. What the eight scores say about the real target

* **Selection dominates budget.** Three "pindrop" submissions used an identical
  budget of exactly **155,021 positive pixels** and scored 0.0830 / 0.1152 /
  0.1193 — a spread of 0.036, which is larger than any feature-level change the
  group has ever measured. The pixels, not the volume, decide the score.
* **Catalogue-hugging is the worst arm.** The file with 73 % of its mass within
  300 m of the catalogue scored 0.0286 — *below* the all-ones-everywhere
  reference (0.0579 on the catalogue target). Files with 8–20 % catalogue overlap
  scored 3–4× higher.
* **A single submission can move 40 places.** `op01` went 0.1293 → 0.2489
  (#44 → #7) between two live leaderboard reads on 2026-09-28. The plateau is an
  emission-policy problem, not a data problem.

## 4. Residual unknowns (flagged, not smoothed over)

* **Upload-level identity** for the three 0.1563 accounts cannot be established
  without DrivenData submission IDs. Artifact-level identity between the two
  repositories is proven; the mapping file→account is group-record only, and the
  manifest itself marks the dual-union pairing as `UNVERIFIED`.
* **The four-decimal tie is not evidence of anything** — a rounded score is not
  a hash. `scripts/check_submission_uniqueness.py` therefore fails on a
  *prediction-array* collision and only warns on a repeated rounded score.
* **The dual-union file's score is recorded as 0.156**, not 0.1563; the live
  leaderboard's three 0.1563 rows are extradr19, SDCF9, smashi34, and SDCF9's
  0.1563 is explicitly recorded as coming from an unrecorded file.
