"""Weekly network report: rules find the problems, the LLM only writes the summary (numbers checked)."""
import json

import re

from .ask import OllamaUnavailable, _chat, _numbers_in
from .engine import load

SUMMARY_PROMPT = """Schreibe eine Zusammenfassung dieses wöchentlichen Franchise-Netzwerkberichts für die Zentrale,
auf Deutsch, 2-3 Sätze. Der erste Satz handelt von "most_urgent" und nennt den Standort. Danach die Gesamtzahlen
des Netzwerks. Verwende nur die angegebenen Zahlen, genau so geschrieben wie angegeben. Keine Ratschläge, keine
wertenden Wörter wie "dramatisch".
Form des ersten Satzes: "Am dringendsten ist <Standort>: <Befund>."
Form des zweiten Satzes: "Im Netzwerk: <Standorte> Standorte, <Umsatz> € Umsatz (<Veränderung> % zum Vormonat), <Kunden> Kunden."
"""


def n(v):
    """German number format: 12.345"""
    return f"{v:,}".replace(",", ".")


def p(v):
    """German percent: -12,5"""
    return f"{v}".replace(".", ",")


# New locations normally run below plan with little cash; only serious cash burn is flagged for them.
RAMP_UP_MONTHS = 18


def _pct(a, b):
    return round(100 * (a / b - 1), 1) if b else None


def build_alerts():
    partners, monthly = load()
    months = sorted(monthly["month"].unique())
    last3, prev3 = months[-3:], months[-6:-3]
    age = {r.location: len([m for m in months if m >= r.opened]) for r in partners.itertuples()}
    alerts = []
    for loc, df in monthly.groupby("location"):
        df = df.set_index("month")
        if not set(prev3) <= set(df.index):
            continue  # opened too recently to compare
        cust_now, cust_before = df.loc[last3, "customers"].mean(), df.loc[prev3, "customers"].mean()
        change = _pct(cust_now, cust_before)
        flow = (df["revenue_eur"] - df["costs_eur"]).loc[months[-4:]]
        cash = int(df.loc[months[-1], "cash_eur"])
        costs = int(df.loc[months[-1], "costs_eur"])
        vs_plan = _pct(df.loc[last3, "revenue_eur"].sum(), df.loc[last3, "plan_revenue_eur"].sum())

        mature = age[loc] > RAMP_UP_MONTHS
        burn = int(-flow[flow < 0].mean()) if (flow < 0).any() else 0
        revenue = int(df.loc[months[-1], "revenue_eur"])
        runway = cash // burn if burn else 99
        if (flow < 0).sum() >= 3 and burn > 0.05 * revenue and (runway <= 6 or mature):
            alerts.append({"level": "high" if runway <= 6 else "medium", "location": loc, "type": "cash burn",
                           "runway": runway,
                           "text": f"{loc}: Kosten über Umsatz in {(flow < 0).sum()} der letzten 4 Monate, "
                                   f"etwa {n(burn)} € pro Monat; die Liquidität von {n(cash)} € reicht noch "
                                   f"etwa {cash // burn} Monate."})
        elif cash < costs and mature:
            alerts.append({"level": "medium", "location": loc, "type": "low cash",
                           "text": f"{loc}: Liquidität {n(cash)} € ist weniger als ein Monat Kosten ({n(costs)} €)."})
        if change is not None and change <= -10:
            alerts.append({"level": "medium", "location": loc, "type": "losing customers",
                           "text": f"{loc}: Kunden {p(abs(change))} % weniger (letzte 3 Monate gegenüber den 3 davor)."})
        if vs_plan is not None and vs_plan <= -15 and mature:
            alerts.append({"level": "medium", "location": loc, "type": "below plan",
                           "text": f"{loc}: Umsatz {p(abs(vs_plan))} % unter Businessplan in den letzten 3 Monaten."})
        if change is not None and change >= 25 and mature:
            alerts.append({"level": "info", "location": loc, "type": "strong growth",
                           "text": f"{loc}: Kunden {p(change)} % mehr (letzte 3 Monate gegenüber den 3 davor)."})
    young = sum(1 for a in age.values() if a <= RAMP_UP_MONTHS)
    return _merge(alerts), months[-1], young


def _merge(alerts):
    """One line per location: the most serious level, all findings joined."""
    order = {"high": 0, "medium": 1, "info": 2}
    merged = {}
    for a in sorted(alerts, key=lambda a: (order[a["level"]], a.get("runway", 99))):
        if a["location"] in merged:
            m = merged[a["location"]]
            m["type"] += f", {a['type']}"
            m["text"] += " Außerdem: " + a["text"].split(": ", 1)[1]
        else:
            merged[a["location"]] = dict(a)
    return sorted(merged.values(), key=lambda a: (order[a["level"]], a.get("runway", 99)))


def network_totals():
    _, monthly = load()
    months = sorted(monthly["month"].unique())
    now, before = monthly[monthly["month"] == months[-1]], monthly[monthly["month"] == months[-2]]
    return {
        "month": months[-1],
        "locations": int(now["location"].nunique()),
        "revenue_eur": int(now["revenue_eur"].sum()),
        "revenue_change_pct": _pct(now["revenue_eur"].sum(), before["revenue_eur"].sum()),
        "customers": int(now["customers"].sum()),
        "new_customers": int(now["new_customers"].sum()),
    }


def _template_summary(totals, alerts):
    high = [a for a in alerts if a["level"] == "high"]
    change = f"{totals['revenue_change_pct']:+}".replace(".", ",")
    s = (f"Im Monat {totals['month']} erzielten die {totals['locations']} Standorte {n(totals['revenue_eur'])} € "
         f"Umsatz ({change} % zum Vormonat) mit {n(totals['customers'])} Kunden.")
    if high:
        s += f" Am dringendsten: {high[0]['text']}"
    return s + f" Insgesamt {len(alerts)} Hinweise."


def weekly_report(use_llm=True):
    alerts, month, young = build_alerts()
    totals = network_totals()
    summary, source = _template_summary(totals, alerts), "Vorlage"
    if use_llm:
        # Numbers go in already written the German way, so the model can copy them exactly.
        german_totals = {**totals, "revenue_eur": n(totals["revenue_eur"]), "customers": n(totals["customers"]),
                         "new_customers": n(totals["new_customers"]),
                         "revenue_change_pct": f"{totals['revenue_change_pct']:+}".replace(".", ",")}
        facts = {"totals": german_totals, "most_urgent": alerts[0]["text"] if alerts else None,
                 "other_alerts": [a["text"] for a in alerts[1:5]], "alert_count": len(alerts)}
        try:
            text = _chat(SUMMARY_PROMPT, json.dumps(facts, ensure_ascii=False)).strip()
            allowed = _numbers_in(json.dumps(facts)) | set(range(0, 61))
            allowed |= {round(n) for n in allowed} | {round(n, -3) for n in allowed}
            unknown = {n for n in _numbers_in(text) if n not in allowed and abs(n) not in allowed}
            # The rules decide what is most urgent; the summary must lead with that location.
            first_sentence = re.split(r"(?<!\d)[.!?](?!\d)", text)[0]
            leads = not alerts or alerts[0]["location"] in first_sentence
            if text and not unknown and leads:
                summary, source = text, "KI (Zahlen geprüft)"
            else:
                source = ("Vorlage (die KI hat nicht mit dem dringendsten Hinweis begonnen)" if not unknown else
                          f"Vorlage (die KI hat Zahlen verwendet, die nicht in den Fakten stehen: {sorted(unknown)[:3]})")
        except OllamaUnavailable:
            source = "Vorlage (Ollama läuft nicht)"
    md = [f"# Wochenbericht Partnernetz ({month})", "", "_Erfundene Zahlen für eine Demo._", "", summary, "",
          "## Hinweise", "", f"_{young} Standorte in ihren ersten {RAMP_UP_MONTHS} Monaten werden nur auf "
          f"Liquiditätsverbrauch geprüft._", ""]
    icons = {"high": "🔴", "medium": "🟠", "info": "🟢"}
    md += [f"- {icons[a['level']]} {a['text']}" for a in alerts] or ["- Keine Hinweise."]
    return {"month": month, "summary": summary, "summary_source": source, "totals": totals,
            "alerts": alerts, "young_locations": young, "markdown": "\n".join(md)}
