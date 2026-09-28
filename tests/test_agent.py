"""Unit tests (standard library only): python -m unittest discover -s tests -v"""
from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from returns_agent import reference
from returns_agent.config import Settings
from returns_agent.rules import PREDICATES, decide
from returns_agent.service import BadRequest, NotFound, ReturnsService, content_hash
from returns_agent.store import Store
from returns_agent.vlm import ModelError, ScriptedProvider

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
ORDER_HEADPHONES = ("org_demo_alpha", "ORD-DEMO-90001")  # SKU-HEADPHONES-BT


def ev(i=0, text="seen"):
    return [{"image_index": i, "observation": text}]


def raw_response(identity="MATCH", id_conf=0.95, best="SKU-HEADPHONES-BT", parts=None, grade="Used - Good",
                 grade_conf=0.9, state="signs_of_use", damage=None):
    parts = parts if parts is not None else {"headphones": "PRESENT", "carrying case": "PRESENT",
                                             "usb cable": "PRESENT", "manual": "PRESENT"}
    return {
        "image_quality": [{"image_index": 0, "usable": True, "issue": ""}],
        "identity": {"verdict": identity, "observed_product": "over-ear headphones", "best_matching_sku": best,
                     "visible_identifiers": [], "confidence": id_conf, "evidence": ev(0, "over-ear cups visible")},
        "components": [{"part": k, "status": v, "confidence": 0.9, "evidence": ev(0, k) if v != "NOT_VISIBLE" else []}
                       for k, v in parts.items()],
        "unexpected_items": [],
        "observed_state": state,
        "damage": damage or [],
        "condition": {"grade": grade, "confidence": grade_conf, "rationale": "light wear", "evidence": ev(0, "wear")},
    }


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))

    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()

    def run_case(self, raw, order=ORDER_HEADPHONES, n_images=1):
        svc = ReturnsService(self.store, ScriptedProvider(raw))
        return svc, svc.inspect(order[0], order[1], [(JPEG, None)] * n_images, "tester")

    def checks(self, rec):
        return {c["check_key"]: c for c in rec["checks"]}


class TestScenarios(Base):
    """The ten scenarios from the problem statement."""

    def test_correct_product_complete_like_new_restock(self):
        _, r = self.run_case(raw_response(grade="Used - Like New", state="opened_unused"))
        self.assertEqual(self.checks(r)["identity"]["verdict"], "PASS")
        self.assertEqual(r["outcome"]["disposition"], "restock")

    def test_wrong_product(self):
        _, r = self.run_case(raw_response(identity="MISMATCH", best=""))
        self.assertEqual(self.checks(r)["identity"]["verdict"], "FAIL")
        self.assertEqual(r["outcome"]["rule_id"], "R03_IDENTITY_FAIL")
        self.assertEqual(r["outcome"]["disposition"], "pending_review")

    def test_missing_one_accessory_matches_brief_example(self):
        parts = {"headphones": "PRESENT", "carrying case": "PRESENT", "usb cable": "ABSENT", "manual": "PRESENT"}
        _, r = self.run_case(raw_response(parts=parts, grade="Used - Good"))
        c = self.checks(r)
        self.assertEqual(c["identity"]["verdict"], "PASS")
        self.assertEqual(c["completeness"]["verdict"], "FAIL")
        self.assertEqual(c["completeness"]["value"]["missing"], ["usb cable"])
        self.assertEqual(c["condition"]["value"]["grade"], "Used - Good")
        self.assertEqual(r["outcome"]["disposition"], "refurbish")
        self.assertIn("Disposition: REFURBISH", r["outcome"]["summary"])

    def test_unseen_part_that_could_change_outcome_goes_to_review(self):
        parts = {"headphones": "PRESENT", "carrying case": "PRESENT", "usb cable": "ABSENT", "manual": "NOT_VISIBLE"}
        _, r = self.run_case(raw_response(parts=parts, grade="Used - Good"))
        self.assertEqual(self.checks(r)["completeness"]["verdict"], "FAIL")
        self.assertEqual(r["outcome"]["rule_id"], "R09B_UNVERIFIED_PARTS_MATTER")
        self.assertEqual(r["outcome"]["disposition"], "pending_review")

    def test_unseen_part_that_cannot_change_outcome_is_decided(self):
        parts = {"headphones": "PRESENT", "carrying case": "ABSENT", "usb cable": "ABSENT", "manual": "NOT_VISIBLE"}
        _, r = self.run_case(raw_response(parts=parts, grade="Used - Good"))
        self.assertEqual(r["outcome"]["rule_id"], "R11_MISSING_MULTIPLE")

    def test_missing_multiple(self):
        parts = {"headphones": "PRESENT", "carrying case": "ABSENT", "usb cable": "ABSENT", "manual": "PRESENT"}
        _, r = self.run_case(raw_response(parts=parts))
        self.assertEqual(r["outcome"]["rule_id"], "R11_MISSING_MULTIPLE")
        self.assertEqual(r["outcome"]["disposition"], "liquidate")

    def test_new_looking(self):
        _, r = self.run_case(raw_response(grade="New", state="factory_sealed"))
        self.assertEqual(r["outcome"]["disposition"], "restock")

    def test_lightly_used(self):
        _, r = self.run_case(raw_response(grade="Used - Very Good"))
        self.assertEqual(r["outcome"]["rule_id"], "R16_COMPLETE_WEAR")

    def test_damaged_acceptable(self):
        _, r = self.run_case(raw_response(grade="Used - Acceptable", state="damaged",
                                          damage=[{"description": "dent", "severity": "moderate", "image_index": 0}]))
        self.assertEqual(r["outcome"]["disposition"], "liquidate")

    def test_heavily_damaged(self):
        _, r = self.run_case(raw_response(grade="Unacceptable", state="damaged",
                                          damage=[{"description": "cracked headband", "severity": "severe", "image_index": 0}]))
        self.assertEqual(self.checks(r)["condition"]["verdict"], "FAIL")
        self.assertEqual(r["outcome"]["disposition"], "dispose")

    def test_ambiguous_condition_goes_to_review(self):
        _, r = self.run_case(raw_response(grade="Used - Good", grade_conf=0.4))
        self.assertEqual(self.checks(r)["condition"]["verdict"], "UNCERTAIN")
        self.assertEqual(r["outcome"]["disposition"], "pending_review")

    def test_lookalike_contradiction_is_uncertain(self):
        _, r = self.run_case(raw_response(identity="MATCH", best="SKU-BOTTLE-500"))
        self.assertEqual(self.checks(r)["identity"]["verdict"], "UNCERTAIN")
        self.assertEqual(r["outcome"]["rule_id"], "R04_IDENTITY_UNCERTAIN")


class TestNoInventedEvidence(Base):
    def test_claim_without_evidence_becomes_uncertain(self):
        raw = raw_response()
        raw["identity"]["evidence"] = []
        _, r = self.run_case(raw)
        self.assertEqual(self.checks(r)["identity"]["verdict"], "UNCERTAIN")

    def test_evidence_citing_nonexistent_image_is_dropped(self):
        raw = raw_response()
        raw["identity"]["evidence"] = [{"image_index": 7, "observation": "logo"}]
        _, r = self.run_case(raw)
        c = self.checks(r)["identity"]
        self.assertEqual(c["verdict"], "UNCERTAIN")
        self.assertIn("discarded", c["detail"])

    def test_unreported_part_is_not_assumed_present(self):
        raw = raw_response()
        raw["components"] = [x for x in raw["components"] if x["part"] != "manual"]
        _, r = self.run_case(raw)
        c = self.checks(r)["completeness"]
        self.assertEqual(c["verdict"], "UNCERTAIN")
        self.assertIn("manual", c["value"]["unverified"])

    def test_sku_without_parts_list_is_not_a_vacuous_pass(self):
        from unittest import mock
        with mock.patch("returns_agent.reference.expected_parts", return_value=[]):
            _, r = self.run_case(raw_response())
        self.assertEqual(self.checks(r)["completeness"]["verdict"], "UNCERTAIN")
        self.assertEqual(r["outcome"]["disposition"], "pending_review")

    def test_invented_grade_rejected(self):
        _, r = self.run_case(raw_response(grade="Mint"))
        self.assertEqual(self.checks(r)["condition"]["verdict"], "UNCERTAIN")

    def test_unusable_images_route_to_review(self):
        raw = raw_response()
        raw["image_quality"] = [{"image_index": 0, "usable": False, "issue": "blurry"}]
        _, r = self.run_case(raw)
        self.assertEqual(r["outcome"]["rule_id"], "R02_NO_USABLE_IMAGES")


class TestFailOpen(Base):
    def test_model_error_keeps_record_and_images(self):
        svc = ReturnsService(self.store, ScriptedProvider(ModelError("timeout")))
        r = svc.inspect(*ORDER_HEADPHONES, [(JPEG, None)], "tester")
        self.assertEqual(r["status"], "review")
        self.assertEqual(r["outcome"]["rule_id"], "R01_MODEL_UNAVAILABLE")
        self.assertTrue(all(c["verdict"] == "UNCERTAIN" for c in r["checks"]))
        self.assertIsNotNone(self.store.get_record("org_demo_alpha", r["record_id"]))
        self.assertEqual(len(self.store.record_images("org_demo_alpha", r["record_id"])), 1)
        # retry after the model recovers
        svc.provider = ScriptedProvider(raw_response())
        r2 = svc.retry("org_demo_alpha", r["record_id"])
        self.assertEqual(r2["outcome"]["disposition"], "refurbish")
        events = [a["event"] for a in self.store.audit_trail("org_demo_alpha", r["record_id"])]
        self.assertEqual(events, ["captured", "model_failed", "decided", "retry_requested", "decided"])

    def test_bad_input_rejected(self):
        svc = ReturnsService(self.store, ScriptedProvider(raw_response()))
        with self.assertRaises(BadRequest):
            svc.inspect(*ORDER_HEADPHONES, [(b"not an image", None)], "t")
        with self.assertRaises(BadRequest):
            svc.inspect(*ORDER_HEADPHONES, [], "t")


class TestOverrides(Base):
    def test_override_preserves_original(self):
        svc, r = self.run_case(raw_response(grade="Used - Very Good"))
        h = r["content_hash"]
        with self.assertRaises(BadRequest):
            svc.override("org_demo_alpha", r["record_id"], "disposition", "restock", "", "sup")
        r2 = svc.override("org_demo_alpha", r["record_id"], "disposition", "restock", "box is pristine, only tape", "supervisor_1")
        self.assertEqual(r2["outcome"]["disposition"], "refurbish")          # agent decision untouched
        self.assertEqual(r2["effective"]["disposition"], "restock")
        self.assertEqual(r2["overrides"][0]["original_value"], "refurbish")
        self.assertEqual(r2["content_hash"], h)
        self.assertEqual(content_hash(r2), h)                                  # agent part unchanged
        r3 = svc.override("org_demo_alpha", r["record_id"], "check:identity", "FAIL", "serial differs from order", "supervisor_1")
        self.assertEqual(len(r3["overrides"]), 2)
        self.assertEqual(self.checks(r3)["identity"]["verdict"], "PASS")


class TestTenancy(Base):
    def test_org_cannot_read_other_org(self):
        _, r = self.run_case(raw_response())
        rid = r["record_id"]
        img = r["images"][0]["image_id"]
        self.assertIsNone(self.store.get_record("org_demo_bravo", rid))
        self.assertIsNone(self.store.get_image("org_demo_bravo", img))
        self.assertEqual(self.store.list_records("org_demo_bravo"), [])
        self.assertEqual(len(self.store.list_records("org_demo_alpha")), 1)
        svc = ReturnsService(self.store, ScriptedProvider(raw_response()))
        with self.assertRaises(NotFound):
            svc.override("org_demo_bravo", rid, "disposition", "dispose", "malicious", "x")
        with self.assertRaises(NotFound):  # order of another org
            svc.inspect("org_demo_bravo", "ORD-DEMO-90001", [(JPEG, None)], "x")

    def test_http_api_isolation(self):
        from http.server import ThreadingHTTPServer
        from returns_agent.server import make_handler
        s = Settings(provider="scripted", org_tokens={"ta": "org_demo_alpha", "tb": "org_demo_bravo"})
        svc = ReturnsService(self.store, ScriptedProvider(raw_response()))
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(svc, s))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{httpd.server_address[1]}"

        def call(method, path, token=None, body=None):
            req = urllib.request.Request(base + path, method=method,
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Content-Type": "application/json",
                                                  **({"Authorization": f"Bearer {token}"} if token else {})})
            try:
                with urllib.request.urlopen(req) as resp:
                    return resp.status, resp.read()
            except urllib.error.HTTPError as e:
                return e.code, e.read()

        try:
            import base64
            code, body = call("POST", "/api/inspections", "ta", {"order_id": "ORD-DEMO-90001", "operator_label": "op",
                              "images": [{"data_base64": base64.b64encode(JPEG).decode()}]})
            self.assertEqual(code, 201)
            rec = json.loads(body)
            self.assertEqual(call("GET", "/api/records")[0], 401)
            self.assertEqual(call("GET", f"/api/records/{rec['record_id']}", "tb")[0], 404)
            self.assertEqual(call("GET", rec["images"][0]["uri"], "tb")[0], 404)
            self.assertEqual(call("GET", rec["images"][0]["uri"], "ta")[0], 200)
            self.assertEqual(json.loads(call("GET", "/api/records", "tb")[1])["records"], [])
            self.assertEqual(json.loads(call("GET", f"/api/records/{rec['record_id']}/verify", "ta")[1])["matches"], True)
        finally:
            httpd.shutdown()
            httpd.server_close()


class TestGeminiClient(unittest.TestCase):
    """Request/response handling with a fake transport (no network)."""

    def _provider(self, script):
        import io
        from returns_agent.vlm import GeminiProvider, ImageInput
        calls = []

        class Resp(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def opener(req, timeout=None):
            body = json.loads(req.data)
            model = req.full_url.split("/models/")[1].split(":")[0]
            calls.append((model, "responseSchema" in body["generationConfig"]))
            self.assertEqual(req.headers.get("X-goog-api-key"), "k")
            step = script.pop(0)
            if isinstance(step, int):
                raise urllib.error.HTTPError(req.full_url, step, "err", {}, io.BytesIO(b"{}"))
            return Resp(json.dumps(step).encode())

        s = Settings(gemini_api_key="k", gemini_model="m1", gemini_fallback_models=["m2"])
        return GeminiProvider(s, opener=opener), calls, ImageInput(JPEG, "image/jpeg")

    def test_schema_rejected_then_fallback_model(self):
        ok = {"candidates": [{"content": {"parts": [{"text": json.dumps(raw_response())}]}}],
              "usageMetadata": {"totalTokenCount": 1234}}
        prov, calls, img = self._provider([400, 404, ok])
        order = reference.get_order(*ORDER_HEADPHONES)
        res = prov.inspect(order, [img])
        self.assertEqual(calls, [("m1", True), ("m1", False), ("m2", True)])
        self.assertEqual(res.model_version, "m2")
        self.assertEqual(res.usage["totalTokenCount"], 1234)

    def test_all_models_fail_raises_model_error(self):
        prov, calls, img = self._provider([429, 429])
        with self.assertRaises(ModelError):
            prov.inspect(reference.get_order(*ORDER_HEADPHONES), [img])

    def test_non_json_output_is_model_error(self):
        prov, _, img = self._provider([{"candidates": [{"content": {"parts": [{"text": "I think it's fine"}]}}]}])
        with self.assertRaises(ModelError):
            prov.inspect(reference.get_order(*ORDER_HEADPHONES), [img])


class TestRulesTable(unittest.TestCase):
    def test_every_rule_has_predicate(self):
        ids = [r["id"] for r in reference.disposition_rules()["rules"]]
        self.assertEqual(set(ids), set(PREDICATES))
        self.assertEqual(ids[-1], "R99_FALLBACK")

    def test_deterministic(self):
        facts = {"usable_images": 2, "identity": "PASS", "completeness": "PASS", "missing": [], "condition": "PASS",
                 "grade": "New", "grade_rank": 5, "observed_state": "factory_sealed", "max_damage": None,
                 "hygiene_sensitive": False}
        self.assertEqual(len({json.dumps(decide(copy.deepcopy(facts))) for _ in range(20)}), 1)

    def test_hygiene_used_disposed(self):
        facts = {"usable_images": 1, "identity": "PASS", "completeness": "PASS", "missing": [], "condition": "PASS",
                 "grade": "Used - Good", "grade_rank": 2, "observed_state": "signs_of_use", "max_damage": None,
                 "hygiene_sensitive": True}
        self.assertEqual(decide(facts)["rule_id"], "R08_HYGIENE_USED")


if __name__ == "__main__":
    unittest.main()
