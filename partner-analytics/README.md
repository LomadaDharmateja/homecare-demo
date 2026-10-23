# Partner analytics assistant (HOMECARE demo, fictional data)

Head-office staff ask questions about the franchise network in German (or English), and get the answer,
a chart and how it was calculated. Every Monday a German report with early-warning alerts lands in Telegram.
The dashboard, report and alerts are in German; answers come back in the language of the question.

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

Examples: "Eröffnen Partner, die mit Freunden gegründet haben, schneller einen zweiten Standort?"
→ *Monate bis zum zweiten Standort: Niedrigste Werte: mit Freunden gegründet 17,0 Monate, danach als Paar
gegründet 27,0 Monate, danach allein gegründet 31,8 Monate.* Also "Welche 5 Standorte haben in den letzten
6 Monaten die meisten Kunden verloren?" or "Which locations are furthest below their business plan?"

## Accuracy

The model's step (question → query form) is tested on 55 hand-written questions. Once the form is right the
number is exact, because Python computes it.

| Set | Result | Note |
|---|---|---|
| Tuning (20, mostly English) | 20/20 | Used while improving prompt and rules, so optimistic |
| Final test (15, mostly English) | 14/15 (93%) | Was 13/15 when blind; see below |
| German tuning (10) | 10/10 | Added later; one miss here led to a new rule |
| **German test (10)** | **10/10** | Written together with the German tuning set, before any change; never tuned on |

**Disclosure:** the English final test is no longer blind. Its first run was 13/15. I then fixed one of the two
misses ("revenue versus plan for Bavaria": a named state was dropped when the model grouped by state; that was
a bug in a rule, not a model error). The remaining miss, "gained the most customers", is read as *new customers*,
which is a defensible reading. The German test was 10/10 before and after the changes.
Details: [eval/report.md](eval/report.md).

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
6. **German everywhere it is read**: German answers with German number format (1.234 €, 12,5 %), German notes
   in "So wurde gerechnet", a German weekly report. The number check on the AI summary had to learn German number
   format first: "12.345 €" would otherwise have been read as 12.345.
7. **"By state" lists were cut to 10 of 13 states** by the default limit. Groupings with a fixed number of groups
   (state, founder type, opening year) now show all of them unless the question asks for a number.

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
