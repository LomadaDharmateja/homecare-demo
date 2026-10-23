# Onboarding-Cockpit (HOMECARE demo, fictional partners)

New franchise partners have 90 days from contract to their first ten customers. In between: company
registration, insurance, a five-day training, the permit from the authority (4–8 weeks), an office, the first
helpers. Partner management follows this today with e-mails, phone calls and a spreadsheet, and often notices
a problem late (permit applied for too late, customer visits before the insurance exists).

This cockpit keeps the **checklist from the partner handbook** (project 4) for each new partner and shows a
traffic light. Partners keep writing e-mails as they do today. The local AI turns each e-mail into a
**proposal** for checklist changes, and a person approves it. Code alone calculates the risks.

## What it does

```
Partner e-mail ──► n8n webhook ──► local API: which checklist tasks does each sentence mention? (word lists)
                                       │
                                       ▼
                          clear wording? ── yes ──► rule decides: obstacle → blocked, plan/question → no change,
                                       │                          "abgeschlossen / ist online / liegt vor" → done
                                       no
                                       ▼
                          qwen2.5:3b answers one small question: "is THIS task done according to THIS clause?"
                                       │   (only allowed if the clause is in the past or describes a state)
                                       ▼
                          proposal: changes + the sentence each is based on + who decided (rule or AI)
                                       │
                                       ▼
                          a person approves (all or some) or rejects ──► checklist + audit log
                                                                          (who, when, before, after, evidence)
Mon–Fri 08:30, n8n ──► GET /risiken ──► Telegram: critical partners first, pending approvals
```

**Rules that fire without any AI** (all in [app/status.py](app/status.py)):
- 🔴 **Customer visits without the preconditions.** The handbook says permit, insurance, background checks and
  contract templates come first. If a partner reports customers and one of these is missing, this is the top
  warning, also directly on the proposal.
- 🔴 A blocked or overdue task that is a precondition for customers.
- 🟠 Any other overdue or blocked task, with the person responsible.
- 🟠/🔴 **Permit forecast.** Application date + 4 to 8 weeks (handbook). If it can arrive after day 90, the
  10-customer target is at risk. If the application hasn't been filed yet, the forecast starts today.
- 🟠 Customer target. Day 61–90 with more new customers needed than one every two days.

The demo has 8 invented partners on day 8 to 96, each showing one situation (see
[data/generate_data.py](data/generate_data.py)). Names are invented, cities only.

## Accuracy

The test messages were written by me **before** each version was built. A message counts as correct only if
the final proposal has exactly the expected changes and customer count. **"Wrongly done"** is the dangerous
error: a task proposed as done that the partner didn't report as done.

| Version | Set | Result | Wrongly done |
|---|---|---|---|
| v1: model reads the whole message | tuning (15) | 7/15 | 0 |
| v2: model judges each sentence + task | tuning | 15/15 (tuned) | 0 |
| v2 | final test (15), **blind** | **11/15** | 0 |
| v2 + a prompt change | fresh test 2 (10), **blind** | **6/10** | 0 |
| v3: rules first, model only for unclear clauses (current) | fresh test 3 (10), **blind** | **8/10** | 0 |
| v3 | all 50 messages (40 no longer blind) | 46/50, details in [eval/report.md](eval/report.md) | 1 (the arguable "Antrag liegt seit sechs Wochen" case below) |

In every blind run the misses were **missed updates, never a wrong "done"**. They show up as "no change", the
person approving still reads the original message, and can tick a task by hand ("Punkt manuell ändern").

Remaining blind misses (test 3): "Unsere erste Kundin betreuen wir seit Mittwoch" (first customer found, but
"erste Kundin" not read as the count 1), and "Ich konnte an der Startschulung nicht teilnehmen, weil ich krank
war" (read as "not yet", not as blocked).

**Disclosures:** I wrote all test messages myself, so they share my phrasing, and real partner e-mails will be
messier. After each blind run I fixed things and then wrote a new set instead of re-using the old one, so each
blind number belongs to one version. Two expectations in test 2 are arguable ("Unser Antrag liegt seit sechs
Wochen beim Landesamt" implies the application was filed; I had expected no change). I kept them as misses.

## What I changed along the way, and why

1. **v1 → v2:** the 3B model reading the whole message copied checklist titles as "quotes" and picked wrong
   tasks. The code checks caught all of that (nothing wrong was proposed), but it found only 7 of 15 updates.
   Now code finds the tasks per sentence and the model judges one small question at a time.
2. **German compound words, three ways round:** "ug" (for UG, a company form) matched inside
   "Führungszeugnis"; "werbung" (advertising) inside "Be**werbung**en" (job applications); "konto" didn't match
   "Geschäfts**konto**". Short words now match only as whole words or at a word's start or end, and a few are
   marked "start of word only".
3. **Generic words:** "Die Führungszeugnisse für beide Helfer liegen vor" was also read as "helpers hired".
   A generic word ("Helfer", "Kunde", "Software") now only counts when no more specific task is in the sentence.
4. **A prompt change made it worse** (tuning 15 → 13, fresh test 6/10), so I reverted it. Prompt tweaks on a
   3B model moved the errors around instead of removing them.
5. **v3:** clear wording is decided by rules. The model may only say "done" when the clause is in the past or
   describes a state. Before that it marked "Die Startschulung machen wir im Dezember" as done.
6. **Dates:** "der Antrag ist raus, wir haben ihn gestern eingereicht": the date is read from the whole sentence.

## Run it (PowerShell, from `homecare-demo\partner-onboarding`)

```powershell
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt     # once
.\.venv\Scripts\python.exe data\generate_data.py                          # before a demo: resets the 8 partners
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.port 8504
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8003             # API for n8n
.\.venv\Scripts\python.exe eval\run_eval.py all                            # about 1 minute
```

API: `GET /partner`, `POST /updates {partner_id, nachricht}`, `GET /vorschlaege`,
`POST /vorschlaege/{id}/entscheidung {freigeben, von, punkte}`, `GET /risiken`, `GET /protokoll`.

### n8n workflow E

`n8n/onboarding_workflow.json` (repo copy with placeholders; `build_workflow.py` writes it, with your chat ID for
the import). Two entry points:
- `POST http://localhost:5678/webhook/partner-update` with `{"partner_id": 3, "nachricht": "..."}` → proposal.
  In production this would be an e-mail trigger on the partner-management inbox.
- Mon–Fri 08:30 → risk digest to Telegram (or open the workflow and click "Execute workflow").

## Limitations

- Word lists are hand-made for 15 tasks. A new checklist task needs its words added.
- One partner per message: the partner is known from the sender's address, not guessed by the AI.
- Messy real e-mails (signatures, quoted earlier mails, typos) are not tested.
- The customer count only reads "N Kunden" / "N customers" in a sentence that isn't a plan.
