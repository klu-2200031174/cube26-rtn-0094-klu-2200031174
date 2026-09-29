# Who labelled the evaluation set

The evaluation labels were **created entirely by two team members**, each working independently and reviewing every photo in the set.

| File               | Labeller      | How it was produced                                                                     |
| ------------------ | ------------- | --------------------------------------------------------------------------------------- |
| `labels_a_raw.csv` | Team member A | Labelled each photo from scratch by inspecting the images and order details.            |
| `labels_b_raw.csv` | Team member B | Independently labelled each photo from scratch without referencing any other label set. |

Both labellers worked **independently**, without access to each other’s annotations, ensuring that the two sets reflect separate human judgments.

**Why this matters for the numbers:** agreement between A and B reflects natural human consistency on the task. Any disagreements represent genuine differences in interpretation (e.g., unclear visibility, borderline condition grading, or ambiguity in missing parts).

Each label records only what is visible:

* **identity** (yes / no / uncertain)
* **missing_parts** (specific part or `?`)
* **condition_grade** (Amazon scale or `UNCERTAIN`)

The `disposition` column in `labels_a.csv` / `labels_b.csv` is **derived**, not manually labelled. The script `eval/derive_dispositions.py` applies the same rule table used by the agent to each label set.

**Ground truth** is defined as the value both label sets agree on.
Cases where they disagree are marked as *disputed* and excluded from accuracy calculations.
