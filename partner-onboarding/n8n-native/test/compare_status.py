"""Check that the n8n JavaScript seed data and traffic light match data/generate_data.py and app/status.py.

Usage: python n8n-native/test/compare_status.py   (needs node on the PATH)
"""
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))
from app.checklist import TASKS  # noqa: E402
from app.status import assess  # noqa: E402
from generate_data import PARTNERS  # noqa: E402

ok_all = True
for today in (date(2026, 10, 26), date(2026, 3, 1), date(2027, 1, 15)):
    py = []
    for pid, (name, city, day, customers, special) in enumerate(PARTNERS, 1):
        start = today - timedelta(days=day - 1)
        tasks = {}
        for t in TASKS:
            if t.id in special:
                status, done_day, note = special[t.id]
            elif t.due_day < day and t.id not in ("erster_kunde", "zehn_kunden"):
                status, done_day, note = "erledigt", t.due_day, ""
            else:
                status, done_day, note = "offen", None, ""
            done_on = (start + timedelta(days=done_day - 1)).isoformat() if done_day else None
            tasks[t.id] = {"status": status, "done_on": done_on, "note": note}
        py.append(assess({"start_date": start.isoformat(), "active_customers": customers}, tasks, today))

    checklist = [{"id": t.id, "title": t.title, "due_day": t.due_day, "owner": t.owner, "gate": t.gate} for t in TASKS]
    code = ROOT / "n8n-native" / "code"
    runner = f"""
const fs = require('fs');
eval(fs.readFileSync({json.dumps(str(code / 'seed_core.js'))}, 'utf8'));
eval(fs.readFileSync({json.dumps(str(code / 'status_core.js'))}, 'utf8'));
const inp = JSON.parse(fs.readFileSync(0, 'utf8'));
const s = seedRows(inp.partners, inp.checklist, inp.today);
const out = s.partnerRows.map(p => {{
  const tasks = Object.fromEntries(s.taskRows.filter(r => r.partner_id === p.partner_id)
    .map(r => [r.aufgabe, {{status: r.status, done_on: r.erledigt_am || null, note: r.notiz}}]));
  return assess({{start_date: p.start, active_customers: p.aktive_kunden}}, tasks, inp.checklist, inp.today);
}});
process.stdout.write(JSON.stringify(out));
"""
    partners = [[n, c, d, k, {t: list(v) for t, v in s.items()}] for n, c, d, k, s in PARTNERS]
    res = subprocess.run(["node", "-e", runner], capture_output=True, text=True, encoding="utf-8",
                         input=json.dumps({"partners": partners, "checklist": checklist, "today": today.isoformat()}))
    if res.returncode:
        sys.exit(res.stderr)
    js = json.loads(res.stdout)
    for a, b in zip(py, js):
        if json.loads(json.dumps(a)) != b:
            ok_all = False
            print("DIFF", today, "\n py:", json.dumps(a, ensure_ascii=False), "\n js:", json.dumps(b, ensure_ascii=False))
    print(today, "levels:", [p["level"] for p in js])
print("identical" if ok_all else "DIFFERENCES FOUND")
