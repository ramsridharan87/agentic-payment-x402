import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def data_dir() -> Path:
    """Root for persisted state (SQLite db, generated documents).

    AGENTIC_PAYMENTS_DATA_DIR points at a mounted persistent disk when
    hosted (e.g. Render); falls back to a local data/ dir for dev.
    """
    override = os.environ.get("AGENTIC_PAYMENTS_DATA_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "data"


DEFAULT_DB_PATH = data_dir() / "audit.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    goal TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(id),
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    tool_name TEXT,
    summary TEXT NOT NULL,
    amount_usd REAL,
    destination TEXT,
    resource_url TEXT,
    network TEXT,
    tx_hash TEXT,
    detail_json TEXT
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _connect(db_path: Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


@dataclass
class AuditLog:
    """Records every agent decision and payment to SQLite for the UI to display."""

    db_path: Path = field(default=DEFAULT_DB_PATH)
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def start_run(self, goal: str) -> str:
        with _connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO runs (id, started_at, goal, status) VALUES (?, ?, ?, 'running')",
                (self.run_id, _now(), goal),
            )
        return self.run_id

    def end_run(self, status: str = "completed") -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                "UPDATE runs SET ended_at = ?, status = ? WHERE id = ?",
                (_now(), status, self.run_id),
            )

    def log(
        self,
        kind: str,
        summary: str,
        *,
        tool_name: str | None = None,
        amount_usd: float | None = None,
        destination: str | None = None,
        resource_url: str | None = None,
        network: str | None = None,
        tx_hash: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Append one event. `kind` examples: reasoning, tool_call, payment_blocked,
        payment_executed, payment_failed, final_answer."""
        with _connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO events
                   (run_id, ts, kind, tool_name, summary, amount_usd, destination,
                    resource_url, network, tx_hash, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.run_id,
                    _now(),
                    kind,
                    tool_name,
                    summary,
                    amount_usd,
                    destination,
                    resource_url,
                    network,
                    tx_hash,
                    json.dumps(detail) if detail else None,
                ),
            )

    def spent_all_time_usd(self) -> float:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(amount_usd), 0) AS total FROM events "
                "WHERE kind = 'payment_executed'"
            ).fetchone()
        return float(row["total"])

    def spent_today_usd(self) -> float:
        """Total USD spent on successful payments across all runs today (UTC)."""
        today_prefix = datetime.now(timezone.utc).date().isoformat()
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(amount_usd), 0) AS total FROM events
                   WHERE kind = 'payment_executed' AND ts LIKE ?""",
                (f"{today_prefix}%",),
            ).fetchone()
        return float(row["total"])


def fetch_runs(db_path: Path = DEFAULT_DB_PATH, limit: int = 50) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT runs.*,
                      COALESCE((SELECT SUM(amount_usd) FROM events
                                WHERE events.run_id = runs.id
                                AND events.kind = 'payment_executed'), 0) AS total_spent_usd,
                      (SELECT COUNT(*) FROM events
                       WHERE events.run_id = runs.id
                       AND events.kind = 'payment_executed') AS payment_count
               FROM runs ORDER BY started_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_run(run_id: str, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def fetch_events(run_id: str, db_path: Path = DEFAULT_DB_PATH) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE run_id = ? ORDER BY id ASC", (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def fetch_payment_events(db_path: Path = DEFAULT_DB_PATH, limit: int = 100) -> list[dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT events.*, runs.goal AS run_goal FROM events
               JOIN runs ON runs.id = events.run_id
               WHERE events.kind IN ('payment_executed', 'payment_blocked', 'payment_failed')
               ORDER BY events.id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
