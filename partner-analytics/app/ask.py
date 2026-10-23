"""Question -> query form (LLM) -> numbers (Python) -> short explanation (LLM, number-checked)."""
import difflib
import json
import os
import re

import httpx
import ollama
from pydantic import ValidationError

from .engine import METRIC_DE, PARTNER_LEVEL, UNITS, QuerySpec, describe, load, run_query

MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OPTIONS = {"temperature": 0, "num_predict": 300}


class OllamaUnavailable(RuntimeError):
    pass


def _chat(system, user, schema=None):
    try:
        r = ollama.chat(model=MODEL, format=schema, options=OPTIONS,
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
    except (httpx.ConnectError, ConnectionError) as e:
        raise OllamaUnavailable("Ollama is not running. Start it with: ollama serve") from e
    return r["message"]["content"]


PLANNER_PROMPT = """You turn a manager's question about franchise locations into a query form (JSON).
You never calculate anything. Pick values only from the allowed lists.

Fields:
- metric: revenue, costs, profit, customers, new_customers, enquiries, hours, staff, cash, conversion_rate
  (new customers / enquiries), revenue_vs_plan (% above/below business plan), locations (count),
  months_to_second_location, share_with_second_location (% of partners who opened a 2nd location)
- group_by: none, location, state, founder_type (solo/friends/couple), opening_year, month (trend over time)
- period: last_month (default), last_3_months, last_6_months, last_12_months, all
- growth: true only if the question asks about change, growth, decline, "compared to", "up/down"
- state, founder_type, location: only if the question names one; otherwise null
- sort: desc for "top/best/highest/most", asc for "worst/lowest/least/declining/losing"
- limit: number of rows asked for, default 10

Examples:
Q: Which 5 locations lost the most customers in the last 6 months?
{"metric":"customers","group_by":"location","period":"last_6_months","growth":true,"state":null,"founder_type":null,"location":null,"sort":"asc","limit":5}
Q: Do partners who started with a friend open a second location faster?
{"metric":"months_to_second_location","group_by":"founder_type","period":"all","growth":false,"state":null,"founder_type":null,"location":null,"sort":"asc","limit":10}
Q: How has total revenue developed over the last year?
{"metric":"revenue","group_by":"month","period":"last_12_months","growth":false,"state":null,"founder_type":null,"location":null,"sort":"desc","limit":12}
Q: Wie hoch ist die Conversion Rate in Bayern?
{"metric":"conversion_rate","group_by":"none","period":"last_month","growth":false,"state":"Bayern","founder_type":null,"location":null,"sort":"desc","limit":10}
"""

def _norm(s):
    return (s.lower().replace("ü", "ue").replace("ö", "oe").replace("ä", "ae").replace("ß", "ss")
            .replace("-", " ").replace("/", " "))


def _snap(value, options):
    """Map a model-picked name onto a real one ('Muenchen Ost' -> 'München-Ost'); unknown -> None."""
    if not value:
        return None
    lookup = {_norm(o): o for o in options}
    if _norm(value) in lookup:
        return lookup[_norm(value)]
    match = difflib.get_close_matches(_norm(value), lookup.keys(), n=1, cutoff=0.75)
    return lookup[match[0]] if match else None


ALIASES = {"bavaria": "bayern", "saxony": "sachsen", "north rhine westphalia": "nrw", "hesse": "hessen",
           "lower saxony": "niedersachsen", "thuringia": "thueringen"}


def plan(question):
    raw = _chat(PLANNER_PROMPT, f"Q: {question}", schema=QuerySpec.model_json_schema())
    spec = QuerySpec.model_validate_json(raw)
    partners, _ = load()
    q = _norm(question)
    for english, german in ALIASES.items():
        q = q.replace(english, german)
    notes = []
    for field, options in (("location", partners["location"]), ("state", partners["state"].unique())):
        picked = getattr(spec, field)
        snapped = _snap(ALIASES.get(_norm(picked), picked) if picked else None, options)
        # Keep a name only if the user wrote it: small models copy names from the prompt examples.
        if snapped and _norm(snapped).split()[0] not in q:
            notes.append(f"{FIELD_DE[field]} „{picked}“ ignoriert: kommt in der Frage nicht vor.")
            snapped = None
        elif picked and not snapped:
            notes.append(f"Unbekannte(s) {FIELD_DE[field]} „{picked}“ ignoriert.")
        setattr(spec, field, snapped)
    return _backstops(spec, question, notes), notes


TREND = re.compile(r"\b(develop\w*|trend\w*|over time|month by month|entwick\w*|verlauf)\b", re.I)
CHANGE = re.compile(r"\b(lost|lose|losing|gain\w*|grew|grow\w*|decline\w*|declining|drop\w*|increas\w*|"
                    r"decreas\w*|chang\w*|compared|verlor\w*|gewachsen|wachstum|rückgang|gesunken|gestiegen)\b", re.I)
DOWN = re.compile(r"\b(lost|losing|least|lowest|worst|fewest|below|drop\w*|declin\w*|decreas\w*|weakest|"
                  r"wenigsten|niedrigst\w*|schlechtest\w*|verlor\w*|rückgang)\b", re.I)
UP = re.compile(r"\b(most|highest|best|top|largest|biggest|grew|gained|strongest|meisten|höchst\w*|"
                r"best\w*|gewachsen)\b", re.I)
BY_STATE = re.compile(r"\b(by|per|each|which|every)\s+states?\b|\b(nach|pro|je|jedes|welches)\s+bundesland", re.I)
WHICH_LOCATIONS = re.compile(r"\b(which|welche)\s+(\d{1,2}\s+)?(locations|standorte|partners|partner)\b", re.I)
LOCATION_WORDS = re.compile(r"\b(locations?|standort\w*|partners?|partner\w*|cities|städte\w*|sites?|where|wo)\b", re.I)
LIMIT = re.compile(r"\b(?:top|bottom|best|worst)?\s*(\d{1,2})\s+(?:\w+\s)?(?:locations|standorte|partners|cities|states)\b"
                   r"|\b(?:top|bottom)\s+(\d{1,2})\b", re.I)


FIELD_DE = {"location": "Standort", "state": "Bundesland", "founder_type": "Gründertyp",
            "group_by": "Gruppierung", "period": "Zeitraum", "growth": "Veränderung", "sort": "Sortierung",
            "limit": "Anzahl", "metric": "Kennzahl"}


def _backstops(spec, question, notes):
    """Rules that catch the planner's common misses; each one is reported in the notes."""
    def fix(field, value, why):
        setattr(spec, field, value)
        notes.append(f"Regel: {FIELD_DE[field]} = {value} ({why}).")

    # Names are found by matching the question against the real list, not left to the model.
    partners, _ = load()
    q = " " + re.sub(r"[^\w ]", " ", _norm(question)) + " "
    for english, german in ALIASES.items():
        q = q.replace(f" {english} ", f" {german} ")
    for field, options in (("location", partners["location"]), ("state", partners["state"].unique())):
        named = [o for o in options if f" {_norm(o)} " in q]
        if not named:  # "Essen" for "Essen", but "Köln" alone is ambiguous between Köln-West and Köln-Ost
            firsts = {}
            for o in options:
                firsts.setdefault(_norm(o).split()[0], []).append(o)
            named = [v[0] for k, v in firsts.items() if len(v) == 1 and f" {k} " in q]
        compare_states = field == "state" and BY_STATE.search(question)
        if len(named) == 1 and (spec.group_by != field or not compare_states):
            if getattr(spec, field) != named[0]:
                fix(field, named[0], "in der Frage genannt")
            if spec.group_by == field and field == "state":
                fix("group_by", "none", "nur ein Bundesland gefragt")
    if spec.location and spec.group_by == "location":
        fix("group_by", "none", "nur ein Standort gefragt")
    if spec.group_by == "location" and not LOCATION_WORDS.search(question):
        fix("group_by", "none", "die Frage verlangt keine Liste von Standorten")
    if spec.group_by == "none" and not spec.location and spec.metric != "locations" and WHICH_LOCATIONS.search(question):
        fix("group_by", "location", "die Frage fragt, welche Standorte")
    if spec.metric == "locations" and spec.group_by == "location":
        fix("group_by", "none", "Standorte werden gezählt")

    # Grouping by a field and filtering on it at once would leave nothing to compare.
    for field in ("founder_type", "state", "location"):
        if spec.group_by == field and getattr(spec, field):
            fix(field, None, f"Vergleich über {FIELD_DE[field]}")
    monthly = spec.metric not in PARTNER_LEVEL
    if monthly and TREND.search(question) and spec.group_by == "none":
        fix("group_by", "month", "die Frage fragt nach der Entwicklung")
        if spec.period == "last_month":
            fix("period", "last_12_months", "ein Verlauf braucht mehr als einen Monat")
    if monthly and spec.group_by == "month" and spec.growth:
        fix("growth", False, "der Monatsverlauf zeigt die Veränderung schon")
    if monthly and not spec.growth and spec.group_by != "month" and CHANGE.search(question):
        fix("growth", True, "die Frage fragt nach einer Veränderung")
    if spec.group_by not in ("none", "month"):
        want = "asc" if DOWN.search(question) else "desc" if UP.search(question) else None
        if want and want != spec.sort:
            fix("sort", want, "die Frage fragt nach den " + ("niedrigsten" if want == "asc" else "höchsten") + " Werten")
    m = LIMIT.search(question)
    if m:
        n = int(m.group(1) or m.group(2))
        if 1 <= n <= 60 and n != spec.limit:
            fix("limit", n, "Anzahl steht in der Frage")
    elif spec.group_by in ("state", "founder_type", "opening_year") and spec.limit < 60:
        fix("limit", 60, "alle Gruppen zeigen, keine Anzahl gefragt")
    return spec


GERMAN_HINT = re.compile(r"[äöüß]|\b(wie|welche[rsmn]?|wo|was|wann|wieviele?|viele|hat|haben|hatten|der|die|das|"
                         r"im|nach|pro|und|letzten|monat|standorte?|umsatz|gewinn|kunden|liquidität)\b", re.I)


def is_german(text):
    return bool(GERMAN_HINT.search(text))


def _fmt(v, unit, de=False):
    if v is None or v != v:
        return "k. A." if de else "n/a"
    if unit == "€":
        s = f"{v:,.0f} €"
    elif unit == "%":
        s = f"{v:.1f} %"
    elif unit == "months":
        s = f"{v:.1f} {'Monate' if de else 'months'}"
    else:
        s = f"{v:,.0f}" if abs(v) >= 100 else f"{v:.1f}"
    # German style: 1.234.567 € and 12,5 %
    return s.replace(",", "_").replace(".", ",").replace("_", ".") if de else s


def _pct_txt(v, de=False):
    s = f"{v:+.1f} %"
    return s.replace(".", ",") if de else s


def _numbers_in(text):
    """Numbers in English (1,234.5) or German (1.234,5) style; '12.345' with 3 digits counts as thousands."""
    text = re.sub(r"(?<=\d)[.,](?=\d{3}\b)", "", text)
    text = re.sub(r"(?<=\d),(?=\d)", ".", text)
    return {float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text)}


LABEL = {"revenue": "Revenue", "costs": "Costs", "profit": "Profit", "customers": "Customers",
         "new_customers": "New customers", "enquiries": "Enquiries", "hours": "Hours delivered", "staff": "Staff",
         "cash": "Cash", "conversion_rate": "Conversion rate", "revenue_vs_plan": "Revenue vs. plan",
         "locations": "Locations", "months_to_second_location": "Months to a second location",
         "share_with_second_location": "Share with a second location"}
WORDS = {
    "en": {"empty": "No data matches this question.", "vs_prev": "compared with the previous period",
           "before": "before", "went": "{l} went from {a} in {m1} to {b} in {m2}{c}.",
           "dec": "Biggest decrease", "inc": "Biggest increase", "low": "Lowest", "high": "Highest",
           "then": ", then ", "other": "At the other end"},
    "de": {"empty": "Zu dieser Frage passen keine Daten.", "vs_prev": "gegenüber dem Zeitraum davor",
           "before": "davor", "went": "{l}: im {m1} {a}, im {m2} {b}{c}.",
           "dec": "Stärkster Rückgang", "inc": "Stärkster Anstieg", "low": "Niedrigste Werte",
           "high": "Höchste Werte", "then": ", danach ", "other": "Am anderen Ende"},
}


FOUNDER_DE = {"solo": "allein gegründet", "friends": "mit Freunden gegründet", "couple": "als Paar gegründet"}


def answer_text(spec, table, de=False):
    """The answer sentence is built from the computed table, so it cannot contain a wrong number."""
    w = WORDS["de" if de else "en"]
    unit = UNITS.get(spec.metric, "")
    label = METRIC_DE[spec.metric] if de else LABEL[spec.metric]
    label = label[0].upper() + label[1:]
    f = lambda v: _fmt(v, unit, de)  # noqa: E731
    if table.empty:
        return w["empty"]
    if spec.group_by == "none":
        row = table.iloc[0]
        if "change_pct" in table and row["change_pct"] == row["change_pct"]:
            return f"{label}: {f(row['value'])}, {_pct_txt(row['change_pct'], de)} {w['vs_prev']} ({f(row['previous'])})."
        if "difference" in table:
            return f"{label}: {f(row['value'])}, {w['before']} {f(row['previous'])}."
        return f"{label}: {f(row['value'])}."
    if spec.group_by == "month":
        first, last = table.iloc[0], table.iloc[-1]
        change = f" ({_pct_txt(100 * (last['value'] / first['value'] - 1), de)})" if first["value"] > 0 else ""
        return w["went"].format(l=label, a=f(first["value"]), m1=first["group"], b=f(last["value"]),
                                m2=last["group"], c=change)
    by_change = "change_pct" in table and table["change_pct"].notna().any()
    name = (lambda g: FOUNDER_DE.get(g, g)) if de else (lambda g: g)  # noqa: E731
    show = ((lambda r: f"{name(r['group'])} {_pct_txt(r['change_pct'], de)}") if by_change else
            (lambda r: f"{name(r['group'])} {f(r['value'])}"))
    rows = [show(r) for _, r in table.head(3).iterrows()]
    first_word = (w["dec"] if by_change and spec.sort == "asc" else w["inc"] if by_change else
                  w["low"] if spec.sort == "asc" else w["high"])
    text = f"{label}: {first_word}: {w['then'].join(rows)}."
    groups_total = spec.limit >= 20 or len(table) < spec.limit  # the whole list is shown, not just a top-N
    if len(table) > 3 and groups_total:
        text += f" {w['other']}: {show(table.iloc[-1])}."
    return text


def ask(question):
    de = is_german(question)
    try:
        spec, notes = plan(question)
    except (ValidationError, json.JSONDecodeError):
        return {"question": question, "error": (
            "Die Frage wurde nicht verstanden. Nennen Sie eine Kennzahl, zum Beispiel Umsatz, Kunden oder Liquidität."
            if de else "Could not understand the question. Try naming a figure, for example revenue, customers or cash.")}
    table, run_notes = run_query(spec)
    source = "aus den berechneten Zahlen gebildet (keine KI)" if de else "built from the computed numbers (no AI)"
    return {"question": question, "lang": "de" if de else "en", "answer": answer_text(spec, table, de),
            "answer_source": source, "query": spec.model_dump(), "query_in_words": describe(spec),
            "notes": notes + run_notes, "partner_level": spec.metric in PARTNER_LEVEL,
            "table": table.to_dict(orient="records")}
