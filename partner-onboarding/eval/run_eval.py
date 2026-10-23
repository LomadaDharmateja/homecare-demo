"""Score partner update -> proposed changes against the hand-written expectations. Writes eval/report.md.

A message counts as correct only if the final, code-checked proposal has exactly the expected changes and
customer count. "Wrong done" counts proposals that would mark something done that the partner didn't say
is done: the dangerous error (a person still approves, but should not have to catch it).
Usage: python eval/run_eval.py [tuning|final_test|all]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.updates import propose  # noqa: E402

HERE = Path(__file__).parent


def score(cases):
    rows = []
    for case in cases:
        t = time.time()
        p = propose(case["msg"])
        got = {c["task"]: c["status"] for c in p["changes"]}
        exp = case["changes"]
        wrong_done = [k for k, v in got.items() if v == "erledigt" and exp.get(k) != "erledigt"]
        ok = got == exp and p["active_customers"] == case.get("active_customers")
        rows.append({"msg": case["msg"], "ok": ok, "expected": exp, "got": got, "wrong_done": wrong_done,
                     "customers": (case.get("active_customers"), p["active_customers"]),
                     "dropped": p["notes"], "seconds": round(time.time() - t, 1)})
    return rows


def fmt(d):
    return ", ".join(f"{k}={v}" for k, v in d.items()) or "keine"


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    data = json.loads((HERE / "updates.json").read_text(encoding="utf-8"))
    sets = ["tuning", "final_test", "final_test_2", "final_test_3"] if which == "all" else [which]
    lines = ["# Partner updates: evaluation", "",
             "Current version (v3). Only final_test_3 was blind for v3; see README for the blind result of each version. Each message is a partner's free-text update. Correct = the final proposal (after the code checks) has "
             "exactly the expected checklist changes and customer count. Model: qwen2.5:3b, temperature 0.", ""]
    for name in sets:
        rows = score(data[name])
        ok = sum(r["ok"] for r in rows)
        wrong_done = sum(len(r["wrong_done"]) for r in rows)
        caught = sum(len(r["dropped"]) for r in rows)
        print(f"{name}: {ok}/{len(rows)} correct, wrong 'done': {wrong_done}, no-change clauses: {caught}")
        lines += [f"## {name}: {ok}/{len(rows)} correct", "",
                  f"Wrongly proposed as done: **{wrong_done}**. Clauses decided as 'no change' (with the reason in the last column): {caught}. "
                  f"Average {sum(r['seconds'] for r in rows) / len(rows):.1f}s per message.", "",
                  "| Message | Result | Expected | Proposed | No change, and why |", "|---|---|---|---|---|"]
        for r in rows:
            cust = "" if r["customers"] == (None, None) else f" (Kunden: {r['customers'][0]} → {r['customers'][1]})"
            drops = "; ".join(f"{','.join(d['tasks'])}: {d['grund']}" for d in r["dropped"])
            lines.append(f"| {r['msg'][:90]} | {'✅' if r['ok'] else '❌'} | {fmt(r['expected'])} | "
                         f"{fmt(r['got'])}{cust} | {drops} |")
        lines.append("")
    if which == "all":
        (HERE / "report.md").write_text("\n".join(lines), encoding="utf-8")
        print("wrote eval/report.md")
    else:
        print("\n".join(lines[4:]))


if __name__ == "__main__":
    main()
