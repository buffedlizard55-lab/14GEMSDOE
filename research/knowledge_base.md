# Knowledge base — line-by-line verified facts

Checked 2026-09-28 (UTC) against the official sources linked in each row.
Status: `VERIFIED` = source opened and claim found there; `CHECKED-PENDING` =
page verified, binary not downloaded; `TEAM-REPORTED` = from the project thread,
not independently verifiable here; `FLAG` = irregularity.

Where the working brief disagrees with the official source, the source wins and
the disagreement is recorded in `research/limitations_and_next.md`.

## 1. Competition & metric

| # | Fact | Source | Status |
|---|------|--------|--------|
| C1 | Task: models/algorithms giving accurate information about faults (structures indicative of geothermal resources) in the GeoDAWN region | [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) | VERIFIED |
| C2 | Metric: distance-weighted Tversky index; α = 0.2 (FP), β = 0.8 (FN); triangular kernel k(d)=max(1−d/R,0), R = 300 m = 3 px | [metric section](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric) | VERIFIED |
| C3 | Worked example printed: TP_w=3.00, FP_w=1.89, FN_w=2.00 → TI_w = 0.60 | same | VERIFIED (arithmetic re-checked: 3/(3+0.378+1.6)=0.6027≈0.60) |
| C4 | Submission: single-layer float32 GeoTIFF, values in [0,1], EPSG:32611, 100 m, same bounds; outside = null/NaN | [submission format](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format) | VERIFIED |
| C5 | Labels: USGS Quaternary Fault and Fold Database + new faults labelled by NLR and USGS experts | [rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) §2, §3.3 | VERIFIED |
| C6 | Training labels come from the INGENIOUS Great Basin Regional Dataset Compilation (Ayling, Faulds, et al. 2022, DOI 10.15121/1881483) | rules PDF §3.3 + footnote 4 | VERIFIED |
| C7 | Two phases: Phase 1 $50,000 split equally among top 5 on the private test set; Phase 2 $250,000 ($100k/$70k/$40k/$25k/$15k) on the expert-expanded label set | rules PDF §1.1; [competition home](https://www.drivendata.org/competitions/306/competition-doe-gems/) | VERIFIED |
| C8 | One submission per entity is scored across both rounds, chosen without private-test knowledge; finalists deliver complete code + documentation | rules PDF §3.4–3.6 | VERIFIED |
| C9 | Three submissions per week per entity | rules PDF §3.2 | VERIFIED |
| C10 | Deadline: Dec. 3, 2026, 11:59 p.m. UTC | competition home | VERIFIED |
| C11 | Known USGS/INGENIOUS fault pixels are masked/excluded from evaluation (both rounds); including them in predictions does not change the score | [forum 11516](https://community.drivendata.org/t/scoring-clarification-are-known-usgs-ingenious-faults-masked-when-scoring-and-are-they-in-the-final-round-label-set/11516), DrivenData staff 2026-09-16 | VERIFIED |
| C12 | Staff will not disclose which data/fault types/coverage produced the hidden test faults; Phase 2 labels expand from expert review of all submissions | [forum 11527](https://community.drivendata.org/t/how-were-the-new-test-faults-identified-data-sources-and-fault-types/11527) | VERIFIED |
| C13 | External data allowed/encouraged with a license permitting use and sharing with the sponsor | [rules highlight](https://www.drivendata.org/competitions/306/competition-doe-gems/), rules | VERIFIED |
| C14 | Eligibility: US citizens/permanent residents; US-captained teams; no FFRDC/federal-employee competitors (cash) | rules §1.3 | VERIFIED |
| C15 | Generative-AI use allowed, must be indicated in the narrative | rules §3.2 | VERIFIED |
| C16 | Reference solution: U-Net + Monte-Carlo CV notebook, author Prof. John Lipor | [reference repo](https://github.com/drivendataorg/gems-prize-reference-solution) | VERIFIED |
| C17 | Feature stack (19 named layers incl. magnetics, gravity, strain rates, conductivity, earthquake density) + `1m_DEM_links.csv` | [provided features](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#provided-features) | VERIFIED (band order not published — FLAG #6) |
| C18 | Competition data tab requires DrivenData login (redirects to /accounts/login/) | [data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) | VERIFIED (redirect observed) |
| C19 | GeoDAWN = airborne magnetic + radiometric surveys, NW Nevada / E California (Glen & Earney 2024) | [DOI 10.5066/P93LGLVQ](https://doi.org/10.5066/P93LGLVQ) | VERIFIED (citation in rules fn.3) |
| C20 | Public leaderboard is DW-Tversky on the public test subset | [leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) | VERIFIED (live page parsed 2026-09-28; top = DARD 0.3168) |
| C21 | **"New fault" means "any fault pixel not already captured by USGS/INGENIOUS" and CAN include newly mapped geometry of an existing fault system** (a continuation past a mapped tip, a splay, a parallel strand in the same zone) | [forum 11536](https://community.drivendata.org/t/where-do-you-draw-the-line/11536), DrivenData staff 2026-09-23 | VERIFIED — **this is the single most important strategy fact in the competition**: extension/splay geometry is scoring truth |
| C22 | Submission allowance resets on a **rolling window**, not a calendar week | [forum 11524](https://community.drivendata.org/t/weekly-submissions/11524), staff 2026-09-17 | VERIFIED |
| C23 | The 19-band order is **not** unpublished: `training_features.tif` carries a per-band `description` and `data_category` tag; the reference notebook reads them with `src.tags(i)`. The "single band / Band 19" confusion in the notebook is a print bug (leftover loop variable), per staff | [forum 11529](https://community.drivendata.org/t/why-does-the-training-fault-labels-file-in-the-data-tab-have-a-single-band-while-the-labels-in-the-reference-solution-repo-have-19-bands/11529), staff 2026-09-24; reference notebook cell 5 | VERIFIED — **corrects FLAG #6** |
| C24 | Reference solution specifics: `data/numeric_features.tif` + `data/labels.tif`; 19 feature bands; U-Net resnet18 (ImageNet weights); MC = 5 random splits; patch 128; test_proportion 0.5; batch 32; 5 epochs; AdamW lr 1e-4; TverskyLoss α=0.2/β=0.8; predictions averaged over the 5 best models; only patches containing labels kept | [reference notebook](https://github.com/drivendataorg/gems-prize-reference-solution/blob/main/unet-mc-cv-reference-solution.ipynb) cells 2,5,6,16,19 | VERIFIED (repo cloned 2026-09-28, sha256 of tarball `05a32550365aef3…`) |
| C25 | The reference solution trains on the **known-fault labels** and predicts the same population — it contains no masking, no hide-and-recover, and no off-catalogue target. Its surrogate is therefore the wrong population for the prize | reference notebook cells 6, 16, 19 | VERIFIED (read line by line) |
| C26 | GeoDAWN lidar was collected through the USGS 3D Elevation Program (3DEP) over a similar extent to the geophysical surveys | [About page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/) | VERIFIED |
| C27 | 15 feature layers are named in the official provided-features list (surface conductivity; depth to conductive base; detrended elevation + its slope; dilatation rate; shear strain rate; 2nd strain invariant; isostatic gravity anomaly + its slope; RTP magnetic anomaly; TMI; vertical and horizontal slope of TMI; top-of-crustal magnetic source depth; earthquake density) = 15 named; the remaining 4 of the 19 are not enumerated publicly (the figure caption additionally mentions total radiometric counts) | [provided features](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#provided-features) | VERIFIED (15 named) + FLAG #6b (4 unnamed) |
| C28 | Problem description itself: "portions of the existing fault data may be misaligned from the true location of the surface fault, which is the prediction target" — the 300 m kernel exists partly to absorb that | [problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#performance-metric) | VERIFIED |

## 2. Structural geology (Faulds inventory)

| # | Fact | Source | Status |
|---|------|--------|--------|
| S1 | 2012 catalogue (250+ fields): step-overs/relay ramps ~32%; normal×strike-slip intersections 22%; normal-fault terminations/tip-lines 22%; accommodation zones 8%; displacement transfer 5%; major normal faults 6%; pull-aparts 4%; range-front 3%; bends 3% | [Faulds et al. 2012 NZ Geothermal Workshop](https://gdr.openei.org/files/383/Faulds%20et%20al%202012%20GeoNZ%20Paper.pdf); [GDR 383](https://gdr.openei.org/submissions/383); [DE-EE0002748 final report](https://gdr.openei.org/files/354/Final%20Report-DE-EE0002748.pdf) | VERIFIED — matches the brief's 32/22/22/8 exactly |
| S2 | Later vintages refine the split: 313 classified systems (Faulds & Hinz 2015 as summarized 2023) = step-overs 25%, horsetails 20%, intersections 18%, accommodation 7%, transfer 4%, pull-aparts 3%, bends 2%, major normal 1%; 2014 GSA abstract: tips 25%, accommodation 9% | [Geoenergy 2023](https://www.lyellcollection.org/doi/full/10.1144/geoenergy2023-009); [GSA 2014](https://gsa.confex.com/gsa/2014AM/webprogram/Paper248671.html) | VERIFIED — FLAG #2 (vintage drift) |
| S3 | ~39% of known Great Basin systems are blind/hidden (no surface hot springs/fumaroles); structural setting undetermined for ~25% | [GBCGE project](https://gbcge.org/recent-projects/characterizing-structural-controls/); DE-EE0002748 | VERIFIED |
| S4 | Step-overs & horsetail terminations show the largest modelled dilatation and Coulomb shear-traction increases of the eight settings | [Geoenergy 2023 conclusions](https://www.lyellcollection.org/doi/full/10.1144/geoenergy2023-009) | VERIFIED |
| S5 | Step-over attributes: relay ramp widths 0.1–14.6 km (mean 2.8 km); high-T systems prefer right-stepping (~56%), hard-linked (~70%), overlapping (~56%); ~17% of all Great Basin step-overs host known systems; step-overs host ~47% of Nevada producing systems | [Giddens & Faulds SGW 2025](https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf) | VERIFIED |
| S6 | J. Faulds is a co-author of the INGENIOUS compilation (= the competition's label source) | rules §3.3 fn.4; [GDR 1391](https://gdr.openei.org/submissions/1391) | VERIFIED |
| S7 | Structural settings of 313 systems catalogued; displacement transfer zones host 24% of Walker Lane classified systems | Geoenergy 2023 | VERIFIED |
| S8 | **Faulds et al. 2026 (SGW): >1,430 favourable structural settings (FSS) mapped in the INGENIOUS study area; FSS polygons occupy ~7.7% of the area; median FSS polygon ~13.4 km²** | [Faulds et al. SGW 2026](https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2026/Faulds.pdf) | VERIFIED |
| S9 | **FSS by count: step-overs 39.6%, intersections 26.1%, terminations 16.7%, accommodation zones 6.8%, pull-aparts 2.3%, displacement transfer 1.4%, bends 0.9%, major normal faults 0.6%. By AREA: step-overs 33.3%, terminations 20.3%, accommodation zones 19.3%, intersections 17.4%** | same | VERIFIED |
| S10 | **403 known geothermal systems (≥37 °C): step-overs 27.54%, intersections 22.08%, terminations 16.63%, accommodation 5.71%, displacement transfer 3.23%, pull-aparts 2.73%, major normal faults 2.23%, **undetermined 17.12%**. 120 training sites (≥120 °C): step-overs 34.2%, intersections 26.7%, terminations 14.2%, displacement transfer 6.7%, accommodation 5.8%, pull-aparts 5.0%** | same | VERIFIED |
| S11 | **"Isostatic residual and horizontal gradient gravity data were the most useful. For example, terminating and intersecting gravity gradients respectively defined many of the fault terminations and fault intersections. This was especially important in defining FSS in the many basins of the region, where basin-fill sediments obscure the subsurface architecture and primary basin-bounding and/or intrabasinal faults."** | same | VERIFIED — **the direct basis for hypothesis N1** |
| S12 | **"magnetic lows and low resistivity anomalies may respectively indicate altered rocks and clay caps at depth induced by geothermal activity"** | same | VERIFIED — **the direct basis for hypothesis N3** |
| S13 | **"Topographic steps along the fronts of mountain ranges/fault blocks may delineate step-overs or relay ramps. Interbasinal highs commonly correspond to accommodation zones between oppositely dipping Quaternary fault systems."** | same | VERIFIED — **the direct basis for hypothesis N5** |
| S14 | **"much of the GBR was inundated by late Pleistocene lakes, and thus faults that have not ruptured in the Holocene are obscured by lake sediments and shoreline features"; "some FSS (e.g., fault tips) are characterized by minor faults with minimal surface ruptures, making them difficult to recognize even with high-resolution lidar"** | same | VERIFIED — **the physical reason the catalogue is incomplete, and the basis for the paleo-shoreline negative mask in N4** |
| S15 | Step-over geometry statistics: ~54% right-stepping, ~51% hard-linked, ~50% underlapping; relay ramp widths 0.1–14.6 km, mean 2.8 km; higher-T (>120 °C) step-overs ~56% right-stepping, ~70% hard-linked, ~56% overlapping, mean ramp width 3.3 km; ~74% of higher-T step-overs lie between N–NNE strands; producing systems preferentially step left (~64%) | [Giddens & Faulds SGW 2025](https://pangea.stanford.edu/ERE/db/IGAstandard/record_detail.php?id=38022) (SGP-TR-229) | VERIFIED |

## 3. External data inventory (free, official)

All from the INGENIOUS release ([GDR 1391](https://gdr.openei.org/submissions/1391),
DOI [10.15121/1881483](https://doi.org/10.15121/1881483), CC BY 4.0) or linked
USGS ScienceBase releases. Page content VERIFIED 2026-09-28; binaries
CHECKED-PENDING (sandbox TLS policy — see FLAG #1). Direct-download links are
recorded in `scripts/download_external_data.sh` verbatim.

| Dataset | URL | Size (as listed) | Use |
|---|---|---|---|
| Quaternary Faults v2 (2023-06-27) | [zip](https://gdr.openei.org/files/1391/qfaults_ingenious_nad83conus117_2023-06-27.zip) | 5.85 MB | H1 enrichment |
| Quaternary Faults v1 | [zip](https://gdr.openei.org/files/1391/faults_quaternary_INGENIOUS_regional_data.zip) | 5.76 MB | provenance diff |
| Quaternary Volcanics (vents, flows) | [zip](https://gdr.openei.org/files/1391/great_basin_q_volcanics.zip) | 9.44 MB | H3 |
| Paleo-geothermal (sinter/tufa) | [zip](https://gdr.openei.org/files/1391/paleo_geothermal_regional.zip) | 82 KB | H3 |
| Well & spring temperature + chemistry | [zip](https://gdr.openei.org/files/1391/wellspringdata.gdb.zip) | 19.85 MB | H3 |
| 2 m temperature probes | [zip](https://gdr.openei.org/files/1391/2m_temperature_probe_INGENIOUS_regional_data.zip) | 1.03 MB | H3 |
| Geodetic shear & dilation models | [zip](https://gdr.openei.org/files/1391/geodetics_INGENIOUS_regional_data.zip) | 51.99 MB | H5 cross-check |
| Earthquake density models | [zip](https://gdr.openei.org/files/1391/seismicity_INGENIOUS_regional_data.zip) | 22.98 MB | cross-check |
| Study area boundary | [zip](https://gdr.openei.org/files/1391/study_area_boundary_INGENIOUS_regional_data.zip) | 6.68 KB | clipping |
| Slip & dilation tendency | [DOI 10.5066/P9YL58W6](https://doi.org/10.5066/P9YL58W6) | — | H4 |
| Heat flow maps | [DOI 10.5066/P9BZPVUC](https://doi.org/10.5066/P9BZPVUC) | — | H3 |
| MT electrical conductance | [DOI 10.5066/P9TWT2LU](https://doi.org/10.5066/P9TWT2LU) | — | cross-check |
| Gravity & magnetics regional | [DOI 10.5066/P9Z6SA1Z](https://doi.org/10.5066/P9Z6SA1Z) | — | context |
| Elevation trend & detrended elevation | [DOI 10.5066/P9MQRCBY](https://doi.org/10.5066/P9MQRCBY) | — | context |
| Thermal conductivity (SMU abridged) | [GDR 1390](https://gdr.openei.org/submissions/1390) | — | context |

## 4. Method references (cited by the sponsor's About page)

| # | Fact | Source | Status |
|---|------|--------|--------|
| M1 | Deep-learning fault mapping from optical imagery + topography is established practice | [Mattéo et al. 2021, JGR Solid Earth, DOI 10.1029/2020JB021269](https://doi.org/10.1029/2020JB021269) | VERIFIED (cited on [About page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/)) |
| M2 | DL mapping of Quaternary faults, western USA | [Hermant et al., SGW 2025](https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Hermant.pdf) | VERIFIED (cited on About page) |
| M3 | Edge detection / Hough transforms named by the sponsor as standard fault-mapping techniques | About page | VERIFIED |
| M4 | **Hermant et al. 2025 (TLS Geothermics): CNN fault mapping in the same region from 3DEP 1/3-arc-second lidar-derived elevation + slope + Sentinel-2 B8A; 1,100 manually mapped faults / 264 km; labels rasterised with a 50 m buffer; USGS Qfault positions differ from lidar ground truth by up to 400 m in N-central Nevada; new faults detected by the CNN were confirmed by experts on lidar; both models also detect paleo-shorelines as false positives; FaultSEG test PR-AUC 0.595, siUNET 0.449** | [Hermant et al. SGW 2025](https://pangea.stanford.edu/ERE/db/GeoConf/papers/SGW/2025/Hermant.pdf) | VERIFIED (cited by the sponsor's About page; full PDF read 2026-09-28) |
| M5 | Qfault density varies regionally for mapping-effort reasons, not geological ones — a regional catalogue-density map is partly a map of who mapped what | Hermant et al. 2025, Fig. 2 | VERIFIED |

## 5. Team-history facts (TEAM-REPORTED unless noted)

| # | Fact | Evidence | Status |
|---|------|----------|--------|
| T1 | GEMSDOE1 and 5GEMSDOE published builders display the same truncated artifact-hash prefix (`7f00890a…`), payload run-count (259,495), and histogram | both published site pages fetched 2026-09-28 | VERIFIED as a match in the displayed site metadata; the full binaries and DrivenData upload records are not in this repo, so exact upload identity is not independently verified |
| T2 | GEMSDOE1 = 0.1563, 5GEMSDOE = 0.1563, 8GEMSDOE = 0.1563, GEMSDOE2 = 0.1560 | project thread | TEAM-REPORTED (consistent with T1 and LB ties) |
| T3 | Grid 3,292 × 3,730 px; catalogue 60,988 px; 716 DEM tiles; blanket floor DTI 0.0956 | GEMSDOE1 site (measured claims) | TEAM-REPORTED (their measurements; re-derived here when data lands) |
| T4 | Prior rejection on the form: "Predicted values must be in range [0, 1]" | project thread | TEAM-REPORTED; failure modes reproduced in tests |
| T5 | Leaderboard accounts SDCF9/wbg1/smrtdoog5/extradr19/smashi34 tie/match group scores | LB snapshot vs thread | mixed — see `results_ledger.md` |
| T6 | **Three separate leaderboard accounts are tied at exactly 0.1563: extradr19 (#26), SDCF9 (#27), smashi34 (#28)** | [live leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) parsed 2026-09-28 | VERIFIED (rows read directly) |
| T7 | Live leaderboard top 5 on 2026-09-28: DARD 0.3168, alexoktaba 0.2993, HardcoreTechGod 0.2854, mzoorob 0.2843, joeyfezster 0.2806 | same | VERIFIED |
| T8 | Sandbox network reachability, re-measured 2026-09-28: `pypi.org`, `files.pythonhosted.org`, `github.com`, `api.github.com`, `codeload.github.com`, `registry.npmjs.org` are reachable from bash. **All other hosts fail the TLS handshake** (drivendata.org, gdr.openei.org, sciencebase.gov, usgs.gov, doi.org, dropbox.com, zenodo.org, ncei.noaa.gov, archive.org, raw.githubusercontent.com). The Arena `fetch_page`/`web_search` tools DO reach those hosts, so every external page above was verified through them | measured | VERIFIED — **updates FLAG #1: the reference-solution repo is now obtainable in-sandbox** |
| T9 | **A NaN-nodata submission file is REJECTED by the form** with exactly "Predicted values must be in range [0, 1]". Observed 2026-09-28 when a team member uploaded the site's then-default download (NaN outside the footprint, per the official format wording "outside = null/NaN"). Mechanism (inferred, not disclosed by staff): the checker evaluates ALL pixels, so NaN fails a `(v >= 0) & (v <= 1)` test. Mitigation shipped: the site's default download and `build_submission.py` emit finite files (0.0 outside the footprint, which cannot change the score — no labels exist there and 0.0 is below any threshold) | team upload attempt + [format page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/#submission-format) wording | TEAM-REPORTED (rejection) + VERIFIED (format wording) — **FLAG #10** |
| T10 | Dropbox share pages supplied in the project brief are reachable and display filenames for `example_submission.tif`, `existing_faults.tif`, `gems-geodawn-numerical-features.tif`, a DEM-links PDF, and rules PDF. They are wired as optional fetch URLs in `scripts/download_competition_data.sh`. Page-level availability was observed; binary contents and provenance as official competition downloads were NOT verified. A SHA256 on retrieval records bytes but does not authenticate source identity. | team-provided URLs; public share pages fetched 2026-09-28; official data tab is [login-gated](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) | TEAM-PROVIDED / CONTENT UNVERIFIED. Do not train or submit based on these files until their CRS, shape, transform, tags and labels are checked against authorized official data. |
| T11 | Leaderboard re-verified 2026-09-28T09:22Z: top-5 unchanged (DARD 0.3168, alexoktaba 0.2993, HardcoreTechGod 0.2854, mzoorob 0.2843, joeyfezster 0.2806); the 0.1563 three-way tie persists (#26 extradr19, #27 SDCF9, #28 smashi34); wbg1 0.1461 (#33, 4 submissions); smrtdoog5 0.1193 (#48, 2 submissions) | [live leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) parsed via fetch tool | VERIFIED (all rows read directly) |
