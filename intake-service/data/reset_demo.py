"""Reset the demo database to five fresh example requests (four German, one English).

Run before a demo, with Ollama running:  .\\.venv\\Scripts\\python.exe data\\reset_demo.py
The old database is copied to data/intake_backup_<time>.db first. The tables are emptied instead of deleting the
file, because the running API and dashboard keep it open on Windows. Goes straight to the agent, not through n8n,
so no Telegram alert is sent.
"""
import shutil
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import agent, db  # noqa: E402
from app.schemas import IntakeIn  # noqa: E402

EXAMPLES = [  # (text, hours ago) - same texts as send_example.ps1, all invented
    ("Guten Tag, wir suchen ab nächster Woche Hilfe beim Einkaufen für meine Oma in Köln. "
     "Bitte rufen Sie mich nachmittags an.", 30),
    ("Hallo, eine Bekannte hat Sie empfohlen. Was für Hilfe bieten Sie eigentlich an?", 26),
    ("Könnte jemand meinen Vater nächsten Mittwoch um 10 Uhr zur Physiotherapie fahren? Er geht mit Rollator.", 5),
    ("My father (84) fell in the kitchen in Neuss this morning. He is okay but shaky and alone. "
     "Can someone stay with him today? Please call me back as soon as possible.", 2),
    ("Meine Mutter (86) ist heute früh in ihrer Wohnung in Düsseldorf gestürzt. Sie ist jetzt allein und sehr "
     "unsicher. Kann heute noch jemand bei ihr bleiben? Bitte rufen Sie mich sofort zurück.", 1),
]


def main():
    db.init_db()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shutil.copy(db.DB_PATH, db.DB_PATH.with_name(f"intake_backup_{stamp}.db"))
    with sqlite3.connect(db.DB_PATH) as con:
        con.execute("DELETE FROM audit_log")
        con.execute("DELETE FROM requests")
        con.execute("DELETE FROM sqlite_sequence WHERE name IN ('requests', 'audit_log')")
    now = datetime.now(timezone.utc)
    for text, hours in EXAMPLES:
        r = agent.process_request(IntakeIn(text=text, channel="web_form",
                                           received_at=(now - timedelta(hours=hours)).isoformat(timespec="seconds")))
        print(f"#{r['id']} {r['urgency']:<6} {r['summary']}")
    print(f"Backup: intake_backup_{stamp}.db")


if __name__ == "__main__":
    main()
