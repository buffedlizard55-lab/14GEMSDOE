# Round 7 — five candidate hypotheses grounded in the problem statement itself

**Recorded:** 2026-09-29 (session-15, 14GEMSDOE). **Status: pre-registration.
No submission slot is spent by anything in this document.**

## 0. Why these five are not R1–R6 in new clothes

Two official statements were sitting in the knowledge base unused, and they
reframe what the hidden truth *is*:

* **C28** (problem description, VERIFIED): *"portions of the existing fault data
  may be misaligned from the true location of the surface fault, which is the
  prediction target."* The **prediction target** is the true surface-fault
  location — not the catalogued raster. The 300 m kernel exists to absorb the
  misregistration.
* **C21** (staff, VERIFIED): a "new fault" *can* be *"newly mapped geometry of
  an existing fault system — a continuation past a mapped tip, a splay, a
  parallel strand in the same zone."*

No arm in R1–R6 models misregistration or along-strike continuation through
cover: every catalogue-geometry channel treats the mapped trace as exact and
terminal. The R1–R6 fleet optimises recovery of *catalogue-position* pixels;
C28 says the scored truth is *elsewhere by up to the kernel width* for the
misregistered portion. That is a different objective, and it is the first
candidate below.

The remaining candidates come from the label producers' own field playbook
(S11–S15, Faulds et al. 2026 — Faulds co-authored the label source, S6) and
from the one verified case study of a concealed fault in this exact province
(Gold et al. 2013, Grizzly Valley, northern Walker Lane). Where a round 1–6
ancestor exists, the difference is stated; where the ancestor's only evidence is
a **synthetic-model kill**, that kill is *not* treated as evidence against the
idea (Session-14 directive 4: "a synthetic-model number is not evidence") and
the re-test is labelled as such.

## 1. Registered candidates (ranked by expected DTI on the hidden truth ÷ cost)

### R7-1: Expression-aligned traces — misregistration correction of the catalogue

* **Layers:** catalogue context traces + `det_elev`, `det_elev_slope`, `tmi_hg`,
  `iso_grav_anom_hg`, `tc` (edge-strength only — see FLAG #11, the `tc` tag
  ambiguity; never used as a depth estimate).
* **Signature:** within ±3 px (the kernel half-width) of each catalogued trace,
  a coherent expression ridge (topographic curvature crest, magnetic-gradient
  ridge, gravity-gradient ridge). The *offset field* between the catalogued
  trace and the expression ridge is a per-pixel feature; the corrected trace is
  an emission candidate.
* **Why a missing fault leaves it:** C28 states portions of the catalogue are
  misaligned from the true surface fault, and the true surface fault is the
  prediction target. The masked known-fault raster (C11) covers the
  *catalogued* pixels; the corrected pixels are neither catalogue pixels nor
  masked, so they are scoring truth. C21 confirms corrected/extended geometry of
  existing systems counts.
* **Difference from everything implemented:** no arm estimates a
  catalogue-to-expression offset; all R1–R6 geometry channels are exact-trace.
  R5-4 curvature is a free ridge detector with no trace anchoring; R6-1 splay
  fans assume the tip position is true.
* **Validation design (pre-registered):** the ordinary gate cannot measure this
  (its truth is the catalogue raster). Two tests instead:
  1. **Misregistration stress test** (new protocol, `scripts/validate_real.py
     --misreg-px δ`): before feature building, randomly translate the *visible*
     context traces by δ ∈ {1, 2, 3} px (rigid per component, direction uniform);
     train/recover hidden components as usual. R7-1's corrected-trace features
     must beat raw-trace features on sparse+far at δ ≥ 1 and must not lose at
     δ = 0. If it wins only at δ > 0, it is promoted as *robustness insurance*
     consistent with C28, not as a measured leaderboard gain.
  2. **Offset statistics on real rasters:** distribution of expression-ridge
     offsets near catalogue traces, reported whether or not they are used.
* **Expected DTI:** unknown on the hidden truth (no ground truth for the
  misregistered fraction exists locally); the *upper* bound is the pixel mass of
  all traces dilated by the offset field. **Cost: medium** (alignment operator +
  stress protocol).

### R7-2: Buried continuation stitching through cover (magnetic/gravity ridge bridge)

* **Layers:** `rtp`, `tmi`, `tmi_hg`, `iso_grav_anom_hg`, `depth_to_base_surf`
  (thick cover = where stitching matters), catalogue endpoints + local strike.
* **Signature:** a potential-field ridge corridor that continues a catalogued
  trace *along strike past its mapped tip* or across a mapped gap, especially
  where basin fill or lake sediments cover the connection
  (`depth_to_base_surf` thick, `det_elev` flat). Collinearity tolerance 30°,
  corridor width ≤ 3 px.
* **Why a missing fault leaves it:** C21 — continuations past a mapped tip are
  scoring truth. S14 — *"faults that have not ruptured in the Holocene are
  obscured by lake sediments and shoreline features"*; the catalogue ends where
  expression ends, the fault does not. Gold et al. 2013 (JGR,
  [10.1002/jgrb.50238](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1002/jgrb.50238),
  VERIFIED): a concealed Quaternary fault in the northern Walker Lane is
  traceable only by subtle lidar lineaments + aeromagnetics between
  discontinuous scarps.
* **Difference:** R6-1 emits an isotropic splay *fan* at tips (no ridge
  following, no collinearity constraint); `relay_corridors` bridges overlapping
  strands across-strike; R3D links surface curvature scarplets, not
  potential-field ridges through cover; `along_strike`/`dist_endpoint` are
  passive features with no bridge emission.
* **Validation:** gate-measurable on hidden components that *continue* a visible
  trace — pre-registered **continuation subset**: hidden components with an
  endpoint within 20 px of a visible endpoint and strike within 30°. Report
  dense/sparse/far on that subset too. **Expected DTI: medium-high on the
  subset, small overall. Cost: medium.**

### R7-3: Gravity-gradient termination & intersection topology (the label producers' basin playbook)

* **Layers:** `iso_grav_anom_hg`, `iso_grav_anom_slope`, `iso_grav_anom_vg`,
  `iso_grav_anom`.
* **Signature:** ridge-skeleton of the gravity-gradient magnitude: segment
  *tips* (terminations), *crossings* (intersections), and short gap-bounded
  collinear continuation candidates — compact topology maps, not raw gradient.
* **Why a missing fault leaves it:** S11 (Faulds et al. 2026, VERIFIED):
  *"terminating and intersecting gravity gradients respectively defined many of
  the fault terminations and fault intersections. This was especially important
  in defining FSS in the many basins of the region, where basin-fill sediments
  obscure the subsurface architecture."* The people who compiled the label
  source found basin faults this way; the hidden expert labels were found by the
  same regional community (C5, S6).
* **Difference / re-test notice:** this is N1's physics. N1's *only* evidence is
  a synthetic-forward-model kill (round 2) — invalid as evidence per directive
  4. It has **never been run against the real rasters**. Not a new idea; a
  mandatory re-test. Different from R6-2 (catalogue-trace intersection halos —
  nothing where the catalogue is blank) and R4A (cross-field edge coincidence,
  never implemented, research-only).
* **Validation:** ordinary component gate; expected to help `far` most.
  **Expected DTI: medium-high on far. Cost: low-medium** (skeletonisation of an
  existing band).

### R7-4: Kinematic strain-budget deficit (geodetic closure)

* **Layers:** `geod_shearrate`, `geod_dilaterate`, `geod_2ndinv` + visible
  catalogue strikes (`local_strike`) and the R6-4 slip-tendency operator if the
  external shapefile ever lands.
* **Signature:** per-pixel deficit between the geodetic strain-rate tensor and
  what nearby catalogued fault strikes could accommodate (project each visible
  strike against the local shear/dilatation rates, take the unaccommodated
  residual). High deficit + high `geod_2ndinv` = strain that the mapped faults
  cannot explain.
* **Why a missing fault leaves it:** Gold et al. 2013 (VERIFIED) close their
  Grizzly Valley paper: including the concealed fault in the regional strain
  budget *"may reduce the discrepancy between geodetic and geologic deformation
  rates."* Concealed faults are exactly where the geodetic budget fails to
  close against the catalogue.
* **Difference:** R5-5 regresses *fault density* against relief/strain smooth
  predictors (a completeness residual); this is a per-pixel *tensor* closure
  with explicit strikes. N2 made raw strain-band lineaments without any
  catalogue-kinematic term. R6-4 is stress-based tendency on assumed geometry
  (external, unfetched).
* **Validation:** ordinary component gate. **Expected DTI: medium. Cost:
  medium.**

### R7-5: Transtensional coupling zones (shear × dilatation interaction)

* **Layers:** `geod_shearrate`, `geod_dilaterate`, `geod_2ndinv`, catalogue
  junction/relay geometry.
* **Signature:** interaction field shear × positive dilatation (transtension),
  modulated by nearby junction/relay density — the kinematic setting, not the
  strain magnitude alone.
* **Why a missing fault leaves it:** S1 (VERIFIED): systems concentrate in
  transtensional areas of highest strain rate; S4: step-overs & horsetail
  terminations show the largest modelled dilatation and Coulomb shear-traction
  increases; S7: displacement-transfer zones host 24 % of Walker Lane classified
  systems. New strands nucleate where shear and dilation couple and the
  catalogue under-represents them.
* **Difference:** `geod_*` bands enter R5/R6 only as raw standardised features;
  no arm forms the shear × dilatation interaction or couples it to junction
  geometry. Distinct from R7-4 (closure deficit vs mapped faults) and R5-5
  (density residual).
* **Validation:** ordinary component gate. **Expected DTI: low-medium. Cost:
  low.**

## 2. Ranking (expected hidden-truth DTI ÷ cost, this session's judgement)

| Rank | ID | Expected DTI on hidden truth | Cost | Gate-measurable? | Slot risk |
|---:|---|---|---|---|---|
| 1 | R7-1 expression-aligned traces | high *if* the C28 misregistered fraction is material | medium | stress test only | zero until stress test passes |
| 2 | R7-2 buried continuation stitching | medium-high (subset), C21-explicit | medium | continuation subset | zero |
| 3 | R7-3 gravity termination/intersection topology | medium-high on `far` | low-medium | direct | zero |
| 4 | R7-4 strain-budget deficit | medium | medium | direct | zero |
| 5 | R7-5 transtensional coupling | low-medium | low | direct | zero |

**Implementation order for the gate:** R7-3 (cheapest, direct) → R7-5 → R7-4 →
R7-2 → R7-1 stress protocol. **Slot order is the reverse of cost: nothing is
uploaded until it beats the current holdout best (post-R6: `all6` or
`geom_horse`) on sparse AND far in ≥ 3 of 4 folds.**

## 3. Pre-registered gate additions

* New arms in `scripts/validate_real.py`: `geom_gravtopo` (R7-3),
  `geom_strain` (R7-4), `geom_trans` (R7-5), `geom_stitch` (R7-2),
  `geom_align` (R7-1, δ = 0 run) — each = geom + geo + its channel(s).
* New protocol flag `--misreg-px` for the R7-1 stress test (rigid per-component
  translation of visible context, δ ∈ {0, 1, 2, 3}).
* **Amendment (2026-09-29, recorded BEFORE any gate numbers):** the alignment
  objective is `mean expression − 0.02·|shift|` px⁻¹. A 256-crop smoke showed
  the unpenalised operator sliding traces to expression noise (mean |offset|
  3.57 px against an injected misregistration of 2 px); the fixed penalty
  reduced it to 2.80 px and is not tuned on any gate result. The tie-break
  (exact ties resolve to the smallest displacement) is unchanged.
* New diagnostic subset (computed from gate JSON split ids + fold fields, no
  re-run): continuation subset as defined in R7-2 — implemented as
  `scripts/continuation_subset.py` with 3 unit tests. **First measurement (on
  the round-6-rest fields): 52.5 % of TEST pixels belong to continuation
  components (hidden components with an endpoint within 20 px of a visible
  endpoint, strike within 30°), and current arms recover them ~2.5× better
  than isolated components (shore: cont 0.0471 vs iso 0.0193; condbase: cont
  0.0420 vs iso 0.0162).** C21's continuation class is the mass of the truth
  population; the isolated remainder is where R7-2's bridge must reach.
* Promote rule unchanged: beat the same-run `geom` on sparse AND far in ≥ 3/4
  folds; for R7-1 additionally the δ ≥ 1 stress condition.

## 4. Irregularities flagged in this round

* **FLAG #11 — `tc` band tag conflicts with the official feature list.** The
  file's own `description` tag says *"Tilt angle or total curvature — magnetic
  field derivative for edge detection"*; the official provided-features list
  (C27) names *"top-of-crustal magnetic source depth"* among the 15 published
  layers, and no other file band matches that name (file tags read line by line
  2026-09-29, `src.tags(i)`, bands 1–19). Either the tag is a generic fallback
  and `tc` is a source-depth product, or the official list item maps to a band
  whose tag was written loosely. **Nothing in this repo may use `tc` as a depth
  estimate until this is resolved** (do not guess — FLAG #1c rule). R7-1 uses
  `tc` only as an edge-strength raster, which both readings support.

## 5. Honesty statement

* No leaderboard number is claimed or predicted here. Expected-DTI entries are
  qualitative priors from the cited sources.
* R7-3 is a re-test of N1; its synthetic kill is void as evidence but it also
  means its prior is not untouched — a null on real data kills it for good.
* R7-1's ordinary-gate numbers (δ = 0) will look *neutral-to-negative* by
  construction (its target pixels are outside the gate's truth); only the
  stress test and the C28/C21 argument support it. It must not be promoted on
  δ = 0 numbers alone, and it must not be described as "validated" unless the
  δ ≥ 1 condition passes.
