"""What the API and the dashboard call. Proposals change nothing until a person approves them; every change
is written to the audit log with who, when, before and after."""
import json
from datetime import date

from . import db
from .checklist import BY_ID, GATE, TASKS
from .status import assess
from .updates import propose


def overview():
    with db.connect() as con:
        out = []
        for p in db.partners(con):
            tasks = db.tasks(con, p["id"])
            out.append({**p, **assess(p, tasks), "tasks": tasks})
        return out


def submit_update(partner_id, message, source="E-Mail"):
    """Partner message -> stored proposal (status 'offen'). Nothing in the checklist changes yet."""
    with db.connect() as con:
        partner = db.partner(con, partner_id)
        if not partner:
            raise KeyError(f"Partner {partner_id} unbekannt")
        tasks = db.tasks(con, partner_id)
        result = propose(message)
        changes, skipped = [], []
        for c in result["changes"]:
            if tasks[c["task"]]["status"] == c["status"]:
                skipped.append({**c, "grund": "steht schon so in der Checkliste"})
            else:
                changes.append({**c, "titel": BY_ID[c["task"]].title, "vorher": tasks[c["task"]]["status"]})
        warnings = []
        after = {t: tasks[t]["status"] for t in tasks} | {c["task"]: c["status"] for c in changes}
        if after["erster_kunde"] == "erledigt":
            missing = [BY_ID[g].title for g in GATE if after[g] != "erledigt"]
            if missing:
                warnings.append("Partner meldet Kundeneinsätze, aber laut Checkliste fehlt noch: " + ", ".join(missing)
                                + ". Bitte sofort klären, bevor weitere Einsätze stattfinden.")
        cur = con.execute("INSERT INTO proposals (partner_id, received_at, message, changes, dropped, warnings, "
                          "active_customers, model_raw) VALUES (?,?,?,?,?,?,?,?)",
                          (partner_id, db.now(), message, json.dumps(changes, ensure_ascii=False),
                           json.dumps(result["notes"] + skipped, ensure_ascii=False),
                           json.dumps(warnings, ensure_ascii=False), result["active_customers"], ""))
        db.audit(con, partner_id, source, "Update eingegangen",
                 {"vorschlag": cur.lastrowid, "änderungen": len(changes), "warnungen": len(warnings)})
        con.commit()
        return db.proposal(con, cur.lastrowid)


def decide(proposal_id, approve, by, tasks=None):
    """Approve (all changes, or only the listed task ids) or reject a proposal."""
    if not by or not by.strip():
        raise ValueError("Bitte angeben, wer entscheidet")
    with db.connect() as con:
        p = db.proposal(con, proposal_id)
        if not p:
            raise KeyError(f"Vorschlag {proposal_id} unbekannt")
        if p["status"] != "offen":
            raise ValueError(f"Vorschlag {proposal_id} ist schon entschieden ({p['status']})")
        chosen = [c for c in p["changes"] if tasks is None or c["task"] in tasks] if approve else []
        for c in chosen:
            con.execute("UPDATE tasks SET status=?, done_on=?, note=? WHERE partner_id=? AND task=?",
                        (c["status"], c["done_on"], c["satz"][:200], p["partner_id"], c["task"]))
            db.audit(con, p["partner_id"], by, "Checkliste geändert",
                     {"vorschlag": proposal_id, "punkt": c["titel"], "vorher": c["vorher"], "nachher": c["status"],
                      "beleg": c["satz"], "entschieden_von": c["entschieden_von"]})
        if approve and p["active_customers"] is not None:
            con.execute("UPDATE partners SET active_customers=? WHERE id=?", (p["active_customers"], p["partner_id"]))
            db.audit(con, p["partner_id"], by, "Kundenzahl geändert", {"vorschlag": proposal_id,
                                                                       "nachher": p["active_customers"]})
        status = "abgelehnt" if not approve else "freigegeben" if len(chosen) == len(p["changes"]) else "teilweise"
        con.execute("UPDATE proposals SET status=?, decided_by=?, decided_at=? WHERE id=?",
                    (status, by.strip(), db.now(), proposal_id))
        db.audit(con, p["partner_id"], by, f"Vorschlag {status}", {"vorschlag": proposal_id,
                                                                    "übernommen": [c["task"] for c in chosen]})
        con.commit()
        return db.proposal(con, proposal_id)


def set_task(partner_id, task, status, by, note=""):
    """Manual change by partner management (e.g. something the assistant missed)."""
    if task not in BY_ID or status not in ("offen", "erledigt", "blockiert"):
        raise ValueError("unbekannter Punkt oder Status")
    if not by or not by.strip():
        raise ValueError("Bitte angeben, wer ändert")
    with db.connect() as con:
        before = db.tasks(con, partner_id)[task]["status"]
        con.execute("UPDATE tasks SET status=?, done_on=?, note=? WHERE partner_id=? AND task=?",
                    (status, date.today().isoformat() if status == "erledigt" else None, note, partner_id, task))
        db.audit(con, partner_id, by, "Checkliste manuell geändert",
                 {"punkt": BY_ID[task].title, "vorher": before, "nachher": status, "notiz": note})
        con.commit()


def risks():
    """Partners that need attention, most serious first, plus a short German text for the Telegram digest."""
    rows = [p for p in overview() if p["level"] != "im Plan"]
    rows.sort(key=lambda p: (p["level"] != "kritisch", -p["day"]))
    with db.connect() as con:
        pending = len(db.proposals(con, "offen"))
    icon = {"kritisch": "🔴", "Achtung": "🟠"}
    lines = [f"🧭 Onboarding neuer Partner: {sum(p['level'] == 'kritisch' for p in rows)} kritisch, "
             f"{sum(p['level'] == 'Achtung' for p in rows)} mit Hinweis"]
    for p in rows:
        lines.append(f"{icon[p['level']]} {p['city']} (Tag {p['day']}): {p['findings'][0]['text']}")
    if pending:
        lines.append(f"📨 {pending} Partner-Update(s) warten auf Freigabe.")
    lines.append("Details im Onboarding-Cockpit. (Erfundene Demo-Daten)")
    return {"count": len(rows), "pending_updates": pending, "text": "\n".join(lines),
            "items": [{"city": p["city"], "day": p["day"], "level": p["level"], "findings": p["findings"]}
                      for p in rows]}


def audit_log(limit=50):
    with db.connect() as con:
        return db.audit_log(con, limit)


def pending():
    with db.connect() as con:
        out = db.proposals(con, "offen")
        for p in out:
            p["city"] = db.partner(con, p["partner_id"])["city"]
        return out


__all__ = ["overview", "submit_update", "decide", "set_task", "risks", "audit_log", "pending", "TASKS"]
