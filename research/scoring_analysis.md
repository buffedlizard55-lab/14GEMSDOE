# Scoring analysis — why 0.1563 and what beats it

## 1. The metric in decision form (all constants VERIFIED, source C2)

    DTI = TP_w / (TP_w + 0.2·FP_w + 0.8·FN_w + ε)

    TP_w = Σ_{g∈GT}     max_{x : d(x,g)≤R} p(x)·k(d(x,g))
    FN_w = Σ_{g∈GT}     1 − max_{x : d(x,g)≤R} p(x)·k(d(x,g))
    FP_w = Σ_{x : p(x)>0} p(x)·[1 − max_{g∈GT} k(d(x,g))]
    k(d) = max(1 − d/R, 0),  R = 300 m = 3 px

Decision consequences (each one is a design rule in the pipeline):

1. **β/α = 4.** A missing fault pixel costs four times an equal false-positive
   pixel. Breadth on plausible structure is cheap; silence is expensive.
2. **Per-ground-truth-pixel max.** Each hidden-fault pixel is credited by the
   single best prediction within 300 m. A thin p≈1 trace on the fault beats a
   diffuse p≈0.3 cloud: the cloud pays FP everywhere and still leaves FN.
3. **k(d) falls linearly:** 1.00 on-pixel, 0.67 at 100 m, 0.33 at 200 m, 0 at
   300 m. Line placement error of 1 px is worth twice 2 px at 100 m pixels.
4. **Masking (C11):** known-fault pixels are excluded from evaluation. Emission
   on the catalogue is free but worthless. All score mass comes from
   off-catalogue pixels.
5. **One file, two rounds (C7/C8):** Phase 2 re-scores against labels expanded
   from everyone's predictions. Genuine novel structures have direct option
   value: if experts adopt them, they become scoring truth.

## 2. The 0.1563 recurrence — what the evidence does and does not establish

* **Observed:** the published GEMSDOE1 and 5GEMSDOE pages display the same
  truncated artifact-hash prefix (`7f00890a…`), run-length payload count
  (259,495), and histogram. This strongly suggests the two *published site
  builders* encode the same field. **Not available:** original uploaded TIFFs,
  full hashes, or DrivenData submission IDs. Therefore upload-level byte/pixel
  identity remains unverified.
* **Observed:** leaderboard snapshots show several different accounts at
  0.1563 when scores are displayed to four decimal places. That is a tie in the
  rounded metric only. It does not show equal confusion components, equal
  rasters, or collaboration. Another artifact can have the same rounded DTI.
* **Reported, not independently reproduced:** group run descriptions identify
  some 0.156x approaches as catalogue-skeleton variants. The repo has no source
  upload files to measure how much of the prediction lies off-catalogue or
  re-score the historical runs against private labels.
* **Audit flags:** abbreviated artifact IDs repeat for ledger rows #1/#8,
  #14/#15, and #18/#19. The last two pairs lack score/upload evidence; the
  repeated IDs can indicate reuse, but shortened IDs are not proof. See
  `research/results_ledger.md`.

**Conclusion:** a repeated 0.1563 is not a platform ceiling and is not, by
itself, evidence of duplicate submissions. The matching published builder
metadata for GEMSDOE1/5GEMSDOE is the strongest reuse signal; retrieve full
prediction-array hashes and upload IDs to close the question. Prevent exact
prediction reuse mechanically; use rounded-score collisions only to trigger a
provenance audit. Real holdout data is absent, so no historic explanation here
is validated against competition labels.

## 3. What raises DTI (ordered by leverage)

| Lever | Mechanism in the equations | Implemented as |
|---|---|---|
| Recall of hidden traces within ±1 px | raises every per-g max term; cuts β·FN | H1/H2 geometry + lineament emission; thin p≈1 skeletons |
| Plausible breadth off-catalogue | FP costs α=0.2 per unit mass at k=0 | corridor fields (relay bridges, expression buffers) at moderate p |
| Avoiding diffuse clouds | clouds pay FP without lifting per-g maxima | skeletonization/NMS before emission (already measured w=0 optimal on prior runs) |
| Phase-2 adoption value | verified discoveries become truth | well-reasoned novel corridors with documented evidence |

## 4. Sensitivities we keep on record

* **Masking semantics (FLAG #5).** "Excluded from evaluation" is implemented as
  both-sides exclusion (`gems/dti.py`). If the platform instead only zeroes the
  FP term on masked pixels, catalogue-hugging predictions could earn extra
  kernel credit; the S5-style catalogue-hedge probe measures which is true —
  run it as a *diagnostic* slot only.
* **ε = 1e-9.** Irrelevant at region scale; kept for division safety and pinned
  in tests.
* **NaN policy (updated 2026-09-28, T9/FLAG #10).** The form's range check
  demonstrably rejects NaN *anywhere in the raster* — a real upload of the
  site's NaN-outside download was bounced with exactly "Predicted values must
  be in range [0, 1]" (the earlier note that "NaN is read as 0.0 outside" is
  superseded by this observation). Default emission is therefore **finite
  everywhere**: 0.0 outside the footprint. That choice is score-neutral in the
  DTI arithmetic — no ground-truth pixels exist outside the footprint, and 0.0
  is below any threshold, so it adds no FP_w — while guaranteeing the range
  check passes. Enforced in `build_submission.py` (clamp + `--fix-nan`) and in
  the site builder's value gate (a build refuses to download if any payload
  value leaves [0, 1]).

## 5. Holdout protocol (the only slot currency)

* Spatial blocks (64 px default) with purge buffer; fold targets are traces
  whose context is removed — the honest local analogue of the hidden test.
* Hide-and-recover inside training: whole components hidden per epoch, leak
  assertion mandatory (`gems/hide_recover.py`).
* A candidate may spend a weekly slot only if mean blocked DTI beats the current
  best AND the delta is recorded in `docs/leaderboard.html` slot log +
  `research/limitations_and_next.md`.
