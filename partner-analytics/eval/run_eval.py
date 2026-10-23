"""Score the question -> query-form step against hand-written expectations. Writes eval/report.md.

Only the planning step is scored: once the form is right, the numbers come from plain Python and are exact.
Usage: python eval/run_eval.py [tuning|final_test|all]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.ask import plan  # noqa: E402

HERE = Path(__file__).parent


def score(cases):
    rows = []
    for case in cases:
        t = time.time()
        try:
            spec, notes = plan(case["q"])
            got = spec.model_dump()
        except Exception as e:  # a crash counts as a miss
            got, notes = {"error": str(e)[:80]}, []
        wrong = {k: (v, got.get(k)) for k, v in case["expect"].items() if got.get(k) != v}
        rows.append({"q": case["q"], "ok": not wrong, "wrong": wrong, "rules": [n for n in notes if n.startswith("Regel")],
                     "seconds": round(time.time() - t, 1)})
    return rows


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    data = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    sets = ["tuning", "final_test", "german_tuning", "german_test"] if which == "all" else [which]
    lines = ["# Partner analytics: evaluation", "",
             "Scores the step where the local model (qwen2.5:3b) turns a question into the query form. "
             "A question counts as correct only if every expected field matches. Numbers are computed by Python "
             "from the form, so a correct form means a correct number.", ""]
    for name in sets:
        rows = score(data[name])
        ok = sum(r["ok"] for r in rows)
        ruled = sum(bool(r["rules"]) for r in rows)
        print(f"{name}: {ok}/{len(rows)} correct")
        lines += [f"## {name}: {ok}/{len(rows)} correct ({100 * ok // len(rows)}%)", "",
                  f"Rules corrected the model on {ruled} questions. Average time "
                  f"{sum(r['seconds'] for r in rows) / len(rows):.1f}s per question.", "",
                  "| Question | Result | Wrong fields (expected → got) |", "|---|---|---|"]
        for r in rows:
            wrong = "; ".join(f"{k}: {e} → {g}" for k, (e, g) in r["wrong"].items())
            lines.append(f"| {r['q']} | {'✅' if r['ok'] else '❌'} | {wrong} |")
        lines.append("")
    (HERE / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
