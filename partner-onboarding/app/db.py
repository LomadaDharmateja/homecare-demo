"""SQLite storage: partners, their checklist, update proposals awaiting approval, and an audit log."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "onboarding.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS partners (id INTEGER PRIMARY KEY, name TEXT, city TEXT, start_date TEXT,
    manager TEXT, active_customers INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS tasks (partner_id INTEGER, task TEXT, status TEXT DEFAULT 'offen', done_on TEXT,
    note TEXT, PRIMARY KEY (partner_id, task));
CREATE TABLE IF NOT EXISTS proposals (id INTEGER PRIMARY KEY, partner_id INTEGER, received_at TEXT, message TEXT,
    changes TEXT, dropped TEXT, warnings TEXT, active_customers INTEGER, model_raw TEXT,
    status TEXT DEFAULT 'offen', decided_by TEXT, decided_at TEXT);
CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, at TEXT, partner_id INTEGER, actor TEXT, action TEXT,
    detail TEXT);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def audit(con, partner_id, actor, action, detail):
    con.execute("INSERT INTO audit (at, partner_id, actor, action, detail) VALUES (?,?,?,?,?)",
                (now(), partner_id, actor, action, json.dumps(detail, ensure_ascii=False)))


def partners(con):
    return [dict(r) for r in con.execute("SELECT * FROM partners ORDER BY start_date")]


def partner(con, partner_id):
    row = con.execute("SELECT * FROM partners WHERE id=?", (partner_id,)).fetchone()
    return dict(row) if row else None


def tasks(con, partner_id):
    return {r["task"]: dict(r) for r in con.execute("SELECT * FROM tasks WHERE partner_id=?", (partner_id,))}


def proposal(con, proposal_id):
    row = con.execute("SELECT * FROM proposals WHERE id=?", (proposal_id,)).fetchone()
    if not row:
        return None
    p = dict(row)
    for k in ("changes", "dropped", "warnings"):
        p[k] = json.loads(p[k] or "[]")
    return p


def proposals(con, status=None):
    q = "SELECT id FROM proposals" + (" WHERE status=?" if status else "") + " ORDER BY id DESC"
    return [proposal(con, r["id"]) for r in con.execute(q, (status,) if status else ())]


def audit_log(con, limit=50):
    rows = con.execute("SELECT a.*, p.city FROM audit a LEFT JOIN partners p ON p.id=a.partner_id "
                       "ORDER BY a.id DESC LIMIT ?", (limit,))
    return [dict(r) for r in rows]
