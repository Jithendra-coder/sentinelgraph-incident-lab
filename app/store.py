import hashlib
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.models import Incident, IncidentStatus, TimelineEvent, now_utc


class Store:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL)")
            db.execute("CREATE INDEX IF NOT EXISTS incidents_tenant_created ON incidents(tenant_id, created_at DESC)")
            db.execute("CREATE TABLE IF NOT EXISTS idempotency (tenant_id TEXT NOT NULL, key_hash TEXT NOT NULL, incident_id TEXT NOT NULL, PRIMARY KEY(tenant_id, key_hash))")

    def create_or_get(self, incident: Incident, idempotency_key: str | None) -> tuple[Incident, bool]:
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest() if idempotency_key else None
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if key_hash:
                row = db.execute(
                    "SELECT incidents.data FROM idempotency JOIN incidents ON incidents.id=idempotency.incident_id "
                    "WHERE idempotency.tenant_id=? AND idempotency.key_hash=?",
                    (incident.tenant_id, key_hash),
                ).fetchone()
                if row:
                    return Incident.model_validate_json(row["data"]), False
            db.execute(
                "INSERT INTO incidents(id, tenant_id, created_at, data) VALUES(?,?,?,?)",
                (incident.id, incident.tenant_id, incident.created_at.isoformat(), incident.model_dump_json()),
            )
            if key_hash:
                db.execute("INSERT INTO idempotency(tenant_id, key_hash, incident_id) VALUES(?,?,?)", (incident.tenant_id, key_hash, incident.id))
        return incident, True

    def save(self, incident: Incident) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO incidents(id, tenant_id, created_at, data) VALUES(?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (incident.id, incident.tenant_id, incident.created_at.isoformat(), incident.model_dump_json()),
            )

    def get(self, incident_id: str, tenant_id: str) -> Incident | None:
        with self.connect() as db:
            row = db.execute("SELECT data FROM incidents WHERE id=? AND tenant_id=?", (incident_id, tenant_id)).fetchone()
        return Incident.model_validate_json(row["data"]) if row else None

    def list(self, tenant_id: str, limit: int = 100) -> list[Incident]:
        with self.connect() as db:
            rows = db.execute("SELECT data FROM incidents WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?", (tenant_id, limit)).fetchall()
        return [Incident.model_validate_json(row["data"]) for row in rows]

    def recover_interrupted(self) -> int:
        self.initialize()
        incidents = []
        with self.connect() as db:
            rows = db.execute("SELECT data FROM incidents").fetchall()
            for row in rows:
                incident = Incident.model_validate_json(row["data"])
                if incident.status == IncidentStatus.investigating:
                    incident.status = IncidentStatus.blocked
                    incident.timeline.append(TimelineEvent(kind="failure", message="Investigation interrupted by service restart; start a new replay."))
                    incident.completed_at = now_utc()
                    incidents.append(incident)
        for incident in incidents:
            self.save(incident)
        return len(incidents)
