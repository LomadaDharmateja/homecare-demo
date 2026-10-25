# HOMECARE intake demo

A small, local demo of automating customer-request intake for an everyday-help service
(shopping, transport, companionship, household help for elderly people). It runs in two styles:

- **Project 1, `intake-service/` (Python):** a FastAPI service where a local LLM agent (Ollama, `qwen2.5:3b`)
  picks from four predefined tools to classify a request, check for missing information, set a priority and
  draft a follow-up (written by code from the checked fields, in the customer's language). Everything goes to
  SQLite with a full audit log. A German Streamlit dashboard lets a human approve or reject every drafted reply.
  Nothing is ever sent automatically.
- **Project 2, `n8n/` (low-code):** two n8n workflows. **A** webhook → agent → Telegram alert if high urgency
  (plus a local `alerts.log` backup) → CSV log. **B** daily 08:00 check of overdue callbacks → summary file.

- **Project 3, `partner-analytics/`:** an assistant for head office. Ask questions about the franchise network
  ("Do friend-founded partners open a second location faster?") and get answer, chart and calculation trail.
  Plus a Monday report with early-warning alerts via n8n and Telegram. See [its README](partner-analytics/README.md).

- **Project 4, `partner-handbook/`:** a German-first assistant (English questions work too) that answers
  partners' questions only from the (fictional) partner handbook, with sources; says so when the handbook has
  no answer and collects those questions as knowledge gaps for head office. n8n workflow **D** offers it as a
  chat inside n8n. See [its README](partner-handbook/README.md).

- **Project 5, `partner-onboarding/`:** an onboarding cockpit for the first 90 days of new partners, using the
  handbook's checklist. Partner e-mails become **proposals** for checklist changes (rules first, the local model
  only for unclear sentences), and a person approves them, with a full audit log. Code alone runs the traffic
  light, for example "customer visits but no permit yet" or a permit forecast. n8n workflow **E** takes partner
  e-mails by webhook and sends a daily risk digest to Telegram. Blind test 8/10, never a wrong "done".
  See [its README](partner-onboarding/README.md).

All data is synthetic and everything runs locally, except the optional Telegram alert. That alert carries only
the case number, service and city, with no names or health details. See [EXPLAINER.md](EXPLAINER.md) for the full
walkthrough and [intake-service/eval/report.md](intake-service/eval/report.md) for accuracy.

**Portfolio page (German / English, with demo clips of every project):**
https://lomadadharmateja.github.io/homecare-demo/

**New here?** Open [`docs/walkthrough.html`](docs/walkthrough.html) in a browser: a plain-language tour that
follows four real requests through the whole pipeline.

**Accuracy** on a 20-case final test set: **90–95% of requests fully correct** (all six fields; 18/20 blind,
19/20 after one German fix, see EXPLAINER step 20), **6/6 urgent requests caught**. That's up from 54% at the first version: most of the gain came from letting
code check the model's extracted facts against the customer's own words.

## Demo day (after the one-time setup below)

```powershell
cd homecare-demo
powershell -ExecutionPolicy Bypass -File .\start_demo.ps1         # Docker+n8n, Ollama, all 4 APIs + 4 dashboards
powershell -ExecutionPolicy Bypass -File .\send_example.ps1 notfall  # also: fehlt | einkauf | unklar | urgent | "eigener Text"
# optional, before a demo: fresh example data (a backup of the old data is kept)
cd intake-service; .\.venv\Scripts\python.exe data\reset_demo.py; cd ..
cd partner-onboarding; .\.venv\Scripts\python.exe data\generate_data.py; cd ..
```

`start_demo.ps1` checks each service, starts only what isn't running (each in a minimized "HOMECARE …" window),
warms up both models and opens the four dashboards and n8n. Add `-NoBrowser` to start without opening tabs.
Close a "HOMECARE …" window to stop that part.

| What | Where |
|---|---|
| 1 Intake dashboard (Anfragen, Freigabe) | http://localhost:8501 |
| 3 Partner analytics (Frage an die Daten, Wochenbericht) | http://localhost:8502 |
| 4 Partner handbook assistant | http://localhost:8503 |
| 5 Onboarding cockpit (Übersicht, Updates & Freigabe, Protokoll) | http://localhost:8504 |
| n8n (workflows A, B, C, D, E) | http://localhost:5678 |
| APIs (docs pages) | :8000/docs, :8001/docs, :8002/docs, :8003/docs |

## Run it (PowerShell)

One-time setup (from the cloned `homecare-demo` folder): `cd intake-service; python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt; ollama pull qwen2.5:3b`

Then, from `homecare-demo\intake-service`, each in its own terminal:

```powershell
# 1. API (agent + database)
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000

# 2. Dashboard: http://localhost:8501
.\.venv\Scripts\python.exe -m streamlit run dashboard.py

# 3. n8n (first time only: creates the container; afterwards just `docker start n8n`)
docker run -d --name n8n -p 127.0.0.1:5678:5678 -v n8n_data:/home/node/.n8n -v "$((Resolve-Path ..\n8n\output).Path):/files" -e GENERIC_TIMEZONE=Europe/Berlin -e N8N_RESTRICT_FILE_ACCESS_TO=/files n8nio/n8n

# 4. Import + publish the workflows (first time only), then restart n8n
docker cp ..\n8n\homecare_intake_workflow.json n8n:/tmp/wf.json; docker exec n8n n8n import:workflow --input=/tmp/wf.json; docker exec n8n n8n publish:workflow --id=HomecareIntakeA1; docker exec n8n n8n publish:workflow --id=HomecareOverdueB; docker restart n8n

# 5. Send a request through n8n
Invoke-RestMethod -Uri http://localhost:5678/webhook/homecare-intake -Method Post -ContentType "application/json" -Body '{"text":"My father fell and cannot get up, he lives in Neuss. Please call me back now.","channel":"web_form"}'
```

Results: the record appears in the dashboard, `n8n\output\intake_log.csv` gets a line, and high-urgency
requests also get a line in `n8n\output\alerts.log` and a Telegram message. Evaluation: `.\.venv\Scripts\python.exe eval\run_eval.py`.

**Telegram (optional):**
1. Create a bot with @BotFather and send it one message.
2. In n8n, add a "Telegram API" credential named `HOMECARE Telegram bot` holding the token.
3. In the node "ALERT: Telegram message", replace `YOUR_TELEGRAM_CHAT_ID` with your chat ID (from
   `https://api.telegram.org/bot<TOKEN>/getUpdates`).

If Telegram isn't set up, that node fails quietly and the rest of the workflow still runs.

## Limitations

- Demo only: no authentication, no cloud deployment, no real CRM or email integration.
  Approving a draft changes its status; it does not send anything to the customer.
- Telegram is a cloud service. Production would need a data processing agreement, or a self-hosted channel.
- Synthetic data only (100 hand-written requests in three sets, English and German). Real messages will be
  messier, so expect lower accuracy than on the test set.
- The 3B model still makes mistakes, more often in German. Code checks its output against the customer's
  words, replies are written by code, and a human reviews every reply.
- Production would need a GDPR data-protection review, an EU AI Act risk classification, access control,
  retention rules and a real integration with the CRM and messaging channels.
