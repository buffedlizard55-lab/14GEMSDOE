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
> different way. Submissions must all be unique; never generate the same score
> submissions twice.
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

## How this repo fulfils the prompt

| Prompt requirement | Where it lives | Verified by |
|---|---|---|
| Auditable data table with official links | `docs/data.html`, `research/knowledge_base.md` | every row carries its source URL + check date |
| No hallucinations; verify line by line | `research/knowledge_base.md` (VERIFIED/TEAM-REPORTED/FLAG vocabulary) | irregularities section `research/limitations_and_next.md` §C |
| Why 0.1563; unique submissions | `research/scoring_analysis.md`, `research/results_ledger.md` | identical-artifact autopsy (hash evidence) |
| 3–5 ranked geological hypotheses + layers/signatures/why-missing/differences | `docs/hypotheses.html`, `research/hypotheses.md` | sources verified; ranking decision log |
| Holdout gate before any submission slot | `gems/blocks.py`, `scripts/validate_blocks.py`, slot log on `docs/leaderboard.html` | `tests/test_blocks.py` |
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

## Current verified scoreboard (2026-09-28)

* Leaderboard #1 **DARD 0.3168** (the brief's "0.3049" figure is stale — FLAG #3).
* This group's best public scores: 0.1563 / 0.1461 / 0.1193 — the 0.1563 family
  is one artifact shipped repeatedly (hash-proven; `research/results_ledger.md`).
* Deadline **Dec 3, 2026 23:59 UTC**; 3 submissions/week; one file scored in both
  rounds; Phase 2 ($250k) re-scores against expert-expanded labels.

## Repository map

```
README.md                  ← you are here (standing prompt above)
docs/                      ← GitHub Pages site (executive summary + TIF builder)
gems/                      ← metric, features, hide-and-recover, blocks, raster gate
scripts/                   ← download → prepare → features → train → validate → build
tests/                     ← 51 tests: metric vectors, leak invariant, format gate,
                             JS↔Python GeoTIFF parity, block splits, feed parser
research/                  ← knowledge base, scoring analysis, hypothesis record,
                             results ledger, limitations & next steps
data/raw/                  ← competition data goes here (login required — see below)
data/external/             ← free external layers (scripts/download_external_data.sh)
submissions/               ← built submission files + NOTE + MANIFEST (never re-used)
```

## Quickstart

```bash
# 1. place the competition data (needs a DrivenData login — the data tab is
#    login-gated; verified) then:
bash scripts/download_competition_data.sh
python3 scripts/prepare_data.py

# 2. free external layers (unrestricted machine):
bash scripts/download_external_data.sh

# 3. train through hide-and-recover and score the spatially-blocked holdout:
python3 scripts/train_hide_recover.py
python3 scripts/validate_blocks.py        # ← the only number that may spend a slot

# 4. build + validate a uniquely-named submission:
python3 scripts/build_submission.py artifacts/pred.npy --policy "h1 relay-bridges r1"

# 5. ship it to the site's one-click builder:
python3 scripts/build_site_payload.py submissions/GEMS_*.tif

# tests (51) and the synthetic end-to-end demo:
python3 -m unittest discover -s tests
python3 scripts/make_demo.py
```

## Limitations in the way (full queue: `research/limitations_and_next.md`)

1. **Competition data requires DrivenData login** (verified) — one-time manual
   placement into `data/raw/` unblocks all real numbers.
2. **This sandbox blocks binary downloads** (TLS policy) — external layers and
   DEM tiles are fetched via the provided scripts on an unrestricted machine.
3. **No GPU here** — logistic-baseline protocol work only; U-Net port queued.
4. **19-band order unpublished** — read from the data dictionary on arrival;
   the code refuses to guess.

## Honesty rules (non-negotiable)

* Every external claim carries its URL and check date; anything unverified is
  labelled `TEAM-REPORTED` or `FLAG`, never stated as fact.
* Blank scores stay blank. Disagreements between brief and official sources are
  recorded as irregularities with both values.
* Tests reproduce every past failure mode deliberately so it cannot recur.
