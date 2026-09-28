# Round-2 hypotheses — five geological ideas we have **not** tried before

Date: 2026-09-28. Ranking by expected DTI gain × implementation cost, then
**validated on the spatially-blocked holdout** before any submission slot was
touched (`scripts/validate_round2.py`, artifact `artifacts/holdout_round2.json`).

Every geological claim below is quoted or paraphrased from a source that was
opened and read on 2026-09-28; the URL is given inline. Claims that could not be
checked are labelled `TEAM-REPORTED` or `FLAG` — never stated as fact.

---

## Why these five, and not another variant of H1–H5

The round-1 set (H1 structural completion, H2 magnetic lineaments, H3
hydrothermal expression, H4 slip/dilation tendency, H5 completeness residuals)
is all built on **catalogue geometry + surface expression**. Every one of them
asks "where does the catalogue imply a fault should be?" The round-2 set asks a
different question: **"where does the physics say a fault must be, in a place the
catalogue never looked?"** That is the population the prize actually scores:
staff confirmed the test set is *"any fault pixel not already captured by
USGS/INGENIOUS"*, and that known-fault pixels are masked out of evaluation
(forum 11516, forum 11536 — both VERIFIED 2026-09-28).

The five ideas below are also deliberately drawn from **layers the competition
already ships** (so three of them need no new data at all), plus one that needs
the free 1 m lidar DEM the sponsor itself points at.

---

## The ranking (before validation)

| Rank | ID | Hypothesis | Signature transform | Layers | Expected DTI gain | Cost | New external data? |
|---|---|---|---|---|---|---|---|
| 1 | **N1** | Gravity-gradient edge **terminations and intersections** = the fault tips and crossings the catalogue omits | horizontal-gradient magnitude → NMS across the ridge → hysteresis → 1-px skeleton → **endpoint & branch-point extraction** | isostatic gravity anomaly + its slope (in-stack) | high | low | **no** |
| 2 | **N2** | **Seismicity-density / strain-invariant lineaments** = buried faults under basin fill | structure-tensor orientation + coherence on the earthquake-density and strain-invariant fields | earthquake density, dilatation/shear strain rate, 2nd strain invariant (in-stack) | high | low-medium | **no** |
| 3 | **N3** | **Hydrothermal alteration-cap margin**: high conductance **AND** magnetic low, fault placed at the cap boundary | boolean conjunction of anomaly masks → level-set boundary (`cap_margin`) | surface conductivity, depth to conductive base, RTP magnetics (in-stack) | medium-high | medium | **no** |
| 4 | **N4** | **1 m lidar scarp / profile-curvature lineaments** with a **paleo-shoreline negative mask** | multi-azimuth hillshade + local relief model → second-derivative (profile-curvature) ridge; shoreline mask suppresses the dominant FP class | 1 m 3DEP lidar DEM (external, free) | high | **high** | **yes** |
| 5 | **N5** | **Range-front topographic step / interbasinal high** = step-over and accommodation-zone proxies | slope + structure-tensor coherence of detrended elevation; step-distance transform | detrended elevation + its slope (in-stack) | medium | low | **no** |

---

## N1 · Gravity-gradient edge terminations and intersections

**Layers.** `training_features.tif` bands: isostatic gravity anomaly and the
slope of the isostatic gravity anomaly (both enumerated in the official
[provided-features list](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#provided-features)).
Optional upgrade: the INGENIOUS regional gravity/magnetics release
([DOI 10.5066/P9Z6SA1Z](https://doi.org/10.5066/P9Z6SA1Z)) for the
higher-quality isostatic-residual product.

**Physical signature.** The first horizontal derivative (gradient magnitude) of
the gravity field. A near-vertical density contrast across a fault produces a
step in the potential field, so |∇g| is a ridge running *along* the fault; the
ridge **vanishes where the contrast dies**, i.e. at the fault tip. Two ridges
that stop against each other mark an intersection. Implemented in
`gems/geoedges.py::ridge_skeleton` / `edge_terminations` / `edge_junctions` /
`edge_termination_field`.

**Why it catches a fault *missing* from the catalogue rather than one already in
it.** Verbatim from the INGENIOUS structural-settings paper
([Faulds et al., SGW 2026](https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2026/Faulds.pdf)):

> "Isostatic residual and horizontal gradient gravity data were the most useful.
> For example, terminating and intersecting gravity gradients respectively
> defined many of the fault terminations and fault intersections. This was
> especially important in defining FSS in the many basins of the region, where
> basin-fill sediments obscure the subsurface architecture and primary
> basin-bounding and/or intrabasinal faults."

So the expert-compiled inventory itself located fault tips and intersections
*from gravity gradients*, specifically in basins where nothing shows at the
surface. A basin floor covered by late-Pleistocene lake sediments has no scarp
and no lineament — which is exactly why such a fault is absent from a
scarp-compiled catalogue — but its density contrast still bends the gravity
field. The signal is therefore *orthogonal* to the catalogue's information
source by construction.

**How it differs from everything already in this repo.** H1 computes relay
corridors *between catalogue tips* (it needs the catalogue). H2 runs a generic
structure tensor on "detrended elevation / magnetics / gravity" but never
extracts gradient ridges, never isolates **edge terminations**, and never uses
the *termination* as the target. H5 uses relief only as a density predictor.
Nothing in the repo computes a gravity-gradient ridge, its skeleton, or its
endpoints. The distinguishing move is that **the target is the end of an edge,
not the edge**.

**Obtainability of new data.** None required — the bands are already in the
competition stack. (The optional INGENIOUS gravity product is free, CC BY 4.0,
and listed with a direct download link in `research/knowledge_base.md` §3.)

---

## N2 · Seismicity-density and strain-invariant lineaments (buried faults)

**Layers.** `training_features.tif` bands: density of earthquakes; dilatation
rate; shear strain rate; second invariant of the strain rate tensor (all
enumerated in the official provided-features list).

**Physical signature.** Structure-tensor orientation + coherence
(`gems/features.py::structure_tensor_orientation`) applied to the
earthquake-density field and to the strain-rate invariant, plus a
maximum-filter ridge of the density itself. A buried fault under basin fill
still accumulates microseismicity on its plane; the epicentre cloud therefore
delineates a lineament that has no surface expression.

**Why it catches a missing fault.** Same Faulds et al. 2026 passage: basin-fill
sediments obscure the subsurface architecture. A fault that has not ruptured in
the Holocene and is buried under Lake Lahontan/Bonneville sediments will never
be picked from imagery or lidar — so it is not in the catalogue — but it is
still slipping and still producing earthquakes. The competition ships the
earthquake-density band precisely because INGENIOUS considers it diagnostic.

**How it differs.** No hypothesis or feature in this repo uses seismicity or
kinematics at all. H1–H5 are entirely static-structure. This is the only arm
whose information source is *present-day motion*.

**New external data.** None required. (The INGENIOUS seismicity GeoTIFFs are
free at
[gdr.openei.org/files/1391/seismicity_INGENIOUS_regional_data.zip](https://gdr.openei.org/files/1391/seismicity_INGENIOUS_regional_data.zip)
if a higher-resolution product is wanted later.)

---

## N3 · Hydrothermal alteration-cap margin

**Layers.** `training_features.tif` bands: surface conductivity, depth to
conductive base surface, reduced-to-pole magnetic anomaly / total magnetic
intensity. Optional upgrade: INGENIOUS Electrical Conductance Maps
([DOI 10.5066/P9TWT2LU](https://doi.org/10.5066/P9TWT2LU)) and heat-flow maps
([DOI 10.5066/P9BZPVUC](https://doi.org/10.5066/P9BZPVUC)).

**Physical signature.** Boolean conjunction `cap = (conductance high OR
conductive base shallow) AND (magnetic low)`, then the **level-set boundary** of
that mask (`gems/geoedges.py::cap_margin` / `cap_mask_from_anomalies`), decaying
both inward and outward. The fault that feeds a clay cap lies at the cap's
margin.

**Why it catches a missing fault.** Verbatim, Faulds et al. 2026:

> "Magnetic and MT data were also useful in some areas in defining subsurface
> fault geometries and FSS … magnetic lows and low resistivity anomalies may
> respectively indicate altered rocks and clay caps at depth induced by
> geothermal activity."

A hydrothermal clay cap is produced by fluid upflow *along a fault*. The fault
must exist at or beside the cap. Alteration is invisible to scarp-based catalogue
compilation, so this is a target class the catalogue cannot produce by
construction. This is the most **contrarian** of the five: it targets the
*geothermal* signal (alteration) rather than the *structural* signal, and then
converts it into fault pixels at the cap margin.

**How it differs.** H3 uses **point** features (springs, sinter/tufa, vents)
from the INGENIOUS release — a surface-expression approach needing new external
data. N3 is a **2-D mask-margin transform on bands already in the stack**, and
its physical target (clay cap) is a different object from a spring.

**New external data.** None required.

---

## N4 · 1 m lidar scarp and profile-curvature lineaments, with a paleo-shoreline negative mask

**Layers.** 1 m lidar DEM from the USGS 3D Elevation Program (3DEP), fetched via
the `1m_DEM_links.csv` the sponsor ships on the data tab, or directly from 3DEP.
Fallback if lidar is unavailable: the in-stack detrended elevation and its slope
at 100 m.

**Physical signature.** Multi-azimuth hillshade + sky-view-factor / local relief
model, then a **profile-curvature** (second derivative along the slope-normal)
ridge detector — the transform that isolates a scarp's break of slope from a
general slope. Plus a **negative mask**: long, quasi-straight, low-curvature
benches that follow ancient lake shorelines are removed.

**Why it catches a missing fault.** Two independent VERIFIED statements:

1. The sponsor's own
   [About page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/)
   records that airborne lidar was collected through 3DEP "over a similar extent
   spanned by the geophysical surveys". At 1 m, scarps that are invisible at the
   100 m competition resolution become detectable.
2. [Hermant et al., SGW 2025](https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Hermant.pdf)
   (cited by the sponsor) documents, for the same region: USGS Qfault positions
   differing from lidar-derived ground truth by **up to 400 m**; **new faults
   detected by their CNN and subsequently confirmed by experts on lidar**; and —
   critically for us — that both of their models **also detect paleo-shorelines
   as false positives**.

The 400 m figure matters directly: the competition's kernel radius is 300 m, and
the problem description itself says *"portions of the existing fault data may be
misaligned from the true location of the surface fault, which is the prediction
target"*. Lidar lets us put the prediction on the *true* trace rather than on the
catalogue's displaced one.

**Why the shoreline mask is the key idea.** Faulds et al. 2026: *"much of the GBR
was inundated by late Pleistocene lakes, and thus faults that have not ruptured
in the Holocene are obscured by lake sediments and shoreline features."* Lake
shorelines are long, straight, and scarp-like — the single largest false-positive
class for any topographic lineament detector in this region. Removing them
raises DTI from the FP side while the true scarps raise it from the TP side.

**How it differs.** No DEM-based scarp or curvature feature exists anywhere in
this repo. H5 uses relief only as a *density predictor* (a completeness
residual), never as a detector, and there is **no negative-evidence /
FP-suppression mask of any kind** in the repo.

**New external data — named, free, official, and obtainability checked.**

| Need | Source | Status |
|---|---|---|
| 1 m lidar DEM over the GeoDAWN footprint | `1m_DEM_links.csv` on the [competition data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (login-gated, VERIFIED redirect to `/accounts/login/`) | obtainable **once**, needs a DrivenData account |
| Same DEM without the login | USGS 3D Elevation Program (3DEP), 1 m lidar-derived DEM, public domain | VERIFIED obtainable: the sponsor's About page states the lidar was collected through 3DEP; 3DEP is a public USGS program |
| Paleo-shoreline geometry (Lake Lahontan / Lake Bonneville) | **NOT YET SOURCED** — see FLAG below | **blocked** |

> **FLAG (needs human review):** no free, official, machine-readable
> paleo-shoreline dataset has been identified yet. Until one is, N4 must use a
> *DEM-derived* shoreline proxy (long, low-curvature, near-horizontal bench
> lineaments at consistent elevation), which is weaker. Naming a verified source
> is a precondition for promoting N4 to a slot-eligible hypothesis. Candidate
> official sources to check: USGS ScienceBase GeoDAWN item
> [657e1d85d34e23d3533209f7](https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7)
> (DOI 10.5066/P93LGLVQ) and the Nevada Bureau of Mines & Geology Quaternary
> fault/lake-level publications. **Do not claim this is sourced until it is.**

---

## N5 · Range-front topographic step and interbasinal high

**Layers.** `training_features.tif` bands: detrended elevation and the slope of
detrended elevation.

**Physical signature.** Slope magnitude + structure-tensor coherence of the
detrended elevation, plus a distance transform to the top-decile slope (the
"front"). A range front is a long, coherent, high-slope lineation; a *step*
along it (a discontinuity in the front line) is the step-over proxy; an
interbasinal high is a locally elevated block between oppositely dipping
systems.

**Why it catches a missing fault.** Verbatim, Faulds et al. 2026:

> "Topographic steps along the fronts of mountain ranges/fault blocks may
> delineate step-overs or relay ramps. Interbasinal highs commonly correspond to
> accommodation zones between oppositely dipping Quaternary fault systems."

The same paper reports that fault terminations, intersections, step-overs and
accommodation zones are *"characterized by closely-spaced, relatively minor
faults with minimal recent surface ruptures"* — i.e. precisely the structures a
regional catalogue omits. And the FSS areal statistics give a quantitative
prior: step-overs occupy **33.3 %** of all FSS area, fault terminations 20.3 %,
accommodation zones 19.3 %, intersections 17.4 %, with a median FSS polygon of
**~13.4 km²**.

**How it differs.** H5's completeness residual compares *catalogue density* with
strain/relief expectations — a regional density statistic. N5 is a *local
geometric detector* on the range front itself. H1's relay corridors are built
from catalogue tip pairs; N5's are built from the topographic front with no
catalogue input.

**New external data.** None required.

---

## What the holdout actually said (this is the part that decides)

Protocol (`scripts/validate_round2.py`): 4 spatial folds of 48-px blocks with a
3-px purge buffer; hide-and-recover logistic regression with a fresh random
component-hiding plan every epoch and the anti-leak assertion run every epoch;
identical model, seeds and protocol across arms; three region seeds.

Two targets, because the prize's private test population is *not disclosed*
(staff declined to say which data/fault types/coverage produced it — forum 11527,
VERIFIED):

* **recovery** — catalogue traces held out of the visible context. This is the
  standard hide-and-recover proxy.
* **discovery** — `blind_traces`: faults present in the synthetic geophysics but
  absent from the catalogue by construction (≥ 22 px from every catalogue trace)
  and **never used as training labels**. This is the local analogue of the
  private test set.
* **combined** — the union, which is the best available guess at "faults not in
  the visible catalogue", i.e. the population the prize scores.

| arm | #feat | recovery | discovery | **combined** | Δ combined | gate |
|---|---|---|---|---|---|---|
| baseline (catalogue geometry + f_elev + f_mag + strain) | 13 | 0.3073 | 0.0081 | 0.2863 | — | baseline |
| **N1** gravity-gradient edges | 17 | 0.3003 | 0.0087 | 0.2804 | **−0.0059** | **FAIL — killed** |
| **N2** seismicity / strain lineaments | 18 | 0.3218 | 0.0569 | 0.3352 | **+0.0489** | **PASS** |
| **N3** alteration-cap margin | 15 | 0.3086 | 0.0057 | 0.2855 | −0.0008 | fail |
| **N5** range-front step | 17 | 0.3214 | 0.0050 | 0.2961 | **+0.0097** | **PASS** |
| GEO-ONLY (geophysical prior alone) | 0 | 0.0822 | 0.0156 | 0.0961 | −0.1903 | fail |
| BLEND (max) | 28 | 0.0822 | 0.0156 | 0.0961 | −0.1902 | fail |
| BLEND-ADD (+0.25·prior) | 28 | 0.1849 | 0.0289 | 0.2029 | −0.0834 | fail |
| **BLEND-MUL (classifier × (1 + 0.5·prior))** | 28 | **0.3673** | **0.0612** | **0.3842** | **+0.0979** | **PASS — best** |

Weight sweep for BLEND-MUL (2 seeds): w=0.25 → 0.3785, **w=0.50 → 0.3851**,
w=1.00 → 0.3746, w=2.00 → 0.3394. w=0.5 is an interior optimum, not an edge.

### The three findings that matter

1. **The literature-ranked top candidate was killed by the gate, and the gate
   worked.** N1 had the strongest published support (a verbatim statement from
   the INGENIOUS authors that gravity-gradient terminations and intersections
   *defined* fault tips and crossings) and the lowest implementation cost. As a
   *classifier feature* it made the blocked holdout slightly **worse**
   (−0.0059 combined). Its information is real — the raw `n1_term_field` alone
   scores DTI 0.08–0.15 against blind faults, ~20× the catalogue-distance
   feature — but feeding it to a model trained on catalogue labels dilutes the
   catalogue signal. **No submission slot was spent on it.** This is exactly the
   behaviour the standing prompt demands.

2. **The multiplicative blend is the winner, and it wins on *both* populations.**
   `classifier × (1 + 0.5 · geophysical_prior)` improves recovery (0.3073 →
   0.3673) *and* discovery (0.0081 → 0.0612, 7.5×). The additive and max blends
   both destroy the classifier's localisation: they smear probability mass over
   the prior's support, which costs FP everywhere without lifting the per-
   ground-truth-pixel maximum. The multiplicative form keeps the classifier's
   thin traces and only *boosts* them where the geophysics independently agrees.

3. **A catalogue-trained model is structurally bad at discovery, and that is the
   whole competition.** The baseline's discovery DTI is 0.0081 — it essentially
   never predicts a fault that is absent from the catalogue, because it has never
   been shown one. Since the prize masks known-fault pixels and scores only
   faults *not* in USGS/INGENIOUS, **the baseline is optimising a population that
   contributes nothing to the score.** Every arm that raised discovery did so by
   injecting information from outside the catalogue.

### Honesty statement

These numbers come from a **synthetic forward model**, not from the competition
rasters (which are behind a DrivenData login — VERIFIED: the data tab redirects
to `/accounts/login/`). They validate (a) the machinery, (b) the *sign* and rough
magnitude of each arm's effect, and (c) that the gate refuses bad ideas. They do
**not** predict a leaderboard score. `scripts/validate_round2.py` runs unchanged
on `data/processed/` once the real rasters are placed.

---

## Promotion decision

* **SLOT-ELIGIBLE (pending real-raster re-run): BLEND-MUL**, then N2, then N5.
* **KILLED by the holdout gate: N1** (as a classifier feature), N3, GEO-ONLY,
  BLEND, BLEND-ADD.
* **NOT YET VIABLE: N4** — needs a verified free official paleo-shoreline source
  (FLAG above) before it can be gated at all.

Next action: place the real rasters, re-run `scripts/validate_round2.py`, and
only then build a submission with `scripts/build_submission.py --policy
"blend-mul w0.5 holdout<value>"`.
