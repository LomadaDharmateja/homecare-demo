"""Check that the n8n JavaScript rules give exactly the same proposals as app/updates.py.

The AI is replaced by the same fake answer in both (a fixed yes/no per clause), so only the rules are compared.
Usage: python n8n-native/test/compare_rules.py   (needs node on the PATH)
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app import updates  # noqa: E402
from app.checklist import TASKS  # noqa: E402

RECEIVED = date(2026, 10, 26)


def fake(clause, task):
    return (len(clause) + len(task)) % 2 == 0


def py_judge(clause, task):
    ok = fake(clause, task)
    return updates.Judgement(begruendung="fake", erledigt=ok)


updates.judge = py_judge
cases = [c for k, v in json.loads((ROOT / "eval" / "updates.json").read_text(encoding="utf-8")).items()
         if not k.startswith("_") for c in v]
extra = ["Am 3.11. war die Schulung, gestern kam der Bescheid. Wir haben zwei Kunden!",
         "Vorgestern haben wir das Büro angemietet; die Bank hat leider abgelehnt.",
         "Unsere erste Kundin betreuen wir seit Mittwoch, aber das Konto fehlt noch."]
msgs = [c["msg"] for c in cases] + extra
py = [updates.propose(m, RECEIVED) for m in msgs]

checklist = [{"id": t.id, "title": t.title, "words": list(t.words)} for t in TASKS]
js = ROOT / "n8n-native" / "code" / "rules_core.js"
runner = f"""
const fs = require('fs');
eval(fs.readFileSync({json.dumps(str(js))}, 'utf8'));
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const fake = (c, t) => (c.length + t.length) % 2 === 0;
const out = input.msgs.map(m => {{
  const r = ruleEvents(m, input.checklist);
  const answers = r.questions.map(q => ({{begruendung: 'fake', erledigt: fake(q.satz, q.task)}}));
  return buildProposal(m, r.events, answers, '2026-10-26');
}});
process.stdout.write(JSON.stringify(out));
"""
res = subprocess.run(["node", "-e", runner], input=json.dumps({"msgs": msgs, "checklist": checklist}),
                     capture_output=True, text=True, encoding="utf-8")
if res.returncode:
    sys.exit(res.stderr)
out = json.loads(res.stdout)
bad = 0
for m, a, b in zip(msgs, py, out):
    a = json.loads(json.dumps(a, ensure_ascii=False))
    if a != b:
        bad += 1
        print("DIFF:", m, "\n  py:", json.dumps(a, ensure_ascii=False), "\n  js:", json.dumps(b, ensure_ascii=False))
print(f"{len(msgs) - bad}/{len(msgs)} messages identical")
