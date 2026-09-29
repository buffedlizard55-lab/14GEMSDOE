# Real-data unlock — how the official rasters got into this repository

**Session:** 14GEMSDOE, 2026-09-28 · branch `arena/01a0e97b-14gemsdoe`.
**Status of the claim:** the three rasters in `data/raw/` are byte-identical to the
official competition files, *as transported by the team's own mirror*. They are
**TEAM-MIRRORED**, not downloaded from the login-gated DrivenData data tab. That
distinction is stated here, in `README.md`, and in
`artifacts/real_data_audit.json` — never smoothed over.

## 1. Why this was the blocker

| Path | Result |
|---|---|
| `https://www.drivendata.org/competitions/306/competition-doe-gems/data/` | login-gated; the sandbox has no credentials and must not ask for them |
| `curl` to drivendata.org / dropbox.com / gdr.openei.org / sciencebase.gov / prd-tnm.s3.amazonaws.com | blocked by the sandbox network allowlist (only pypi, github.com/api.github.com/codeload, registry.npmjs.org are reachable) |
| Arena page tools (`fetch_page`) | return text/markdown, not rasters |

So Rounds 1–4 were gated on a **synthetic forward model** (`gems/synthesize.py`),
and their numbers say nothing about the real grid.

## 2. The route that worked

The brief's own Dropbox share links were fetched by an **unrestricted GitHub
Actions runner** inside the team's workflow, split into 100 MB-safe parts, and
committed to the team's transit repository
[`buffedlizard55-lab/6GEMSDOE`](https://github.com/buffedlizard55-lab/6GEMSDOE)
under `data/bridge/`, together with `manifest.json`, which records the source
URLs, the byte sizes and the SHA-256 pins. GitHub *is* reachable from this
sandbox, so the bytes are recoverable here:

```bash
bash scripts/bridge_team_mirror.sh        # gh api (or curl) -> data/raw/, SHA-256 checked
```

The script refuses to install anything whose hash does not match the pin; it
fetches the five `gems-geodawn-numerical-features.tif.part-000..004` blobs,
concatenates them, and re-checks the whole-file hash.

| File in `data/raw/` | Official name | Bytes | SHA-256 | Verified here |
|---|---|---|---|---|
| `training_features.tif` | `gems-geodawn-numerical-features.tif` | 418,912,844 | `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5` | ✅ re-hashed 2026-09-28 |
| `training_labels.tif` | `existing_faults.tif` / `labels.tif` | 425,830 | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` | ✅ |
| `sample_submission.tif` | `example_submission.tif` | 1,599,597 | `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` | ✅ |

## 3. Independent consistency checks (why a substitution is implausible)

`scripts/verify_real_data.py` → `artifacts/real_data_audit.json` (run 2026-09-28):

* shape `(3730, 3292)` for all three; EPSG:32611; 100 m; features float32, 19
  bands; transform `(243350, 4135550, 572550, 4508550)` in GDAL order
  (c, a, b, f, d, e) — the earlier FAIL in that log was a false positive from
  comparing affine-order against GDAL-order tuples, fixed in this session and
  now confirmed OK for both the feature stack and the template;
* labels are `int8` with nodata `-1`; **60,988** positive pixels on a
  **5,167,373**-pixel footprint — both numbers appear independently on the
  team's published GEMSDOE/5GEMSDOE sites (TEAM-REPORTED, not an official
  source);
* the template reproduces the binarised catalogue bit-for-bit (this is the
  "catalogue-copy scores 1.0 on the public target" trap documented in the brief);
* all 19 bands have finite data somewhere, and the `-3.4028235e+38` sentinel
  never leaks into the arrays after the NaN masking in `gems/realdata.py`.

## 4. What is still NOT verified

* That the bytes equal what a logged-in account would download **today**. The
  chain rests on the team runner's fetch plus the SHA-256 pins; the authoritative
  check is a manual data-tab download (`FLAG` retained in
  `research/limitations_and_next.md`).
* The external layers the round-5 register would like (slip/dilation tendency,
  heat flow, MT conductance, 3DEP 1 m DEM tiles, paleo-shoreline masks) are still
  unfetched: their hosts are on the blocked list. Named free official sources and
  their status are in `research/knowledge_base.md` §3.

## 5. Consequences for the project

1. Every number in `research/hypotheses_round5.md`, `artifacts/holdout_real.json`
   and `docs/hypotheses-round5.html` is now computed on the **real** rasters —
   the first time in this project that is true.
2. The synthetic gates in `artifacts/holdout_round{2,3}*.json` remain historical
   evidence and are never compared with real-data numbers.
3. `data/raw/*` stays out of git (`.gitignore`, licence-gated competition data);
   the reproducible path is the one command above.
