# Round 6 — five new geological hypotheses distinct from R1–R5

**Session:** 14GEMSDOE, 2026-09-29 · branch `arena/01a0ea95-14gemsdoe`.
**Data status:** real competition rasters present and hash-verified in `data/raw/` (see `research/real_data_unlock.md`). External slip/dilation tendency raster (DOI 10.5066/P9YL58W6) is an additional free official source checked via fetch_page (ScienceBase catalog reachable, shapefile 27–34 MB).
**No DrivenData submission slot is spent in this session under any outcome.**

## 0. Why these five, and how they differ from everything already run

Round 5 interim (2 folds) showed:
- R5-4 profile curvature winning both sparse and far in both folds (only arm to do so)
- Every R5 arm improved `far` (>1 km from catalogue) in 2/2 folds — geophysical priors carry information about genuinely unmapped structures
- Calibrated budget ~0.5% of footprint (25,837 px), 6× smaller than historic 155,021 px

All R5 arms used: relay interior, accommodation polarity, magnetic tilt angle, profile curvature, conditioned completeness. None used:
- horsetail splay geometry (explicitly called out in brief as "horse-tailing at tips")
- orthogonal intersection halos (normal × strike-slip intersections 22% of systems)
- conductive-base gradient + clay-cap coincidence (magnetic low + resistivity low)
- external slip/dilation tendency mechanics (prompt says "Slip and dilation tendency from the INGENIOUS release" — never implemented)
- paleo-lake shoreline suppression + sub-lake fault enhancement

Sibling registers H11–H41 (12GEMSDOE) include: gravity zero-contour, tc-as-tilt, Laplacian of gravity slope, 10 m DEM external. None include horsetail fan, orthogonal intersection halos, conductive-base HGM, slip/dilation raster, or paleo-shoreline masking.

## 1. Registered candidates (ranked by expected DTI gain ÷ implementation cost)

### R6-1: Horsetail splay fan at fault terminations
**Layers:** `training_labels.tif` (catalogue geometry) + `det_elev` (band 12) + `det_elev_slope` (band 19) + structure tensor of detrended elevation
**Physical signature:** At each catalogue tip, a 120° fan (60° each side of outward strike) radius 0.5–2 km (5–20 px), weight = (1 - d/R) × exp(-Δθ² / 2σ²) where Δθ is angle from outward direction, σ=35°. Fan intensity modulated by local slope coherence (high coherence = real scarp, not noise) and by slope magnitude (scarplets). Morphological max over all tips.
**Why missing:** Faulds et al. 2026: "some FSS (e.g., fault tips) are characterized by minor faults with minimal surface ruptures, making them difficult to recognize even with high-resolution lidar" (KB S14). Catalogue records main strand but not distributed horsetail splay. Step-over/tip settings: Faulds 2012: terminations 22% of systems, horsetails 20% in later vintage (KB S2). These are exactly the small connecting structures brief hypothesizes are omitted.
**Difference:** R3A = decaying cones past single tips (isotropic probability wedge, no fan, no slope modulation). R5-1 = relay *interior* between overlapping strands, not tip splay. R3D = curvature-linkage of scarplets point-wise, no tip-anchored fan. No sibling arm targets horsetail fans.
**Cost:** low (geometry + 2 bands, O(n_tips × R²))
**Expected DTI:** +0.003–0.006 on sparse, +0.004–0.008 on far (tip structures are >1 km from other traces, so far protocol should capture). Rank 2 (high gain, low cost).

### R6-2: Normal × strike-slip intersection halos
**Layers:** `training_labels.tif` + `geod_shearrate` (band 7) + `geod_dilaterate` (band 8) + `tmi_hg` (band 3) + `trace_density` + `junction_density`
**Physical signature:** (1) Detect high-angle intersections: for each junction pixel (trace pixel with ≥3 neighbours), sample local strike field in 5×5 window, compute circular variance; if max strike difference >45° (orthogonal = normal × strike-slip), mark as candidate. (2) Also detect near-miss intersections: components whose tips come within 2 km but strike diff >45°. (3) Emit halo: Gaussian (σ=10 px = 1 km) around each candidate, weight = (shear_norm × dilation_norm) × (1 - strike_parallelism) × junction_density_norm. Shear and dilation from geodetic bands (second invariant already in GEO_BANDS, but shear and dilation are more diagnostic of intersection).
**Why missing:** Faulds et al. 2012: normal/strike-slip intersections 22% of catalogued systems, 26.1% of FSS by count (2026). Intersection interior contains many small connecting faults that are buried under basin fill (Faulds: "basin-fill sediments obscure subsurface architecture"). Catalogue records crossing strands but not linking faults. Geodetic strain shows active deformation where no scarp.
**Difference:** `junction_density` counts any junction, no strike filter, no halo, no geodetic weighting. `relay_corridors` requires sub-parallel strands (≤40° diff), opposite of this (≥45°). No arm uses shear × dilation product. Sibling H11–H41 have no orthogonal intersection detector.
**Cost:** low (geometry + 2 geodetic bands already cached, KDTree for near-miss)
**Expected DTI:** +0.004–0.007 sparse, +0.005–0.009 far. Intersections are spatially compact, so per-pixel precision high, recall boost moderate. Rank 1 (highest expected gain ÷ cost).

### R6-3: Conductive-base step / clay-cap edge
**Layers:** `cond_surf` (band 17) + `depth_to_base_surf` (band 15) + `tmi` (band 14) + `iso_grav_anom_hg` (band 18) + `det_elev_slope` (band 19)
**Physical signature:** (1) HGM of depth_to_base_surf: |∇ depth| via Sobel, threshold 90th percentile → ridge = fault-controlled base step. (2) High cond_surf (≥80th percentile) = clay cap. (3) Magnetic low: tmi ≤20th percentile (altered rocks). (4) Coincidence: HGM ridge within 500 m of cond high AND mag low. (5) Cap margin distance: distance transform from coincidence mask, then Gaussian decay σ=5 px. Physical: fault controls conductive base depth and feeds alteration cap; edge of cap marks fault.
**Why missing:** Faulds et al. 2026: "magnetic lows and low resistivity anomalies may respectively indicate altered rocks and clay caps at depth induced by geothermal activity" (KB S12). Fault feeding cap is not necessarily mapped, cap invisible to scarp-based catalogue. 39% of Great Basin systems are blind (KB S3) — no surface hot springs, but cap exists.
**Difference:** N3 = (high conductance AND magnetic low) mask → margin, but no depth_to_base gradient, and N3 killed on synthetic (not real). R5-3 = tilt angle, no conductivity. No arm uses depth_to_base HGM. Sibling H18 used tc band as tilt, not conductivity.
**Cost:** medium (4 bands, gradient, coincidence)
**Expected DTI:** +0.002–0.005 sparse, +0.003–0.006 far. Targets blind systems, so far protocol improvement expected but may be noisy. Rank 3.

### R6-4: Slip & dilation tendency corridors (external INGENIOUS release)
**Layers:** External: `Shapefile_INGENIOUS area.zip` from DOI 10.5066/P9YL58W6 (Siler 2022, USGS) → rasterized slip_tendency + dilation_tendency (0–1) on competition grid (EPSG:32611, 100 m, bilinear resample) + catalogue geometry + `det_elev`
**Physical signature:** Slip tendency = τ/σ_n, dilation tendency = (σ1 - σ_n)/(σ1 - σ3) — both 0–1, high where fault optimally oriented for slip/opening under ambient stress (Morris et al. 1996). Transform: (1) Rasterize external shapefile to grid (each fault segment carries slip, dilation values). (2) Interpolate between segments via inverse distance (faults not everywhere). (3) Emit where dilation >0.7 AND slip >0.5 AND catalogue absent within 300 m (i.e., optimally oriented but unmapped). Weight = dilation × slip × (1 - catalogue_proximity_norm).
**Why missing:** Catalogue compilation is geometry-only, not mechanics-based. Faults optimally oriented for dilation are more likely to be permeable and host geothermal fluid (Siler et al., INGENIOUS). Such faults may be subtle/buried but mechanically favored, so missing from Qfaults. INGENIOUS authors explicitly calculated this to "help identify faults likely to host as-yet-undiscovered hydrothermal processes" (ScienceBase abstract, verified 2026-09-29).
**Difference:** No arm in this repo or siblings uses external stress-derived rasters. Prompt explicitly lists "Slip and dilation tendency from the INGENIOUS release" as a feature to turn into candidate corridors — never implemented until now. Sibling H41 uses distance-to-catalogue as anti-target, not mechanics.
**Cost:** medium-high (requires external fetch 27 MB, unzip, rasterize via geopandas/rasterio, reprojection). Implementation needs geopandas + shapely.
**Expected DTI:** +0.005–0.010 far, +0.003–0.006 sparse. Directly tied to geothermal favorability, so should improve discovery of hidden geothermal-relevant faults. Rank 1 tie, but cost higher than R6-2, so ranked 2 after accounting for cost.
**Free official source:** https://doi.org/10.5066/P9YL58W6 — verified via fetch_page 2026-09-29, ScienceBase item 6296974dd34ec53d276bb33d, files: Shapefile_INGENIOUS area.zip (27.35 MB) + Shapefile_Full Study.zip (34.25 MB). License: public domain (USGS). Obtainable: yes, via `curl -L https://www.sciencebase.gov/catalog/file/get/6296974dd34ec53d276bb33d?f=__disk__...` or direct download link from JSON API `https://www.sciencebase.gov/catalog/item/6296974dd34ec53d276bb33d?format=json` which lists download URLs. Checked: fetch_page returned file list. So viable.

### R6-5: Paleo-lake shoreline suppression + sub-lake fault enhancement
**Layers:** `det_elev` (band 12) + `det_elev_slope` (band 19) + `iso_grav_anom` (band 13) + `iso_grav_anom_hg` (band 18) + `det_elev` structure tensor
**Physical signature:** (1) Detect paleo-shorelines: high coherence (>0.7) + low slope (<30th percentile) + sub-horizontal strike (0±15° or 90±15° from north? Actually shorelines follow elevation contours, so strike ~ perpendicular to regional slope). Use detrended elevation to find near-constant elevation bands: histogram peaks of det_elev where slope low and coherence high → shoreline mask. (2) Two outputs: shoreline_mask (to suppress false positives where scarps are shorelines) and sub_lake_enhanced: where det_elev < shoreline elevation (i.e., former lake bottom) AND gravity HGM high (basin structure beneath sediments) → enhanced fault probability. Weight = gravity_HGM_norm × (1 - shoreline_proximity).
**Why missing:** Faulds et al. 2026: "much of the GBR was inundated by late Pleistocene lakes, and thus faults that have not ruptured in the Holocene are obscured by lake sediments and shoreline features" (KB S14). Hermant et al. 2025: CNN detects paleo-shorelines as false positives (KB M4) — shoreline scarps look like fault scarps. So faults under lake beds are systematically missing from catalogue, and shorelines cause false positives that should be suppressed.
**Difference:** N4 idea (lidar scarp + shoreline suppression) was pre-registered but never implemented due to missing external paleo-shoreline dataset (FLAG #1b). This arm does NOT require external shoreline dataset — it derives shorelines from det_elev + slope + coherence, and uses gravity to see through lake fill (Faulds: gravity gradients defined terminations in basins). R5-4 = profile curvature alone, no shoreline concept. Sibling H32 uses external 10 m DEM, not detrended elevation.
**Cost:** medium (structure tensor + histogram + gravity)
**Expected DTI:** +0.001–0.004 sparse (suppression reduces FP), +0.002–0.005 far (enhancement under lakes). Lower expected than others because shoreline detection noisy. Rank 5.

## 2. Ranking by expected DTI improvement ÷ cost

| Rank | Arm | Expected Δ sparse vs geom | Expected Δ far vs geom | Cost | Ratio | Rationale |
|------|-----|---------------------------|------------------------|------|-------|-----------|
| 1 | R6-2 intersection halos | +0.004–0.007 | +0.005–0.009 | low | **high** | Targets 22–26% of systems, uses existing bands, orthogonal filter novel, geodetic weighting, compact halos = high precision |
| 2 | R6-1 horsetail splay fan | +0.003–0.006 | +0.004–0.008 | low | high | Targets 22% terminations, horsetail minor faults explicitly called hard to recognize, fan geometry novel vs cones |
| 3 | R6-4 slip/dilation tendency | +0.003–0.006 | +0.005–0.010 | med-high | medium-high | Directly geothermal-relevant, external data required but verified obtainable, mechanics-based not geometry-only |
| 4 | R6-3 conductive-base step | +0.002–0.005 | +0.003–0.006 | medium | medium | Targets 39% blind systems, uses cap + base gradient, but N3 ancestor killed (though on synthetic) |
| 5 | R6-5 paleo-shoreline | +0.001–0.004 | +0.002–0.005 | medium | low-medium | Important for completeness but detection noisy, suppression may help FP more than TP |

Top candidate for validation: **R6-2 intersection halos** (lowest cost, highest expected gain, fully implementable without external fetch).

## 3. Gate (pre-registered before scoring)

Same as Round 5 gate (`scripts/validate_real.py` protocol component, 4 folds, seed 20260928, TEST 20% / CALIB 20% / HIDE 35% / visible 25%, logistic regression 150 iters, emission policy calibrated on CALIB only, truth protocols dense/sparse(20%)/far(>1 km from context)).

Arms to validate in this round:
- geom (baseline, 12 geom features)
- geo (geom + 12 official bands)
- geom_ramp, geom_acc, geom_tilt, geom_curv, geom_gap, all (R5 incumbents)
- geom_horse (R6-1)
- geom_xsec (R6-2) ← top candidate
- geom_condbase (R6-3)
- geom_shore (R6-5)
- geom_slip (R6-4, if external data present, else skip with FLAG)
- all6 = geom + geo + R5-1…R5-5 + R6-1…R6-5 (or without slip if missing)

Decision rule (unchanged): promote an arm only if it beats geom baseline on **both** sparse and far in ≥3 of 4 folds. No slot spent until promote rule met.

## 4. Results — TO BE FILLED AFTER GATE RUN

(Will be transcribed from `artifacts/holdout_round6.json` after full run)

## 5. Honesty statement

- Scored population at DrivenData is privately withheld new-fault set; catalogue is only proxy.
- Far protocol is closest analogue of hidden set; ranking on far drives decisions.
- No arm slot-eligible until promote rule met; no slot spent in this session.
- R6-4 requires external shapefile fetch; if not present, it is flagged and not scored, but source is verified obtainable.
