"""Evaluation harness.

Inputs (see eval/README.md):
  eval/eval_set.csv   case_id, org_id, order_id, image_paths (';' separated, relative to eval/), scenario
  eval/labels_a.csv   case_id, identity, missing_parts, condition_grade, disposition   (labeller A)
  eval/labels_b.csv   same columns                                                     (labeller B)

Method:
  1. Human agreement per field (percent agreement + Cohen's kappa).
  2. Ground truth = the value both labellers agree on. Disagreements are
     reported as "disputed" and excluded from agent accuracy (they are the
     genuinely ambiguous cases), but the agent's UNCERTAIN rate on them is shown.
  3. The agent runs once per case (raw model output cached by image hash so a
     re-run of the report does not re-call the model).
  4. For identity and completeness, "positive" = a problem (FAIL).
     FP = agent FAIL but truth PASS (false alarm), FN = agent PASS but truth FAIL
     (missed problem - the costly error). UNCERTAIN is counted separately as review.
"""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from . import reference
from .config import ROOT
from .service import ReturnsService
from .store import Store
from .vlm import Provider, ScriptedProvider

EVAL_DIR = ROOT / "eval"
FIELDS = ["identity", "completeness", "condition_grade", "disposition"]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return [{k.strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(fh)]


def _label_value(row: dict[str, str], field: str) -> str:
    if field == "completeness":
        mp = row.get("missing_parts", "")
        if mp == "?":
            return "UNCERTAIN"
        return "PASS" if not mp else "FAIL"
    v = row.get(field, "")
    if field == "identity":
        return {"yes": "PASS", "no": "FAIL", "uncertain": "UNCERTAIN"}.get(v.lower(), v.upper())
    if field == "disposition":
        return v.lower()
    return v


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    if pe == 1:
        return 1.0 if po == 1 else 0.0
    return round((po - pe) / (1 - pe), 3)


def _agent_value(record: dict[str, Any], field: str) -> str:
    by = {c["check_key"]: c for c in record["checks"]}
    if field == "identity":
        return by["identity"]["verdict"]
    if field == "completeness":
        return by["completeness"]["verdict"]
    if field == "condition_grade":
        return (by["condition"].get("value") or {}).get("grade") or "UNCERTAIN"
    return record["outcome"]["disposition"]


class CachingProvider(Provider):
    """Wraps a provider; stores raw model output per (case images + prompt version)."""

    def __init__(self, inner: Provider, cache_dir: Path, use_cache: bool = True):
        self.inner, self.cache_dir, self.use_cache = inner, cache_dir, use_cache
        self.name = inner.name
        cache_dir.mkdir(parents=True, exist_ok=True)

    def inspect(self, order, images, operator_note: str = ""):
        h = hashlib.sha256()
        h.update(order.ordered_sku.encode())
        h.update(json.dumps(reference.disposition_rules()["thresholds"]).encode())
        for img in images:
            h.update(hashlib.sha256(img.data).digest())
        path = self.cache_dir / f"{h.hexdigest()[:24]}.json"
        if self.use_cache and path.exists():
            c = json.loads(path.read_text(encoding="utf-8"))
            res = ScriptedProvider(c["raw"], c["model_version"]).inspect(order, images)
            res.latency_ms, res.usage = c["latency_ms"], c.get("usage", {})
            return res
        res = self.inner.inspect(order, images, operator_note)
        path.write_text(json.dumps({"raw": res.raw, "model_version": res.model_version,
                                    "latency_ms": res.latency_ms, "usage": res.usage}, indent=1), encoding="utf-8")
        return res


def run_eval(provider: Provider, eval_dir: Path = EVAL_DIR, use_cache: bool = True) -> dict[str, Any]:
    cases = _read_csv(eval_dir / "eval_set.csv")
    la = {r["case_id"]: r for r in _read_csv(eval_dir / "labels_a.csv")}
    lb = {r["case_id"]: r for r in _read_csv(eval_dir / "labels_b.csv")}
    results_dir = eval_dir / "results"
    cprov = CachingProvider(provider, results_dir / "cache", use_cache)

    # ignore_cleanup_errors: on Windows the SQLite file can still be locked at exit
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        service = ReturnsService(Store(Path(tmp)), cprov)
        rows = []
        for case in cases:
            cid = case["case_id"]
            paths = [eval_dir / p.strip() for p in case["image_paths"].split(";") if p.strip()]
            missing_files = [str(p) for p in paths if not p.exists()]
            if missing_files:
                rows.append({"case_id": cid, "error": f"missing image files: {missing_files}"})
                continue
            rec = service.inspect(case["org_id"], case["order_id"], [(p.read_bytes(), None) for p in paths],
                                  "eval_runner")
            row = {"case_id": cid, "scenario": case.get("scenario", ""), "record_id": rec["record_id"],
                   "model_latency_ms": rec["metrics"].get("model_latency_ms"),
                   "usage": rec["metrics"].get("usage", {}), "rule_id": rec["outcome"]["rule_id"],
                   "model_failed": bool(rec.get("errors"))}
            for f in FIELDS:
                a = _label_value(la.get(cid, {}), f) if cid in la else ""
                b = _label_value(lb.get(cid, {}), f) if cid in lb else ""
                row[f] = {"agent": _agent_value(rec, f), "label_a": a, "label_b": b,
                          "truth": a if a and a == b else None}
            agent_missing = sorted(next(c for c in rec["checks"] if c["check_key"] == "completeness")
                                   .get("value", {}).get("missing", []))
            ma = sorted(x.strip().lower() for x in la.get(cid, {}).get("missing_parts", "").split(";") if x.strip() and x.strip() != "?")
            mb = sorted(x.strip().lower() for x in lb.get(cid, {}).get("missing_parts", "").split(";") if x.strip() and x.strip() != "?")
            row["missing_parts"] = {"agent": agent_missing, "truth": ma if ma == mb else None}
            rows.append(row)
        service.store.db.close()  # release the temp database before the folder is removed (Windows)

    report = summarise(rows)
    results_dir.mkdir(parents=True, exist_ok=True)
    (results_dir / "results.json").write_text(json.dumps({"summary": report, "cases": rows}, indent=2), encoding="utf-8")
    (results_dir / "report.md").write_text(render_markdown(report, rows), encoding="utf-8")
    return report


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if "error" not in r]
    out: dict[str, Any] = {"cases_total": len(rows), "cases_run": len(ok),
                           "cases_with_errors": [r["case_id"] for r in rows if "error" in r]}
    for f in FIELDS:
        a = [r[f]["label_a"] for r in ok if r[f]["label_a"] and r[f]["label_b"]]
        b = [r[f]["label_b"] for r in ok if r[f]["label_a"] and r[f]["label_b"]]
        agreed = [r for r in ok if r[f]["truth"] is not None]
        disputed = [r for r in ok if r[f]["truth"] is None and r[f]["label_a"]]
        decided = [r for r in agreed if r[f]["agent"] != "UNCERTAIN" and r[f]["agent"] != "pending_review"]
        correct = [r for r in agreed if r[f]["agent"] == r[f]["truth"]]
        m: dict[str, Any] = {
            "human_percent_agreement": round(sum(x == y for x, y in zip(a, b)) / len(a), 3) if a else None,
            "human_cohen_kappa": cohen_kappa(a, b),
            "n_ground_truth": len(agreed),
            "n_disputed": len(disputed),
            "accuracy_all": round(len(correct) / len(agreed), 3) if agreed else None,
            "accuracy_when_agent_decided": round(sum(r[f]["agent"] == r[f]["truth"] for r in decided) / len(decided), 3) if decided else None,
            "agent_uncertain_rate": round(sum(r[f]["agent"] in ("UNCERTAIN", "pending_review") for r in ok) / len(ok), 3) if ok else None,
            "agent_uncertain_rate_on_disputed": round(sum(r[f]["agent"] in ("UNCERTAIN", "pending_review") for r in disputed) / len(disputed), 3) if disputed else None,
            "confusion": dict(Counter(f"truth={r[f]['truth']} -> agent={r[f]['agent']}" for r in agreed)),
        }
        if f in ("identity", "completeness"):
            m["false_positives"] = [r["case_id"] for r in agreed if r[f]["agent"] == "FAIL" and r[f]["truth"] == "PASS"]
            m["false_negatives"] = [r["case_id"] for r in agreed if r[f]["agent"] == "PASS" and r[f]["truth"] == "FAIL"]
            m["FP"], m["FN"] = len(m["false_positives"]), len(m["false_negatives"])
        if f == "condition_grade":
            within1 = 0
            for r in agreed:
                ra, rt = reference.grade_rank(r[f]["agent"]), reference.grade_rank(r[f]["truth"])
                if ra is not None and rt is not None and abs(ra - rt) <= 1:
                    within1 += 1
            m["within_one_grade"] = round(within1 / len(agreed), 3) if agreed else None
        out[f] = m
    mp = [r for r in ok if r["missing_parts"]["truth"] is not None]
    out["missing_parts_exact_match"] = round(sum(r["missing_parts"]["agent"] == r["missing_parts"]["truth"] for r in mp) / len(mp), 3) if mp else None
    out["review_rate"] = round(sum(r["disposition"]["agent"] == "pending_review" for r in ok) / len(ok), 3) if ok else None
    out["model_failures"] = sum(r["model_failed"] for r in ok)
    lats = [r["model_latency_ms"] for r in ok if r["model_latency_ms"]]
    out["latency_ms"] = {"p50": statistics.median(lats), "p95": sorted(lats)[max(0, int(len(lats) * 0.95) - 1)],
                         "max": max(lats)} if lats else None
    toks = [r["usage"].get("totalTokenCount", 0) for r in ok if r.get("usage")]
    out["tokens"] = {"total": sum(toks), "mean_per_case": round(sum(toks) / len(toks)) if toks else 0} if toks else None
    out["by_scenario"] = {}
    for r in ok:
        s = out["by_scenario"].setdefault(r["scenario"] or "unspecified", {"n": 0, "disposition_correct": 0, "review": 0})
        s["n"] += 1
        s["disposition_correct"] += int(r["disposition"]["truth"] is not None and r["disposition"]["agent"] == r["disposition"]["truth"])
        s["review"] += int(r["disposition"]["agent"] == "pending_review")
    return out


def render_markdown(s: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    L = ["# Evaluation report", "", f"Cases run: {s['cases_run']} / {s['cases_total']}  ",
         f"Model failures (routed to review): {s['model_failures']}  ",
         f"Overall review rate (disposition = pending_review): {s['review_rate']}  ",
         f"Missing-parts exact match: {s['missing_parts_exact_match']}  ",
         f"Latency (model, ms): {s['latency_ms']}  ", f"Tokens: {s['tokens']}", "",
         "Ground truth = value both labellers agree on; disputed cases are excluded from accuracy.",
         "Positive class for identity/completeness = FAIL (a problem). FN = missed problem.", ""]
    L += ["| Check | Human agreement | Kappa | GT n | Disputed | Accuracy (all) | Accuracy (decided) | Uncertain rate | FP | FN |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for f in FIELDS:
        m = s[f]
        L.append(f"| {f} | {m['human_percent_agreement']} | {m['human_cohen_kappa']} | {m['n_ground_truth']} | "
                 f"{m['n_disputed']} | {m['accuracy_all']} | {m['accuracy_when_agent_decided']} | "
                 f"{m['agent_uncertain_rate']} | {m.get('FP', '-')} | {m.get('FN', '-')} |")
    L += ["", f"Condition within one grade: {s['condition_grade'].get('within_one_grade')}", "", "## Confusion"]
    for f in FIELDS:
        L.append(f"\n**{f}**\n")
        for k, v in sorted(s[f]["confusion"].items()):
            L.append(f"- {k}: {v}")
    L += ["", "## By scenario", "", "| Scenario | n | Disposition correct | Sent to review |", "|---|---|---|---|"]
    for k, v in sorted(s["by_scenario"].items()):
        L.append(f"| {k} | {v['n']} | {v['disposition_correct']} | {v['review']} |")
    L += ["", "## Per case", "", "| Case | Scenario | Identity (agent/truth) | Completeness | Grade | Disposition | Rule |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            L.append(f"| {r['case_id']} | error: {r['error']} | | | | | |")
            continue
        cell = lambda f: f"{r[f]['agent']} / {r[f]['truth'] if r[f]['truth'] is not None else 'disputed'}"
        L.append(f"| {r['case_id']} | {r['scenario']} | {cell('identity')} | {cell('completeness')} | "
                 f"{cell('condition_grade')} | {cell('disposition')} | {r['rule_id']} |")
    return "\n".join(L) + "\n"
