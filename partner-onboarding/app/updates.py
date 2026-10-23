"""Partner update message -> proposed checklist changes. Code finds, rules or the model judge, a person approves.

1. Code splits the message into clauses and finds which checklist tasks each clause mentions (word lists).
2. Clear wording is decided by rules, in this order:
     obstacle ("leider", "abgesagt", "fehlt", "immer noch nicht") -> blockiert, for the task named first;
     plan / question / "noch nicht"                                 -> no change;
     clear state ("abgeschlossen", "ist online", "liegt vor")       -> erledigt.
   An obstacle in a clause without a task belongs to the task just before it
   ("Den Antrag haben wir noch nicht abgeschickt, uns fehlt noch ein Formular").
3. Only the remaining, unclear clauses go to the model, one small question each: is this task done?
4. Customer counts are read by a pattern ("6 Kunden"), not by the model.
Nothing is written to the checklist here; that happens only when a person approves (see service.py).

History (see README): v1 let the model read the whole message (7/15 tuning). v2 asked the model per sentence
(15/15 tuning, 11/15 blind). A prompt change for v2 scored 6/10 on a fresh blind set. This v3 uses rules first.
"""
import re
from datetime import date, timedelta
from typing import Literal

import httpx
import ollama
from pydantic import BaseModel, ValidationError

from .checklist import BY_ID, TASKS

MODEL = "qwen2.5:3b"
JUDGED = [t for t in TASKS if t.id != "zehn_kunden"]  # 10 customers comes from the count, not from a judgement

# Generic words: they mention a task in passing more often than they report on it.
WEAK = {"helfer": {"helfer", "mitarbeiter", "personal", "staff", "carer", "helper"},
        "erster_kunde": {"kunde", "kundin", "customer", "client"},
        "software": {"software"}}  # "Vertragsvorlagen in der Software" is about the templates

BLOCKED = re.compile(r"leider|abgesagt|abgesprungen|abgelehnt|fehlt|fehlen|nachgefordert|immer noch nicht|"
                     r"warten immer noch|zickt|klappt( es)?( leider)? nicht|keine passenden|problem|"
                     r"cancel+ed|rejected|refused|missing", re.I)
NOT_DONE = re.compile(r"\b(noch nicht|nicht|kein|keine|keinen|werden|wird|planen|geplant|nächste[nrs]?|bald|"
                      r"morgen|hoffentlich|sobald|demnächst|wollen|möchten|soll|dauert noch|"
                      r"not|no|will|plan|planned|next|soon|tomorrow|hope)\b|\?", re.I)
DONE = re.compile(r"\b(abgeschlossen|eröffnet|angemeldet|eingestellt|angemietet|gegründet|verteilt|erschienen|"
                  r"gekommen|online|aktiv|eingerichtet|raus|liegt vor|liegen vor|ist da|sind da|zugelassen|anerkannt|"
                  r"teilgenommen|besucht|stattgefunden|signed|done|open|ready|hired|approved|registered|completed)\b",
                  re.I)
# The model may only call something done in a clause that reports the past or a state.
PAST = re.compile(r"\b(ist|sind|war|waren|wurde|wurden|hat|haben|hatten|seit|bereits|schon|"
                  r"is|are|was|were|has|have|had|already)\b|\bge\w+[t|n]\b|\w+ed\b", re.I)
NUM = {"ersten": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9,
       "zehn": 10, "elf": 11, "zwölf": 12}
CUSTOMERS = re.compile(r"\b(\d{1,3}|" + "|".join(NUM) + r")\s+(?:aktive[n]?\s+)?(kunden|kundinnen|kunde|kundin|"
                       r"customers|clients)\b", re.I)


class Judgement(BaseModel):
    begruendung: str  # written first, so the decision comes after reading
    erledigt: bool


SYSTEM = ("Du hilfst dem Partnermanagement eines Franchise für Alltagshilfe. Ein neuer Partner schreibt ein Update. "
          "Du bekommst einen Satzteil aus seiner Nachricht und einen Punkt seiner Checkliste. "
          "erledigt=true nur, wenn der Satzteil meldet, dass genau dieser Punkt schon passiert ist. "
          "Bei Plänen, Fragen, Terminen in der Zukunft, oder wenn der Punkt nur nebenbei vorkommt: erledigt=false. "
          "begruendung: ein kurzer Halbsatz.")


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def clauses(sentence):
    return [c.strip() for c in re.split(r",\s+|;\s+|\s+(?:aber|but)\s+", sentence) if c.strip()]


def _has(text, word):
    """Position of a word. Long words also inside compounds ('Haftpflichtversicherung'); 4-5 letters at the
    start or end of a word ('Geschäftskonto'); 2-3 letters only as a whole word ('ug' is not in 'Führungszeugnis')."""
    if word.startswith("^"):  # word start only: "^werbe" finds "Werbung", not "Gewerbe" or "Bewerbung"
        m = re.search(r"(?<!\w)" + re.escape(word[1:]), text)
        return m.start() if m else -1
    if len(word) >= 6:
        return text.find(word)
    w = re.escape(word)
    pattern = rf"\b{w}\b" if len(word) <= 3 else rf"(?<!\w){w}|{w}(?!\w)"
    m = re.search(pattern, text)
    return m.start() if m else -1


def mentioned(text):
    """Tasks a clause talks about, in the order they appear. A generic word only counts when nothing more
    specific is there: 'Führungszeugnisse für beide Helfer liegen vor' is about the certificate."""
    low = re.sub(r"antrag(s|es)? auf (anerkennung|zulassung)", "antrag", text.lower())

    def first(task, weak):
        hits = [_has(low, w) for w in task.words if (w in WEAK.get(task.id, ())) == weak]
        hits = [h for h in hits if h >= 0]
        return min(hits) if hits else None
    strong = {t.id: first(t, False) for t in JUDGED if first(t, False) is not None}
    found = strong or {t.id: first(t, True) for t in JUDGED if first(t, True) is not None}
    return sorted(found, key=found.get)


def judge(clause, task):
    try:
        raw = ollama.chat(model=MODEL, format=Judgement.model_json_schema(),
                          options={"temperature": 0, "num_predict": 100},
                          messages=[{"role": "system", "content": SYSTEM},
                                    {"role": "user", "content": f"Checklisten-Punkt: {BY_ID[task].title}\n"
                                                                f"Satzteil des Partners: {clause}"}])
        return Judgement.model_validate_json(raw["message"]["content"])
    except (httpx.ConnectError, ConnectionError) as e:
        raise RuntimeError("Ollama is not running. Start it with: ollama serve") from e
    except ValidationError:
        return Judgement(begruendung="ungültige Modellantwort", erledigt=False)


def done_date(text, received):
    low = text.lower()
    if "vorgestern" in low:
        return received - timedelta(days=2)
    if "gestern" in low or "yesterday" in low:
        return received - timedelta(days=1)
    m = re.search(r"\bam (\d{1,2})\.(\d{1,2})\.", low)
    if m:
        try:
            return date(received.year, int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return received


def customer_count(message):
    """'Stand heute: 4 Kunden aktiv' -> 4. Not from plans ('hoffentlich 10 Kunden')."""
    for s in sentences(message):
        if NOT_DONE.search(s):
            continue
        m = CUSTOMERS.search(s)
        if m:
            n = m.group(1).lower()
            return int(n) if n.isdigit() else NUM[n]
    return None


def propose(message, received=None):
    """Returns the proposed changes (each with the clause and who decided: rule or model) and the customer count."""
    received = received or date.today()
    accepted, notes = {}, []

    sentence_now = [""]  # the date ("gestern") may sit in another clause of the same sentence

    def add(task, status, clause, how):
        old = accepted.get(task)
        if old and (old["status"] == "erledigt" or status == "blockiert"):
            return  # one change per task; "done" wins (marketing started, one flyer misprinted)
        accepted[task] = {"task": task, "status": status, "satz": clause, "entschieden_von": how,
                          "done_on": done_date(sentence_now[0], received).isoformat() if status == "erledigt" else None}

    for s in sentences(message):
        sentence_now[0] = s
        previous = []
        for c in clauses(s):
            tasks = mentioned(c)
            if not tasks:
                if BLOCKED.search(c) and previous:  # "..., uns fehlt noch ein Formular"
                    add(previous[0], "blockiert", f"{s}", "Regel: Hindernis genannt")
                continue
            previous = tasks
            if BLOCKED.search(c):
                add(tasks[0], "blockiert", c, "Regel: Hindernis genannt")
            elif NOT_DONE.search(c):
                notes.append({"satz": c, "tasks": tasks, "grund": "Plan, Frage oder 'noch nicht': keine Änderung"})
            elif DONE.search(c):
                for t in tasks:
                    add(t, "erledigt", c, "Regel: als erledigt gemeldet")
            else:
                if not PAST.search(c):  # "Die Startschulung machen wir im Dezember": the model said done
                    notes.append({"satz": c, "tasks": tasks, "grund": "keine Vergangenheit, kein Zustand: keine Änderung"})
                    continue
                for t in tasks:
                    j = judge(c, t)
                    if j.erledigt:
                        add(t, "erledigt", c, f"KI: {j.begruendung}")
                    else:
                        notes.append({"satz": c, "tasks": [t], "grund": f"KI: keine Änderung ({j.begruendung})"})

    customers = customer_count(message)

    # Follow-on facts: a permit implies the application; customers imply the first visit.
    def derive(task, why):
        if accepted.get(task, {}).get("status") != "erledigt":
            accepted[task] = {"task": task, "status": "erledigt", "satz": why, "entschieden_von": "Regel: Folgerung",
                              "done_on": received.isoformat()}
    if accepted.get("zulassung", {}).get("status") == "erledigt":
        derive("antrag", "Zulassung liegt vor, also wurde der Antrag gestellt")
    if customers and customers >= 1:
        derive("erster_kunde", f"{customers} aktive Kunden, also hat der erste Einsatz stattgefunden")
    if customers and customers >= 10:
        derive("zehn_kunden", f"{customers} aktive Kunden")
    return {"changes": list(accepted.values()), "notes": notes, "active_customers": customers}
