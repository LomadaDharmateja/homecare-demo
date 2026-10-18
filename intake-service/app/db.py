"""SQLite storage: one table for request records, one append-only audit log."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Module-level so the eval script can point at a separate database.
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "intake.db"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                channel TEXT NOT NULL,
                text TEXT NOT NULL,
                service_type TEXT,
                when_needed TEXT,             -- time phrase as written by the customer
                urgency TEXT,
                callback_requested INTEGER,
                preferred_contact_time TEXT,
                location TEXT,
                missing_info TEXT,            -- JSON list
                summary TEXT,
                priority INTEGER,             -- 1 = handle first
                followup_draft TEXT,
                followup_status TEXT NOT NULL DEFAULT 'none',  -- none | pending_approval | approved | rejected
                reviewed_at TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                timestamp TEXT NOT NULL,
                step TEXT NOT NULL,           -- e.g. received, agent_decision, tool_call, human_review
                tool TEXT,
                input TEXT,                   -- JSON
                output TEXT                   -- JSON
            );
            """
        )


def log_audit(request_id, step, tool=None, input_data=None, output_data=None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO audit_log (request_id, timestamp, step, tool, input, output) VALUES (?, ?, ?, ?, ?, ?)",
            (request_id, now_iso(), step, tool,
             json.dumps(input_data, ensure_ascii=False, default=str),
             json.dumps(output_data, ensure_ascii=False, default=str)),
        )


def insert_request(text: str, channel: str, received_at: str) -> int:
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO requests (received_at, channel, text, created_at) VALUES (?, ?, ?, ?)",
            (received_at, channel, text, now_iso()),
        )
        return cur.lastrowid


# Whitelist so callers can never inject arbitrary column names into the UPDATE.
UPDATABLE_COLUMNS = {
    "service_type", "when_needed", "urgency", "callback_requested", "preferred_contact_time", "location",
    "missing_info", "summary", "priority", "followup_draft", "followup_status", "reviewed_at",
}


def update_request(request_id: int, **fields) -> None:
    unknown = set(fields) - UPDATABLE_COLUMNS
    if unknown:
        raise ValueError(f"Not updatable: {unknown}")
    if "missing_info" in fields:
        fields["missing_info"] = json.dumps(fields["missing_info"], ensure_ascii=False)
    assignments = ", ".join(f"{column} = ?" for column in fields)
    with connect() as conn:
        conn.execute(f"UPDATE requests SET {assignments} WHERE id = ?", (*fields.values(), request_id))


def _row_to_dict(row: sqlite3.Row) -> dict:
    record = dict(row)
    record["missing_info"] = json.loads(record["missing_info"] or "[]")
    record["callback_requested"] = bool(record["callback_requested"])
    return record


def get_request(request_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM requests WHERE id = ?", (request_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_requests() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM requests ORDER BY priority, received_at").fetchall()
    return [_row_to_dict(row) for row in rows]


def list_overdue(hours: int = 24) -> list[dict]:
    """Callback was requested, more than `hours` have passed, and no follow-up has been approved."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    with connect() as conn:
        rows = conn.execute(
            """SELECT * FROM requests
               WHERE callback_requested = 1 AND followup_status != 'approved' AND received_at < ?
               ORDER BY received_at""",
            (cutoff,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def review_followup(request_id: int, decision: str) -> None:
    """The only path that moves a draft out of pending_approval; called from the human-facing dashboard."""
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be 'approved' or 'rejected'")
    update_request(request_id, followup_status=decision, reviewed_at=now_iso())
    log_audit(request_id, "human_review", output_data={"followup_status": decision})


if __name__ == "__main__":
    init_db()
    test_id = insert_request("db.py self-test", "web_form", now_iso())
    update_request(test_id, urgency="low", missing_info=["location"], callback_requested=True)
    log_audit(test_id, "self_test", output_data={"ok": True})
    print(get_request(test_id))
    with connect() as conn:
        conn.execute("DELETE FROM requests WHERE id = ?", (test_id,))
        conn.execute("DELETE FROM audit_log WHERE request_id = ?", (test_id,))
    print("db.py self-test passed, database at", DB_PATH)
