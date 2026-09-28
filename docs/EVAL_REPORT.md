# Evaluation report

> Fill this in after running `python -m returns_agent eval`. The full generated tables are in `eval/results/report.md`.

## Method
- Units: __ held-out units (__ photos), 10 scenarios, photographed on __ (phone model, lighting).
- Labellers: two people labelled independently, without seeing each other's labels or the agent output.
- Ground truth: the value both labellers agree on. Disputed cases are excluded from accuracy and reported separately.
- Model: `__` (from the record's `agent.model_version`), one call per unit, temperature 0.
- Positive class for identity and completeness = FAIL (problem found). FN = a problem the agent missed.

## Results

| Check | Human kappa | Accuracy (all) | Accuracy (when decided) | UNCERTAIN rate | FP | FN |
|---|---|---|---|---|---|---|
| Identity | | | | | | |
| Completeness | | | | | | |
| Condition grade (exact / ±1) | | | | | – | – |
| Disposition | | | | | – | – |

Review rate (pending_review): __ · Latency p50 / p95: __ / __ ms · Tokens per unit: __

## Failure modes
1. __ (case ids, what the agent saw vs the truth, why)
2. __

## What we would change
- __
