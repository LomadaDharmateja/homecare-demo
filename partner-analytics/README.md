# Partner analytics assistant (HOMECARE demo, fictional data)

Head-office staff ask questions about the franchise network in plain English or German, and get the answer,
a chart and how it was calculated. Every Monday a report with early-warning alerts lands in Telegram.

All figures are **invented** (55 locations, 24 months). Names of places are used only as labels.

## The idea in one sentence

**The AI only understands the question. Python calculates every number, and the answer sentence is built from
those numbers**, so the assistant cannot state a wrong figure, and every answer shows its query form for checking.

```
question ──► local LLM fills a typed query form ──► rules check the form ──► Python computes ──► answer + chart
             (metric, grouping, period, filters;     (names, trend words,      (pandas over       + "how this was
              fixed lists only, no SQL)               counts, sort direction)   SQLite)              calculated"

Monday 08:00 ──► n8n ──► /report/weekly ──► rules find alerts ──► LLM writes summary ──► Telegram + .md file
                                                                  (numbers checked, must lead
                                                                   with the most urgent alert)
```

## What it can answer

Revenue, costs, profit, customers, new customers, enquiries, hours, staff, cash, conversion rate, revenue vs.
business plan, number of locations, months to a second location, share of partners with a second location.
Grouped by location, state, founder type (solo / friends / couple), opening year or month, over the last
1, 3, 6 or 12 months, optionally compared with the period before.

Examples: "Do partners who founded with a friend open a second location faster?" (yes: 17 vs. 32 months),
"Which 5 locations lost the most customers in the last 6 months?", "Wie hoch ist die Conversion Rate nach Bundesland?"

## Accuracy

The model's step (question → query form) is tested on 35 hand-written questions. Once the form is right the
number is exact, because Python computes it.

| Set | Result | Note |
|---|---|---|
| Tuning (20 questions) | 20/20 | Used while improving prompt and rules, so optimistic |
| Final test (15 questions) | **13/15 (86%)** | Written at the same time, never tuned on |

The two final-test misses: "revenue versus plan for Bavaria" (grouped by state instead of filtering, a
bug in one rule) and "gained the most customers" (read as *new customers*). Details: [eval/report.md](eval/report.md).

## What I changed along the way, and why

1. **The model kept missing names** ("How many staff does Essen have?"). Names are now found by matching the
   question against the real list of locations and states. Code does that perfectly; a 3B model doesn't.
2. **Rules back up the model** for trend words ("develop" → monthly trend), counts ("top 3") and direction
   ("lost", "least" → lowest first). Each rule that fires is shown in "How this was calculated".
3. **The model's written explanations were unreliable** (it answered "No" to everything when asked to start
   with yes/no). The answer sentence is now built from the table: faster and never wrong.
4. **The first alert list had 32 alerts**: nobody reads that. New locations (first 18 months) normally run
   below plan with little cash, so they are only checked for serious cash burn. Cash alerts are graded by how
   many months the cash will last. Result: 7 alerts, with the location at real risk on top.
5. **A percentage change from a loss is meaningless** (−2,540 € → −61,787 € is not "+2,333 %"), so the
   plain difference is shown instead.

## Run it (PowerShell, from `homecare-demo\partner-analytics`)

```powershell
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt   # once
.\.venv\Scripts\python.exe data\generate_data.py                         # once: creates data\partners.db
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8001          # API for n8n
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.port 8502
.\.venv\Scripts\python.exe eval\run_eval.py                               # accuracy report
```

n8n: import `n8n/weekly_report_workflow.json`, set your Telegram chat ID and credential in the Telegram node,
then publish. "Run now (manual test)" sends the report immediately.

## Limitations

- Fictional data with planted patterns; real partner data will be messier (missing months, late bookings).
- The query form covers common questions only. Anything outside it gets a "could not understand" answer
  rather than a guess. That's deliberate.
- Production would need role-based access (a partner sees only their own figures), a connection to the real
  accounting and partner software, and a data-protection review.
