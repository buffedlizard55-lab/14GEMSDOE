# Hypotheses — research record

The rendered, source-linked version lives at `docs/hypotheses.html`; this file
records the validation protocol and the decision history behind the ranking.

## Ranking (2026-09-28) — expected DTI gain × cost

| Rank | ID | Hypothesis | Gain | Cost | External data | Gate |
|------|----|------------|------|------|---------------|------|
| 1 | H1 | Structural completion: relay ramps / horsetails / intersections — the small connecting faults catalogues omit | high | low | none (optional: INGENIOUS Qfaults v2) | hidden-connector hide-and-recover |
| 2 | H2 | Magnetic lineaments of concealed faults (structure-tensor edges on GeoDAWN magnetics) | high | medium | none (in-stack) | lineament DTI on held-out blocks |
| 3 | H3 | Hydrothermal-expression gaps (springs, sinter/tufa, warm wells, vents) | medium-high | medium | INGENIOUS GDR 1391 + heat flow DOI | enrichment ≥2× + DTI delta |
| 4 | H4 | Slip/dilation-tendency corridors (INGENIOUS stress product) | medium | low-medium | DOI 10.5066/P9YL58W6 | tendency-weighted A/B |
| 5 | H5 | Catalogue-completeness residuals (strain + relief vs observed density) | medium | low | DEM via provided links | masked-region recovery |

Geological basis (verified, `knowledge_base.md` S1–S7): step-overs/relay ramps
~32%, terminations ~22%, intersections ~22%, accommodation zones ~8% of
catalogued Great Basin geothermal systems (Faulds et al. 2012); ~39% of systems
blind; step-overs/horsetails concentrate dilatation and shear traction. The
competition's hidden labels are expert-mapped faults *absent from the USGS
catalogue* (C1) — the omitted class is exactly the small connecting/concealed
structures these signatures mark.

## Why each catches MISSING faults (not re-detections)

* **H1** — emissions live at catalogue-distance > 0 by construction
  (hide-and-recover context); connectors/splays are what strand geometry
  predicts and compilations omit.
* **H2** — concealed faults have no scarp or catalogue trace; only the magnetic
  field expresses them; scored on lineaments in catalogue-blank areas.
* **H3** — hydrothermal expression requires a permeable pathway; expression
  without a mapped fault implies an unmapped fault.
* **H4** — tendency is computed from stress + assumed geometry; favourable
  corridors lacking a strand point at strand omissions.
* **H5** — strain/relief predict deformation independent of mapping effort;
  negative catalogue-density residuals mark omission.

## Validation protocol (mandatory before any weekly slot)

1. `python3 scripts/validate_blocks.py` (spatial blocks + purge buffer) — the
   candidate must beat the current `artifacts/holdout.json` mean DTI.
2. The delta (before → after) is written into the slot log on
   `docs/leaderboard.html` and the run's MANIFEST before upload.
3. Hash uniqueness across the whole ledger is checked
   (`scripts/build_submission.py` names every file by content sha8).
4. If a candidate needs external data, the data must be listed in
   `knowledge_base.md` with a verified obtainable source first — otherwise the
   hypothesis is recorded as not-viable-yet, not as progress.

## Decision history

* 2026-09-28 — ranked as above after source verification. No hypothesis has yet
  been evaluated on real competition labels (data behind login, B1); the
  synthetic end-to-end demo proves the machinery, not the ranking. H1 leads on
  (a) direct match to the omitted-structure hypothesis, (b) zero external-data
  dependency, (c) cheapest honest validation. Do not reorder without holdout
  evidence.
