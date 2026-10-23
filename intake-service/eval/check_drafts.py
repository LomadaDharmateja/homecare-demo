r"""Check the drafted replies for the 20 final-test requests. Writes eval/drafts_report.md.

The field evaluation (run_eval.py) does not look at drafts. This script counts, per draft:
- written by the model or replaced by the safe code template (and why),
- reply in the customer's language,
- anything still promising a booking or asking the customer to call (should be 0: the guard catches these).
A person should still read the drafts in the report; a 3B model's wording is not always natural.

Run from intake-service/:  .\.venv\Scripts\python.exe eval\check_drafts.py
"""
import json
import sys
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVICE_DIR))

from app import agent, db, tools  # noqa: E402
from app.schemas import IntakeIn  # noqa: E402

db.DB_PATH = SERVICE_DIR / "data" / "eval_drafts.db"
db.DB_PATH.unlink(missing_ok=True)


def main():
    cases = json.loads((SERVICE_DIR / "data" / "final_test_requests.json").read_text(encoding="utf-8"))
    rows = []
    for case in cases:
        r = agent.process_request(IntakeIn(text=case["text"], channel=case["channel"]))
        draft = r["followup_draft"] or ""
        german = tools._looks_german(case["text"])
        template = draft == tools._template_draft(r, german, case["text"])
        right_language = tools._looks_german(draft) == (case["language"] == "de")
        leak = bool(tools.ECHOED_CALL.search(draft) or tools.PROMISE.search(draft))
        rows.append((case, draft, template, right_language, leak))
        print(f"case {case['id']}: {'template' if template else 'model'}, language {'ok' if right_language else 'WRONG'}"
              f"{', PROMISE LEFT' if leak else ''}")
    n = len(rows)
    lines = ["# Drafted replies: final test set", "",
             f"- Written by the model: **{sum(not r[2] for r in rows)}/{n}**; replaced by the safe template: "
             f"**{sum(r[2] for r in rows)}/{n}**",
             f"- Reply in the customer's language: **{sum(r[3] for r in rows)}/{n}**",
             f"- Drafts still promising something or asking the customer to call: **{sum(r[4] for r in rows)}/{n}**",
             "", "| # | Lang | Source | Draft |", "|---|---|---|---|"]
    for case, draft, template, _, _ in rows:
        lines.append(f"| {case['id']} | {case['language']} | {'template' if template else 'model'} | "
                     f"{draft.replace(chr(10), ' ').replace('|', '/')} |")
    (SERVICE_DIR / "eval" / "drafts_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[2:5]))


if __name__ == "__main__":
    main()
