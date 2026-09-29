# Evaluation report

Cases run: 50 / 50  
Model failures (routed to review): 0  
Overall review rate (disposition = pending_review): 0.34  
Missing-parts exact match: 0.84  
Latency (model, ms): {'p50': 8100.5, 'p95': 12188, 'max': 40327}  
Tokens: {'total': 129400, 'mean_per_case': 2588}

Ground truth = value both labellers agree on; disputed cases are excluded from accuracy.
Positive class for identity/completeness = FAIL (a problem). FN = missed problem.

| Check | Human agreement | Kappa | GT n | Disputed | Accuracy (all) | Accuracy (decided) | Uncertain rate | FP | FN |
|---|---|---|---|---|---|---|---|---|---|
| identity | 0.94 | 0.859 | 47 | 3 | 0.915 | 0.955 | 0.1 | 0 | 0 |
| completeness | 0.96 | 0.935 | 48 | 2 | 0.792 | 0.778 | 0.06 | 0 | 0 |
| condition_grade | 0.62 | 0.523 | 31 | 19 | 0.516 | 0.444 | 0.1 | - | - |
| disposition | 0.82 | 0.763 | 41 | 9 | 0.732 | 0.654 | 0.34 | - | - |

Condition within one grade: 0.516

## Confusion

**identity**

- truth=FAIL -> agent=FAIL: 9
- truth=PASS -> agent=PASS: 33
- truth=PASS -> agent=UNCERTAIN: 2
- truth=UNCERTAIN -> agent=FAIL: 2
- truth=UNCERTAIN -> agent=UNCERTAIN: 1

**completeness**

- truth=FAIL -> agent=FAIL: 10
- truth=PASS -> agent=PASS: 25
- truth=UNCERTAIN -> agent=FAIL: 8
- truth=UNCERTAIN -> agent=PASS: 2
- truth=UNCERTAIN -> agent=UNCERTAIN: 3

**condition_grade**

- truth=UNCERTAIN -> agent=UNCERTAIN: 4
- truth=UNCERTAIN -> agent=Unacceptable: 4
- truth=UNCERTAIN -> agent=Used - Good: 2
- truth=UNCERTAIN -> agent=Used - Very Good: 2
- truth=Unacceptable -> agent=Unacceptable: 2
- truth=Used - Acceptable -> agent=Used - Good: 2
- truth=Used - Good -> agent=Used - Good: 4
- truth=Used - Good -> agent=Used - Like New: 2
- truth=Used - Like New -> agent=Unacceptable: 1
- truth=Used - Like New -> agent=Used - Like New: 4
- truth=Used - Very Good -> agent=Used - Good: 1
- truth=Used - Very Good -> agent=Used - Like New: 1
- truth=Used - Very Good -> agent=Used - Very Good: 2

**disposition**

- truth=dispose -> agent=dispose: 9
- truth=dispose -> agent=liquidate: 1
- truth=liquidate -> agent=liquidate: 1
- truth=liquidate -> agent=pending_review: 1
- truth=liquidate -> agent=refurbish: 2
- truth=pending_review -> agent=liquidate: 1
- truth=pending_review -> agent=pending_review: 13
- truth=pending_review -> agent=refurbish: 2
- truth=refurbish -> agent=dispose: 1
- truth=refurbish -> agent=pending_review: 1
- truth=refurbish -> agent=refurbish: 3
- truth=refurbish -> agent=restock: 1
- truth=restock -> agent=dispose: 1
- truth=restock -> agent=restock: 4

## By scenario

| Scenario | n | Disposition correct | Sent to review |
|---|---|---|---|
| ambiguous | 6 | 2 | 2 |
| complete_correct | 7 | 4 | 0 |
| damaged | 5 | 2 | 0 |
| heavily_damaged | 2 | 2 | 0 |
| lightly_used | 7 | 5 | 0 |
| main_part_missing | 5 | 3 | 4 |
| missing_accessory | 5 | 1 | 2 |
| new_looking | 4 | 2 | 0 |
| similar_lookalike | 3 | 3 | 3 |
| wrong_product | 6 | 6 | 6 |

## Per case

| Case | Scenario | Identity (agent/truth) | Completeness | Grade | Disposition | Rule |
|---|---|---|---|---|---|---|
| E01 | complete_correct | PASS / PASS | PASS / PASS | Used - Like New / Used - Like New | restock / restock | R15_COMPLETE_LIKE_NEW |
| E02 | complete_correct | PASS / PASS | PASS / PASS | Used - Like New / disputed | restock / disputed | R15_COMPLETE_LIKE_NEW |
| E03 | complete_correct | PASS / PASS | PASS / PASS | Used - Very Good / disputed | refurbish / refurbish | R16_COMPLETE_WEAR |
| E04 | complete_correct | PASS / PASS | PASS / PASS | Used - Like New / Used - Like New | restock / restock | R15_COMPLETE_LIKE_NEW |
| E05 | complete_correct | PASS / PASS | PASS / PASS | Used - Like New / Used - Like New | restock / restock | R15_COMPLETE_LIKE_NEW |
| E06 | complete_correct | PASS / PASS | PASS / PASS | Used - Like New / disputed | restock / disputed | R15_COMPLETE_LIKE_NEW |
| E07 | complete_correct | PASS / PASS | PASS / PASS | Used - Like New / Used - Very Good | restock / refurbish | R15_COMPLETE_LIKE_NEW |
| E08 | wrong_product | FAIL / FAIL | FAIL / UNCERTAIN | UNCERTAIN / UNCERTAIN | pending_review / pending_review | R03_IDENTITY_FAIL |
| E09 | wrong_product | FAIL / FAIL | FAIL / UNCERTAIN | Used - Good / UNCERTAIN | pending_review / pending_review | R03_IDENTITY_FAIL |
| E10 | wrong_product | FAIL / FAIL | FAIL / UNCERTAIN | UNCERTAIN / UNCERTAIN | pending_review / pending_review | R03_IDENTITY_FAIL |
| E11 | wrong_product | FAIL / FAIL | FAIL / UNCERTAIN | UNCERTAIN / UNCERTAIN | pending_review / pending_review | R03_IDENTITY_FAIL |
| E12 | wrong_product | FAIL / FAIL | FAIL / UNCERTAIN | Unacceptable / UNCERTAIN | pending_review / pending_review | R03_IDENTITY_FAIL |
| E13 | wrong_product | FAIL / FAIL | PASS / UNCERTAIN | Unacceptable / UNCERTAIN | pending_review / pending_review | R03_IDENTITY_FAIL |
| E14 | missing_accessory | PASS / PASS | FAIL / FAIL | Unacceptable / disputed | dispose / refurbish | R06_UNACCEPTABLE_SEVERE |
| E15 | missing_accessory | PASS / PASS | FAIL / FAIL | Used - Good / Used - Good | dispose / dispose | R08_HYGIENE_USED |
| E16 | missing_accessory | PASS / PASS | FAIL / FAIL | Unacceptable / disputed | liquidate / dispose | R07_UNACCEPTABLE |
| E17 | missing_accessory | UNCERTAIN / disputed | FAIL / FAIL | Used - Good / disputed | pending_review / disputed | R04_IDENTITY_UNCERTAIN |
| E18 | missing_accessory | UNCERTAIN / PASS | FAIL / FAIL | Used - Very Good / Used - Very Good | pending_review / refurbish | R04_IDENTITY_UNCERTAIN |
| E19 | main_part_missing | UNCERTAIN / disputed | FAIL / FAIL | Used - Good / disputed | pending_review / disputed | R04_IDENTITY_UNCERTAIN |
| E20 | main_part_missing | PASS / PASS | FAIL / FAIL | Used - Good / Used - Very Good | liquidate / liquidate | R10_MISSING_CORE_PART |
| E21 | main_part_missing | FAIL / UNCERTAIN | FAIL / FAIL | Unacceptable / disputed | pending_review / pending_review | R03_IDENTITY_FAIL |
| E22 | main_part_missing | UNCERTAIN / PASS | FAIL / FAIL | UNCERTAIN / disputed | pending_review / liquidate | R04_IDENTITY_UNCERTAIN |
| E23 | main_part_missing | FAIL / UNCERTAIN | FAIL / FAIL | Unacceptable / disputed | pending_review / pending_review | R03_IDENTITY_FAIL |
| E24 | new_looking | PASS / PASS | PASS / PASS | Used - Like New / disputed | restock / disputed | R15_COMPLETE_LIKE_NEW |
| E25 | new_looking | PASS / PASS | PASS / PASS | Unacceptable / Used - Like New | dispose / restock | R06_UNACCEPTABLE_SEVERE |
| E26 | new_looking | PASS / PASS | PASS / PASS | Used - Like New / Used - Like New | restock / restock | R15_COMPLETE_LIKE_NEW |
| E27 | new_looking | PASS / PASS | PASS / PASS | Used - Like New / Used - Good | dispose / dispose | R08_HYGIENE_USED |
| E28 | lightly_used | PASS / PASS | PASS / PASS | Used - Like New / Used - Good | dispose / dispose | R08_HYGIENE_USED |
| E29 | lightly_used | PASS / PASS | PASS / PASS | Used - Good / Used - Good | dispose / dispose | R08_HYGIENE_USED |
| E30 | lightly_used | PASS / PASS | PASS / PASS | Used - Like New / disputed | restock / disputed | R15_COMPLETE_LIKE_NEW |
| E31 | lightly_used | PASS / PASS | PASS / PASS | Used - Very Good / disputed | dispose / dispose | R08_HYGIENE_USED |
| E32 | lightly_used | PASS / PASS | PASS / PASS | Used - Good / Used - Good | dispose / dispose | R08_HYGIENE_USED |
| E33 | lightly_used | PASS / PASS | PASS / PASS | Used - Very Good / Used - Very Good | refurbish / refurbish | R16_COMPLETE_WEAR |
| E34 | lightly_used | PASS / PASS | PASS / PASS | Used - Very Good / disputed | refurbish / disputed | R16_COMPLETE_WEAR |
| E35 | damaged | PASS / PASS | PASS / PASS | Used - Good / disputed | refurbish / disputed | R16_COMPLETE_WEAR |
| E36 | damaged | PASS / PASS | PASS / PASS | Used - Good / Used - Acceptable | refurbish / liquidate | R16_COMPLETE_WEAR |
| E37 | damaged | PASS / PASS | PASS / PASS | Used - Good / Used - Acceptable | refurbish / liquidate | R16_COMPLETE_WEAR |
| E38 | damaged | PASS / PASS | PASS / PASS | Used - Good / Used - Good | refurbish / refurbish | R16_COMPLETE_WEAR |
| E39 | damaged | PASS / PASS | PASS / disputed | Used - Like New / disputed | dispose / dispose | R08_HYGIENE_USED |
| E40 | heavily_damaged | PASS / PASS | UNCERTAIN / UNCERTAIN | Unacceptable / Unacceptable | dispose / dispose | R06_UNACCEPTABLE_SEVERE |
| E41 | heavily_damaged | PASS / PASS | PASS / PASS | Unacceptable / Unacceptable | dispose / dispose | R06_UNACCEPTABLE_SEVERE |
| E42 | ambiguous | UNCERTAIN / UNCERTAIN | UNCERTAIN / UNCERTAIN | UNCERTAIN / UNCERTAIN | pending_review / pending_review | R02_NO_USABLE_IMAGES |
| E43 | ambiguous | PASS / PASS | PASS / PASS | Used - Like New / disputed | restock / disputed | R15_COMPLETE_LIKE_NEW |
| E44 | ambiguous | PASS / PASS | PASS / PASS | Used - Very Good / UNCERTAIN | refurbish / pending_review | R16_COMPLETE_WEAR |
| E45 | ambiguous | PASS / disputed | PASS / disputed | Used - Good / UNCERTAIN | refurbish / pending_review | R16_COMPLETE_WEAR |
| E46 | ambiguous | PASS / PASS | UNCERTAIN / UNCERTAIN | Used - Good / disputed | pending_review / pending_review | R09_COMPLETENESS_UNCERTAIN |
| E47 | ambiguous | PASS / PASS | FAIL / UNCERTAIN | Used - Good / disputed | liquidate / pending_review | R10_MISSING_CORE_PART |
| E48 | similar_lookalike | FAIL / FAIL | PASS / UNCERTAIN | Used - Very Good / UNCERTAIN | pending_review / pending_review | R03_IDENTITY_FAIL |
| E49 | similar_lookalike | FAIL / FAIL | FAIL / UNCERTAIN | Unacceptable / UNCERTAIN | pending_review / pending_review | R03_IDENTITY_FAIL |
| E50 | similar_lookalike | FAIL / FAIL | FAIL / UNCERTAIN | Unacceptable / UNCERTAIN | pending_review / pending_review | R03_IDENTITY_FAIL |
