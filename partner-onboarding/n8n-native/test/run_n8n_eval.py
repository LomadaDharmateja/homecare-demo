"""Send the 50 test messages through the live n8n workflow F2 (dry run, nothing saved) and score them.

Same scoring as eval/run_eval.py: correct = exactly the expected checklist changes and customer count.
The same test cases are in the data table ob_testfaelle for n8n's own Evaluations tab.
Usage: python n8n-native/test/run_n8n_eval.py   (n8n and Ollama running, workflow F2 published)
"""
import json
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
URL = "http://localhost:5678/webhook/onboarding-update"
cases = json.loads((HERE.parents[1] / "eval" / "updates.json").read_text(encoding="utf-8"))
lines = ["# n8n version: evaluation", "",
         "The 50 partner messages from eval/updates.json, sent through the live n8n workflow F2 "
         "(dry run: nothing saved). Model qwen2.5:3b through n8n's Ollama + Basic LLM Chain nodes.", ""]
total = right = wrong_done_total = 0
for name, rows in cases.items():
    if name.startswith("_"):
        continue
    ok_n, table = 0, []
    for c in rows:
        body = json.dumps({"partner_id": 0, "nachricht": c["msg"], "nur_testen": True}).encode()
        req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
        t = time.time()
        r = json.loads(urllib.request.urlopen(req, timeout=180).read())
        got = {x["task"]: x["status"] for x in r["aenderungen"]}
        ok = got == c["changes"] and r["kunden"] == c.get("active_customers")
        wrong_done = [k for k, v in got.items() if v == "erledigt" and c["changes"].get(k) != "erledigt"]
        ok_n += ok
        wrong_done_total += len(wrong_done)
        fmt = lambda d: ", ".join(f"{k}={v}" for k, v in d.items()) or "keine"  # noqa: E731
        table.append(f"| {c['msg'][:80]} | {'✅' if ok else '❌'} | {fmt(c['changes'])} | {fmt(got)} | {time.time() - t:.1f}s |")
    total += len(rows)
    right += ok_n
    print(f"{name}: {ok_n}/{len(rows)}")
    lines += [f"## {name}: {ok_n}/{len(rows)} correct", "", "| Message | Result | Expected | Proposed | Time |",
              "|---|---|---|---|---|", *table, ""]
lines.insert(4, f"**All: {right}/{total} correct. Wrongly proposed as done: {wrong_done_total}.**\n")
(HERE.parent / "eval_report.md").write_text("\n".join(lines), encoding="utf-8")
print(f"all: {right}/{total}, wrong done: {wrong_done_total}")
