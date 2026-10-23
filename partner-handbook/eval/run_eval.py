"""Score the handbook assistant. Writes eval/report.md.  Usage: python eval/run_eval.py [tuning|final_test|all]

A question passes when:
- answerable: status is 'answered' or 'excerpt_shown', the expected file is cited, and every 'must' string
  appears in the answer;
- refuse: the assistant says the handbook doesn't cover it (status 'not_found');
- emergency: status 'emergency' and the answer contains 112.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import assistant  # noqa: E402

# Keep the evaluation out of the real question log.
assistant.LOG_DB = ROOT / "data" / "eval_questions.db"


def judge(case, r):
    files = [s["file"] for s in r["sources"]]
    text = r["answer"].lower()
    if case.get("refuse"):
        return r["status"] == "not_found", "should say it's not in the handbook"
    if case.get("emergency"):
        return r["status"] == "emergency" and "112" in text, "should start with 112"
    problems = []
    if r["status"] not in ("answered", "excerpt_shown"):
        problems.append(f"status {r['status']}")
    if case["source"] not in files:
        problems.append(f"source {case['source']} not cited (got {files})")
    missing = [m for m in case["must"] if not any(alt.lower() in text for alt in m.split("|"))]
    if missing:
        problems.append(f"missing {missing}")
    return not problems, "; ".join(problems)


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    data = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
    lines = ["# Partner handbook assistant: evaluation", "",
             "Local models: qwen2.5:3b (answers) and granite-embedding:278m (search). "
             "Questions were written before the assistant was built.", ""]
    for name in (["tuning", "final_test", "english_tuning", "english_test"] if which == "all" else [which]):
        rows = []
        for case in data[name]:
            t = time.time()
            r = assistant.ask(case["q"])
            ok, why = judge(case, r)
            rows.append((case, r, ok, why, time.time() - t))
        passed = sum(r[2] for r in rows)
        shown = sum(r[1]["status"] == "excerpt_shown" for r in rows)
        print(f"{name}: {passed}/{len(rows)}")
        lines += [f"## {name}: {passed}/{len(rows)} passed ({100 * passed // len(rows)}%)", "",
                  f"Average {sum(r[4] for r in rows) / len(rows):.1f}s per question. "
                  f"{shown} answers were replaced by the handbook excerpt because the check failed.", "",
                  "| Question | Status | Pass | Problem | Answer |", "|---|---|---|---|---|"]
        for case, r, ok, why, _ in rows:
            ans = r["answer"].replace("\n", " ").replace("|", "/")[:160]
            lines.append(f"| {case['q']} | {r['status']} | {'✅' if ok else '❌'} | {'' if ok else why} | {ans} |")
        lines.append("")
    (ROOT / "eval" / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
