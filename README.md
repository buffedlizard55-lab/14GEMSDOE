# 14GEMSDOE — GEMS Prize Challenge

**Goal: place top of the leaderboard in the [GEMS Prize Challenge](https://www.drivendata.org/competitions/306/competition-doe-gems/)**
(Geologic Enhanced Mapping System, US DOE Office of Geothermal) by finding
geological **faults missing from the public USGS/INGENIOUS catalogue** in the
GeoDAWN region — the structures that indicate hidden geothermal resources.

**Live status site (GitHub Pages):** `docs/index.html` in this repo — executive
summary first, one-click submission `.tif` builder, verified source tables,
leaderboard feed. **Start there to make a submission.**

---

## ⚡ 60-second submission

1. Open the site → **Build submission.tif** → the file downloads with a unique name.
2. Copy the **Note** shown beside it.
3. DrivenData → *Submit* → *Make new submission* → choose the file → paste the Note.
4. If the form says *"Predicted values must be in range [0, 1]"* — the site's
   [How to submit §6](docs/how-to-submit.html#rejection) has the exact fix.

---

## Standing prompt — read at the start of every session

> The goal of this project is to place top of the leaderboard in this
> competition. We need a project that can compete and place top of the
> leaderboard. Understand the problem, collect all the data and organize it into
> a clean easily auditable table with official verified links for manual
> verification.
>
> Work line by line verifying from official verified trusted sources, provide
> links for manual review. There should be no manual input, work on your own to
> complete tasks. Flag any irregularities for review. **No hallucinations.
> Verify line by line.**
>
> We need to figure out why we keep scoring 0.1563 — are we copying the same
> work over and over? We need different ideas, not the same idea tried a
> different way. Never re-upload byte-identical prediction artifacts. A repeated
> leaderboard score rounded to four decimals is an audit trigger, not proof that
> two prediction rasters are identical; compare the pixel-array hash and platform
> submission records where available.
>
> Generate 3–5 candidate geological hypotheses we haven't tried yet, each
> naming: the specific layer(s) involved, the physical signature being targeted,
> why it should catch a fault missing from the USGS/INGENIOUS catalogue rather
> than one already in it, and how it differs from anything already implemented.
> Rank them by expected DTI improvement and implementation cost. Validate the
> top candidate on our spatially-blocked holdout set before touching a weekly
> submission slot — do not spend a submission slot on an idea that hasn't beaten
> the current holdout best. If a candidate can't be validated without new
> external data, name the specific free, official source needed and check it's
> obtainable before proposing the idea as viable.
>
> Catalogue geometry and published structural geology seed the hypotheses
> (Faulds et al.: step-overs/relay ramps host ~32% of catalogued Great Basin
> systems, terminations and normal/strike-slip intersections ~22% each,
> accommodation zones ~8% — settings of overlapping strands, horsetail tips and
> many small connecting faults; our hypothesis: such small connecting structures
> are what regional catalogues most often omit — to be tested, not assumed).
> Turn them into features and candidate corridors: distance and azimuth to the
> nearest known trace; along-strike versus across-strike distance to trace
> endpoints; overlapping-tip detection and bridging corridors; intersection
> density; the angle between a local lineament and neighboring known strikes;
> slip and dilation tendency from the INGENIOUS release. Add a completeness
> angle: compare known-fault density with what strain rate, relief and
> range-front geometry would predict; treat strongly negative residuals that
> coincide with independent geophysical or topographic evidence as gap
> candidates. Train only through hide-and-recover, hiding a random share of
> known traces from the context inputs each epoch and scoring recovery of the
> hidden ones — so the model cannot read "distance to a known fault = 0" as the
> answer.
>
> Deep research into the part that matters most — the scientific discovery of
> geothermal resources. Store all information and knowledge gathered from
> official verified sources as a starting point for other projects. Think
> outside the box but stay grounded in proper scientific research; be contrarian
> but smart. Find sources of data others are overlooking.
>
> The site must generate the submission TIF as easily as download-and-click,
> obvious when you visit. Explain exactly how to make a submission in an
> executive summary. Give every submission a unique name and a short comment to
> tell submissions apart.
>
> **Round-2 directive (2026-09-28).** Stop re-shipping the catalogue skeleton.
> Generate 3–5 geological hypotheses we have NOT tried, each naming the specific
> layers, the physical signature (edge-detection or curvature transform), why it
> catches a fault missing from the USGS/INGENIOUS catalogue rather than one
> already in it, and how it differs from anything already in the repo. Rank by
> expected DTI gain and implementation cost. Validate the top candidate on the
> spatially-blocked holdout BEFORE touching a weekly submission slot — never
> spend a slot on an idea that has not beaten the current real-data holdout best.
> If a candidate needs new external data, name the specific free official source
> and verify availability. Figure out why we keep scoring 0.1563 and whether
> 5GEMSDOE and GEMSDOE1 reused an artifact; never re-upload a byte-identical
> prediction raster. A four-decimal score tie is not proof of identical work.
> Do deep research into geothermal systems; store official-source evidence and
> limitations. Think outside the box but stay grounded in science. Find data
> others overlook. Be contrarian but smart. Track the live public leaderboard
> (checked 2026-09-28: DARD 0.3168; not directly comparable to local synthetic
> or blocked-holdout scores). Keep the Core Values (Maximize P(Win), Own the
> Outcome) focal to every decision.
>
> **Core values: Maximize P(Win)** — in every decision weigh tradeoffs, assess
> risk, choose the path that maximizes the probability of winning. **Own the
> outcome** — we own results end to end; problems are acted on without waiting
> for permission; failure and success are signals we improve from.
>
> Run every task through multiple passes: (1) implement completely and verify;
> (2) review for bugs, missing requirements, wrong assumptions, edge cases and
> fix them; (3) re-check against the original request, improve accuracy,
> reliability, completeness and code quality. Do not stop after the first pass.

*This block is the project's constitution. Every deliverable in this repo is
traced to a line of it in the table below.*

## Round-2 result — what the blocked holdout actually decided (2026-09-28)

Nine feature arms, one model, one protocol
(`scripts/validate_round2.py` → `artifacts/holdout_round2.json`):

| arm | recovery | discovery | combined DTI | Δ vs baseline | decision |
|---|---|---|---|---|---|
| baseline (catalogue geometry + fields) | 0.3073 | 0.0081 | 0.2863 | — | incumbent |
| N1 gravity-gradient edge terminations | 0.3003 | 0.0087 | 0.2804 | −0.0059 | **killed** |
| N2 seismicity / strain lineaments | 0.3218 | 0.0569 | 0.3352 | +0.0489 | promoted |
| N3 alteration-cap margin | 0.3086 | 0.0057 | 0.2855 | −0.0008 | killed |
| N5 range-front topographic step | 0.3214 | 0.0050 | 0.2961 | +0.0097 | promoted |
| GEO-ONLY / BLEND(max) / BLEND-ADD | 0.08–0.18 | 0.02–0.03 | 0.10–0.20 | negative | killed |
| **BLEND-MUL `classifier × (1 + 0.5·prior)`** | **0.3673** | **0.0612** | **0.3842** | **+0.0979** | **promoted** |

Three findings that change the strategy:

1. **The literature-ranked top candidate was killed by the gate — and that is the
   gate working.** N1 (gravity-gradient terminations) had a verbatim statement
   from the INGENIOUS authors backing it and the lowest cost, and it still made
   the holdout worse. No slot was spent on it.
2. **A multiplicative blend of classifier and geophysics beats both.** It is the
   only form that improves recovery *and* discovery; additive and max blends
   smear probability mass and pay FP without lifting the per-truth-pixel maximum.
3. **A catalogue-trained model is structurally bad at discovery — and discovery
   is the entire competition.** The baseline's discovery DTI is 0.0081 because it
   has never been shown a fault that is absent from the catalogue, while the
   prize masks known-fault pixels and scores only off-catalogue faults.

Full record with sources, layer names, transforms and the honesty statement:
**[`research/hypotheses_round2.md`](research/hypotheses_round2.md)**.

## Round-3 result — five new hypotheses, gate says keep the incumbent (2026-09-28)

Session 14 pre-registered five genuinely new candidates
(`scripts/validate_round3.py` → `artifacts/holdout_round3.json`, identical
round-2 protocol, incumbent reproduced exactly):

| candidate | layers / transform | Δ combined vs incumbent | decision |
|---|---|---|---|
| R3A tip-continuation cones | catalogue geometry; oriented decaying wedge past each trace tip | −0.1071 | **killed** |
| R3B completeness-angle residual | ridge OLS of catalogue density on relief/strain/range-front; signed residual | −0.1047 | **killed** |
| R3C magnetic-basement lineaments | structure-tensor + ridge skeleton on magnetics; strike agreement | −0.1028 | **killed** |
| R3D scarplet curvature-linkage | Laplacian curvature → trend closing → bridge pixels | −0.0787 (best non-blend, +0.019 vs baseline) | **killed** |
| R3E tendency-weighted corridors | slip/dilation tendency × corridors | not gated — external raster pending | **not slot-eligible** |
| BMUL-R3A / BMUL-R3AC (incumbent stacks) | ALL + R3 blocks | −0.0052 / −0.0084 | **killed** |
| BMUL-R3Dp (bridge into the prior) | prior-channel test | **+0.0000** | **null — mechanism found** |

Two findings:

1. **The incumbent survived its strongest challenge yet.** Every plausible new
   idea lost to `classifier(ALL) × (1+0.5·prior)` (0.3842). The gate has now
   killed eleven source-backed arms across two rounds; no submission slot was
   ever spent on a loser.
2. **The multiplicative prior can only re-weight the classifier's support — it
   can never extend it** (the null: at a bridge pixel the classifier scores ~0,
   (1+0.5·prior)·0 = 0; where the classifier is ~1 the product clips at 1).
   Any future "field X through the prior" idea must first show pixel overlap
   with the classifier's confident support. The remaining leverage is the real
   rasters, then U-Net capacity — not more logistic-era feature arms.

Full record: **[`research/hypotheses_round3.md`](research/hypotheses_round3.md)**,
site page **`docs/hypotheses-round3.html`**.

## Round-4 research — pre-registered, not slot-eligible (2026-09-28)

A new review produced four candidate mechanisms that are not duplicate feature
arms: (1) multi-physics edge topology across gravity, magnetics and conductivity;
(2) channel deflection/offset from USGS 3DEP elevation plus 3DHP hydrography;
(3) geologic-contact offset graphs from USGS/Nevada map data; and (4) signed,
alternating scarp-polarity sequences from high-resolution elevation. Each entry
names its layers, signature, missing-fault rationale, repo-difference, qualitative
upside/cost, source and unresolved availability checks in
[`research/hypotheses_round4.md`](research/hypotheses_round4.md).

**No real-data validation was possible and no slot was spent.** `data/raw/`,
`data/processed/`, and `data/external/` contain only placeholders. The top
candidate is therefore a research hypothesis, not an implemented or validated
improvement. Existing round-2/3 scores are explicitly synthetic and must not be
compared with the public leaderboard score. This review installed test
requirements into the ignored `.venv/` and verified **102 tests passed**; that
checks software behavior, not geology or competition performance. Slot decision:
**HOLD** until a real, spatially-blocked hide-and-recover result beats the
real-data incumbent.

### Audit correction: repeated scores are not duplicate-file evidence

The GEMSDOE1 and 5GEMSDOE Pages currently publish the same pinned artifact SHA
prefix (`7f00890a…`) and the same run-length payload description. That is strong
evidence their *published builders* encode the same prediction field. The repo
does not contain the original upload binaries or DrivenData submission IDs, so
it cannot independently prove which exact file was uploaded. The reported
0.1563 leaderboard ties for 8GEMSDOE or other accounts do **not** prove identical
rasters: scores are rounded to four decimals and different fields can yield the
same displayed score. Hash each actual pixel array and retain submission IDs;
use score collisions only to trigger a provenance audit. The ledger also has
repeated shortened artifact IDs (`6452ae1d00`, `0c9199f14e62`) for separate
entries; the uniqueness script flags them for review, but the missing original
files prevent proving whether those uploads duplicated predictions.

## How this repo fulfils the prompt

| Prompt requirement | Where it lives | Verified by |
|---|---|---|
| Auditable data table with official links | `docs/data.html`, `research/knowledge_base.md` | every row carries its source URL + check date |
| No hallucinations; verify line by line | `research/knowledge_base.md` (VERIFIED/TEAM-REPORTED/FLAG vocabulary) | irregularities section `research/limitations_and_next.md` §C |
| Why 0.1563; unique submissions | `research/scoring_analysis.md`, `research/results_ledger.md` | matching published builder metadata; upload binaries/IDs unavailable; exact prediction hashes are the only duplicate proof |
| 3–5 ranked geological hypotheses + layers/signatures/why-missing/differences | `docs/hypotheses.html`, `research/hypotheses.md` | sources verified; ranking decision log |
| Holdout gate before any submission slot | `gems/blocks.py`, `scripts/validate_blocks.py`, `scripts/validate_round2.py`, slot log on `docs/leaderboard.html` | `tests/test_blocks.py`, `tests/test_hypotheses_round2.py` |
| Round-2 hypotheses N1–N5 | `research/hypotheses_round2.md`, `gems/hypotheses.py`, `gems/geoedges.py`, `docs/hypotheses-round2.html` | holdout values are synthetic; not real competition validation |
| Round-4 novel hypotheses and validation status | `research/hypotheses_round4.md`, `docs/hypotheses-round4.html` | four ranked candidates; real holdout blocked; no slot spent |
| Unique prediction artifacts | `scripts/check_submission_uniqueness.py`, `scripts/build_submission.py` (prediction-array + TIFF hashes) | exact hash collision is hard failure; rounded scores are review warnings only |
| External data obtainability checked, not assumed | `research/knowledge_base.md` §3 + T8, `scripts/download_external_data.sh` | every row carries URL + check date; reachability measured 2026-09-28 |
| External data: named free official sources, obtainability checked | `research/knowledge_base.md` §3, `scripts/download_external_data.sh` | GDR 1391 + ScienceBase DOIs opened 2026-09-28 |
| Catalogue-geometry features + corridors | `gems/features.py` | `tests/test_features.py` |
| Slip/dilation tendency (INGENIOUS) | `gems/features.py::load_external_raster`, DOI 10.5066/P9YL58W6 | source table |
| Completeness angle (strain/relief vs catalogue) | H5 in `docs/hypotheses.html` | gate defined per hypothesis |
| Hide-and-recover training | `gems/hide_recover.py`, `scripts/train_hide_recover.py` | leak invariant asserted every epoch; `tests/test_hide_recover.py` |
| Site: obvious TIF generation | `docs/index.html` (hero builder), `docs/js/tif_writer.js` | `tests/test_tif_writer.py` (node ↔ rasterio bit-compare) |
| Executive summary: exactly how to submit | `docs/how-to-submit.html` | rejection modes reproduced in tests |
| Unique name + short comment per submission | `scripts/build_submission.py` (`GEMS_<policy>_<UTC>_<sha8>.tif` + NOTE.txt + MANIFEST.json) | `tests/test_submission_gate.py` |
| Up-to-date feed; no manual checking | `scripts/refresh_leaderboard.py` → `docs/leaderboard.html` | `tests/test_leaderboard_parser.py` |
| Multi-pass working | session log in `research/limitations_and_next.md` | passes recorded per session |

## Public leaderboard check (2026-09-28)

* Leaderboard #1 **DARD 0.3168** (the brief's "0.3049" figure is stale — FLAG #3;
  top-5 re-verified live, T11).
* Team-thread reported scores include 0.1563 / 0.1461 / 0.1193; they are not
  independently tied to submission IDs in this checkout. GEMSDOE1 and 5GEMSDOE
  pages show matching artifact metadata, but their upload binaries/IDs are absent.
  Other 0.1563 ties are not proof of duplicate predictions.
* Deadline **Dec 3, 2026 23:59 UTC**; 3 submissions/week (rolling window, C22);
  one file scored in both rounds; Phase 2 ($250k) re-scores against
  expert-expanded labels.
* **Submission-form fact (T9/FLAG #10):** the form rejects NaN-nodata files with
  "Predicted values must be in range [0, 1]". The site's default download and
  `build_submission.py` now emit finite files (0.0 outside the footprint —
  score-neutral).

## Repository map

```
README.md                  ← you are here (standing prompt above)
docs/                      ← GitHub Pages site (executive summary + TIF builder,
                             round-1 + round-2 hypothesis pages)
gems/
  dti.py                   ← the official metric (equations transcribed, tested)
  features.py              ← catalogue-geometry features (distance, azimuth,
                             along/across, relay corridors, junction density,
                             strike mismatch, slip/dilation tendency)
  geoedges.py              ← NEW: gravity-gradient ridges, edge terminations,
                             junctions, alteration-cap margin
  hypotheses.py            ← NEW: the N1–N5 arm feature blocks
  hide_recover.py          ← hide-and-recover protocol + anti-leak invariant
  blocks.py                ← spatially-blocked folds with purge buffer
  raster.py                ← GeoTIFF read/write + submission format gate
  synthesize.py            ← synthetic GeoDAWN-like forward model, now with a
                             catalogue/true-fault split and geophysical analogues
scripts/
  validate_round2.py       ← round-2 hypothesis A/B gate (the slot currency)
  validate_round3.py       ← NEW: round-3 gate (R3 arms vs the true incumbent)
  check_submission_uniqueness.py ← exact TIFF/prediction-hash gate; rounded scores warn
  build_submission.py      ← unique sha8 name + NOTE + MANIFEST + format gate
                             (clamps to [0,1], fixes NaN — T9)
  train_hide_recover.py    ← hide-and-recover training (arm-aware, R3 context-safe)
  download_competition_data.sh ← team-provided Dropbox shares (unverified) + sha256
  build_features.py, build_site_payload.py, refresh_leaderboard.py,
  download_external_data.sh, prepare_data.py,
  make_demo.py, validate_blocks.py, validate_submission.py
tests/                     ← 101 tests: metric vectors, leak invariant, format gate,
                             JS↔Python GeoTIFF parity, block splits, feed parser,
                             geoedge geometry, R3 arm geometry/leak-safety,
                             mirror-list guard, uniqueness gate
research/                  ← knowledge base, scoring analysis, round-1/2/3
                             hypothesis records, results ledger, limitations
data/raw/                  ← competition data goes here (one command — see below)
data/external/             ← free external layers (scripts/download_external_data.sh)
submissions/               ← built submission files + NOTE + MANIFEST (never re-used)
artifacts/                 ← holdout JSON + model runs; git-ignored EXCEPT the
                             tracked gate evidence holdout_round2.json /
                             holdout_round3.json / holdout_round3_followup.json
```

## Quickstart

```bash
# 0. environment (first time on any machine; numpy/scipy/rasterio/scikit-image):
python3 -m venv .venv
./.venv/bin/pip install numpy scipy rasterio scikit-image pytest

# 1. attempt data placement. The Dropbox links supplied in the project brief
#    are team-provided shares, not verified official mirrors. Hashes record
#    downloaded bytes but do not authenticate them. Confirm files against the
#    official login-gated data tab before training; use its download if unsure.
bash scripts/download_competition_data.sh
python3 scripts/prepare_data.py

# 2. free external layers (unrestricted machine):
bash scripts/download_external_data.sh

# 3. train through hide-and-recover and score the spatially-blocked holdout:
python3 scripts/train_hide_recover.py
python3 scripts/validate_blocks.py        # ← the only number that may spend a slot

# 3b. the hypothesis gates (round 2 = N-arms + blends; round 3 = R3 arms +
#     incumbent stacks; both run on the synthetic forward model today and
#     unchanged on the real rasters once data/processed/ exists):
python3 scripts/validate_round2.py
python3 scripts/validate_round3.py
python3 scripts/check_submission_uniqueness.py   # must exit 0 before any upload

# 4. build + validate a uniquely-named submission:
python3 scripts/build_submission.py artifacts/pred.npy --policy "bmul w0.5 holdout<VALUE>"

# 5. ship it to the site's one-click builder:
python3 scripts/build_site_payload.py submissions/GEMS_*.tif

# tests (102 passed in this review) and the synthetic end-to-end demo:
./.venv/bin/python -m pytest tests -q
./.venv/bin/python scripts/make_demo.py
```

## Limitations in the way (full queue: `research/limitations_and_next.md`)

1. **Competition data is not present.** `bash scripts/download_competition_data.sh`
   can fetch team-provided Dropbox shares on machines with network access, but
   those links are not independently authenticated as official competition
   mirrors. SHA256 records file integrity only, not source identity. The official
   DrivenData data tab is login-gated. Verify the downloaded rasters and source
   metadata against the official files before training. Until actual labels and
   features are present, all holdout numbers in this repo are synthetic-model
   results and cannot establish leaderboard improvement.
2. **This sandbox TLS-allowlists {pypi, pythonhosted, github, api.github,
   codeload, npmjs}** (re-measured 2026-09-28, T8) — Dropbox/GDR/ScienceBase
   downloads and the DEM tiles must be fetched elsewhere; the Arena page-fetch
   tools *do* reach those hosts, which is how every source in
   `knowledge_base.md` was verified.
3. **No GPU here** — logistic-baseline protocol work only; U-Net port queued
   (the reference solution's exact hyperparameters are recorded, C24). Round 3
   showed the logistic model's *support* is now the binding constraint
   (prior-extensibility null), so capacity is the next lever after real data.
4. **4 of the 19 feature bands are not named in any public document** (15 are,
   C27) — read all 19 `description`/`data_category` tags on arrival; the code
   refuses to guess.
5. **No verified free official paleo-shoreline dataset yet** — this blocks
   hypothesis N4 (lidar scarp + shoreline suppression) until one is sourced
   (FLAG #1b).
6. **Submission-form range check rejects NaN** anywhere in the raster (T9,
   FLAG #10) — finite emission is the default everywhere (site builder +
   `build_submission.py`), and the value gate refuses out-of-range builds.

## Honesty rules (non-negotiable)

* Every external claim carries its URL and check date; anything unverified is
  labelled `TEAM-REPORTED` or `FLAG`, never stated as fact.
* Blank scores stay blank. Disagreements between brief and official sources are
  recorded as irregularities with both values.
* Tests reproduce every past failure mode deliberately so it cannot recur.
