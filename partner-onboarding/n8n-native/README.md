# Onboarding cockpit, built only in n8n

The same onboarding cockpit as the Python version (`../app`), but built entirely in n8n: no Python API, no
Streamlit. Data in **n8n Data Tables**, rules in **Code nodes**, the AI through n8n's **Ollama + Basic LLM
Chain + Structured Output Parser** nodes, human approval through a **Wait node with a form**, tests wired for
**n8n Evaluations**, and the cockpit page served by n8n itself.

**Open the cockpit:** http://localhost:5678/webhook/onboarding-cockpit
**Reset demo data (before a demo):** `Invoke-RestMethod -Method Post http://localhost:5678/webhook/onboarding-einrichtung`

## The 5 workflows

| Workflow | Trigger | What it does |
|---|---|---|
| **F1 · Einrichtung** | manual or webhook | Creates 6 data tables and fills them: checklist (15 items from the handbook), 8 invented partners, their tasks, 50 test cases. Partner days count from today, so run it before a demo. |
| **F2 · Partner-Update → Vorschlag → Freigabe** | webhook `POST /webhook/onboarding-update` `{partner_id, nachricht}`; second trigger: Evaluations | Rules split the message and decide clear clauses; the AI is asked only about unclear ones; result is stored as a **proposal**; the workflow then **waits** until a person approves in a form (name required); only then the checklist, customer count and audit log change. `"nur_testen": true` returns the proposal without saving. |
| **F3 · Ampel berechnen** | called by F4 and F5 | Traffic light per partner, plain rules (same as `app/status.py`). |
| **F4 · Morgen-Bericht** | Mon–Fri 08:30, or manual | Red and orange partners to Telegram. |
| **F5 · Cockpit-Webseite** | webhook `GET /webhook/onboarding-cockpit` | HTML page: partners with traffic light and reasons, open proposals with approval link, a form to send a new update, the audit log. |

## Inside F2, step by step

1. **Eingang vorbereiten:** webhook body or one test case from `ob_testfaelle`.
2. **Checkliste laden:** the 15 items with their keyword lists, from a data table (head office can edit it in n8n).
3. **Regeln: Satzteile und Punkte (code):** split into sentences and clauses, find the items by keywords, then
   obstacle → *blockiert*, plan/question/"noch nicht" → no change, clear state → *erledigt*. Only clauses that
   are still unclear **and** in the past tense become questions for the AI.
4. **KI nötig?** If no question is left, the AI is skipped completely.
5. **KI: Ist der Punkt erledigt? (Basic LLM Chain + Ollama qwen2.5:3b + Structured Output Parser):** one small
   question per clause; answer `{begruendung, erledigt}`, temperature 0.
6. **Vorschlag zusammensetzen (code):** rule and AI decisions in message order, customer count by pattern,
   follow-on facts (permit → application done; customers → first visit done).
7. **Test oder echt? (Evaluation node):** test runs go to the comparison and metrics, real ones continue.
8. **Mit Checkliste abgleichen (code):** drop what is already so, and warn if customers are reported while a
   must-have item (insurance, permit, background checks, contract templates) is still open.
9. **Vorschlag speichern → Protokoll → Antwort:** the sender gets the proposal and the approval link at once.
10. **Warten auf Freigabe (Form):** the execution pauses until someone decides, with their name.
11. **Entscheidung auswerten → Protokoll → Status → Kundenzahl → Checkliste aktualisieren.**

## Tests

- `test/compare_rules.py`: the JavaScript rules give **identical** proposals to `app/updates.py` on all 50 test
  messages plus 3 extra ones (the AI replaced by the same fake answer in both).
- `test/compare_status.py`: traffic light and demo data identical to the Python version on 3 different dates.
- `test/run_n8n_eval.py`: the 50 messages through the live workflow (dry run): **47/50 correct, 0 wrongly
  proposed as done** ([eval_report.md](eval_report.md)). The Python version scores 46/50 on the same set; the
  difference is the model call (n8n's chain node vs. the Ollama client), not the rules. These 50 messages were
  used while building the rules, so this is not a blind score; the blind history is in `../README.md`.
- **n8n Evaluations:** F2 has an Evaluation Trigger on `ob_testfaelle` and sets two metrics per case
  (`korrekt`, `falsch_erledigt`). The Evaluations tab of a self-hosted community n8n asks you to register the
  instance once (free) before it runs.

## Files

- `code/*.js`: the logic, one readable source for the Code nodes (`rules`, `status`, `seed`, `page`).
- `build_workflows.py`: builds the workflow JSON from the JS files. `workflows/` is the repo copy with the
  Telegram chat ID as placeholder.
- `import_to_n8n.ps1`: import into the local container with your chat ID (kept in a temp folder only).

## Python version or n8n version?

Both work. The n8n version is easier to see and change for a non-developer: every step is a block, and the
checklist is a table. The Python version is easier to test in depth and to put under version control line by
line. In practice I'd keep the flow in n8n and move logic into code (Code nodes or an API) when it needs
serious testing; here the rules are tested against the Python version to get both.
