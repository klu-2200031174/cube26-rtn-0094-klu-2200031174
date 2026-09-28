"""HTTP API + operator UI (standard library only).

Auth: every /api call needs `Authorization: Bearer <org token>`; the token
decides the org. There is no way to pass an org id directly, so a caller can
only ever reach its own org's orders, records and images.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from . import reference
from .config import WEB_DIR, Settings
from .service import BadRequest, NotFound, ReturnsService, content_hash
from .store import Store

MAX_BODY = 130 * 1024 * 1024


def make_handler(service: ReturnsService, settings: Settings):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ReturnsManager/0.1"

        def log_message(self, fmt, *args):  # quieter logs, never log headers (tokens)
            print("%s %s" % (self.command, self.path.split("?")[0]))

        # ---------------- helpers ----------------
        def _json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _org(self) -> str | None:
            auth = self.headers.get("Authorization", "")
            if not auth.startswith("Bearer "):
                return None
            return settings.org_tokens.get(auth[7:].strip())

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise BadRequest("request too large")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise BadRequest("body must be JSON")
            if not isinstance(data, dict):
                raise BadRequest("body must be a JSON object")
            return data

        def _dispatch(self, method: str) -> None:
            path = urlparse(self.path).path
            try:
                if method == "GET" and path in ("/", "/index.html"):
                    return self._static()
                if not path.startswith("/api/"):
                    return self._json(404, {"error": "not found"})
                org = self._org()
                if org is None:
                    return self._json(401, {"error": "missing or invalid org token"})
                return self._api(method, path, org)
            except NotFound as e:
                self._json(404, {"error": str(e)})
            except BadRequest as e:
                self._json(400, {"error": str(e)})
            except Exception as e:  # never lose the request silently
                print("internal error:", repr(e))
                self._json(500, {"error": "internal error", "detail": str(e)[:300]})

        def _static(self) -> None:
            body = (WEB_DIR / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        # ---------------- API ----------------
        def _api(self, method: str, path: str, org: str) -> None:
            if method == "GET" and path == "/api/session":
                return self._json(200, {"organization_id": org, "provider": service.provider.name,
                                        "model": settings.gemini_model if service.provider.name == "gemini" else service.provider.name,
                                        "condition_scale": reference.condition_scale(),
                                        "rules": reference.disposition_rules()})
            if method == "GET" and path == "/api/orders":
                cat = reference.catalogue()
                out = []
                for o in reference.orders_for_org(org):
                    d = o.to_dict()
                    item = cat.get(o.ordered_sku, {})
                    d["title"] = item.get("title")
                    d["expected_parts"] = [p["name"] for p in item.get("parts", [])]
                    out.append(d)
                return self._json(200, {"orders": out})
            if method == "GET" and path == "/api/records":
                return self._json(200, {"records": service.store.list_records(org)})
            if method == "POST" and path == "/api/inspections":
                body = self._body()
                images = []
                for img in body.get("images") or []:
                    b64 = str(img.get("data_base64", ""))
                    if "," in b64 and b64.startswith("data:"):
                        b64 = b64.split(",", 1)[1]
                    try:
                        images.append((base64.b64decode(b64, validate=True), img.get("mime")))
                    except (binascii.Error, ValueError):
                        raise BadRequest("image data is not valid base64")
                rec = service.inspect(org, str(body.get("order_id", "")), images,
                                      str(body.get("operator_label", "")), str(body.get("operator_note", "")))
                return self._json(201, rec)
            m = re.fullmatch(r"/api/records/([A-Za-z0-9\-]+)(/override|/retry|/audit|/verify)?", path)
            if m:
                rid, action = m.group(1), m.group(2)
                if method == "GET" and not action:
                    rec = service.store.get_record(org, rid)
                    if rec is None:
                        raise NotFound("record not found")
                    return self._json(200, rec)
                if method == "GET" and action == "/audit":
                    if service.store.get_record(org, rid) is None:
                        raise NotFound("record not found")
                    return self._json(200, {"audit": service.store.audit_trail(org, rid)})
                if method == "GET" and action == "/verify":
                    rec = service.store.get_record(org, rid)
                    if rec is None:
                        raise NotFound("record not found")
                    stored = rec.get("content_hash")
                    return self._json(200, {"stored": stored, "recomputed": content_hash(rec),
                                            "matches": stored == content_hash(rec)})
                if method == "POST" and action == "/override":
                    b = self._body()
                    rec = service.override(org, rid, str(b.get("field", "")), str(b.get("revised", "")),
                                           str(b.get("reason", "")), str(b.get("operator_label", "")))
                    return self._json(200, rec)
                if method == "POST" and action == "/retry":
                    return self._json(200, service.retry(org, rid))
            m = re.fullmatch(r"/api/images/([0-9a-f]{32})", path)
            if m and method == "GET":
                got = service.store.get_image(org, m.group(1))
                if got is None:
                    raise NotFound("image not found")
                data, mime = got
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "private, no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            self._json(404, {"error": "not found"})

        def do_GET(self):
            self._dispatch("GET")

        def do_POST(self):
            self._dispatch("POST")

    return Handler


def serve(settings: Settings, service: ReturnsService) -> None:
    httpd = ThreadingHTTPServer((settings.host, settings.port), make_handler(service, settings))
    print(f"Returns Manager running at http://{settings.host}:{settings.port}  (provider: {service.provider.name})")
    orgs = sorted(set(settings.org_tokens.values()))
    print(f"Orgs configured: {', '.join(orgs)}. Sign in on the page with an org token from your .env.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
