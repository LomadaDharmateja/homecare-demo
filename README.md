# HOMECARE intake demo

A small, local demo of automating customer-request intake for an everyday-help service
(shopping, transport, companionship, household help for elderly people). It runs in two styles:

- **Project 1, `intake-service/` (Python):** a FastAPI service where a local LLM agent (Ollama, `qwen2.5:3b`)
  picks from four predefined tools to classify a request, check for missing information, set a priority and
  draft a follow-up. Everything goes to SQLite with a full audit log. A Streamlit dashboard lets a human
  approve or reject every drafted reply. Nothing is ever sent automatically.
- **Project 2, `n8n/` (low-code):** two n8n workflows. **A** webhook → agent → alert if high urgency → CSV log.
  **B** daily 08:00 check of overdue callbacks → summary file.

All data is synthetic and everything runs locally. See [EXPLAINER.md](EXPLAINER.md) for the full
walkthrough and [intake-service/eval/report.md](intake-service/eval/report.md) for accuracy.

**Accuracy** on a 20-case test set never used for tuning: **90% of requests fully correct** (all six fields),
**6/6 urgent requests caught**. That's up from 54% at the first version: most of the gain came from letting
code check the model's extracted facts against the customer's own words.

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
requests also get a line in `n8n\output\alerts.log`. Evaluation: `.\.venv\Scripts\python.exe eval\run_eval.py`.

## Limitations

- Demo only: no authentication, no cloud deployment, no real CRM, email or Telegram integration.
  Approving a draft changes its status; it does not send anything.
- Synthetic data only (100 hand-written requests in three sets, English and German). Real messages will be
  messier, so expect lower accuracy than on the test set.
- The 3B model still makes mistakes, more often in German. Drafted replies sometimes imply a booking or a
  time. Rule-based guardrails catch some errors, and a human reviews every reply.
- Production would need a GDPR data-protection review, an EU AI Act risk classification, access control,
  retention rules and a real integration with the CRM and messaging channels.
