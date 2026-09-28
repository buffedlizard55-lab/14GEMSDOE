# Round-3 geological hypotheses — the completeness angle, continuation
# cones, magnetic fabric, scarplet linkage (session 14GEMSDOE, 2026-09-28)

Answers, line by line, the standing prompt's round-3 directive: **3–5 candidate
hypotheses we have NOT tried**, each naming the specific layer(s), the physical
signature (an edge-detection or curvature transform where applicable), why it
catches a fault **missing from the USGS/INGENIOUS catalogue** rather than one
already in it, how it differs from anything already implemented in this repo,
ranked by expected DTI improvement and implementation cost — with the top
candidates **validated on the spatially-blocked holdout BEFORE any submission
slot is spent**. Candidates needing new external data name the specific free
official source and its verified obtainability.

Companion artefacts: `gems/hypotheses.py` (R3 arms), `scripts/validate_round3.py`
(the gate), `artifacts/holdout_round3.json` (the numbers), `tests/test_hypotheses_round3.py`.

---

## 1. The candidates, ranked a-priori (pre-registered before the gate ran)

Rank = expected combined-DTI gain per unit implementation cost, judged from the
round-2 evidence (knowledge base C21, S1–S15, M4/M5) and the structure of the
metric (`research/scoring_analysis.md`). Nothing here was promoted on judgement
alone — every gated arm below won or died on the blocked holdout.

| rank | id | hypothesis | layer(s) (official stack names, C17) | physical signature / transform | why it catches a MISSING fault | how it differs from everything in this repo | new data needed? |
|---|---|---|---|---|---|---|---|
| 1 | **R3A** | **Tip-continuation cones** — a trace that stops is an unfinished object | catalogue traces only (USGS QFaults + INGENIOUS, C5/C6) | anisotropic distance transform: oriented decaying wedge past each terminal pixel along its local strike (half-angle 25°, reach 20 px = 2 km) | the sponsor ruled "new fault" **includes a continuation past a mapped tip** (forum 11536, C21); terminations/tip-lines host 16.7–22% of Great Basin systems (S1, S9, S10) and Faulds 2026 explicitly says fault tips are "characterized by minor faults with minimal surface ruptures" (S14) — i.e. the mapped tip is often not the real one | `relay_corridors` needs an OVERLAPPING partner pair (a minority of tips); `along_across_strike`/`dist_endpoint` are unsigned scalar distances with no direction; nothing in the repo emits an oriented continuation prior | none |
| 2 | **R3B** | **Completeness-angle residual** — where strain + relief say "fault here" but the catalogue is empty, the catalogue is wrong | detrended elevation + slope; dilatation/shear strain rate + 2nd invariant; catalogue (context only) | coarse-cell ridge OLS of log catalogue density on relief, strain and range-front proximity; the signed residual raster (z-scored), smoothed, is the feature | this is the literal "completeness angle": Hermant et al. 2025 show Qfault density is partly a map of who mapped what (M5) and ~39% of GB systems are blind (S3) — a strongly negative residual localises the under-mapped corridors the sponsor's experts added labels in | the repo has single-field transforms (N1–N5, R3C/R3D) and pure catalogue geometry (H1, R3A); **no existing feature compares observed catalogue density against a prediction from independent layers** | none |
| 3 | **R3C** | **Magnetic-basement lineaments** — fabric the surface cannot show | RTP magnetic anomaly; TMI + its vertical/horizontal slopes; top-of-crustal magnetic source depth (all C17) | structure-tensor orientation + coherence of the magnetic field; hysteresis ridge skeleton (gradient → NMS → skeleton); strike-AGREEMENT feature vs the nearest catalogue strike | a basement-rooted fault with no scarp and no seismicity still offsets magnetised basement; GeoDAWN magnetics exist precisely to see through basin fill (C19); Faulds 2026: basin-fill sediments "obscure the subsurface architecture" (S11) | N1 used the **gravity** horizontal-gradient and was killed by the gate as a feature; R3C reads the **magnetic** field and, crucially, does NOT feed raw edge terminations to the classifier — its new information is the orientation-coherence ridge and the parallel-agreement with visible catalogue strikes (the step-over/intersection geometry of S8–S10) | none (synthetic f_mag today; real bands on arrival) |
| 4 | **R3D** | **Scarplet curvature-linkage** — the briding matters, not the scarp | detrended elevation + slope (C17); 1-m DEM tiles when landed (`1m_DEM_links.csv`) | Laplacian negative-curvature threshold (curvature transform) → speckle removal → morphological closing along trend → the LINK pixels between scarplets are the feature | the latest intra-basin slips leave decimetre scarplets below catalogue amplitude; Hermant's CNN confirmed experts find real faults on lidar that Qfault lacks (M4); lakebed sediments hide pre-Holocene ruptures (S14) — linked low-amplitude scarplets are candidate catalogue gaps | N5 is a slope-magnitude threshold at range fronts (no curvature, no linkage); the team's out-of-repo "dem-scarp" probes (h20/h28) were single uploads with no offline gate — R3D scores the CONNECTIVITY transform, and is gated before any slot | none (lidar tiles improve it later) |
| 5 | **R3E** | **Dilation-tendency-weighted corridors** — weight every bridge by how open it should be | slip & dilation tendency (external, DOI [10.5066/P9YL58W6](https://doi.org/10.5066/P9YL58W6)) + catalogue geometry | multiply R3A/R3A-like corridor scores by the tendency raster before emission | step-overs and terminations are the highest-dilation settings (S4, S5); a tendency-weighted prior spends probability mass where opening-mode failure is actually admissible | the repo LOADS external rasters (`load_external_raster`) but nothing uses tendency to weight corridors; this is a re-weighting of the round-3/round-1 geometry, not a new edge detector | **YES — external raster; source named, obtainability verified** (GDR 1391 release, CC BY 4.0; `scripts/download_external_data.sh` row exists; sandbox-blocked, fetches on any unrestricted machine — T8). **Not gated this session for exactly this reason; gate on arrival** |

Sequencing note (pre-registered): arms R3A–R3D run in the gate today because
they need nothing new; R3E is deliberately NOT slotted or emitted until its
raster exists and an enrichment statistic on hidden traces has been computed.

## 2. The gate (pre-registered, unchanged round-2 protocol)

`scripts/validate_round3.py`, identical to round 2 so numbers are comparable
with `artifacts/holdout_round2.json`: synthetic GeoDAWN-like regions, 176 px,
seeds 11/12/13, 4 spatial folds of 48 px blocks with 3 px purge buffer, 5
hide-and-recover epochs, hide fraction 0.35, discovery radius 3 px, logistic
classifier, geophysical prior w = 0.5.

Pre-registered arms (all run regardless of outcome):

```
baseline    round-2 baseline                      (reference)
BMUL        round-2 PROMOTED emission:            (incumbent to beat)
            classifier(ALL) × (1 + 0.5·prior)
R3A, R3B, R3C, R3D, R3AC                 (classifier over baseline + R3 block)
BMUL-R3A    classifier(ALL + R3A)  × (1+0.5·prior)
BMUL-R3AC   classifier(ALL + R3A + R3C) × (1+0.5·prior)
```

Gate metric: combined DTI on the fold's off-context population (held-out
catalogue traces + blind traces). A candidate is **slot-eligible only if it
beats BMUL**.

### Audit trail of the gate runs (honesty record)

1. Run 1 (09:26Z) executed with a real bug: `_outward_direction` returned the
   outward vector in the wrong coordinate frame, so R3A cones were empty on
   axis-aligned traces (the unit test caught it after the run started). Run 1
   is VOID; its only surviving information was that R3D (bug-independent)
   looked promising.
2. Re-run preparation exposed a second, more serious issue: the round-2
   "BLEND-MUL" arm trained its classifier on the ALL feature block
   (`DERIVED_ARMS` mapping in `validate_round2.py`), not on baseline. The
   first re-run had therefore compared candidates against a WEAKER incumbent
   (BMUL 0.3212 instead of the true 0.3842). `validate_round3.py` was fixed so
   BMUL reproduces the exact round-2 emission (feature arm ALL), and composite
   arms `ALLR3A`/`ALLR3AC` were added so boosted candidates keep the ALL block.
3. Run 2 (final, with both fixes) is the recorded result below. Baseline
   reproduces round-2's 0.3073 recovery to 4 decimals, which pins protocol
   equivalence.

## 3. Results (run 2 + follow-up)

Run 2 (`artifacts/holdout_round3.json`, generated 2026-09-28T09:34Z):

| arm | n_feat | recovery | discovery | combined | Δ vs incumbent | decision |
|---|---|---|---|---|---|---|
| baseline | 13 | 0.3073 | 0.0081 | 0.2863 | −0.0979 | reference (reproduces round 2 exactly) |
| **BMUL (incumbent)** | 28 | **0.3673** | **0.0612** | **0.3842** | — | **stands** |
| R3A tip-continuation cones | 15 | 0.2977 | 0.0080 | 0.2772 | −0.1071 | **killed** |
| R3B completeness residual | 15 | 0.3003 | 0.0078 | 0.2796 | −0.1047 | **killed** |
| R3C magnetic lineaments | 18 | 0.3023 | 0.0079 | 0.2815 | −0.1028 | **killed** |
| R3D scarplet linkage | 17 | 0.3322 | 0.0056 | 0.3056 | −0.0787 | **killed** (best non-blend gain vs baseline, +0.019, still far below incumbent) |
| R3AC cones + magnetics | 20 | 0.2930 | 0.0078 | 0.2726 | −0.1116 | **killed** |
| BMUL-R3A | 30 | 0.3624 | 0.0607 | 0.3790 | −0.0052 | **killed** (dilutes the incumbent) |
| BMUL-R3AC | 35 | 0.3599 | 0.0598 | 0.3758 | −0.0084 | **killed** (dilutes the incumbent) |

Follow-up run (`artifacts/holdout_round3_followup.json`, arm pre-registered
after run 2 on mechanism grounds, before being scored):

| arm | recovery | discovery | combined | Δ vs incumbent | decision |
|---|---|---|---|---|---|
| BMUL (incumbent) | 0.3673 | 0.0612 | 0.3842 | — | stands |
| BMUL-R3Dp (scarplet-bridge field max-joined into the prior) | 0.3673 | 0.0612 | 0.3842 | **+0.0000** | **null** |

## 4. Decisions and what they mean

1. **The incumbent stands. No round-3 candidate is slot-eligible, and no
   submission slot was spent.** This is the second consecutive gate in which
   plausible, source-backed geological ideas failed to beat a multiplicative
   blend of catalogue-geometry classifier and geophysical prior — round 2
   killed N1 despite verbatim INGENIOUS-author support, and round 3 killed all
   five new candidates plus two incumbent-stack variants.
2. **Why the classifier arms fail (mechanism, consistent with round 2):** a
   logistic model trained on hide-and-recover catalogue labels treats an extra
   field as one more noisy column; the fields carry real signal (R3D lifts the
   pure-classifier family +0.019 over baseline) but not enough to pay the
   dilution cost against a 28-feature stack whose best signal (relay corridors,
   junction density) already spans the same structures in this synthetic model.
3. **Why the follow-up is null (mechanism):** the multiplicative blend scales
   the classifier's own probability. A bridge pixel where the classifier
   predicts ~0 stays ~0 however large the prior is there, and where the
   classifier predicts ~1 the term saturates the clip at 1.0 regardless. **The
   prior can only re-weight the classifier's support, never extend it.** Any
   future "field X through the prior" proposal must first show pixel-level
   overlap with the classifier's confident support, or it is dead on arrival —
   this measurement settles the question for the whole prior family.
4. **Where the remaining leverage actually is** (pre-registered for the next
   session, in order): (a) the real rasters (B1) — every synthetic verdict
   must be re-measured on the 19-band stack; (b) N2 (seismicity/strain
   lineaments) and N5 re-run on real data — they were the two promoted
   classifier features in round 2 and are NOT re-tested here (they are part of
   the incumbent's prior); (c) U-Net capacity (B3) — a logistic model's support
   is the binding constraint the mechanism finding above exposes; (d) R3E
   tendency-weighting once the INGENIOUS raster lands — with the same
   prior-overlap test applied FIRST, before any gate run.
5. **The completeness angle remains open, not dead.** R3B was killed as a
   logistic *feature* under this protocol; the residual field itself is exactly
   the deliverable the brief describes for human/analyst use (a ranked map of
   under-mapped corridors), and its value can only be judged on real data where
   catalogue density varies for mapping-effort reasons (M5). It stays in the
   toolkit, with its gate result attached.

## 5. Honesty statement

These numbers come from the **synthetic forward model**, not the competition
rasters (login-gated, C18; mirrors TLS-blocked in-sandbox, T8/FLAG #1). They
validate the machinery, the sign and rough magnitude of each arm's effect, and
that the gate refuses ideas — they do NOT predict a leaderboard score. The
round-2 experience (N1: strongest literature support of any arm, killed by the
gate anyway) is the standing warning against reading publication support as
DTI. `scripts/validate_round3.py` runs unchanged on `data/processed/` once the
real rasters are placed; the incumbent to beat is then re-measured on real data
before any slot is spent.

## 6. Sources used above (all VERIFIED unless marked)

* C21 "newly mapped geometry / continuation past a mapped tip" —
  [forum 11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536)
* C17 official layer list — [provided features](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#provided-features)
* C19 GeoDAWN provenance — DOI 10.5066/P93LGLVQ
* S1/S9/S10 Faulds setting shares (2012 + 2026 vintages) —
  [Faulds et al. SGW 2026](https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2026/Faulds.pdf),
  [Faulds et al. 2012](https://gdr.openei.org/files/383/Faulds%20et%20al%202012%20GeoNZ%20Paper.pdf)
* S3 blind-system share — [GBCGE](https://gbcge.org/recent-projects/characterizing-structural-controls/)
* S4/S5 step-over dilatation & geometry —
  [Geoenergy 2023](https://www.lyellcollection.org/doi/full/10.1144/geoenergy2023-009),
  [Giddens & Faulds SGW 2025](https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf)
* S14 lake-obscured faults & tip minor-faults — Faulds et al. SGW 2026 (above)
* M4/M5 Hermant et al. SGW 2025 (lidar mapping, catalogue-density caveat) —
  [PDF](https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Hermant.pdf)
* R3E tendency raster — DOI 10.5066/P9YL58W6 (in GDR 1391, CC BY 4.0)
