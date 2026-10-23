# Partnerhandbuch-Assistent (HOMECARE demo, fictional handbook)

Franchise partners and their staff ask questions in German (or English) and get a short answer **from the
partner handbook only**, with the section, the responsible department and the date. If the handbook
doesn't cover it, the assistant says so and logs the question, so head office sees which topics are missing.

The handbook (10 chapters, 50 sections: onboarding, billing with the care insurers, emergencies, staff,
scheduling, quality, data protection, KPIs, marketing) is **invented for this demo**. Amounts and deadlines
are examples, not legal advice.

## How it works

```
Frage ──► Notfall-Wörter? ──yes──► "112 wählen" first (fixed text, no AI)
   │
   ▼
search the handbook: meaning (granite-embedding, multilingual) + exact words (BM25, German compounds)
   │  top 5 sections
   ▼
qwen2.5:3b answers ONLY from those numbered sections, cites them, or says found=false
   │
   ▼
code checks: cited sections exist? every number in the answer appears in a cited section?
   ├─ ok ─────────► answer + sources
   ├─ check failed ► show the handbook section itself (no unverified AI text)
   └─ not found ──► "steht nicht im Handbuch" + logged under "Wissenslücken"
```

Everything runs locally with Ollama. No question or answer leaves the laptop.

## Accuracy

Questions were written **before** the assistant was built: answerable ones (right source cited and key fact
in the answer), ones the handbook can't answer (must say so) and emergencies (must lead with 112).

| Set | Result |
|---|---|
| Tuning (17 questions) | 17/17. Used while improving, so optimistic |
| Final test (15 questions, never tuned on) | **14/15 (93%)**. All 3 unanswerable questions correctly refused, emergency correct |

The final-test miss: "Wie schnell muss ich auf eine Beschwerde reagieren?" got the same-day logging rule but
not the 2-working-day reply deadline. Full results: [eval/report.md](eval/report.md).

**Disclosure:** after the first run I let the test accept "5" as well as "fünf" (and similar), because a
correct answer ("5 Tage") was being marked wrong by my test, not by the assistant.

## What I changed along the way, and why

1. **German compound words broke the word search**: "Versicherung" didn't find
   "Betriebshaftpflicht**versicherung**". Word search now also matches parts of compounds.
2. **The model said "not in the handbook" although the right section was first.** It had to decide
   found/not-found *before* writing the answer (field order in the JSON form). Answer first, decision last fixed it.
3. **Number check knows number words**, so "fünftägige Schulung" supports the answer "5 Tage".
4. **Similarity scores can't tell answerable from unanswerable questions** (0.62–0.70 vs. 0.70+), so there is
   no score threshold; the model decides and code verifies.

## Run it (PowerShell, from `homecare-demo\partner-handbook`)

```powershell
python -m venv .venv; .\.venv\Scripts\pip install -r requirements.txt     # once
ollama pull qwen2.5:3b; ollama pull granite-embedding:278m                 # once
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.port 8503
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8002             # optional API: POST /frage
.\.venv\Scripts\python.exe eval\run_eval.py
```

The first start builds the search index (about 15 seconds); it is rebuilt automatically when the handbook changes.

## Limitations

- A 3B model sometimes gives incomplete answers; the cited section is always one click away.
- Real handbooks have tables, PDFs and versions. They would need a proper import and a review process
  (owner + date per section already exists for that reason).
- Production: access by role (partner vs. head office), a feedback loop with the handbook owners, and a
  decision on where the model runs (local server vs. an EU cloud with a data processing agreement).
