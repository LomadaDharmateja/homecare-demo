"""Create 8 fictional new partners at different points of their 90 days, relative to today.

Run again before a demo so "day X" stays the same: python data/generate_data.py
Names are invented, cities only, no addresses. Each partner shows one situation the cockpit must spot.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import db  # noqa: E402
from app.checklist import TASKS  # noqa: E402

# (name, city, day in onboarding, active customers, {task: (status, day done or None, note)})
# Tasks not listed: done on their due day if that day has passed, otherwise open.
PARTNERS = [
    ("Jana Albers", "Bochum", 8, 0, {}),
    ("Murat Demir", "Essen", 26, 0, {"konto": ("offen", None, "")}),  # bank account overdue (not a gate task)
    ("Lena und Tom Wagner", "Münster", 44, 0, {"antrag": ("offen", None, "")}),  # application late -> permit late
    ("Sven Ott", "Kassel", 40, 0, {"antrag": ("erledigt", 30, ""), "haftpflicht": ("blockiert", None, "Versicherer verlangt erst Handelsregisterauszug")}),
    ("Aylin Yilmaz", "Regensburg", 58, 0, {"antrag": ("erledigt", 20, ""), "zulassung": ("offen", None, "")}),
    ("Peter Brandt", "Lübeck", 71, 3, {"antrag": ("erledigt", 33, ""), "zulassung": ("offen", None, ""),
                                       "fuehrungszeugnis": ("offen", None, ""),
                                       "erster_kunde": ("erledigt", 66, "Kundin seit Tag 66 betreut")}),  # visit without permit
    ("Nora Fischer", "Freiburg", 84, 4, {"antrag": ("erledigt", 25, ""), "zulassung": ("erledigt", 58, ""),
                                         "erster_kunde": ("erledigt", 70, "")}),  # 4 of 10 customers, 6 days left
    ("Klaus Remmers", "Erfurt", 96, 12, {"antrag": ("erledigt", 28, ""), "zulassung": ("erledigt", 61, ""),
                                         "erster_kunde": ("erledigt", 68, ""), "zehn_kunden": ("erledigt", 88, ""),
                                         "abschluss": ("offen", None, "")}),  # final meeting overdue
]


def main():
    con = db.connect()
    # Empty the tables instead of deleting the file: on Windows the running API/dashboard keep the file open.
    for table in ("partners", "tasks", "proposals", "audit"):
        con.execute(f"DELETE FROM {table}")
    today = date.today()
    for pid, (name, city, day, customers, special) in enumerate(PARTNERS, 1):
        start = today - timedelta(days=day - 1)
        con.execute("INSERT INTO partners VALUES (?,?,?,?,?,?)",
                    (pid, name, city, start.isoformat(), "Frau Becker" if pid % 2 else "Herr Yıldız", customers))
        for t in TASKS:
            if t.id in special:
                status, done_day, note = special[t.id]
            elif t.due_day < day and t.id not in ("erster_kunde", "zehn_kunden"):
                status, done_day, note = "erledigt", t.due_day, ""
            else:
                status, done_day, note = "offen", None, ""
            done_on = (start + timedelta(days=done_day - 1)).isoformat() if done_day else None
            con.execute("INSERT INTO tasks VALUES (?,?,?,?,?)", (pid, t.id, status, done_on, note))
        db.audit(con, pid, "system", "angelegt", {"start": start.isoformat()})
    con.commit()
    print(f"{len(PARTNERS)} partners written to {db.DB_PATH}")


if __name__ == "__main__":
    main()
