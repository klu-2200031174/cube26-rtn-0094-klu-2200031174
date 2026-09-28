"""Persistence with tenant isolation.

Every table carries org_id and every query is filtered by it. Images are
stored under var/images/<org_id>/ with random 128-bit ids and are only served
through an endpoint that checks the caller's org; a record or image of another
org is reported as "not found" (no existence leak).

Audit events and overrides are append-only: nothing in this module updates or
deletes them.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  record_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  unit_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  status TEXT NOT NULL,
  disposition TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  record_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_records_org ON records(org_id, created_at);
CREATE TABLE IF NOT EXISTS images (
  image_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  record_id TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  mime TEXT NOT NULL,
  path TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_images_org ON images(org_id, record_id);
CREATE TABLE IF NOT EXISTS overrides (
  override_id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL,
  record_id TEXT NOT NULL,
  field TEXT NOT NULL,
  original_value TEXT,
  revised_value TEXT NOT NULL,
  reason TEXT NOT NULL,
  operator_label TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  org_id TEXT NOT NULL,
  record_id TEXT NOT NULL,
  event TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_audit_org ON audit_log(org_id, record_id);
"""

EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/heic": ".heic"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _safe_org(org_id: str) -> str:
    if not org_id or not all(ch.isalnum() or ch in "_-" for ch in org_id):
        raise ValueError("invalid org_id")
    return org_id


class Store:
    def __init__(self, var_dir: Path):
        self.var_dir = Path(var_dir)
        self.var_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir = self.var_dir / "images"
        self.images_dir.mkdir(exist_ok=True)
        self._lock = threading.Lock()
        self.db = sqlite3.connect(str(self.var_dir / "returns.db"), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.db.commit()

    # ---- images --------------------------------------------------------
    def save_image(self, org_id: str, record_id: str, data: bytes, mime: str, sha256: str) -> str:
        org = _safe_org(org_id)
        image_id = secrets.token_hex(16)
        folder = self.images_dir / org
        folder.mkdir(exist_ok=True)
        path = folder / f"{image_id}{EXT.get(mime, '.bin')}"
        path.write_bytes(data)
        with self._lock:
            self.db.execute("INSERT INTO images VALUES (?,?,?,?,?,?,?)",
                            (image_id, org, record_id, sha256, mime, str(path.relative_to(self.var_dir)), now_iso()))
            self.db.commit()
        return image_id

    def get_image(self, org_id: str, image_id: str) -> tuple[bytes, str] | None:
        row = self.db.execute("SELECT mime, path FROM images WHERE image_id=? AND org_id=?",
                              (image_id, org_id)).fetchone()
        if not row:
            return None
        path = (self.var_dir / row["path"]).resolve()
        if self.images_dir.resolve() / org_id not in path.parents:
            return None
        return path.read_bytes(), row["mime"]

    def record_images(self, org_id: str, record_id: str) -> list[tuple[bytes, str]]:
        rows = self.db.execute("SELECT image_id FROM images WHERE org_id=? AND record_id=? ORDER BY rowid",
                               (org_id, record_id)).fetchall()
        return [img for r in rows if (img := self.get_image(org_id, r["image_id"]))]

    # ---- records -------------------------------------------------------
    def put_record(self, record: dict[str, Any]) -> None:
        org = _safe_org(record["organization_id"])
        ts = now_iso()
        disp = (record.get("outcome") or {}).get("disposition")
        with self._lock:
            exists = self.db.execute("SELECT 1 FROM records WHERE record_id=? AND org_id=?",
                                     (record["record_id"], org)).fetchone()
            if exists:
                self.db.execute("UPDATE records SET status=?, disposition=?, updated_at=?, record_json=? "
                                "WHERE record_id=? AND org_id=?",
                                (record["status"], disp, ts, json.dumps(record), record["record_id"], org))
            else:
                self.db.execute("INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?)",
                                (record["record_id"], org, record["subject"]["unit_id"], record["subject"]["order_id"],
                                 record["status"], disp, ts, ts, json.dumps(record)))
            self.db.commit()

    def get_record(self, org_id: str, record_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT record_json FROM records WHERE record_id=? AND org_id=?",
                              (record_id, org_id)).fetchone()
        return json.loads(row["record_json"]) if row else None

    def list_records(self, org_id: str, limit: int = 200) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT record_id, unit_id, order_id, status, disposition, created_at "
                               "FROM records WHERE org_id=? ORDER BY created_at DESC LIMIT ?",
                               (org_id, limit)).fetchall()
        return [dict(r) for r in rows]

    # ---- overrides & audit (append-only) --------------------------------
    def add_override(self, org_id: str, record_id: str, field: str, original: Any, revised: str,
                     reason: str, operator_label: str) -> dict[str, Any]:
        ov = {"override_id": "OVR-" + secrets.token_hex(6), "field": field,
              "original_value": original, "revised_value": revised, "reason": reason,
              "operator_label": operator_label, "created_at": now_iso()}
        with self._lock:
            self.db.execute("INSERT INTO overrides VALUES (?,?,?,?,?,?,?,?,?)",
                            (ov["override_id"], org_id, record_id, field, json.dumps(original), revised,
                             reason, operator_label, ov["created_at"]))
            self.db.commit()
        return ov

    def audit(self, org_id: str, record_id: str, event: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self.db.execute("INSERT INTO audit_log (org_id, record_id, event, payload_json, created_at) VALUES (?,?,?,?,?)",
                            (org_id, record_id, event, json.dumps(payload), now_iso()))
            self.db.commit()

    def audit_trail(self, org_id: str, record_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute("SELECT seq, event, payload_json, created_at FROM audit_log "
                               "WHERE org_id=? AND record_id=? ORDER BY seq", (org_id, record_id)).fetchall()
        return [{"seq": r["seq"], "event": r["event"], "payload": json.loads(r["payload_json"]),
                 "created_at": r["created_at"]} for r in rows]
