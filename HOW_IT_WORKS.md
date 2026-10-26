# How it works, step by step (all 5 projects)

This document goes through each project one step at a time. For every step it says:

- **who does it**: 🟧 AI (the local model), 🟩 code (fixed Python rules), or 🟦 a person;
- **how it works inside**: the actual logic, with the file and function name;
- **why it is built that way**: the intuition, which is what you explain in an interview.

The diagrams for the same steps are at https://lomadadharmateja.github.io/homecare-demo/workflows.html.

**The one idea behind all five projects:**
> The AI only reads and understands language. Code checks what the AI said and does all decisions and
> calculations. A person approves anything that changes data or goes to a customer. Every step is logged.

A 3B model on a laptop is good at *reading* ("this person wants a lift on Monday in Krefeld") but bad at
*judging* ("is this priority 2 or 3?") and at *arithmetic*. So each project gives the model as small a job as
possible, and puts a code check right after it.

---

## Project 1: Customer intake (`intake-service/`)

### The case for it

**The problem today:** customer requests arrive by web form and email, written freely by elderly people or
their relatives, in German or English, with typos, long stories and missing details. Every request has to be:
read, sorted (what kind of help, which city, which day), checked for what is missing, ranked by urgency, and
answered. This is done by hand, so:
- an urgent case ("my father fell") sent on a Sunday evening can sit in the inbox until Monday morning;
- staff spend time on reading and typing instead of on customers;
- callbacks get forgotten, because nobody sees which ones are overdue;
- there is no record of who decided what and why.

**How it is solved:** every request goes through the same automatic first pass in a few seconds. The AI reads
the text and fills a form; code checks the form, sets the priority and writes a reply draft. Urgent cases go
to the team's phone on Telegram at once. Staff open one dashboard with a sorted list and a draft ready for
each case: they read, fix if needed, approve. Every morning, a list of overdue callbacks is created
automatically.

**What gets automated:** reading, sorting, the missing-information check, prioritising, the first reply draft,
the urgent alert, the CSV log and the overdue reminder. **What stays human:** the approval of every reply,
and the actual care decisions.

**End-to-end example:**
> Sunday, 21:40, web form: *"Mein Vater ist gestürzt und kommt nicht hoch. Kann heute Abend jemand in Siegen
> bei ihm bleiben? Bitte rufen Sie mich sofort zurück."*
1. n8n receives it and calls the API; the form gets "received" back immediately.
2. AI reads it: companionship, "heute Abend", Siegen, callback yes.
3. Code checks: "heute Abend" and "Siegen" are in the text ✓, "rufen … zurück" is a call word ✓.
4. Emergency words "gestürzt", "kommt nicht hoch" → **priority 1**, whatever the AI said.
5. Draft (German, by code): "…Wir behandeln Ihre Anfrage vorrangig. Bei einem medizinischen Notfall rufen
   Sie bitte sofort 112 an. Eine Kollegin oder ein Kollege ruft Sie zurück."
6. Telegram to the team: "HOMECARE: urgent request #12, Service: companionship, City: Siegen, Callback
   requested: yes. Details and draft reply: open the dashboard." (only minimal data, no name or full text)
7. A colleague calls back within minutes, then approves the draft in the dashboard. All steps are in the log.

**Why use AI here, and not plain automation?** Plain automation (n8n alone, keyword rules, a strict form)
needs structured input. Customers do not write structured input: "Mama", "my mum", "meine Mutter";
"Monday at half nine", "Mo. 9:30", "übermorgen"; cities with typos. Covering all of that with rules never ends,
and a strict form with ten required fields scares off exactly the elderly customers HOMECARE serves. An LLM
reads free text in any wording and language. **But an LLM alone is not trusted either:** it sometimes invents
a date or a city. So the AI only *reads*; code *checks and decides*; a person *approves*.

**Why an agent?** An agent means the model chooses *which step to run next* from a list of tools, instead of
following a fixed order. Here it shows the pattern a growing intake system needs: the model chooses, code
runs only whitelisted tools, every decision is logged, and guardrails force the steps that must always run.
To be honest: for today's 4 tools the order is almost always the same, so a fixed pipeline would work too,
and the guardrails make sure the result is the same either way. The agent becomes really useful when more
tools are added whose use depends on the case: for example "look up existing customer", "check helper
availability in that city", "translate", "ask for missing details" — steps that some requests need and others
do not. Then the model picks what this request needs, and the same safety rules still apply.

**The chain:** n8n webhook → `POST /intake` → save → agent loop (4 tools) → record + audit log → person approves
the reply in the dashboard. In parallel, n8n sends a Telegram alert for urgent cases and writes a CSV line.

Running example (from `agent.py`):
> "My mum needs a lift to the dentist on Monday at 9:30. She lives in Krefeld. Please call me back in the morning."

### Step 1: The request comes in 🟩
`main.py` → `process_request()` in `agent.py`.
The text is saved in SQLite (`requests` table) with the time in UTC, and the first audit line `received` is written.
**Why save first:** if anything fails later, the request is still there. Nothing gets lost.

### Step 2: The agent picks a tool 🟧 (with code limits)
`agent.py` → `choose_next_tool()`. Yes, the agent has a prompt. This is it (`PLANNER_PROMPT`):

```
You coordinate the intake of a customer request for a home-help service.
Choose the next tool to run, or "finish" when the record is complete.
A complete record has: extracted fields, checked missing information, a priority, and a drafted
follow-up message for staff to approve. Each tool can run only once.

Tools:
- extract_fields: Read the request and extract the structured fields. Must run first.
- check_missing_info: Verify which information staff still need from the customer.
- draft_followup: Draft a reply to the customer for a human to approve.
- set_priority: Assign a work priority (1 = handle first, 5 = can wait).
```

Along with it, the model gets the customer's text and the progress so far ("tools already run", "fields found").
It must answer with JSON only: `{"tool": "...", "reason": "..."}`.

**How the tool choice is controlled:** the call to Ollama includes a JSON schema in which `tool` is a fixed list
(an *enum*) of only the tools that have **not run yet**, plus `finish`. So the model cannot invent a tool, run
one twice, or write free text. Python then runs the chosen function (`tools.run_tool`). The model never runs
anything itself.

The loop repeats up to **4 times** (`MAX_STEPS = 4`).

**Three guardrails in code:**
1. If the model does not pick `extract_fields` first, code overrides it, because nothing works without the
   extracted fields. The override is logged as "guardrail override".
2. If the model says `finish` early, code runs the missing tools anyway. Every record needs a priority and a
   draft. This happened in testing: the model chose "finish" while its own reason said a draft was still needed.
3. If extraction fails completely, the request gets **priority 1** and "please check manually". It goes to
   the top of the list, never to the bottom.

**Honest point for the interview:** for this task the order is almost fixed, so the agent's freedom is small on
purpose. I kept the agent loop to show the pattern (the model chooses, code runs only whitelisted functions,
everything is logged) and the guardrails around it. For a fixed task like this one, a simple fixed pipeline
would also work in production. An agent is worth it when the right steps really differ from case to case.

### Step 3: Tool `extract_fields`. The AI reads the text 🟧
`tools.py` → `extract_fields()`. This tool **contains a second prompt** (`EXTRACTION_PROMPT`):
- what each field means, e.g. "transport = driving the person themselves somewhere";
- "urgency high = safety or health risk, or help needed today";
- "callback_requested: true only if the person explicitly asks to be called";
- four invented worked examples (one German).

The model must fill this form (`ExtractedFields` in `schemas.py`). Every field with a fixed list is an enum:

| Field | Allowed values | Krefeld example |
|---|---|---|
| service_type | shopping, transport, companionship, household, other | transport |
| when_needed | the customer's own words, or null | "Monday at 9:30" |
| urgency | low, medium, high | medium |
| callback_requested | true / false | true |
| preferred_contact_time | morning, afternoon, evening, null | morning |
| location | city as written, or null | Krefeld |
| summary | one German sentence | (rebuilt by code, see step 4) |

Settings: `temperature 0`, so the same input gives the same output, and `num_predict 400`, a hard length limit,
because a small model once got stuck in a loop.

**Why the field order matters:** the model writes `when_needed` *before* `urgency`. It first copies the time
words and then decides urgency with those words already in front of it.

### Step 4: Check against the customer's own words 🟩
`tools.py` → `ground_in_text()`. This is the "grounding check". **Idea:** the model is good at finding facts,
but sometimes it *invents* or *misspells* them. So every fact must be backed by the original text. Plain
Python, no AI:

| Field | Check | Example |
|---|---|---|
| when_needed | Every word of the phrase must appear in the text (fuzzy match, ≥ 80 % similar, `difflib`). Vague phrases ("next year", "irgendwann") are removed. | Model said "tomorrow" but the text never says it → removed. |
| when_needed (backstop) | If it is empty now, a fixed list of day/time phrases is searched in the text (today, Monday, 9:30, heute Abend, …). | Model missed "Freitag" → code finds it. |
| location | The city must appear in the text. If not, it is snapped to the closest word the customer wrote (≥ 75 % similar). "near the station" is not a city → removed. | Model wrote "Henne" → corrected to "Herne". |
| callback_requested | Must have a call word in the text (call, ring, anrufen, Rückruf…). | Model said true, no call word → false. |
| preferred_contact_time | There must be a call/reach word. If the call sentence names exactly one time of day, the customer's word wins. | "call me in the evening", model said morning → evening. |

Then code **rebuilds the summary** (`_code_summary()`). The model's German summaries were sometimes garbled
or contained the customer's name. The code version only uses checked fields and relation words, never names:
> "Fahrdienst für Mutter in Krefeld, „Monday at 9:30“. Rückruf gewünscht (vormittags)."

**Every correction is kept in the audit log** as `grounding_corrections`: what the model said and what code
changed it to. So you can always see where the AI was wrong.

### Step 5: Tool `check_missing_info`. What is missing? 🟩
Pure rules: no city → ask for `location`; no concrete day → `date`; service `other` → `details`.
**Why not the AI:** in the first evaluation the model judged "is something missing?" correctly only 20 % of the
time. But it reliably *extracts* whether a city or day was mentioned. So: AI extracts, code decides.
Krefeld example: nothing missing.

### Step 6: Tool `set_priority`. How urgent? 🟩
Pure rules, so staff can predict and explain the order:

| Urgency | With callback | Without callback |
|---|---|---|
| high | 1 | 1 |
| medium | 2 | 3 |
| low | 4 | 5 |

Before that, **safety floors** that can only *raise* urgency, never lower it:
1. **Emergency word list:** fall, can't get up, not breathing, chest pain, bleeding, stroke, out of insulin,
   gestürzt, Atemnot, … → always high, whatever the model said. Checked on all 100 test requests: no false alarm.
2. "today / tonight / heute / sofort" in the time words → high.
3. A concrete day with urgency low → at least medium.

**Why only raise:** missing an urgent case is much worse than handling a normal one a bit early.
Krefeld example: medium + callback → **priority 2**.

### Step 7: Tool `draft_followup`. Reply draft 🟩 (by default)
`_template_draft()`. Code writes the reply from the checked fields, in the customer's language (code detects
German by common words):
> "Hello, thank you for your message. You are looking for a lift in Krefeld (Monday at 9:30). A colleague will
> call you back in the morning. — Your HOMECARE team"

Rules built in: it asks for missing information, adds "call 112" only if the case is urgent **and** someone is
hurt or ill, and **never promises** anything (no booking, no time, no price), because nothing is booked yet.

There is also an AI mode (`DRAFT_MODE=model`) with its own prompt. A guard checks the model's text for promises
("we will", "confirmed", "kostenlos", a € amount) or "call me" copied from the customer. If it finds one, it
falls back to the template. **Why template is the default:** on the final test the 3B model's drafts needed
editing in 7 of 13 cases. A bigger model could change that.

### Step 8: Record, audit log, person 🟦
Every agent decision and every tool call is saved in `audit_log` (input and output as JSON). The draft gets
status `pending_approval`. In the Streamlit dashboard a person approves or rejects it. **There is no send
function in the code at all.** Approving only changes a status.

Also: the model never writes SQL. All SQL is fixed code in `db.py` with parameters.

### n8n around it
- **Workflow A:** Webhook → HTTP call to `/intake` → *Respond to Webhook* (answers the form right away) → two
  parallel paths: IF urgency = high → Telegram + line in `alerts.log`; and always a line in `intake_log.csv`.
- **Workflow B:** every day at 08:00 → `GET /overdue` (callback requested, older than 24 h, not handled) → if
  the count > 0, write a summary file.

### Accuracy (`eval/report.md`)
Final test (20 requests never looked at while building): **19/20 fully correct**, urgent cases **6/6**.
The first version scored 54 %. Better code checks raised it to 90 %, not a bigger model.

---

## Project 2: Partner analytics (`partner-analytics/`)

### The case for it

**The problem today:** HOMECARE has many franchise locations, each reporting monthly numbers (revenue, costs,
customers, cash). Management has questions like "Which locations lost customers?", "Is anyone running out of
cash?", "Do partners who start with a friend grow faster?". Today someone exports data and builds an Excel
sheet for each question, which takes hours or days, so many questions are never asked. Problems (a location
burning cash) are noticed late, when someone happens to look.

**How it is solved:** two parts.
1. **Ask in plain words:** management types the question in German or English and gets the answer in seconds,
   with the table and a line saying exactly what was calculated.
2. **Weekly report without asking:** every Monday at 08:00, n8n triggers a check of all locations. Rules find
   the problems, the report arrives on Telegram and as a file, most urgent location first.

**What gets automated:** turning a question into a calculation, the calculation itself, and the weekly
check of every location. **What stays human:** deciding what to do about a struggling partner.

**End-to-end example:**
> "Welche 5 Standorte haben in den letzten 6 Monaten die meisten Kunden verloren?"
1. AI fills the form: metric customers, by location, last 6 months, growth yes, sort ascending, limit 5.
2. Code checks the form: "verloren" → sort ascending ✓, "5 Standorte" → limit 5 ✓.
3. Pandas compares the last 6 months with the 6 before, for every location.
4. Code writes: "Kunden: Stärkster Rückgang: Standort A −18,2 %, danach …" plus the table and
   "computed as: Kunden, nach Standort, letzte 6 Monate, Veränderung zum Zeitraum davor".

**Why use AI here, and not plain automation?** A dashboard with fixed charts only answers the questions
someone thought of in advance. Every new question would need a developer or an analyst. The AI turns any
wording ("lost the most", "größter Rückgang", "worst 5") into the same form. **Why not let the AI calculate or
write SQL?** Language models are bad at arithmetic and can write wrong queries that *look* right; a wrong
number in a management meeting destroys trust. So the AI only fills a form from fixed lists, and Python
calculates. A correct form always gives a correct number.

**Why not an agent?** The steps are always the same: understand the question → calculate → write the
answer. When the order never changes, a fixed pipeline is simpler, faster and easier to test. Knowing when
*not* to use an agent is part of the job. An agent would make sense if questions needed several different
lookups chained together ("compare the worst locations with their marketing spend and staff turnover").

**The chain:** question → 🟧 AI fills a query form → 🟩 code corrects the form → 🟩 pandas calculates →
🟩 code writes the answer sentence → table + "computed as" shown under it.

### Step 1: The AI fills a query form 🟧
`ask.py` → `plan()`. Prompt (`PLANNER_PROMPT`): "You turn a manager's question into a query form. **You never
calculate anything.** Pick values only from the allowed lists," with 4 examples. The form (`QuerySpec` in
`engine.py`):

| Field | Allowed |
|---|---|
| metric | revenue, costs, profit, customers, cash, conversion_rate, … (14 options) |
| group_by | none, location, state, founder_type, opening_year, month |
| period | last_month, last_3_months, last_6_months, last_12_months, all |
| growth | true/false (compare with the period before) |
| state / location / founder_type | filters, or null |
| sort, limit | asc/desc, 1–60 |

**Why a form and not SQL:** the model cannot write a wrong or dangerous query. It can only pick from lists.
And a correct form always gives a correct number, so we only need to check the form.

### Step 2: Code corrects the form 🟩
- **Names:** "Muenchen Ost" is snapped to the real "München-Ost" (fuzzy match). A name is **kept only if the
  user actually wrote it**. Small models copy names from the prompt examples (e.g. "Bayern").
- **Backstop rules** (`_backstops()`) for the model's common mistakes, each written into the notes the user sees:
  - "lost / least / worst" → sort ascending; "most / top / best" → descending;
  - "develop / trend / over time" → group by month, last 12 months;
  - "changed / compared / grew" → growth = true;
  - "Top 5 locations" → limit 5;
  - a city named in the question → filter on that location.

### Step 3: Python calculates 🟩
`engine.py` → `run_query()`. Pandas over the SQLite data. Inside:
- *flows* (revenue, costs, hours) are **added** over months; *stocks* (customers, staff, cash) are **averaged**
  over months;
- ratios (conversion rate, vs. plan) are recalculated from the sums, never averaged;
- growth compares with the same-length period before. If the earlier value was 0 or negative, the % is left
  out, because it would be misleading.

### Step 4: The answer sentence 🟩
`answer_text()` builds the sentence **from the result table**, so it cannot contain a wrong number. Under every
answer the form is shown in words ("Kunden, nach Standort, letzte 6 Monate, Veränderung zum Zeitraum davor").
A person can check exactly what was calculated.

### Step 5: Weekly report (n8n workflow C, Mondays 08:00) 🟩 + 🟧
`report.py`:
1. **Rules find the problems** (`build_alerts()`): cash burn (costs above revenue in ≥ 3 of 4 months, and cash
   lasts ≤ 6 months → red), losing ≥ 10 % customers, ≥ 15 % below business plan, strong growth ≥ 25 %.
   New locations (first 18 months) are only checked for cash burn, because running below plan is normal for
   them. That cut the list from 32 alerts to 7 useful ones.
2. **The AI only writes 2–3 summary sentences** from these facts.
3. **Code checks the AI's text:** every number in it must appear in the facts, and the first sentence must
   name the most urgent location. If not, a template sentence is used instead, and the report says why.

### Accuracy
Final test 14/15, German test 10/10. "Correct" means every field of the form is right.

---

## Project 3: Partner handbook assistant (`partner-handbook/`)

### The case for it

**The problem today:** franchise partners and their staff have questions every day: "By when do I bill the
care insurance?", "May a helper accept a gift?", "What do I do if a customer doesn't open the door?". The
answers are in a long partner handbook, but nobody reads 10 chapters to find one sentence. So they call or
email head office. Head office answers the same questions again and again, answers differ depending on who
picks up, and nobody knows which topics the handbook explains badly.

**How it is solved:** a chat assistant that answers **only from the handbook**, in 1–3 sentences, always
with the chapter and section as the source. If the handbook does not cover it, it says so and logs the
question, so head office sees which topics are missing. Emergency questions get "call 112" first, from a
fixed text.

**What gets automated:** finding the right section, writing a short answer, and collecting the gaps in the
handbook. **What stays human:** head office answers what the handbook does not cover, and keeps the handbook
up to date.

**End-to-end example:**
> Partner: "Darf eine Alltagshelferin ein Geschenk von einer Kundin annehmen?"
1. Search (meaning + exact words) finds the section *Personal – Geschenke* and 4 others.
2. AI answers only from these: "Nein, … ausgenommen kleine Aufmerksamkeiten bis zu 10 Euro." Source: [2].
3. Code checks: source [2] exists ✓, the number 10 is in that section ✓, long enough ✓.
4. Partner sees the answer + "Quelle: 05_personal.md – Geschenke, Stand …".

**Why use AI here, and not plain automation?** A keyword search returns whole documents, not answers, and
fails when the partner uses other words than the handbook ("present" vs "Aufmerksamkeit"). A classic FAQ bot
needs every question written down in advance. The AI understands the question in any wording or language and
writes a short answer. **Why not just ChatGPT?** A general chatbot answers from general knowledge and invents
rules that are not HOMECARE's. And the handbook would leave the company. Here the model runs locally, only
sees the found sections, must cite them, and code checks every number against the source.

**Why not an agent?** The steps are always the same (search → answer → check). This is "RAG": retrieval
followed by generation. An agent would make sense if the assistant also had to look things up elsewhere, for
example in the partner's own data ("How many hours did my team work this month?").

**The chain:** question → 🟩 emergency check → (English? 🟧 translate) → 🟩 search → 🟧 AI answers only from
the found sections → 🟩 check → answer with source, or "not in the handbook" + log.

### Step 1: Split the handbook 🟩
`index.py` → `load_sections()`. 10 Markdown files, cut at every `## ` heading. Each section keeps its
document title, owner and date, used for the citation.

### Step 2: Search, two ways combined 🟩 (+ embedding model)
`Index.search()`:
- **Meaning search:** every section is turned into a vector by `granite-embedding:278m` (cached; recomputed only
  if the handbook changes). The question becomes a vector too, and cosine similarity finds sections with the
  same *meaning* ("Geschenk" ≈ "Aufmerksamkeit").
- **Word search (BM25):** classic keyword scoring. It finds exact terms like "Pflegekasse" or "Entlastungsbetrag". German
  compounds are handled: "Versicherung" also hits "Betriebshaftpflichtversicherung".
- **Combined** with reciprocal rank fusion: each section scores 1/(60 + rank) in both lists, and the top 5 win.

**Why both:** meaning search alone misses exact terms and numbers. Word search alone misses other wording.

### Step 3: Emergency first 🟩
If the question contains "bewusstlos, atmet nicht, Brustschmerz, unconscious…", the fixed text **"call 112"**
comes first, before any AI. The emergency section of the handbook is always included.

### Step 4: English questions 🟧
The handbook is German, so an English question is translated to German first, with a fixed glossary
("utilisation = Auslastung", "mileage allowance = Kilometergeld"). Without the glossary the model invented
words like "Zieldurchnutzung". The answer stays in English.

### Step 5: The AI answers, only from the excerpts 🟧
Prompt (`SYSTEM`): "Answer **only** from the numbered excerpts. Give the numbers of the excerpts you used. If
the answer is really not there: found=false. **Never guess.**" The answer form is
`{answer, sources, found}`. `found` comes **last**, so the model decides after writing, not before.

### Step 6: Code checks the answer 🟩
- Do the cited excerpt numbers exist?
- Does **every number** in the answer (deadlines, amounts, %) appear in a cited section? Number words count too
  ("fünftägig" = 5).
- Is the answer at least 4 words? "Verboten" alone drops the exception "bis 10 Euro".

If a check fails, the model's text is **not shown**. The handbook section itself is shown instead
("The handbook says: …").

### Step 7: Not found → knowledge gap 🟩
"Not in the handbook, please contact head office" + the question is logged. The dashboard shows head office
which topics are missing from the handbook. 👍/👎 feedback is logged too.

### Accuracy
Final test 14/15, English test 10/10. The "not in handbook" questions were correctly refused.

---

## Project 4: n8n workflows (`n8n/` + each project's `n8n/` folder)

### The case for it

**The problem today:** even when the logic exists, someone must *start* it and *move the results* to people:
check overdue callbacks every morning, send the weekly report every Monday, forward an urgent case to the
on-call phone at night, copy every request into a list. Done by hand, this is forgotten on busy days, and
every new connection (a new form, email, Telegram) means custom code that only a developer understands.

**How it is solved:** n8n workflows connect triggers (a form is sent, it is 08:00, a chat message arrives) to
the local APIs and to where people work (Telegram, files). Each workflow is a visible chain of blocks.

**End-to-end example:** Monday 08:00 → workflow C calls `/report/weekly` → the report arrives in the
management Telegram chat ("Am dringendsten ist Standort X: Kosten über Umsatz in 4 der letzten 4 Monate…") and
is saved as a file. Nobody had to remember to do it.

**Why n8n and not code, and why no AI in n8n?** n8n is made for "when X happens, do Y, then tell Z", it has
ready connectors (webhooks, Telegram, email, Google Sheets, CRMs), and a non-developer can open a workflow and
see what happens. The AI and checking logic stays in tested Python code, so n8n only moves data and every
block is easy to understand. This split is also what the job description asks for: workflows in
n8n/Make/Zapier, plus APIs and webhooks.

### What each workflow does

n8n is the **plumbing**: when something happens (webhook, schedule, chat), call the local API, then route the
result (IF), notify (Telegram) and store it (file). All the AI and checking logic sits *inside* the API, so
n8n stays simple and every workflow can be read by a non-developer.

| Workflow | Trigger | Does |
|---|---|---|
| A: intake | Webhook (form/email) | /intake → answer the form → urgent? Telegram + alerts.log; always CSV line |
| B: overdue | daily 08:00 | /overdue → if any: summary file |
| C: weekly report | Monday 08:00 | /report/weekly → Telegram + .md file |
| D: handbook chat | n8n chat | /frage → answer with sources |
| E: onboarding | Webhook + weekdays 08:30 | /updates → proposal; /risiken → Telegram digest |

**Why this split:** n8n is good for triggers, schedules and connections, and anyone can see the flow. Python
is good for logic you need to test. The logic has evals; n8n only moves data.

---

## Project 5: Onboarding cockpit (`partner-onboarding/`)

### The case for it

**The problem today:** every new franchise partner goes through a 90-day start: register the company, open a
bank account, get insurance, apply for the official permit, rent an office, hire helpers, get their background
checks, start marketing, win the first 10 customers. Partners report progress in free-text emails like
"Gewerbe ist angemeldet, aber der Vermieter hat abgesagt". Partner management reads every email and updates a
spreadsheet by hand. With several partners at once, things slip:
- a task is overdue and nobody notices;
- the permit takes 4–8 weeks, so a late application quietly ruins the 90-day target;
- worst case: a partner starts serving customers **before** insurance, permit or background checks are done.
  That is a legal and safety risk for the whole brand.

**How it is solved:** partner emails go (via n8n) to the onboarding API. It turns each email into a
**proposal**: "insurance → done", "office → blocked (landlord cancelled)", each with the sentence it came from.
Partner management approves with one click. A traffic light per partner, built from fixed rules, shows who is
on plan, who needs attention and who is critical, and why. Every weekday at 08:30 the red and orange cases
arrive on Telegram.

**What gets automated:** reading the updates, proposing checklist changes, tracking deadlines, forecasting
the permit date and spotting critical risks. **What stays human:** approving every change, and talking to the
partner.

**End-to-end example:**
> Partner Essen, day 52: *"Kurzes Update: Wir haben schon 3 Kunden! Das Büro ist angemietet, aber mit der
> Versicherung klappt es leider noch nicht."*
1. Split into clauses; tasks found by word lists: customers, office, insurance.
2. Rules: "angemietet" → office **done**; "leider … nicht" → insurance **blocked**. The pattern "3 Kunden" →
   customer count 3, so the first customer visit happened (the AI was asked about that clause and agreed).
3. **Warning:** customers are being served, but insurance (a must-have before the first visit) is not done →
   "Bitte sofort klären".
4. The proposal waits for approval. Once approved, the traffic light for Essen turns 🔴 and the next
   Telegram digest starts with Essen.

**Why use AI here, and not plain automation?** Partners write naturally, mix good and bad news in one sentence,
and use many words for the same thing. Plain automation would need partners to fill a strict status form,
which they do not do in practice. Rules handle the clear wording (most cases); the AI is only asked about
clauses the rules cannot decide. **Why not let the AI do everything?** The first version did: 7/15 correct,
with confident wrong answers. Rules first, AI only for the unclear rest, a person approves: no wrong "done"
in any blind test.

**Why not an agent?** Every email goes through the same steps. A fixed pipeline with one small AI question
per unclear clause is more predictable and easier to test than letting a model plan.

**The chain:** partner email → 🟩 split into clauses → 🟩 find which checklist task each clause is about →
🟩 rules decide clear cases / 🟧 AI only for unclear ones → proposal → 🟦 person approves → audit log + 🟩
traffic light.

### Step 1: The checklist 🟩
`checklist.py`: 15 tasks from the handbook, each with a due day, an owner and **a word list** (e.g. insurance:
"haftpflicht, versicherung, police, insurance"). 4 tasks are *gate* tasks. They must be done before the first
customer visit: liability insurance, permit, background checks and training of the helpers, contract templates.

### Step 2: Split and find tasks 🟩
`updates.py`: message → sentences → clauses (split at commas, "aber", "but"). For each clause, `mentioned()`
finds which tasks it talks about via the word lists. Generic words like "Helfer" only count if nothing more
specific is there: "Führungszeugnisse für beide Helfer liegen vor" is about the background check.

### Step 3: Rules decide the clear cases 🟩
In this order:
1. **Obstacle** ("leider, abgesagt, fehlt, immer noch nicht, rejected") → task **blocked**.
2. **Plan, question or "noch nicht"** ("werden, nächste Woche, soon, ?") → **no change**.
3. **Clear state** ("abgeschlossen, eröffnet, liegt vor, ist online, signed") → **done**.

### Step 4: The AI only for unclear clauses 🟧
Only clauses that matched no rule, and that talk about the past (`PAST` check), go to the model. **One small
question each:** "Checklist item: X. Partner's clause: Y. Is this item done?" The answer form is
`{begruendung, erledigt}`: reason first, then the decision. A clause without any past tense is never sent to
the model. Example: "Die Startschulung machen wir im Dezember", where the model wrongly said "done".

### Step 5: Numbers and follow-on facts 🟩
- Customer count by pattern ("6 Kunden"), not by the model, and never from plans ("hoffentlich 10 Kunden").
- Follow-on facts: permit is there → the application was made; customers > 0 → first visit happened.

### Step 6: Proposal, not a change 🟦
`service.py` → `submit_update()` stores a **proposal**. Nothing in the checklist changes. Each proposed change
shows the clause it came from and who decided (rule or AI + reason). **Warning:** if the partner reports
customers while a gate task is still open → "Bitte sofort klären". A person approves all, part, or nothing,
**with their name**. Every change goes into the audit log with before/after.

### Step 7: Traffic light 🟩
`status.py` → `assess()`, plain rules, each finding says why:
- 🔴 customers served while gate tasks are open; a gate task blocked or overdue; the permit (4–8 weeks after
  the application) can only arrive after day 90.
- 🟠 a normal task overdue/blocked; the permit is late for the 10-customer target; the customer target is
  unrealistic (more than one new customer every 2 days needed).

n8n workflow E sends the red/orange list to Telegram every weekday at 08:30.

### Accuracy, with the honest history
v1 (model reads the whole message): 7/15. v2 (model per clause): 11/15 blind, and a prompt tweak made it worse
(6/10). v3 (rules first, model only for unclear clauses): **8/10 on a fresh blind set**. In every blind run the
misses were **missed updates, never a wrong "done"**. That is the safe direction: a person sees "no change"
and adds it by hand.

---

## When to use what: plain automation, an LLM step, or an agent

This is the decision I make for every process, and the reason the five projects look different:

| Situation | Tool | Example here |
|---|---|---|
| Input is already structured, the steps are fixed | **Plain automation** (n8n, rules, a script). No AI. | Daily overdue list, weekly trigger, CSV log, traffic-light rules |
| Input is free text (emails, forms, questions), the steps are fixed | **Pipeline with one small LLM step**, checked by code | Analytics question → form; handbook answer; unclear partner clause |
| Input is free text **and** the right next step depends on the case | **Agent**: the model picks from whitelisted tools, code guards it | Intake (and more so once tools like "look up customer" are added) |
| Anything that reaches a customer or changes data | **A person approves**, everything logged | Reply drafts, checklist changes |

Rules that apply to all of them:
1. **Use the smallest amount of AI that solves the problem.** Every AI step is a place that can be wrong, so
   each one gets a code check right after it.
2. **AI reads, code decides and calculates.** Priorities, numbers, deadlines and warnings come from rules
   that staff can understand and change.
3. **Measure it.** Each project has a test set written before tuning and a blind set, so "it works" is a number.
4. **Data stays local.** The model runs on our own machine, so customer data never goes to an outside AI service.

### How to say it in the interview (≈ 30 seconds)

> "In every process I first ask: is the input structured? If yes, plain automation with n8n is enough, with no
> AI. If people write free text, I add one LLM step that turns the text into structured data, and code checks
> it against the source. I only use an agent where the next step really depends on the case, like the intake,
> and even there the model can only choose from whitelisted tools. Decisions and numbers come from rules, and
> anything that goes to a customer is approved by a person. That way the AI removes the reading and typing
> work, but the team stays in control."

German version:

> „Bei jedem Prozess frage ich zuerst: Sind die Daten strukturiert? Dann reicht eine normale Automatisierung
> mit n8n, ohne KI. Wenn Menschen freien Text schreiben, nutze ich einen KI-Schritt, der den Text in feste
> Felder übersetzt, und der Code prüft das gegen den Originaltext. Einen Agenten nutze ich nur, wenn der
> nächste Schritt wirklich vom Fall abhängt, wie bei den Kundenanfragen. Entscheidungen und Zahlen kommen aus
> Regeln, und alles, was zum Kunden geht, gibt ein Mensch frei. So nimmt die KI die Lese- und Tipparbeit ab,
> aber das Team behält die Kontrolle."

## Where the prompts are (quick reference)

| Project | Prompt | File | What the model must return |
|---|---|---|---|
| 1 | PLANNER_PROMPT | intake-service/app/agent.py | `{tool, reason}`, tool from an enum |
| 1 | EXTRACTION_PROMPT | intake-service/app/tools.py | the 7-field form |
| 1 | DRAFT_PROMPT (only in model mode) | intake-service/app/tools.py | `{message}` |
| 2 | PLANNER_PROMPT | partner-analytics/app/ask.py | the query form (QuerySpec) |
| 2 | SUMMARY_PROMPT | partner-analytics/app/report.py | 2–3 sentences (numbers checked) |
| 3 | TRANSLATE | partner-handbook/app/assistant.py | `{deutsch}` |
| 3 | SYSTEM | partner-handbook/app/assistant.py | `{answer, sources, found}` |
| 5 | SYSTEM | partner-onboarding/app/updates.py | `{begruendung, erledigt}` |

All calls: local Ollama, `qwen2.5:3b`, temperature 0, JSON schema enforced, output length capped.
**Everything not in this table is plain Python code.**

## Questions you might get, short answers

- **"Are the tools prompts or code?"** Code. Only `extract_fields` calls the model inside it (to read the text).
  The other three tools are plain rules.
- **"How does the agent know which tools exist?"** The prompt lists them with a one-line description, and the
  JSON schema only allows those names, and only those that have not run yet.
- **"How do you stop the AI from making things up?"** Every fact is checked against the source: the customer's
  words (project 1), the real list of locations (2), the cited handbook section (3), the partner's clause (5).
  If the check fails, code replaces or drops the AI's output, and the log shows both versions.
- **"Why such a small model?"** It runs locally, so no customer data leaves the building (GDPR). The
  checks make it reliable enough. A bigger model would make it better, but the checks would stay.
- **"What if the AI is wrong anyway?"** A person approves everything that goes to a customer or changes data,
  and the audit log shows exactly what the AI said and what code changed.
