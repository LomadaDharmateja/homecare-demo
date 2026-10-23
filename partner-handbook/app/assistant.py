"""Handbook assistant: answers only from the handbook, cites sections, says so when the handbook has no answer.

Safety layers, in order:
1. Emergency words -> "call 112" comes first, from a fixed text, before any AI is involved.
2. The model must answer only from the numbered excerpts and say found=false if they don't contain it.
3. Code checks the cited excerpt numbers exist and every number in the answer appears in a cited excerpt.
   If not, the assistant shows the most relevant excerpt itself instead of the model's text.
4. Every unanswered question is logged, so head office sees which topics the handbook is missing.
"""
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import httpx
import ollama
from pydantic import BaseModel, Field, ValidationError

from .index import Index

MODEL = "qwen2.5:3b"
LOG_DB = Path(__file__).resolve().parent.parent / "data" / "questions.db"
_index = None


def index():
    global _index
    if _index is None:
        _index = Index()
    return _index


class Answer(BaseModel):
    # Order matters: the model writes the answer first and decides "found" last, after reading.
    answer: str = Field(description="short answer from the excerpts, in the language of the question")
    sources: list[int] = Field(description="numbers of the excerpts the answer is based on")
    found: bool = Field(description="true only if the excerpts contain the answer")


SYSTEM = """Du beantwortest Fragen von Franchisepartnern ausschließlich anhand der nummerierten Auszüge aus dem
Partnerhandbuch.
Regeln:
- Antworte kurz (1-3 Sätze) und in der Sprache der Frage.
- Nutze nur Informationen aus den Auszügen. Nenne Zahlen, Fristen und Beträge genau so wie im Auszug.
- Nennt der Auszug Ausnahmen oder Grenzen (z. B. "bis zu 10 Euro"), gehören sie in die Antwort.
- Gib in "sources" die Nummern der Auszüge an, auf denen die Antwort beruht.
- Wenn ein Auszug die Frage beantwortet, auch sinngemäß (z. B. "verboten" beantwortet "Dürfen wir ...?"),
  setze found=true.
- Steht die Antwort wirklich nicht in den Auszügen, setze found=false und answer="". Rate niemals.
- Keine medizinischen oder rechtlichen Einschätzungen über das Handbuch hinaus."""

EMERGENCY = re.compile(
    r"bewusstlos|atmet (nicht|schwer|kaum)|atemnot|keine luft|blutet stark|starke blutung|brustschmerz|"
    r"reagiert nicht|krampf|herzinfarkt|schlaganfall|unconscious|not breathing|can'?t breathe|chest pain|"
    r"bleeding heavily|stroke", re.I)
EMERGENCY_TEXT = {
    "de": "🚨 Bei Lebensgefahr, Bewusstlosigkeit oder Atemnot sofort den Notruf 112 wählen. "
          "Danach die Partnerleitung informieren.",
    "en": "🚨 If life is in danger, the person is unconscious or cannot breathe: call 112 immediately. "
          "Then inform the location manager.",
}
NOT_FOUND = {
    "de": "Dazu steht nichts im Partnerhandbuch. Bitte wende dich an die Zentrale. "
          "Die Frage wurde notiert, damit das Handbuch ergänzt werden kann.",
    "en": "The partner handbook doesn't cover this. Please contact head office. "
          "The question has been logged so the handbook can be extended.",
}


def _lang(text):
    german = len(re.findall(r"\b(der|die|das|und|ich|wie|was|wann|muss|darf|kann|ist|ein|eine|nicht|bis|"
                            r"mein|meine|wir|soll)\b|[äöüß]", text, re.I))
    english = len(re.findall(r"\b(the|and|what|how|when|is|are|do|does|can|should|my|our|much|many)\b", text, re.I))
    return "en" if english > german else "de"


WORDS = {"ein": "1", "zwei": "2", "drei": "3", "vier": "4", "fünf": "5", "sechs": "6", "sieben": "7",
         "acht": "8", "neun": "9", "zehn": "10", "zwölf": "12", "halb": "0.5"}


def _numbers(text):
    """Numbers as written, normalised: '3.539' and '3,539' -> '3539'; '0,30' -> '0.30';
    number words count too ('fünftägig' -> '5')."""
    out = {d for w, d in WORDS.items() if re.search(rf"\b{w}", text, re.I)}
    for n in re.findall(r"\d+(?:[.,]\d+)*", text):
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", n):
            out.add(n.replace(".", "").replace(",", ""))
        else:
            out.add(n.replace(",", "."))
    return out


def _log(question, status, sources):
    LOG_DB.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(LOG_DB)
    try:
        con.execute("CREATE TABLE IF NOT EXISTS questions (id INTEGER PRIMARY KEY, asked_at TEXT, question TEXT, "
                    "status TEXT, sources TEXT, feedback TEXT)")
        cur = con.execute("INSERT INTO questions (asked_at, question, status, sources) VALUES (?,?,?,?)",
                          (datetime.now(timezone.utc).isoformat(timespec="seconds"), question, status,
                           json.dumps(sources, ensure_ascii=False)))
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def feedback(question_id, helpful):
    con = sqlite3.connect(LOG_DB)
    try:
        con.execute("UPDATE questions SET feedback=? WHERE id=?", ("helpful" if helpful else "not helpful", question_id))
        con.commit()
    finally:
        con.close()


def knowledge_gaps():
    """Questions the handbook could not answer, plus answers marked unhelpful."""
    if not LOG_DB.exists():
        return []
    con = sqlite3.connect(LOG_DB)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("SELECT asked_at, question, status, feedback FROM questions "
                           "WHERE status='not_found' OR feedback='not helpful' ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def _cite(s):
    return {"file": s["file"], "doc": s["doc"], "section": s["section"], "owner": s["owner"], "date": s["date"],
            "text": s["text"]}


def ask(question):
    lang = _lang(question)
    hits = index().search(question, k=5)
    emergency = bool(EMERGENCY.search(question))
    if emergency:  # make sure the emergency rules are among the excerpts
        notfall = [s for s in index().sections if s["file"] == "04_notfaelle.md" and s["section"] == "Grundregel"]
        hits = notfall + [h for h in hits if h["id"] != notfall[0]["id"]][:3]

    excerpts = "\n\n".join(f"[{n}] {h['doc']} – {h['section']}:\n{h['text']}" for n, h in enumerate(hits, 1))
    try:
        raw = ollama.chat(model=MODEL, format=Answer.model_json_schema(), options={"temperature": 0, "num_predict": 300},
                          messages=[{"role": "system", "content": SYSTEM},
                                    {"role": "user", "content": f"Auszüge:\n{excerpts}\n\nFrage: {question}"}])
        result = Answer.model_validate_json(raw["message"]["content"])
    except (httpx.ConnectError, ConnectionError) as e:
        raise RuntimeError("Ollama is not running. Start it with: ollama serve") from e
    except ValidationError:
        result = Answer(found=False, answer="", sources=[])

    cited = [hits[n - 1] for n in dict.fromkeys(result.sources) if 1 <= n <= len(hits)]
    check = "ok"
    if result.found and result.answer.strip():
        if not cited:
            check = "no valid source cited"
        else:
            unknown = _numbers(result.answer) - set().union(*(_numbers(c["text"] + " " + c["section"]) for c in cited))
            if unknown:
                check = f"numbers not in the cited sections: {sorted(unknown)}"

    if emergency:
        status = "emergency"
        body = result.answer if result.found and check == "ok" else ""
        answer = EMERGENCY_TEXT[lang] + (f"\n\n{body}" if body else "")
        cited = cited or hits[:1]
    elif not result.found or not result.answer.strip():
        status, answer, cited = "not_found", NOT_FOUND[lang], []
    elif check != "ok":
        # Don't show an answer we can't verify; show the most relevant section itself.
        top = cited[0] if cited else hits[0]
        status = "excerpt_shown"
        intro = "Im Handbuch steht dazu:" if lang == "de" else "The handbook says:"
        answer, cited = f"{intro}\n\n{top['text']}", [top]
    else:
        status, answer = "answered", result.answer.strip()

    question_id = _log(question, status, [f"{c['file']}#{c['section']}" for c in cited])
    return {"id": question_id, "question": question, "answer": answer, "status": status, "check": check,
            "sources": [_cite(c) for c in cited],
            "retrieved": [{"section": f"{h['doc']} – {h['section']}", "cosine": h.get("cosine"), "bm25": h.get("bm25")}
                          for h in hits]}
