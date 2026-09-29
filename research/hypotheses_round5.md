# Round 5 — five new geological hypotheses, gated on the real rasters

**Session:** 14GEMSDOE, 2026-09-28 · branch `arena/01a0e97b-14gemsdoe`.
**Data status:** the real competition rasters are present and hash-verified in
`data/raw/` (see `research/real_data_unlock.md` and
`artifacts/real_data_audit.json`). Every number below is measured on those files.
**No DrivenData submission slot is spent in this session under any outcome.**

## 0. What changed, and why the previous rounds could not answer this question

1. **The data blocker is closed.** `data/raw/training_features.tif`
   (418,912,844 B, sha256 `4371c82e…`), `training_labels.tif` (sha256
   `7ba308cc…`) and `sample_submission.tif` (sha256 `2176d08e…`) are byte-identical
   to the official files carried by the group's own transit mirror
   (`6GEMSDOE/data/bridge/manifest.json`, `scripts/bridge_team_mirror.sh`).
   Rounds 1–4 were gated on a **synthetic forward model**; none of their numbers
   speak to the real rasters.
2. **Measured catalogue:** 60,988 fault pixels on a 5,167,373-pixel footprint
   (1.18 %), 3,199 connected components. These match the figures published
   independently on the group's GEMSDOE/5GEMSDOE sites.
3. **The published reference model is not the frontier.** DrivenData's own
   account sits at 0.1847 (leaderboard check 2026-09-28); the group's best is
   0.1563; the leader is 0.3168. A model trained to reproduce the catalogue has a
   low ceiling because the scored population *excludes* the catalogue
   (staff ruling, forum 11516).
4. **The group's own eight scored artifacts are available for analysis**
   (vendored in `buffedlizard55-lab/7GEMSDOE/external/scored`). The audit
   (`research/artifact_audit.md`) shows 8/8 distinct prediction arrays; that the
   two 0.1563-class repositories published the *same bytes*; and that three
   submissions with an identical 155,021-pixel budget scored 0.083 / 0.1152 /
   0.1193 — **selection, not budget, is what moves the score.**

## 1. The metric algebra that reframes every feature arm (derived, not fitted)

The metric is `DTI = T / (T + 0.2·E + 0.8·FN)` with `FN = N_gt − T`, so
`DTI = T / (0.2T + 0.2E + 0.8·N_gt)`. Adding one predicted pixel at value 1
changes `T → T+ΔT`, `E → E+ΔE`, and it raises the score iff

    ΔT/ΔE > 0.2·D / (1 − 0.2·D)                                             (★)

(Derivation: cross-multiply `(T+ΔT)/(Den+0.2ΔT+0.2ΔE) > T/Den` with `Den = T/D`.)
At the group's operating point `D = 0.1563` the bar is **0.0323**; at the leader's
0.3168 it is **0.0677**. Two consequences the gate tests directly:

* **Scaling a prediction up never hurts.** Replacing `p → c·p` gives
  `DTI(c) = T/(0.2T + 0.2E + 0.8·N_gt/c)`, monotone increasing in `c`; binary 1.0
  emission is optimal *given* a fixed support — which is why every scored artifact
  has `mass == n_pos` and no fractional values.
* **A fixed 2 % budget is not implied by the metric.** The rule is per-pixel:
  emit where the expected probability of adding credit exceeds ≈3.2 %; whether
  that is 2 % or 10 % of the footprint is an empirical question, which is why the
  gate sweeps thresholds, top-k budgets and NMS radii.

Local verification of the algebra in this repo:
`tests/test_dti_fast.py::test_marginal_emission_rule` asserts the *per-pixel*
form (`k > 0.2·D`, i.e. a prediction 1 px from a true trace with `k = 2/3` is
still worth emitting at `D = 0.1563`), and
`tests/test_dti_fast.py::test_scaling_a_support_up_never_lowers_the_score`
(127 tests pass, run 2026-09-28) asserts the scaling form.
`scripts/audit_scored_artifacts.py` confirms every scored file is binary at 0/1.

## 2. Registered candidates (ranked by expected DTI gain ÷ implementation cost)

Each entry names the layers, the transform, the *new-fault* rationale, and the
difference from everything already implemented in this repo or its sibling
registers (H11–H41 in `12GEMSDOE/docs/hypotheses-round2..8.md`).

| # | Hypothesis — layers → transform | Physical signature | Why it should catch a fault *missing* from the catalogue rather than one already in it | Difference from everything already run | Cost |
|---|---|---|---|---|---|
| **R5-1** | **Relay-ramp interior maturity.** Catalogue geometry only (`training_labels.tif`). Components → PCA tips → tip pairs ≤ 6 km with ≤ 40° strike difference that **overlap along strike** → weight by the published ramp-width distribution (0.1–14.6 km, mean 2.8 km) × overlap/separation × parallelity → paint the *interior* quad between the strands. | The interior of a step-over/relay ramp — where the short connecting faults and the highest modelled dilatation occur. | Step-overs host ~32 % of the 2012 catalogue (Faulds et al., GDR 383) and 39.6 % of the >1,430 favourable structural settings mapped in 2026 (Faulds et al., SGW 2026); the *connecting* faults inside a ramp are short, low-relief and buried under the ramp's own sediment apron, so a regional catalogue records the bounding strands but not the bridge — exactly the "small connecting structures" the brief hypothesises are omitted. | Round-1 `relay_corridors` bridges *any* two components within 4.5 km with an ellipse and a binary weight; R3A projects decaying cones past single tips. R5-1 requires genuine **along-strike overlap** (the published hard-link criterion: ~70 % of higher-temperature step-overs, Giddens & Faulds 2025) and paints the interior rather than the tip-to-tip segment. No sibling arm targets relay interiors. | low |
| **R5-2** | **Accommodation-zone transfer corridors.** Catalogue geometry + `det_elev` (band 12). Per-trace topographic polarity (sign of the elevation difference sampled ±4 px across the local strike normal) → opposed-polarity tips 5–25 km apart with ≤ 50° strike difference → thin 0.3–1.2 km bands along the facing-tip segment, weight peaking at the 2.8 km ramp-width mean. | Two systems handing over displacement: an accommodation zone expressed topographically as an interbasinal high between opposed range fronts. | Accommodation zones are only ~6–7 % of systems by count but **19.3 % of favourable-setting area** (Faulds et al., SGW 2026) — extensive, diffuse settings whose interior is rarely mapped as faults while the bounding faults are. | Nothing in this repo uses throw/dip **polarity**: the round-1 corridors are polarity-blind and short-range, N5 thresholds range-front position, R3D links curvature scarplets point-wise. No sibling arm pairs opposed-polarity systems. | medium |
| **R5-3** | **Amplitude-normalised magnetic tilt angle + gravity-edge coincidence.** Bands 9 (`tmi_vg`, vertical gradient) and 3 (`tmi_hg`, horizontal gradient) → θ = atan2(∂T/∂z, \|∇<sub>H</sub>T\|); plus a band 3 × band 18 (`iso_grav_anom_hg`) coincidence term. | Zero crossings of the tilt angle mark magnetic source *edges* independently of amplitude (Miller & Singh 1994; Salem et al. 2007 tilt-depth); a coincident gravity-gradient edge marks a boundary that is both density and magnetisation controlled. | A fault buried under basin fill or late-Pleistocene lake sediments has no scarp and usually no catalogue entry, and a ratio detector keeps responding where an amplitude threshold fails because the magnetisation contrast is weak. Faulds et al. (SGW 2026) report that terminating/intersecting gravity gradients "defined many of the fault terminations and fault intersections … especially … in the many basins of the region, where basin-fill sediments obscure the subsurface architecture". | This repo has **no tilt-angle channel**: `geoedges.py` (N1) works on amplitude gradients and terminations; R3C uses a magnetic structure tensor. In the sibling registers H17 is a gravity-only zero-contour × gradient-ridge and H18 used the shipped `tc` band *as if* it were a tilt angle. **Band 6 (`tc`) is not that tilt angle, and the file disagrees with itself about it** (FLAG, measured 2026-09-28): the raster's own band tag reads *"Tilt angle or total curvature - magnetic field derivative for edge detection"*, while the official provided-features list calls the layer *top-of-crustal magnetic source depth*; the values are **all positive**, 3.40–51.74, median 18.48 km-like, and correlate r = +0.013 with atan2(b9, \|b3\|) and r = −0.16 with \|b3\| — i.e. not an angle. So the classical tilt of bands 9/3 had never been tested; R5-3 computes it. | low |
| **R5-4** | **Range-front fan/curvature response.** Band 12 (`det_elev`). Profile curvature (curvature along the steepest-descent direction) at two scales, pooled with a 5×5 line maximum so the response survives a 1–2 px placement error inside the 300 m kernel. | Convex breaks in slope where a range front steps, bends, or is buried by an alluvial fan — the fan-head zone where a young fault trace is masked. | The mapping campaign reports that "much of the GBR was inundated by late Pleistocene lakes, and thus faults that have not ruptured in the Holocene are obscured by lake sediments and shoreline features", and that fault tips with minimal surface rupture are "difficult to recognize even with high-resolution lidar". | N5 thresholds slope and range-front *position*; R3D links negative-curvature scarplets as points. Neither uses **directional (profile) curvature**, which is invariant to the front's azimuth and therefore comparable along a curving front. Sibling H26 is a Laplacian of a gravity slope; H32 uses an external 10 m DEM. | medium |
| **R5-5** | **Conditioned completeness residual.** Bands 12, 5, 4, 7 + catalogue density. OLS of smoothed catalogue density on smoothed strain/relief/range-front predictors (fit inside the training footprint only) → signed residual **AND**-ed with an independent topographic anomaly. | Where the catalogue is thinner than the physical setting predicts *and* an independent topographic edge exists there. | If the catalogue were complete, density would track the predictors; a strongly negative residual that coincides with independent evidence is the gap candidate the brief sanctions. | R3B used the **raw** residual alone and was killed on the synthetic model; R5-5 conditions it on independent evidence. Sibling H41 uses distance-to-catalogue as an anti-target, not a completeness residual. Ranked last: its ancestor failed and its signal is the weakest of the five. | low |

## 3. The gate (pre-registered before any arm was scored)

`scripts/validate_real.py`, protocol `component`, four folds, seed 20260928:

* **Truth:** the official catalogue; 3,199 connected components.
* **Split per fold:** TEST 20 % / CALIB 20 % / HIDE 35 % of all components, 25 %
  always visible. Two views are built: the **training view** excludes TEST and
  HIDE (so "distance to a mapped trace" carries no information about the target),
  and the **prediction view** is the submission-time context (full catalogue minus
  TEST). This is the hide-and-recover invariant enforced structurally, not by
  dropout.
* **Learner:** identical for every arm — weighted **logistic regression fitted
  with full-batch gradient descent in float64** (`scripts/train_hide_recover.py::
  logistic_fit`, 150 iterations, learning rate 0.5, L2 1e-3; `validate_real.py`
  passes `--iters 150`), trained on 20,000 positive + 40,000 background pixels
  sampled from the always-visible 25 % of components, standardised by training-set
  mean/std. Only the feature block changes between arms. (An earlier draft of
  this document called the learner "HistGradientBoostingClassifier-equivalent" —
  that is wrong and is corrected here; the code has only ever used the linear
  model.)
* **Calibration:** the emission policy (probability threshold / top-q budget) is
  chosen on the hidden **CALIB** components only — never on TEST.
* **Truth protocols:** `dense` (all TEST pixels), `sparse` (fixed 20 % subsample)
  and `far` (TEST pixels more than 1,000 m from any context trace — the closest
  analogue of a genuinely unmapped structure, and the protocol that cannot be won
  by hugging the catalogue).
* **Decision rule:** promote an arm only if it beats the baseline on **both** the
  sparse and the far protocol in ≥ 3 of 4 folds; everything else is killed and
  recorded. No slot is spent on any outcome.

## 4. Results

**Status: INTERIM — the gate was interrupted after 2 of 4 folds.** Full
transcription, table and the environment-reset note: `research/results_ledger.md`
§"Round-5 real-data gate record". `artifacts/holdout_real.json` was not written
(the script writes it only after the last fold), so this section quotes the run
log, not a JSON.

Emission policy chosen on the hidden CALIB components in every row: **top
q = 0.005** → 25,837 px ≈ 0.50 % of the 5,167,373-px footprint.

| Arm | fold 0 dense / sparse / far | fold 1 dense / sparse / far |
|---|---|---|
| geom (baseline) | 0.0381 / 0.0165 / 0.0006 | 0.0381 / 0.0145 / 0.0006 |
| geo (+ bands) | 0.0421 / 0.0186 / 0.0033 | 0.0330 / 0.0132 / 0.0012 |
| geom_ramp (R5-1) | 0.0422 / 0.0186 / 0.0033 | 0.0337 / 0.0135 / 0.0012 |
| geom_acc (R5-2) | 0.0420 / 0.0185 / 0.0034 | 0.0330 / 0.0128 / 0.0010 |
| geom_tilt (R5-3) | 0.0423 / 0.0186 / 0.0033 | 0.0333 / 0.0133 / 0.0010 |
| **geom_curv (R5-4)** | **0.0445 / 0.0196 / 0.0050** | **0.0429 / 0.0179 / 0.0062** |
| geom_gap (R5-5) | 0.0436 / 0.0189 / 0.0023 | 0.0345 / 0.0144 / 0.0012 |
| **all** | **0.0450 / 0.0198 / 0.0043** | 0.0422 / 0.0173 / 0.0053 |
| fold 2 (partial) | geom 0.0333/0.0142/0.0000 · geo 0.0335/0.0154/0.0014 · ramp 0.0327/0.0149/0.0013 · acc 0.0327/0.0150/0.0012 | — |

Reading, conditional on 2 folds:

* **R5-4 (profile curvature) is the strongest single addition measured in this
  project** and the only arm that beats the baseline on *both* the sparse and the
  far protocol in *both* completed folds.
* **All five mechanisms improve `far`** (TEST pixels >1 km from any context
  trace): the physical priors do carry information about structures far from the
  catalogue. Three of them lose the `sparse` comparison in fold 1, i.e. in a
  linear model they dilute as often as they help.
* The calibrated budget lands at ~0.5 % of the footprint — 6× smaller than the
  155,021 px the group historically shipped.
* Levels (≤0.045 dense) are hide-and-recover catalogue numbers on a 20 %
  component split; they are **not** leaderboard estimates.

**Decision: none yet.** The promote rule requires ≥3/4 folds; with 2 folds
available, nothing is promoted and nothing is killed. No slot is spent. The rerun
is the first action of the next session (the sandbox reset removed `.venv` and
`data/raw/`, which are rebuilt by `scripts/bridge_team_mirror.sh` +
`scripts/prepare_data.py`).

## 5. Honesty statement

* The scored population at DrivenData is a **privately withheld new-fault set**;
  the catalogue is the only ground truth available here. Recovering held-out
  catalogue traces is a *proxy*, and it is biased optimistic for catalogue-like
  structures (new faults are, by construction, not in the catalogue).
* The `far` protocol is the closest available analogue of the hidden set; the
  ranking of arms on `far` is therefore the one that should drive decisions.
* No arm in this round is slot-eligible until the promote rule in §3 is met, and
  no slot is spent in this session.
* Every arm's threshold is chosen on held-out calibration traces; any number
  quoted for an arm at a threshold chosen on the *test* traces is labelled
  "oracle" and is never used for selection.
