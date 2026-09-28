# Round 4 — genuinely distinct candidate hypotheses (pre-registration)

**Recorded:** 2026-09-28. **Status: research/pre-registration only. No feature arm,
submission, or weekly slot was changed or used.**

## Decision at a glance

| Rank | ID | Hypothesis / layers | Target signature | Why a missing fault could leave it | Difference from implemented repo | Expected DTI upside* | Cost / data gate |
|---:|---|---|---|---|---|---|---|
| 1 | R4A | Joint geophysical boundary topology: official-stack isostatic gravity anomaly/slope + RTP/TMI magnetic anomaly/gradients + surface conductivity/depth-to-conductive-base | Coincident, strike-consistent multi-field edge segments; edge terminations and short gaps where one field loses contrast but the others continue it | Subsurface faults in basin fill can lack a scarp and catalogue trace while juxtaposing density, magnetic, or conductive units. Independent physical contrasts may persist where any one field is weak. This is a testable targeting rationale, not proof that every coincident edge is a fault. | No existing arm jointly evaluates edge orientation/topology across gravity, magnetic **and** conductivity. N1 is gravity-only edge endpoints; R3C is magnetic-only structure tensor; N3 is a thresholded conductivity-and-magnetic cap mask. | Medium, high uncertainty; no numeric DTI claim | Medium. Uses named competition layers; training rasters and tags are absent from this checkout, so cannot validate now. No additional external dataset required. |
| 2 | R4B | Hydrographic deflection / offset: competition 1 m DEM tiles where available + USGS 3D Hydrography Program (3DHP) flowlines | Coherent channel deflection, abrupt channel offset, or aligned knickpoint sequence with a common local strike; separate tectonic candidate traces from slope/curvature scarps | Fault displacement can deform channels even when a coherent scarp is absent. A peer-reviewed mapping study documents fault-related deflected streams ([Geosphere 2012](https://pubs.geoscienceworld.org/gsa/geosphere/article/8/3/581/132511/Map-of-the-late-Quaternary-active-Kern-Canyon-and)); a USGS trench study also documents a stream deflection with a nontectonic cause ([USGS OFR 2015-1122](https://pubs.usgs.gov/publication/ofr20151122)), so the signature is not diagnostic alone. It targets channel-network geometry rather than a fault-shaped terrain ridge; screen lithology, drainage capture, roads, and DEM artefacts. | No hydrologic-network, channel-offset, or channel-knickpoint feature exists. N5 uses elevation slope/range-front proxies; R3D links curvature scarplets. Neither models fluvial network displacement. | Medium, high uncertainty | High. USGS 3DEP and 3DHP are official free sources (links below); the exact GeoDAWN tile coverage and time alignment have not been checked because `1m_DEM_links.csv` and DEM tiles are absent. Do not call the regional data ready until those checks pass. |
| 3 | R4C | Contact-offset graph: public geologic-map unit polygons/contacts from USGS National Geologic Map Database (NGMDB), prioritizing available large-scale Nevada/AASG/USGS maps | Repeated truncation, lateral offset, or abrupt termination of mapped stratigraphic contacts along a common lineament; consistency across more than one unit boundary | A concealed or unmapped fault may juxtapose or offset geologic units without a mapped fault line. Contact geometry is an independent map-derived observation, not a projection from the fault catalogue. Map scale, compilation age, and source-map fault overlays can cause false evidence or label leakage. | No geologic-unit polygons, contact network, or contact-offset graph is used by `gems/features.py` or the N1–N5/R3 feature arms. | Medium, high uncertainty | High. NGMDB MapView advertises free map exploration/download, but map availability, downloadable vector format, and scale at each GeoDAWN tile are not established here. Only include contacts from source maps with documented scale/date; never treat NGMDB's catalog of maps as a ready-to-use seamless layer. |
| 4 | R4D | Fault-zone texture from multi-directional illumination of competition 1 m DEM / 3DEP bare-earth elevation | Repeated, aligned subtle uphill- and downhill-facing scarplets with alternating polarity, evaluated as a *paired* strike-slip shear-zone texture rather than isolated curvature ridges | A concealed/weakly expressed strike-slip strand may produce discontinuous, alternating small scarps or be visible only in bare-earth microtopography. Paired polarity is more specific than a generic slope/curvature threshold but can still arise from nontectonic landforms. | N5 thresholds slope and range-front position; R3D links negative-curvature scarplets. Neither tests the signed, alternating scarp-polarity sequence as a shear-zone signature. This is related terrain evidence, so it is lower-ranked and must not be described as wholly independent from R3D. | Low-to-medium, high uncertainty | Medium-high. Requires the 1 m DEM subset and coverage/quality review. USGS 3DEP provides a free download path, but the exact local files are not present or verified. |

\* **Expected upside is a qualitative prior, not a score prediction.** The only
comparative evidence allowed for promotion is the pre-registered, real-data,
spatially blocked holdout result against the current incumbent. No synthetic
holdout score is represented here as evidence of real leaderboard gain.

## Why R4A is ranked first (not already a renamed old arm)

The official stack's named layers include gravity anomaly/slope, RTP/TMI and
magnetic slopes, surface conductivity, and depth to conductive base (competition
[provided-features list](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#provided-features)).
USGS's 2019 Great Basin play-fairway report describes blind-system evidence at
Southeastern Gabbs Valley combining structural setting, intersecting/terminating
gravity gradients, magnetic low, temperature anomaly, and low resistivity
([USGS publication 70221765](https://pubs.usgs.gov/publication/70221765)). A
USGS study at Argenta Rise reports basin-fill-obscured structures and jointly
models gravity, magnetic, and magnetotelluric data
([USGS publication 70271418](https://pubs.usgs.gov/publication/70271418)).
These sources support **integrating independent observations**, not any particular
feature's leaderboard value.

R4A pre-registers a cross-layer *topology* test, not another single-layer edge
map: for each named field compute scale-matched gradients and local orientation;
score a candidate segment only when at least two physically independent fields
have compatible edge orientation within a fixed tolerance; preserve the
individual-field edge support and endpoint/gap continuity as separate channels.
Do not use a hidden label, full catalogue geometry, or a trace's own pixels to
construct features. All layer transforms and thresholds must be fixed using the
training folds only (or pre-registered without labels). Compare against the same
model/holdout split with a single additional ablation removing each modality.

**Key risk:** correlated interpolation products are not independent evidence.
The data audit must determine which bands are original measurements versus
processed derivatives, whether their grids/support differ, and whether coverage
or missingness itself would leak location. If the four unnamed stack bands remain
unresolved from the file tags, they are excluded—not guessed.

## Official source / obtainability checks (manual-review links)

| Source | What the source page establishes | What remains unverified here |
|---|---|---|
| Competition provided features — [DrivenData feature list](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#provided-features) | Competition-provided geophysical/topographic features include the named layers listed above. | Actual TIFF band tags, raster validity, transforms, and data contents: competition files are not in `data/raw/`. |
| Great Basin blind-system integration — [USGS 70221765](https://pubs.usgs.gov/publication/70221765) | Official paper record and abstract describe gravity, magnetic, temperature, resistivity and structural evidence integration. | It does not establish pixel-level fault predictions or DTI improvement. |
| Argenta Rise — [USGS 70271418](https://pubs.usgs.gov/publication/70271418) | Official abstract describes a broad step-over, basin-fill-obscured intra-basin structures, and joint gravity/magnetic/MT interpretation. | It is a local case study, not validation for the GeoDAWN competition grid. |
| USGS elevation products — [3DEP](https://www.usgs.gov/3d-elevation-program), [download access](https://www.usgs.gov/the-national-map-data-delivery/gis-data-download) | USGS states 3DEP products are free; its download page documents DEM/lidar download paths. | Coverage/resolution for each GeoDAWN tile; the repo's tile index and DEM assets are absent. |
| USGS hydrography — [3DHP](https://www.usgs.gov/3d-hydrography-program) | Official program/source for hydrography products. | Specific regional flowline coverage, product version, downloadability and alignment must be checked before R4B is viable. |
| USGS/AASG geologic-map inventory — [NGMDB MapView](https://ngmdb.usgs.gov/mapview/) | Official catalog/viewer describes exploring and downloading geologic maps. | Seamless, sufficiently detailed contact vectors over the entire contest footprint are not confirmed. |
| Nevada geologic map data — [USGS Data Series 249](https://pubs.usgs.gov/ds/2007/249/) | Official USGS source for a digital Nevada geologic map and GIS files at regional map scale. | Its scale is 1:250,000; adequacy for 100 m local offset measurements is not established and should be tested before use. |

The official USGS catalog for geothermal heat flow / tendency also confirms the
presence of public heat-flow, gravity/magnetic, and slip/dilation products
([USGS data catalog record](https://data.usgs.gov/datacatalog/data/USGS:60be89e3d34e86b938912329),
[DOI 10.5066/P9V5SQRD](https://doi.org/10.5066/P9V5SQRD)). I did **not** rank a
heat-flow-gradient arm as new: H3 in `research/hypotheses.md` already proposed
hydrothermal/heat-flow evidence, and this round is intended to avoid renaming
that idea.

## Validation gate and current result

**Result: not run on real holdout; no candidate is slot-eligible.** This checkout
contains no competition TIFFs, labels, submission template, external rasters, or
DEM links: `data/raw`, `data/processed`, and `data/external` contain only
`.gitkeep` placeholders. Python also lacks `numpy`, `scipy`, `rasterio`, and
`pytest`, which this repository's current validator/test suite requires. Thus
neither the 2026-09-28 synthetic artifacts nor literature evidence can satisfy
the user's required real spatially-blocked validation.

Before R4A implementation/gating:

1. Obtain authorized competition rasters and labels using the official DrivenData
data tab (requires the account that has competition access); do not substitute
synthetic labels or a public proxy and call it the competition holdout.
2. Install the pinned project environment and verify the official raster band
metadata, CRS, transform, masks, and valid-data intersection before feature
engineering.
3. Reproduce the current incumbent on exactly the same spatial folds and
hide-and-recover protocol. Keep geographic blocks and purge buffers fixed;
ensure no random pixel split or label-derived transform leaks into features.
4. Evaluate R4A vs incumbent and pre-register discovery/recovery/combined DTI,
mean and dispersion per fold/seed, and a paired confidence interval. Promote
only if the real blocked result improves the agreed gate metric and does not
materially harm discovery. If it does not beat the real incumbent, kill it.
5. Only after a documented win, produce a fresh artifact, validate the GeoTIFF
against the official template, compare its prediction hash with all prior
uploads, and then consider a weekly slot.

**Current slot decision: HOLD.** No candidate has beaten the real holdout
incumbent because the data required to make that comparison is absent.

## Source and scope notes

- Structural context from [Faulds et al. 2012, GDR 383](https://gdr.openei.org/submissions/383): relay ramps, intersections, and terminations are common Great Basin geothermal settings, but their catalogue percentages are descriptive associations, not a probability model for hidden faults.
- The [current public leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) was fetched on 2026-09-28 and showed DARD at 0.3168. The brief's 0.3049 is stale as of that check. This public score is not comparable to synthetic or local blocked-holdout metrics.
- Sources were opened through Arena's web research tools on 2026-09-28; binary external datasets were not downloaded or hash-verified from this sandbox.
