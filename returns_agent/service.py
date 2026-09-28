"""Orchestration: capture -> persist -> inspect (1 model call) -> checks -> rules -> record.

Fail open: images and a 'pending' record are persisted BEFORE the model is
called. If the model fails, the record is kept with UNCERTAIN checks and
routed to pending_review; it can be retried later from the stored images.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any

from . import AGENT_NAME, AGENT_VERSION, SCHEMA_VERSION, reference
from .checks import UNCERTAIN, build_checks
from .rules import decide
from .store import Store, now_iso
from .vlm import ImageInput, ModelError, Provider

MAX_IMAGES = 8
MAX_IMAGE_BYTES = 15 * 1024 * 1024
DISPOSITIONS = ["restock", "refurbish", "liquidate", "dispose", "pending_review"]
VERDICTS = ["PASS", "FAIL", "UNCERTAIN"]


class NotFound(Exception):
    pass


class BadRequest(Exception):
    pass


def sniff_mime(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def content_hash(record: dict[str, Any]) -> str:
    """SHA-256 over the agent's decision (record minus mutable fields). This lets a
    reader detect that the agent-authored part changed; on its own it is NOT
    tamper-proof (whoever can edit the DB can recompute it)."""
    body = {k: v for k, v in record.items() if k not in ("content_hash", "overrides", "status", "effective")}
    return "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def summary_line(checks: list[dict[str, Any]], outcome: dict[str, Any]) -> str:
    by = {c["check_key"]: c for c in checks}
    parts = [f"Identity: {by['identity']['verdict']}"]
    comp = by["completeness"]
    miss = comp.get("value", {}).get("missing") or []
    parts.append(f"Completeness: {comp['verdict']}" + (f" (missing: {', '.join(miss)})" if miss else ""))
    grade = by["condition"].get("value", {}).get("grade")
    parts.append(f"Condition: {grade or 'UNCERTAIN'}")
    parts.append(f"Disposition: {outcome['disposition'].upper()}")
    return " | ".join(parts)


class ReturnsService:
    def __init__(self, store: Store, provider: Provider):
        self.store = store
        self.provider = provider

    # ------------------------------------------------------------------
    def inspect(self, org_id: str, order_id: str, images: list[tuple[bytes, str | None]],
                operator_label: str, operator_note: str = "") -> dict[str, Any]:
        t_start = time.monotonic()
        order = reference.get_order(org_id, order_id)
        if order is None:
            raise NotFound(f"order {order_id} not found")
        if not images:
            raise BadRequest("at least one photo is required")
        if len(images) > MAX_IMAGES:
            raise BadRequest(f"at most {MAX_IMAGES} photos per inspection")
        operator_label = (operator_label or "").strip()[:80] or "unknown_operator"

        checked: list[tuple[bytes, str]] = []
        for data, _declared in images:
            if len(data) > MAX_IMAGE_BYTES:
                raise BadRequest("photo larger than 15 MB")
            mime = sniff_mime(data)
            if mime is None:
                raise BadRequest("unsupported image format (use JPEG, PNG or WebP)")
            checked.append((data, mime))

        unit_num = order.unit_id.split("-")[-1]
        record_id = f"RTN-{unit_num}-{secrets.token_hex(3).upper()}"
        item = reference.catalogue().get(order.ordered_sku, {})
        image_meta = []
        for idx, (data, mime) in enumerate(checked):
            sha = hashlib.sha256(data).hexdigest()
            image_id = self.store.save_image(org_id, record_id, data, mime, sha)
            image_meta.append({"image_id": image_id, "index": idx, "sha256": sha, "mime": mime,
                               "bytes": len(data), "uri": f"/api/images/{image_id}"})

        record: dict[str, Any] = {
            "record_id": record_id,
            "schema_version": SCHEMA_VERSION,
            "organization_id": org_id,
            "client_id": order.client_id,
            "agent": {"name": AGENT_NAME, "version": AGENT_VERSION, "provider": self.provider.name,
                      "model_version": None, "rules_version": reference.disposition_rules()["version"],
                      "condition_scale": reference.condition_scale()["scale_id"]},
            "subject": {"stage": "customer_return", "unit_id": order.unit_id, "order_id": order.order_id,
                        "sku": order.ordered_sku, "asin": order.ordered_asin, "title": item.get("title"),
                        "expected_parts": [p["name"] for p in item.get("parts", [])]},
            "captured_at": now_iso(),
            "operator_label": operator_label,
            "operator_note": operator_note[:500],
            "images": image_meta,
            "checks": [],
            "outcome": None,
            "overrides": [],
            "status": "pending",
            "errors": [],
            "attempts": 0,
        }
        self.store.put_record(record)
        self.store.audit(org_id, record_id, "captured", {"images": [m["sha256"] for m in image_meta],
                                                         "operator_label": operator_label})
        return self._run(record, [ImageInput(d, m) for d, m in checked], order, t_start)

    # ------------------------------------------------------------------
    def retry(self, org_id: str, record_id: str) -> dict[str, Any]:
        record = self.store.get_record(org_id, record_id)
        if record is None:
            raise NotFound("record not found")
        if record["overrides"]:
            raise BadRequest("record already has human overrides; create a new inspection instead")
        order = reference.get_order(org_id, record["subject"]["order_id"])
        if order is None:
            raise NotFound("order not found")
        imgs = [ImageInput(d, m) for d, m in self.store.record_images(org_id, record_id)]
        self.store.audit(org_id, record_id, "retry_requested", {"previous_outcome": record.get("outcome")})
        return self._run(record, imgs, order, time.monotonic())

    # ------------------------------------------------------------------
    def _run(self, record: dict[str, Any], imgs: list[ImageInput], order, t_start: float) -> dict[str, Any]:
        org_id, record_id = record["organization_id"], record["record_id"]
        record["attempts"] = record.get("attempts", 0) + 1
        try:
            res = self.provider.inspect(order, imgs, record.get("operator_note", ""))
            checks, facts = build_checks(res.raw, order, len(imgs), res.model_version, res.latency_ms)
            record["agent"]["model_version"] = res.model_version
            record["model_observations"] = res.raw
            record["metrics"] = {"model_latency_ms": res.latency_ms, "usage": res.usage}
            record["errors"] = []
        except ModelError as e:
            facts = {"model_failed": True, "usable_images": len(imgs), "identity": UNCERTAIN,
                     "completeness": UNCERTAIN, "missing": [], "condition": UNCERTAIN, "grade": None,
                     "grade_rank": None, "observed_state": "uncertain", "max_damage": None, "hygiene_sensitive": False}
            detail = "Not inspected: the vision model was unavailable (see errors). Photos are saved; use Retry."
            checks = [{"check_key": k, "verdict": UNCERTAIN, "confidence": 0.0, "detail": detail,
                       "evidence": [], "model_version": None, "latency_ms": None}
                      for k in ("image_quality", "identity", "completeness", "condition")]
            record["errors"] = [{"at": now_iso(), "error": str(e)[:1000]}]
            record["metrics"] = {"model_latency_ms": None}
            self.store.audit(org_id, record_id, "model_failed", {"error": str(e)[:1000]})

        decision = decide(facts)
        decision["summary"] = summary_line(checks, decision)
        record["checks"] = checks
        record["outcome"] = decision
        record["decided_at"] = now_iso()
        record["metrics"]["total_latency_ms"] = int((time.monotonic() - t_start) * 1000)
        record["status"] = "review" if decision["needs_human_review"] else "decided"
        record["effective"] = {"disposition": decision["disposition"], "source": "agent"}
        record["content_hash"] = content_hash(record)
        self.store.put_record(record)
        self.store.audit(org_id, record_id, "decided", {"disposition": decision["disposition"],
                                                        "rule_id": decision["rule_id"],
                                                        "content_hash": record["content_hash"]})
        return record

    # ------------------------------------------------------------------
    def override(self, org_id: str, record_id: str, field: str, revised: str, reason: str,
                 operator_label: str) -> dict[str, Any]:
        record = self.store.get_record(org_id, record_id)
        if record is None:
            raise NotFound("record not found")
        if record["status"] == "pending" or not record.get("outcome"):
            raise BadRequest("record has no agent decision yet")
        reason = (reason or "").strip()
        operator_label = (operator_label or "").strip()
        if len(reason) < 5:
            raise BadRequest("an override needs a reason (at least 5 characters)")
        if not operator_label:
            raise BadRequest("operator_label is required")

        if field == "disposition":
            if revised not in DISPOSITIONS:
                raise BadRequest(f"disposition must be one of {DISPOSITIONS}")
            original = record["effective"]["disposition"]
        elif field == "condition_grade":
            if revised not in reference.grade_names():
                raise BadRequest(f"grade must be one of {reference.grade_names()}")
            original = next(c for c in record["checks"] if c["check_key"] == "condition").get("value", {}).get("grade")
        elif field.startswith("check:"):
            key = field.split(":", 1)[1]
            chk = next((c for c in record["checks"] if c["check_key"] == key), None)
            if chk is None:
                raise BadRequest(f"unknown check '{key}'")
            if revised not in VERDICTS:
                raise BadRequest(f"verdict must be one of {VERDICTS}")
            original = chk["verdict"]
        else:
            raise BadRequest("field must be 'disposition', 'condition_grade' or 'check:<check_key>'")

        ov = self.store.add_override(org_id, record_id, field, original, revised, reason, operator_label)
        # The agent's checks/outcome are left untouched; overrides are layered on top.
        record["overrides"].append(ov)
        if field == "disposition":
            record["effective"] = {"disposition": revised, "source": "override", "override_id": ov["override_id"]}
        record["status"] = "overridden"
        self.store.put_record(record)
        self.store.audit(org_id, record_id, "override", ov)
        return record
