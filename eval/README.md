# Evaluation set: how to build, label and run it

The agent's vision checks are measured on **held-out photos it has never seen**, each labelled by **two people independently**.

## 1. Plan the 50 cases (5 per scenario)

Use real objects you have (headphones, a water bottle, a USB cable, mugs, a desk lamp...). First make each catalogue entry you use (`reference/catalogue.json`) describe your real object, and add orders for them in `reference/demo_orders.csv`. Do this **before** you look at any eval result, and do not change it afterwards to fit the results.

| Scenario tag | How to stage it (5 cases each, vary objects, light and background) |
|---|---|
| `correct_product` | Ordered item, complete, lightly handled |
| `wrong_product` | Photograph a *different* object against the order (e.g. order = headphones, box contains a mug) |
| `missing_accessory` | Remove one accessory; lay out all contents so its absence is visible |
| `missing_multiple` | Remove two or more accessories |
| `new_looking` | Sealed or pristine item in its packaging |
| `lightly_used` | Clean item, slight handling marks |
| `damaged` | Visible scratches / dents / scuffs, still usable |
| `heavily_damaged` | Cracked, broken, stained |
| `ambiguous_condition` | Dim light, blur, partial view, or wear that is hard to judge |
| `similar_lookalike` | Photograph the look-alike SKU (e.g. USB-A cable against a USB-C order, green towel against blue) |

Per case, take 2–4 photos: **one overview with all contents laid out**, plus close-ups of labels and damage. Save them as `eval/photos/<case_id>_<n>.jpg`.

**Keep the set held out.** Don't tune prompts or thresholds on these cases. If you need tuning data, shoot a separate small dev set.

## 2. List the cases in `eval/eval_set.csv`

```
case_id,org_id,order_id,image_paths,scenario
E01,org_demo_alpha,ORD-DEMO-90001,photos/E01_1.jpg;photos/E01_2.jpg,missing_accessory
```

## 3. Label independently (two people)

Each labeller fills in their own file **without seeing the other's labels or the agent's output**. Labeller A uses `labels_a.csv` and labeller B uses `labels_b.csv`:

```
case_id,identity,missing_parts,condition_grade,disposition
E01,yes,usb cable,Used - Good,refurbish
```

- `identity`: `yes` / `no` / `uncertain`
- `missing_parts`: part names exactly as in the catalogue, separated by `;`. Leave empty if complete, or write `?` if it can't be told from the photos.
- `condition_grade`: one of `New`, `Used - Like New`, `Used - Very Good`, `Used - Good`, `Used - Acceptable`, `Unacceptable`, `UNCERTAIN` (definitions in `reference/condition_scale.json`)
- `disposition`: `restock` / `refurbish` / `liquidate` / `dispose` / `pending_review`, applying the rule table in ARCHITECTURE.md §5

## 4. Run

```bash
python -m returns_agent eval            # uses cached model outputs where available
python -m returns_agent eval --no-cache # force fresh model calls
```

Output: `eval/results/report.md` (human agreement and kappa, per-check accuracy, FP/FN, UNCERTAIN rate, confusion matrices, per-scenario and per-case tables, latency and tokens) and `eval/results/results.json`. Raw model responses are cached in `eval/results/cache/`, so anyone can regenerate the report without an API key.

## 5. Write up

Copy the key numbers into `docs/EVAL_REPORT.md`. Explain the important failure modes by looking at the FP/FN case ids and their records, and report every result, including the bad ones.
