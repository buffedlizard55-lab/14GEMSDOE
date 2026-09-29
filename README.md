# 14GEMSDOE — GEMS Prize Challenge

**Goal: place top of the leaderboard in the [GEMS Prize Challenge](https://www.drivendata.org/competitions/306/competition-doe-gems/)**
(Geologic Enhanced Mapping System, US DOE Office of Geothermal) by finding
geological **faults missing from the public USGS/INGENIOUS catalogue** in the
GeoDAWN region — the structures that indicate hidden geothermal resources.

**Live status site (GitHub Pages):** `docs/index.html` in this repo — executive
summary first, one-click submission `.tif` builder, verified source tables,
leaderboard feed, artifact audit. **Start there to make a submission.**

---

## ⚡ 60-second submission

1. Open the site → **Build submission.tif** → the file downloads with a unique name.
2. Copy the **Note** shown beside it (it names the arm, the holdout value and the
   artifact hash).
3. DrivenData → *Submit* → *Make new submission* → choose the file → paste the Note.
4. The file is **finite everywhere inside the scored footprint** and `0.0` outside.
   If the form still answers *"Predicted values must be in range [0, 1]"*, see
   [How to submit §6](docs/how-to-submit.html#rejection) — the observed cause is a
   NaN or an out-of-range value anywhere in the raster.

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
> different way. Never re-upload a byte-identical prediction artifact. A repeated
> leaderboard score rounded to four decimals is an audit trigger, not proof that
> two prediction rasters are identical; compare the prediction-array hash, and
> when the upload records are missing, say so instead of asserting identity.
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
> density; the angle between a local lineament and neighbouring known strikes;
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
> **Session-14 directives (2026-09-28).** (1) The data blocker is closed: verify
> the real rasters by hash and grid before any modelling
> (`scripts/bridge_team_mirror.sh`, `scripts/verify_real_data.py`). (2) Answer
> the 0.1563 question with hashes — a rounded-score tie is evidence of nothing;
> a matching prediction-array SHA-256 is evidence of everything. (3) The metric
> pays for **recall**, not for a frozen 2 % budget: add a pixel when
> ΔTP/ΔFP > 0.2·D/(1−0.2·D) (= 0.0323 at D = 0.1563), and scaling a support up
> never lowers the score — so the emission policy, not the feature list, is the
> first thing to test on real data. (4) Validate every new arm on the real
> hide-and-recover gate before spending a slot; a synthetic-model number is not
> evidence. (5) Record every result — winners *and* kills — with the exact
> command that produced it.
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

## State of the project — 2026-09-29 (session 14GEMSDOE)

### 1. The data is real, in the repo's working tree, and hash-verified

| File | Bytes | SHA-256 | Grid |
|---|---|---|---|
| `data/raw/training_features.tif` (19 bands) | 418,912,844 | `4371c82e3b8339b807bdffcf4ef59a225520fe2988d521be208ae33743123bc5` | 3,730 × 3,292, EPSG:32611, 100 m, float32, nodata `-3.4028235e+38` |
| `data/raw/training_labels.tif` | 425,830 | `7ba308ccdc4418b31a178f4f1ef21aaa6e152e4028f2f6f64b01f7eb25ae4093` | same grid, int8, nodata `-1` |
| `data/raw/sample_submission.tif` | 1,599,597 | `2176d08e485aa2cd2860ce8df539db4faf4d76163b38a4dd8c30a40454d35cbc` | same grid, float32, nodata NaN |

Fetch with **`bash scripts/bridge_team_mirror.sh`** (the group's own transit
mirror through the GitHub Contents API; every byte SHA-256-checked), then
**`python3 scripts/verify_real_data.py`** which re-measures the grid, CRS, band
count, band descriptions, nodata sentinel, the 60,988-pixel catalogue and the
5,167,373-pixel footprint against the official specification and writes
`artifacts/real_data_audit.json`. The rasters are licence-gated competition data
and are **not** tracked in git; only the hashes and the audit are.

This closes the previous session's stated blocker. The files are
**team-mirrored**, i.e. transported from the shares named in the project brief
rather than downloaded from the login-gated data tab; that distinction is
recorded in `research/real_data_unlock.md` and is why the verification script
measures the files against independent expectations instead of trusting a name.

### 2. Why the group kept scoring 0.1563 — answered with hashes

`research/artifact_audit.md`, evidence `artifacts/scored_artifact_audit.json`:

* **GEMSDOE1 and 5GEMSDOE published byte-identical files.** Their copies of
  `data/evidence/runs/ens12-adopted-floor0.1-w0/submission.tif` carry the same
  git blob SHA-1 (`812e61b7…`), the same 570,890 bytes and the same SHA-256
  (`7f00890a…`). Identical pixels ⇒ identical score. This is *artifact-level*
  proof; the upload-level claim still rests on group records, because no
  DrivenData submission IDs exist in any of the group's repositories.
* **Eight scored artifacts, eight distinct prediction arrays** — the group has
  not been uploading one file over and over. But two of them (`ens12` 0.1563 and
  `dual-union` 0.1560) overlap with Jaccard 0.94: the same idea twice.
* **The three "pindrop" submissions used an identical 155,021-pixel budget and
  scored 0.0830 / 0.1152 / 0.1193.** Selection moved the score by 0.036 — more
  than any feature round has.
* **The catalogue-hugging field scored worst** (0.0286, with 73 % of its mass
  inside 300 m of the catalogue) while fields with 8–20 % catalogue overlap
  scored 3–4× higher. The scored population is not the catalogue neighbourhood.

### 3. The metric algebra that the whole group was missing

`DTI = T/(0.2T + 0.2E + 0.8·N_t)`, so a pixel is worth emitting iff
`ΔT/ΔE > 0.2·D/(1 − 0.2·D)` — **0.0323 at D = 0.1563**, 0.0677 at the leader's
0.3168 — and scaling an existing support up (`p → c·p`) *never* lowers the score
(monotone in `c`). Binary emission is therefore optimal given a support, and the
binding question is not "which feature" but **"what support"**. This is derived,
not fitted, and it is checked numerically in `tests/test_dti_fast.py` against the
reference transcription of the published equations.

### 4. Round 5: five new hypotheses, gated on the real rasters

`research/hypotheses_round5.md` — R5-1 relay-ramp interior maturity, R5-2
accommodation-zone transfer corridors between opposed-polarity systems, R5-3
amplitude-normalised magnetic tilt angle co-located with gravity edges, R5-4
range-front profile-curvature (fan-buried) response, R5-5 conditioned
completeness residual. Each entry names its layers, its physical signature, why
it should catch a fault *missing* from the catalogue, and its difference from
every arm previously run here or in the sibling registers (H1–H41). Ranking and
the pre-registered decision rule are in that document.

The gate is `scripts/validate_real.py` — real rasters, two-view hide-and-recover
component split (TEST 20 % / CALIB 20 % / HIDE 35 % / visible 25 %; the model
trains with TEST **and** HIDE removed so "distance to a mapped trace" cannot leak
the target, then predicts with the submission-time context), emission policy
calibrated on hidden CALIB components only, scored with the official metric on
`dense`, `sparse(20 %)` and `far` (>1 km from any context trace) truth protocols.

**Status (2026-09-29, session 15): superseded by the round-6 gates.** The
round-5 full-grid run was interrupted twice (sandbox resets) and its interim
2-fold table is preserved in `research/results_ledger.md`. The completed
round-6 gates (`artifacts/holdout_round6_horse.json`,
`artifacts/holdout_round6_rest.json`) run the same protocol with four folds:
**R6-1 horsetail splay, R6-5 paleo-shoreline and R6-3 conductive-base step each
meet the promote rule** (sparse AND far in ≥3/4 folds vs the same-run geom
baseline); R6-2 intersection halos is killed by rule. The all6 ensemble gate
(R5+R6) completed: 0.0679/0.0221/0.0074 vs horse 0.0624/0.0217/0.0040 — better
means but sparse wins on only 2/4 folds, so the pre-registered fold-wise rule
sends the weekly slot to the rebuilt horse ensemble
(`submissions/GEMS_r5-geom-horse-ensemble_20260929T044943Z_b9d51ebb.tif`,
uniqueness audit PASS, HUMAN upload pending). Round-7 hypotheses — grounded in
C28 (misregistration-as-target) and C21 (continuations-as-truth) — were
pre-registered in `research/hypotheses_round7.md` and gated this session:
**R7-1, R7-2, R7-3, R7-5 PROMOTED** (far 4/4 each; R7-2's buried-continuation
bridge lifts the isolated truth subset +19 %), R7-4 killed by the prior. Two
ensemble attempts (all6, then the pre-registered horse7 = horse + R7-1/3/5)
both fail the fold-wise sparse rule (2/4) despite better means — the horse
artifact stands as the single upload candidate.

## How this repo fulfils the prompt

| Prompt requirement | Where it lives | Verified by |
|---|---|---|
| Auditable data table with official links | `docs/data.html`, `research/knowledge_base.md` | every row carries its source URL + check date |
| Real competition data verified before use | `scripts/bridge_team_mirror.sh`, `scripts/verify_real_data.py`, `artifacts/real_data_audit.json` | grid/CRS/bands/nodata/catalogue-pixel checks against the official spec |
| No hallucinations; verify line by line | `research/knowledge_base.md` (VERIFIED / TEAM-REPORTED / FLAG vocabulary), `research/limitations_and_next.md` §C | irregularities enumerated with both values |
| Why 0.1563; unique submissions | `research/artifact_audit.md`, `artifacts/scored_artifact_audit.json` | git blob SHA-1 = byte identity across two repos; 8/8 distinct prediction arrays |
| 3–5 ranked geological hypotheses with layers/signature/why-missing/differences | `research/hypotheses_round7.md` (rounds 1–6 archived alongside), `docs/hypotheses-round7.html` | pre-registered before each gate ran |
| Holdout gate before any submission slot | `scripts/validate_real.py`, `gems/realchannels.py`, `tests/` | real rasters; calibration on hidden traces only |
| Catalogue-geometry features + corridors | `gems/realchannels.py` (distance/azimuth, along- vs across-strike, endpoint distance, relay corridors, accommodation corridors, junction density, strike mismatch) | `tests/test_realchannels.py` |
| Completeness angle (strain/relief/range-front vs catalogue) | `gems/realchannels.completeness_residual` (+ R5-5 conditioning) | fit restricted to the training footprint |
| Slip/dilation tendency (INGENIOUS) | `gems/features.py::load_external_raster`, DOI 10.5061/… see KB §3 | source table; raster not yet fetched (FLAG #1b) |
| Hide-and-recover training | `gems/hide_recover.py`, `scripts/validate_real.py --protocol component` | anti-leak invariant; calibration traces never seen by the scored model |
| Emission policy derived from the metric | `gems/dti_fast.py`, `scripts/validate_real.py` sweep | `tests/test_dti_fast.py` (reference-agreement + NMS equivalence) |
| Site: obvious TIF generation | `docs/index.html` (hero builder), `docs/js/tif_writer.js` | `tests/test_tif_writer.py` |
| Executive summary: exactly how to submit | `docs/how-to-submit.html` | rejection modes reproduced in tests |
| Unique name + short comment per submission | `scripts/build_submission.py` (`GEMS_<policy>_<UTC>_<sha8>.tif` + NOTE + MANIFEST) | `tests/test_submission_gate.py` |
| Up-to-date feed; no manual checking | `scripts/refresh_leaderboard.py` → `docs/leaderboard.html` | `tests/test_leaderboard_parser.py` |
| Multi-pass working | session log in `research/limitations_and_next.md` | passes recorded per session |

## Public leaderboard check (live, fetched 2026-09-28 this session)

Source: <https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/>
(read directly, rows 1–50; full row list in `research/leaderboard_snapshot.json`,
feed regenerated into `docs/js/leaderboard.js`).

* #1 **DARD 0.3168** (11 submissions); #2 alexoktaba 0.2993; #3 HardcoreTechGod
  0.2854; #4 mzoorob 0.2843; #5 joeyfezster 0.2806; #6 GrigorSargsyan 0.2742;
  #7 op01 0.2489. The brief's "0.3049" figure is stale (FLAG #3).
* **`op01` moved 0.1293 → 0.2489 in this refresh** (from #44 to #7, 1 h 57 min
  before the fetch): a single submission can jump 40 places, so the plateau is
  not a ceiling — it is an emission-policy problem, not a data problem.
* **DrivenData's own reference account `doegemsDrivendata` is #19 with 0.1847** —
  the reference U-Net trained to reproduce the catalogue is *not* the frontier,
  consistent with the scored population excluding the catalogue.
* **The 0.1563 plateau is now exactly three consecutive accounts** — #27
  extradr19, #28 SDCF9, #29 smashi34 (3 / 3 / 2 submissions) — and the group has
  *proven* that GEMSDOE and 5GEMSDOE publish byte-identical artifacts
  (`research/artifact_audit.md`). No other leaderboard row in the top 50 shows
  that score.
* Other group rows: #34 wbg1 0.1461, #48 smrtdoog5 0.1193.
* Deadline **Dec 3, 2026 23:59 UTC**; 3 submissions per rolling week (C22); one
  file is scored in both phases; Phase 2 ($250k) re-scores against
  expert-expanded labels.

## Repository map

```
README.md                  ← you are here (standing prompt above)
docs/                      ← GitHub Pages site: executive summary, TIF builder,
                             data table, hypotheses (rounds 1–5), artifact audit
gems/
  dti.py                   ← reference transcription of the official metric + tests
  dti_fast.py              ← float32 full-grid metric, NMS/top-k/threshold emitters
  realdata.py              ← real raster access (labels, template, bands, hashes)
  realchannels.py          ← catalogue geometry, geophysics, curvature,
                             completeness, round-5 channels (R5-1 … R5-5)
  features.py              ← round-1 feature library (synthetic + real capable)
  geoedges.py, hypotheses.py ← round-2/3 arms (synthetic-model era)
  hide_recover.py, blocks.py ← hide-and-recover protocol + spatial blocks
  raster.py                ← GeoTIFF I/O + submission format gate
  synthesize.py            ← legacy synthetic forward model (rounds 1–3 only)
scripts/
  bridge_team_mirror.sh    ← fetch + SHA-256-verify the real rasters
  verify_real_data.py      ← official-spec audit → artifacts/real_data_audit.json
  validate_real.py         ← THE gate: real rasters, hide-and-recover, emission sweep
  audit_scored_artifacts.py ← artifact identity audit (file + pixel hashes, Jaccard)
  check_submission_uniqueness.py ← blocks byte-identical prediction arrays
  build_submission.py      ← unique name + NOTE + MANIFEST + format gate
  prepare_data.py, build_features.py, train_hide_recover.py,
  validate_blocks.py, validate_round2.py, validate_round3.py,
  build_site_payload.py, refresh_leaderboard.py, download_external_data.sh
tests/                     ← unit + protocol tests (see `pytest tests -q`)
research/                  ← knowledge base, round-1…5 hypothesis records,
                             artifact audit, results ledger, limitations
data/raw/                  ← real rasters (git-ignored; fetch with the bridge script)
data/processed/            ← grid.json, valid_mask.npy, known_faults.npy, channels/
artifacts/                 ← gate results + audits (git-ignored except the
                             documented holdout JSONs)
submissions/               ← built submission files + NOTE + MANIFEST (never re-used)
```

## Quickstart

```bash
# 0. environment  (NOTE: .venv/, data/ and artifacts/ other than the three
#    whitelisted holdout JSONs do NOT survive a sandbox reset — after a reset,
#    start here)
python3 -m venv .venv
./.venv/bin/pip install numpy scipy rasterio scikit-image scikit-learn pytest

# 1. real data (needs gh or curl; SHA-256 verified) + official-spec audit
bash scripts/bridge_team_mirror.sh
./.venv/bin/python scripts/verify_real_data.py
./.venv/bin/python scripts/prepare_data.py

# 2. THE gate: real rasters, hide-and-recover, plus the emission sweep
./.venv/bin/python scripts/validate_real.py --protocol component --folds 4 \
    --arms geom geo geom_ramp geom_acc geom_tilt geom_curv geom_gap all \
    --n-pos 20000 --n-neg 40000 --iters 150 --out artifacts/holdout_real.json
./.venv/bin/python scripts/sweep_real.py --gate artifacts/holdout_real.json \
    --out artifacts/emission_sweep.json          # policy chosen on CALIB only

# 3. (optional) the spatial-block protocol, for extrapolation behaviour
./.venv/bin/python scripts/validate_real.py --protocol block --folds 4 \
    --out artifacts/holdout_real_block.json

# 4. artifact identity audit (never re-upload a repeated prediction array)
./.venv/bin/python scripts/audit_scored_artifacts.py --fetch-scored
./.venv/bin/python scripts/check_submission_uniqueness.py

# 5. build a uniquely-named submission from the validated gate fields
#    (selects the winning arm by the pre-registered rule, averages the four
#     fold fields, emits at the CALIB-calibrated budget, clamps to [0,1])
./.venv/bin/python scripts/build_real_submission.py            # or --arm all
./.venv/bin/python scripts/check_submission_uniqueness.py      # must exit 0
./.venv/bin/python scripts/build_site_payload.py submissions/GEMS_*.tif

# 6. tests
./.venv/bin/python -m pytest tests -q
```

## Limitations in the way (full queue: `research/limitations_and_next.md`)

1. **The scored truth is not observable.** Phase-1 labels are a privately
   withheld "new fault" set (C12); every local number is a proxy computed against
   the public catalogue, and a promotion here is a hypothesis that survived, not
   a leaderboard gain.
2. **The rasters are team-mirrored, not authenticated from the data tab.** Hash
   and grid verification make a substitution implausible (the 60,988-pixel
   catalogue and the exact grid match independent published measurements), but
   the authoritative check is a login-gated download.
3. **No GPU, 3.9 GB RAM, CPU-only.** A U-Net of the reference class is not
   trainable here; the gate uses histogram gradient boosting over engineered
   channels (~35 features). The reference solution is the floor to beat, not the
   ceiling.
4. **The external layers (slip/dilation tendency, heat flow, MT conductance,
   paleo-shorelines, 3DEP/topographic tiles) are still unfetched** — the sandbox
   cannot open gdr.openei.org / sciencebase.gov / prd-tnm.s3.amazonaws.com, and
   the Arena page tools return text, not rasters (FLAG #1). Named free official
   sources are recorded in `research/knowledge_base.md` §3 with check dates.
5. **The `far` protocol is a diagnostic subset, not a leaderboard estimate**;
   `dense` is optimistic and `sparse(20 %)` is the honest analogue of a thin
   new-fault population. Both are reported for every arm.
6. **Upload receipts do not exist in this project.** Score↔file attribution for
   historical submissions rests on group records; the audit says exactly which
   pairings are proven (byte-identity between two repositories) and which are
   inferred.

## Honesty rules (non-negotiable)

* Every external claim carries its URL and check date; anything unverified is
  labelled `TEAM-REPORTED` or `FLAG`, never stated as fact.
* Blank scores stay blank. Disagreements between brief and official sources are
  recorded as irregularities with both values.
* A four-decimal score tie is never evidence of duplicate work; a matching
  prediction-array SHA-256 is.
* Tests reproduce every past failure mode deliberately so it cannot recur.
