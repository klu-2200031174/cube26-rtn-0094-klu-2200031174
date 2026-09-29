# Evaluation report

Full generated tables (per case, per scenario, confusion matrices): `eval/results/report.md`. Raw numbers: `eval/results/results.json`. Cached model outputs: `eval/results/cache/` (the report can be regenerated without an API key).

## Method
- Units: 50 held-out units (50 photos, one per unit), 10 scenarios, photographed on 2026-09-29 with a phone under ordinary home lighting (see `eval/photo_map.csv`).
- Labellers: two people labelled independently, without seeing each other's labels or the agent output.
- Ground truth: the value both labellers agree on. Disputed cases are excluded from accuracy and reported separately.
- Model: one call per unit, temperature 0. Gemini's primary model was overloaded during the run, so most units were answered by the fallback models: gemini-3.1-flash-lite 30, gemini-3.5-flash-lite 11, gemini-3.5-flash 6, gemini-3.6-flash 3 (recorded per case in `agent.model_version`). The results mostly reflect the lighter models.
- Positive class for identity and completeness = FAIL (problem found). FN = a problem the agent missed.

## Results

| Check | Human kappa | Accuracy (all) | Accuracy (when decided) | UNCERTAIN rate | FP | FN |
|---|---|---|---|---|---|---|
| Identity | 0.86 | 0.915 (43/47) | 0.955 | 0.10 | 0 | 0 |
| Completeness | 0.94 | 0.792 (38/48) · **1.00 (31/31) on right-item cases** | 0.778 | 0.06 | 0 | 0 |
| Condition grade (exact / ±1) | 0.52 | 0.52 (16/31) · on right-item cases: 0.63 exact, 0.84 within one grade (19 cases) | 0.44 | 0.10 | – | – |
| Disposition | 0.76 | 0.732 (30/41) | 0.654 | 0.34 | – | – |

Review rate (pending_review): 34% · Latency p50 / p95 / max: 8.1 s / 12.2 s / 40.3 s · Tokens per unit: 2,588 (129,400 total for 50 units)

How to read the completeness row: on the 13 wrong-item and look-alike cases the labels say "cannot tell" for parts (the item is not the ordered one), while the agent still reports the ordered parts as absent. Those cases count as errors in the raw figure but do not change the outcome, because identity FAIL sends them to review first (rule R03). On the 31 cases where the right item was returned and both labels decided, completeness was correct every time.

## What worked
- **No wrong item was accepted.** All 6 wrong-product cases and all 3 look-alikes (Samsung vs OPPO charger, wired vs wireless earbuds) were caught as identity FAIL and sent to review. Identity FN = 0, FP = 0.
- **Missing parts were found reliably:** no confirmed-present part was reported missing and no confirmed-missing part was missed (completeness FP = 0, FN = 0).
- **Unusable evidence is refused:** the fully dark photo (E42) was rejected as unusable and routed to review (R02).
- **Heavily damaged items:** both burnt/taped cable cases (E40, E41) graded Unacceptable, DISPOSE.
- **Model outages did not lose cases:** during the run the primary model was overloaded; every unit was still answered via fallbacks (0 model failures in the final run).

## Failure modes

| # | Cases | What happened | Effect | Fix |
|---|---|---|---|---|
| 1 | E14, E16 | A missing lid was treated as damage: the model graded the item "Unacceptable" because a part was missing, although the prompt says missing parts are handled separately (Amazon lists "missing essential parts" as unacceptable, see FINDINGS F7). | E14: DISPOSE instead of REFURBISH (recoverable item thrown away). E16: LIQUIDATE instead of DISPOSE. | Ignore "Unacceptable" when the only stated reason is a missing catalogued part; evaluate the hygiene rule before the Unacceptable rules. |
| 2 | E25 | Invented damage: a clean claw clip photographed from above was described as "missing its spring hinge" (the hinge is simply not visible). | DISPOSE instead of RESTOCK. The most costly error in the set. | Require a severe-damage claim to cite something visible; route every DISPOSE to a quick human confirmation. |
| 3 | E36, E37, E07 | Grading optimism: stained pouches graded Used - Good (labels: Acceptable); a used charger graded Like New (labels: Very Good). | REFURBISH instead of LIQUIDATE (E36, E37); RESTOCK instead of REFURBISH (E07). | Add stain/discolouration examples to the grading prompt; tune the condition threshold on labelled data. |
| 4 | E44, E45 | Over-confidence on poor photos: a blurry soft toy and a bottle photographed from across the room were graded (Very Good, Good) where both labellers said the grade cannot be judged. | REFURBISH instead of REVIEW. | Mark blurry / distant photos as low quality and require UNCERTAIN grades for them. |
| 5 | E47 | A part was declared absent without being visible: the earbuds case photographed at an angle, contents hidden, reported as "earbuds absent". | LIQUIDATE instead of REVIEW. | Treat ABSENT on an enclosed container as NOT_VISIBLE unless the inside is shown. |
| 6 | E18, E22 | Conservative identity: an OPPO adapter alone and a bottle lid alone were marked UNCERTAIN. | REVIEW instead of REFURBISH / LIQUIDATE. A safe error: a human decides. | Acceptable; could improve with brand/label reading. |

Disposition errors split into **value-destroying** (E14, E25: recoverable items disposed), **optimistic** (E07, E36, E37: better outcome than warranted), **missed review** (E44, E45, E47) and **safe review** (E18, E22).

## Limitations
- 50 units, 12 household item types, one photo each, one home and one phone. The numbers are indicative, not a production estimate.
- 44 of 50 answers came from fallback models because the primary model was overloaded. A rerun with `python -m returns_agent eval --no-cache` when the primary model is available may give different (likely better) numbers.
- Condition grade is the least reliable check, for labellers and agent alike (labeller kappa 0.52): the gap between adjacent grades is a judgement call from a single photo.
- The rule thresholds were set before the evaluation and were not tuned on these cases.

## What we would change next
1. Gate every DISPOSE behind a one-click human confirmation (would have caught E14 and E25).
2. Separate "missing part" from "damage" in code, not only in the prompt (fixes failure mode 1).
3. Stronger photo-quality gate for blur and distance (failure mode 4).
4. Re-run the evaluation on the primary model and tune the three confidence thresholds on a separate dev set.
