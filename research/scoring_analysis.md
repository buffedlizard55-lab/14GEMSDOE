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

## 2. The 0.1563 attractor — autopsy (VERIFIED evidence, T1–T5)

* GEMSDOE1 and 5GEMSDOE publish the **same artifact hash** `7f00890a…` and the
  same 259,495-run payload (their sites, fetched 2026-09-28). Byte-identical
  fields ⇒ identical TP_w/FP_w/FN_w ⇒ identical DTI.
* The public leaderboard has **three accounts tied at exactly 0.1563**
  (extradr19 #26, SDCF9 #27, smashi34 #28) — the signature of a shared or
  equivalently-derived emission, not of independent approaches converging.
* The field is catalogue-skeleton-based (thinned `ens12` emission at floor 0.1).
  Under masking, its score is produced entirely by its thin off-catalogue
  fringe. Variants that thin or buffer the same skeleton change the score only
  through that fringe — hence 0.1563 / 0.1560 clustering.
* The surrogate DTI those runs optimized was computed against the **training
  catalogue** — the wrong population (the prize scores hidden new faults, C1/C12).
  Optimizing the surrogate selects "be the catalogue", which masking scores at
  whatever the fringe earns.

**Conclusion:** the repeated score is self-plagiarism of one artifact family
plus surrogate-metric misdirection — not a platform ceiling. The
blanket-coverage floor of ~0.0956 (T3) and the 0.01–0.05 scores of divergent
first probes show the headroom below and above.

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
* **NaN policy.** Scorer treatment of NaN is not spelled out in the docs; the
  prior team's empirical statement ("NaN is read as 0.0" outside the footprint)
  is TEAM-REPORTED. The gate nonetheless forbids NaN inside the footprint
  because the form's range check demonstrably rejects it (T4, reproduced in
  `tests/test_submission_gate.py`).

## 5. Holdout protocol (the only slot currency)

* Spatial blocks (64 px default) with purge buffer; fold targets are traces
  whose context is removed — the honest local analogue of the hidden test.
* Hide-and-recover inside training: whole components hidden per epoch, leak
  assertion mandatory (`gems/hide_recover.py`).
* A candidate may spend a weekly slot only if mean blocked DTI beats the current
  best AND the delta is recorded in `docs/leaderboard.html` slot log +
  `research/limitations_and_next.md`.
