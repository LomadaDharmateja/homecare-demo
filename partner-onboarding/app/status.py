"""Traffic light per partner. Plain rules, no AI: every finding says which rule fired and why."""
from datetime import date, timedelta

from .checklist import BY_ID, GATE, PERMIT_WEEKS, TARGET_CUSTOMERS, TASKS

LEVELS = ["im Plan", "Achtung", "kritisch"]


def day_of(start_date, today=None):
    return ((today or date.today()) - date.fromisoformat(start_date)).days + 1


def assess(partner, tasks, today=None):
    """Returns day, progress, level and findings (each finding: level + German text)."""
    today = today or date.today()
    start = date.fromisoformat(partner["start_date"])
    day = day_of(partner["start_date"], today)
    findings = []

    def add(level, text):
        findings.append({"level": level, "text": text})

    # 1. First customer visit without the handbook's preconditions: the most serious case.
    missing_gate = [g for g in GATE if tasks[g]["status"] != "erledigt"]
    if tasks["erster_kunde"]["status"] == "erledigt" and missing_gate:
        add("kritisch", "Kundeneinsätze laufen, aber Voraussetzungen fehlen: "
            + ", ".join(BY_ID[g].title for g in missing_gate) + ".")

    # 2. Blocked and overdue tasks. A gate task blocks the start of customer care, so it is critical.
    for t in TASKS:
        row = tasks[t.id]
        if row["status"] == "blockiert":
            add("kritisch" if t.gate else "Achtung",
                f"Blockiert: {t.title}" + (f" ({row['note']})" if row["note"] else "") + ".")
        elif row["status"] == "offen" and t.due_day < day:
            add("kritisch" if t.gate else "Achtung",
                f"Überfällig seit Tag {t.due_day}: {t.title} (zuständig: {t.owner}).")

    # 3. Permit forecast: the authority needs 4-8 weeks after the application (handbook).
    if tasks["zulassung"]["status"] != "erledigt":
        if tasks["antrag"]["status"] == "erledigt" and tasks["antrag"]["done_on"]:
            filed = date.fromisoformat(tasks["antrag"]["done_on"])
            basis = f"Antrag gestellt am {filed:%d.%m.}"
        else:
            filed, basis = today, "Antrag noch nicht gestellt, frühestens heute"
        first = (filed + timedelta(weeks=PERMIT_WEEKS[0]) - start).days + 1
        last = (filed + timedelta(weeks=PERMIT_WEEKS[1]) - start).days + 1
        if first > 90:
            add("kritisch", f"Zulassung kommt erst zwischen Tag {first} und {last} ({basis}). "
                "Vor Tag 90 sind keine Kundeneinsätze möglich.")
        elif last > 90:
            add("Achtung", f"Zulassung kommt zwischen Tag {first} und {last} ({basis}). "
                f"Das Ziel von {TARGET_CUSTOMERS} Kunden bis Tag 90 ist gefährdet.")

    # 4. Customer target in phase 3.
    customers = partner["active_customers"]
    if 60 < day <= 90 and customers < TARGET_CUSTOMERS and not missing_gate:
        left = 90 - day + 1
        need = TARGET_CUSTOMERS - customers
        if need > left / 2:  # more than one new customer every two days: unrealistic
            add("Achtung", f"{customers} von {TARGET_CUSTOMERS} Kunden, noch {left} Tage bis Tag 90 "
                f"(nötig: {need} neue Kunden).")

    done = sum(tasks[t.id]["status"] == "erledigt" for t in TASKS)
    level = max((f["level"] for f in findings), key=LEVELS.index, default="im Plan")
    findings.sort(key=lambda f: -LEVELS.index(f["level"]))
    phase = 1 if day <= 30 else 2 if day <= 60 else 3
    return {"day": day, "phase": phase, "done": done, "total": len(TASKS), "level": level, "findings": findings,
            "ready_for_customers": not missing_gate, "missing_for_customers": [BY_ID[g].title for g in missing_gate]}
