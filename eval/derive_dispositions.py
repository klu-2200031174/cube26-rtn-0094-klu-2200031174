"""Fill the `disposition` column of labeller files from their identity / missing parts / grade.

Labellers answer only what they can see (identity, missing parts, condition grade).
The expected disposition is then derived with the SAME published rule table the agent
uses (reference/disposition_rules.json), so disposition accuracy measures whether the
agent reaches the rule-correct outcome, not whether it matches a labeller's gut feeling.

Assumptions (documented in docs/EVAL_REPORT.md):
- a labeller grade of "Unacceptable" is treated as severe damage;
- observed state is inferred from the grade (New -> factory_sealed, otherwise opened/used).

Usage: python eval/derive_dispositions.py eval/labels_a_raw.csv eval/labels_a.csv
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from returns_agent import reference  # noqa: E402
from returns_agent.rules import decide  # noqa: E402

ID = {"yes": "PASS", "no": "FAIL", "uncertain": "UNCERTAIN"}


def derive(row: dict, order_id: str) -> str:
    order = reference.get_order("org_demo_alpha", order_id)
    item = reference.catalogue()[order.ordered_sku]
    parts = item["parts"]
    identity = ID.get(row["identity"].strip().lower(), "UNCERTAIN")
    mp = row["missing_parts"].strip()
    if mp == "?":
        completeness, missing = "UNCERTAIN", []
    elif not mp:
        completeness, missing = "PASS", []
    else:
        missing = [reference.match_part(n, parts) or {"name": n, "replaceable": False} for n in mp.split(";") if n.strip()]
        completeness = "FAIL"
    grade = row["condition_grade"].strip()
    rank = reference.grade_rank(grade)
    condition = "UNCERTAIN" if rank is None else ("FAIL" if rank == 0 else "PASS")
    facts = {
        "usable_images": 1, "identity": identity, "completeness": completeness, "missing": missing,
        "unverified": [], "condition": condition, "grade": grade if rank is not None else None, "grade_rank": rank,
        "observed_state": "factory_sealed" if rank == 5 else "signs_of_use",
        "max_damage": "severe" if rank == 0 else None, "hygiene_sensitive": bool(item.get("hygiene_sensitive")),
    }
    return decide(facts)["disposition"]


def main(src: str, dst: str) -> None:
    orders = {r["case_id"]: r["order_id"] for r in csv.DictReader(open(Path(__file__).parent / "eval_set.csv", encoding="utf-8"))}
    rows = list(csv.DictReader(open(src, encoding="utf-8")))
    with open(dst, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["case_id", "identity", "missing_parts", "condition_grade", "disposition", "note"])
        for r in rows:
            order = reference.get_order("org_demo_alpha", orders[r["case_id"]])
            parts = reference.catalogue()[order.ordered_sku]["parts"]
            mp = r["missing_parts"].strip()
            if mp not in ("", "?"):  # normalise part names to the catalogue's
                mp = ";".join((reference.match_part(n, parts) or {"name": n.strip()})["name"] for n in mp.split(";") if n.strip())
            r["missing_parts"] = mp
            w.writerow([r["case_id"], r["identity"].strip().lower(), mp, r["condition_grade"].strip(),
                        derive(r, orders[r["case_id"]]), r.get("note", "")])
    print(f"wrote {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
