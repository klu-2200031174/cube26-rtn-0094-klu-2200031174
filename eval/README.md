# Evaluation set: how to build, label and run it

The agent's vision checks are measured on **held-out photos it has never seen**, each labelled by **two people independently**.

## 1. The 50-case set

50 held-out cases, **one photo each**, taken on 2026-09-29 with a phone under ordinary home lighting. The items are real household objects described in `reference/catalogue.json` (chargers, earbuds, wired earphones, face mask jar, toner, water bottle, vase, claw clip, pouch, comb, soft toy); orders are in `reference/demo_orders.csv`.

| Scenario tag | Cases | What it tests |
|---|---|---|
| `complete_correct` | 7 | right item, all parts |
| `wrong_product` | 6 | a different item sent against the order |
| `missing_accessory` | 5 | one replaceable part left out (lid, cap, cable) |
| `main_part_missing` | 5 | only the accessory came back |
| `new_looking` | 4 | clean, neat items |
| `lightly_used` | 7 | opened / used but fine |
| `damaged` | 5 | visible wear, scuffs, stains |
| `heavily_damaged` | 2 | taped / burnt charger cable |
| `ambiguous` | 6 | dark, blurry, far away, closed case |
| `similar_lookalike` | 3 | Samsung vs OPPO charger, wired vs wireless earbuds |

Files:
- `eval_set.csv`: case id, org, order, photo path, scenario
- `photos/E01_1.jpg ... E50_1.jpg`: the photos
- `photo_map.csv`: what is in each photo and its original phone file name
- `PHOTO_PLAN.md`: summary of the set

## 2. Label files

Two label sets: `labels_a_raw.csv` (labeller A) and `labels_b_raw.csv` (labeller B), each with:

```
case_id,identity,missing_parts,condition_grade,note
E14,yes,lid,Used - Good,bottle is there but lid missing
```

- `identity`: `yes` / `no` / `uncertain`
- `missing_parts`: part names exactly as in the catalogue, separated by `;`; empty if complete; `?` if it can't be told from the photo
- `condition_grade`: `New`, `Used - Like New`, `Used - Very Good`, `Used - Good`, `Used - Acceptable`, `Unacceptable` or `UNCERTAIN` (definitions in `reference/condition_scale.json`)

The expected **disposition** is not labelled by hand. It is derived from each label set with the same rule table the agent uses:

```bash
python eval/derive_dispositions.py eval/labels_a_raw.csv eval/labels_a.csv
python eval/derive_dispositions.py eval/labels_b_raw.csv eval/labels_b.csv
```

`labels_a.csv` / `labels_b.csv` are what the evaluation reads.

## 3. Run

```bash
python -m returns_agent eval            # uses cached model outputs where available
python -m returns_agent eval --no-cache # force fresh model calls
```

Output: `eval/results/report.md` (labeller agreement and kappa, per-check accuracy, FP/FN, UNCERTAIN rate, confusion matrices, per-scenario and per-case tables, latency and tokens) and `eval/results/results.json`. Raw model responses are cached in `eval/results/cache/`, so the report can be regenerated without an API key.

Ground truth = the value both label sets agree on; disagreements are reported as *disputed* and excluded from accuracy.

## 4. Write up

Key numbers and failure modes go in `docs/EVAL_REPORT.md`.
