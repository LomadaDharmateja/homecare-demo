"""Partner analytics dashboard (German UI). Run: python -m streamlit run dashboard.py --server.port 8502"""
import pandas as pd
import streamlit as st

from app.ask import FOUNDER_DE, OllamaUnavailable, ask
from app.engine import GROUP_DE, UNITS
from app.report import weekly_report

st.set_page_config(page_title="HOMECARE Partner-Analyse", page_icon="📊", layout="wide")
st.title("📊 HOMECARE Partner-Analyse")
st.caption("Demo mit erfundenen Zahlen für 55 Standorte. Die KI füllt nur ein Abfrage-Formular aus; "
           "jede Zahl rechnet Python. Alles läuft lokal.")

def de_number(v):
    if v is None or v != v:
        return "–"
    s = f"{v:,.0f}" if float(v).is_integer() or abs(v) >= 1000 else f"{v:,.1f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


ask_tab, report_tab = st.tabs(["Frage an die Daten", "Wochenbericht & Hinweise"])

BEISPIELE = [
    "Eröffnen Partner, die mit Freunden gegründet haben, schneller einen zweiten Standort?",
    "Welche 5 Standorte haben in den letzten 6 Monaten die meisten Kunden verloren?",
    "Wie hat sich der Umsatz in den letzten 12 Monaten entwickelt?",
    "Welche 3 Standorte haben die wenigste Liquidität?",
    "Wie hoch ist die Conversion Rate nach Bundesland?",
    "Which locations are furthest below their business plan?",
]

with ask_tab:
    pick = st.selectbox("Beispielfragen", ["(eigene Frage unten eingeben)"] + BEISPIELE)
    question = st.text_input("Ihre Frage (Deutsch oder Englisch)", value="" if pick.startswith("(") else pick)
    if st.button("Fragen", type="primary") and question.strip():
        with st.spinner("Das lokale Modell liest die Frage..."):
            try:
                r = ask(question)
            except OllamaUnavailable as e:
                st.error(str(e))
                st.stop()
        if "error" in r:
            st.warning(r["error"])
        else:
            st.subheader(r["answer"])
            table = pd.DataFrame(r["table"])
            q = r["query"]
            if q["group_by"] == "founder_type":
                table["group"] = table["group"].map(lambda g: FOUNDER_DE.get(g, g))
            value_col = "change_pct" if "change_pct" in table and table["change_pct"].notna().any() else "value"
            if len(table) > 1:
                chart = table.set_index("group")[value_col]
                if q["group_by"] == "month":
                    st.line_chart(chart)
                else:
                    st.bar_chart(chart)
            unit = UNITS.get(q["metric"], "").replace("months", "Monate")
            # German number format in the table (31,8 and 1.234.567); the chart above uses the raw numbers.
            for col in ("value", "previous", "difference", "change_pct"):
                if col in table:
                    table[col] = table[col].map(de_number)
            st.dataframe(table.rename(columns={"group": GROUP_DE.get(q["group_by"], "Gruppe"),
                                               "value": f"Wert {unit}".strip(), "previous": "davor",
                                               "difference": "Differenz", "change_pct": "Veränderung %"}),
                         hide_index=True, use_container_width=True)
            with st.expander("So wurde gerechnet"):
                st.write(f"**Abfrage-Formular:** {r['query_in_words']}")
                st.json(q)
                for note in r["notes"]:
                    st.write(f"- {note}")
                st.write(f"**Antwortsatz:** {r['answer_source']}")

with report_tab:
    st.write("Jeden Montag um 08:00 holt n8n diesen Bericht und schickt die Zusammenfassung per Telegram.")
    if st.button("Bericht dieser Woche erstellen"):
        with st.spinner("Alle Standorte werden geprüft..."):
            rep = weekly_report()
        t = rep["totals"]
        de_num = lambda v: f"{v:,}".replace(",", ".")  # noqa: E731
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Standorte", t["locations"])
        c2.metric(f"Umsatz {t['month']}", f"{de_num(t['revenue_eur'])} €",
                  f"{t['revenue_change_pct']:+} %".replace(".", ","))
        c3.metric("Kunden", de_num(t["customers"]))
        c4.metric("Neukunden", de_num(t["new_customers"]))
        st.info(rep["summary"])
        st.caption(f"Zusammenfassung geschrieben von: {rep['summary_source']}. "
                   f"{rep['young_locations']} Standorte in der Anlaufphase werden nur auf Liquiditätsverbrauch geprüft.")
        icons = {"high": "🔴", "medium": "🟠", "info": "🟢"}
        for a in rep["alerts"]:
            st.write(f"{icons[a['level']]} {a['text']}")
