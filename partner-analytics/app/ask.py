"""Question -> query form (LLM) -> numbers (Python) -> short explanation (LLM, number-checked)."""
import difflib
import json
import os
import re

import httpx
import ollama
from pydantic import ValidationError

from .engine import PARTNER_LEVEL, UNITS, QuerySpec, describe, load, run_query

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
            notes.append(f"Ignored {field} '{picked}': not mentioned in the question.")
            snapped = None
        elif picked and not snapped:
            notes.append(f"Ignored unknown {field} '{picked}'.")
        setattr(spec, field, snapped)
    return _backstops(spec, question, notes), notes


TREND = re.compile(r"\b(develop\w*|trend\w*|over time|month by month|entwick\w*|verlauf)\b", re.I)
CHANGE = re.compile(r"\b(lost|lose|losing|gain\w*|grew|grow\w*|decline\w*|declining|drop\w*|increas\w*|"
                    r"decreas\w*|chang\w*|compared|verlor\w*|gewachsen|wachstum|rückgang|gesunken|gestiegen)\b", re.I)
DOWN = re.compile(r"\b(lost|losing|least|lowest|worst|fewest|below|drop\w*|declin\w*|decreas\w*|weakest|"
                  r"wenigsten|niedrigst\w*|schlechtest\w*|verlor\w*|rückgang)\b", re.I)
UP = re.compile(r"\b(most|highest|best|top|largest|biggest|grew|gained|strongest|meisten|höchst\w*|"
                r"best\w*|gewachsen)\b", re.I)
LIMIT = re.compile(r"\b(?:top|bottom|best|worst)?\s*(\d{1,2})\s+(?:\w+\s)?(?:locations|standorte|partners|cities|states)\b"
                   r"|\b(?:top|bottom)\s+(\d{1,2})\b", re.I)


def _backstops(spec, question, notes):
    """Rules that catch the planner's common misses; each one is reported in the notes."""
    def fix(field, value, why):
        setattr(spec, field, value)
        notes.append(f"Rule: {field} set to {value} ({why}).")

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
        if len(named) == 1 and getattr(spec, field) != named[0] and (spec.group_by != field or field == "location"):
            fix(field, named[0], "named in the question")
    if spec.location and spec.group_by == "location":
        fix("group_by", "none", "one location asked about")
    if spec.metric == "locations" and spec.group_by == "location":
        fix("group_by", "none", "counting locations")

    # Grouping by a field and filtering on it at once would leave nothing to compare.
    for field in ("founder_type", "state", "location"):
        if spec.group_by == field and getattr(spec, field):
            fix(field, None, f"comparing across {field.replace('_', ' ')}")
    monthly = spec.metric not in PARTNER_LEVEL
    if monthly and TREND.search(question) and spec.group_by == "none":
        fix("group_by", "month", "question asks how it developed")
        if spec.period == "last_month":
            fix("period", "last_12_months", "a trend needs more than one month")
    if monthly and spec.group_by == "month" and spec.growth:
        fix("growth", False, "the monthly trend already shows the change")
    if monthly and not spec.growth and spec.group_by != "month" and CHANGE.search(question):
        fix("growth", True, "question asks about a change")
    if spec.group_by not in ("none", "month"):
        want = "asc" if DOWN.search(question) else "desc" if UP.search(question) else None
        if want and want != spec.sort:
            fix("sort", want, "question asks for " + ("the lowest" if want == "asc" else "the highest"))
    m = LIMIT.search(question)
    if m:
        n = int(m.group(1) or m.group(2))
        if 1 <= n <= 60 and n != spec.limit:
            fix("limit", n, "number given in the question")
    return spec


def _fmt(v, unit):
    if v is None or v != v:
        return "n/a"
    if unit == "€":
        return f"{v:,.0f} €"
    if unit in ("%", "months"):
        return f"{v:.1f}{' %' if unit == '%' else ' months'}"
    return f"{v:,.0f}" if abs(v) >= 100 else f"{v:.1f}"


def _numbers_in(text):
    return {float(n.replace(",", "").replace(" ", "")) for n in re.findall(r"-?\d[\d,]*\.?\d*", text)}


LABEL = {"revenue": "Revenue", "costs": "Costs", "profit": "Profit", "customers": "Customers",
         "new_customers": "New customers", "enquiries": "Enquiries", "hours": "Hours delivered", "staff": "Staff",
         "cash": "Cash", "conversion_rate": "Conversion rate", "revenue_vs_plan": "Revenue vs. plan",
         "locations": "Locations", "months_to_second_location": "Months to a second location",
         "share_with_second_location": "Share with a second location"}


def answer_text(spec, table):
    """The answer sentence is built from the computed table, so it cannot contain a wrong number."""
    unit = UNITS.get(spec.metric, "")
    label = LABEL[spec.metric]
    if table.empty:
        return "No data matches this question."
    if spec.group_by == "none":
        row = table.iloc[0]
        if "change_pct" in table and row["change_pct"] == row["change_pct"]:
            return (f"{label}: {_fmt(row['value'], unit)}, {row['change_pct']:+.1f} % compared with the "
                    f"previous period ({_fmt(row['previous'], unit)}).")
        if "difference" in table:
            return f"{label}: {_fmt(row['value'], unit)}, before {_fmt(row['previous'], unit)}."
        return f"{label}: {_fmt(row['value'], unit)}."
    if spec.group_by == "month":
        first, last = table.iloc[0], table.iloc[-1]
        change = f" ({100 * (last['value'] / first['value'] - 1):+.1f} %)" if first["value"] > 0 else ""
        return (f"{label} went from {_fmt(first['value'], unit)} in {first['group']} "
                f"to {_fmt(last['value'], unit)} in {last['group']}{change}.")
    by_change = "change_pct" in table and table["change_pct"].notna().any()
    col = "change_pct" if by_change else "value"
    show = (lambda r: f"{r['group']} {r['change_pct']:+.1f} %") if by_change else            (lambda r: f"{r['group']} {_fmt(r['value'], unit)}")
    rows = [show(r) for _, r in table.head(3).iterrows()]
    first_word = ("Biggest decrease" if by_change and spec.sort == "asc" else
                  "Biggest increase" if by_change else "Lowest" if spec.sort == "asc" else "Highest")
    text = f"{label}: {first_word}: {', then '.join(rows)}."
    if len(table) > 3:
        other = table.iloc[-1]
        text += f" At the other end: {show(other)}."
    return text


def ask(question):
    try:
        spec, notes = plan(question)
    except (ValidationError, json.JSONDecodeError):
        return {"question": question, "error": "Could not understand the question. Try naming a figure, "
                                               "for example revenue, customers or cash."}
    table, run_notes = run_query(spec)
    answer, source = answer_text(spec, table), "built from the computed numbers"
    return {"question": question, "answer": answer, "answer_source": source, "query": spec.model_dump(),
            "query_in_words": describe(spec), "notes": notes + run_notes,
            "partner_level": spec.metric in PARTNER_LEVEL, "table": table.to_dict(orient="records")}
