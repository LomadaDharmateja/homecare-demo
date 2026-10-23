"""Partner analytics dashboard. Run: python -m streamlit run dashboard.py --server.port 8502"""
import pandas as pd
import streamlit as st

from app.ask import OllamaUnavailable, ask
from app.engine import UNITS
from app.report import weekly_report

st.set_page_config(page_title="HOMECARE partner analytics", page_icon="📊", layout="wide")
st.title("HOMECARE partner analytics")
st.caption("Demo with fictional figures for 55 locations. The AI fills in a query form; Python does every calculation.")

ask_tab, report_tab = st.tabs(["Ask the data", "Weekly report & alerts"])

EXAMPLES = [
    "Do partners who founded with a friend open a second location faster?",
    "Which 5 locations lost the most customers in the last 6 months?",
    "How did total revenue develop over the last 12 months?",
    "Which 3 locations have the least cash?",
    "Wie hoch ist die Conversion Rate nach Bundesland?",
]

with ask_tab:
    pick = st.selectbox("Example questions", ["(type your own below)"] + EXAMPLES)
    question = st.text_input("Your question (English or German)", value="" if pick.startswith("(") else pick)
    if st.button("Ask", type="primary") and question.strip():
        with st.spinner("The local model is reading the question..."):
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
            value_col = "change_pct" if "change_pct" in table and table["change_pct"].notna().any() else "value"
            if len(table) > 1:
                chart = table.set_index("group")[value_col]
                if q["group_by"] == "month":
                    st.line_chart(chart)
                else:
                    st.bar_chart(chart)
            unit = UNITS.get(q["metric"], "")
            st.dataframe(table.rename(columns={"group": q["group_by"], "value": f"value {unit}".strip(),
                                               "change_pct": "change %"}),
                         hide_index=True, use_container_width=True)
            with st.expander("How this was calculated"):
                st.write(f"**Query form:** {r['query_in_words']}")
                st.json(q)
                for note in r["notes"]:
                    st.write(f"- {note}")
                st.write(f"**Answer text:** {r['answer_source']}")

with report_tab:
    st.write("Every Monday at 08:00 n8n fetches this report and sends the summary to Telegram.")
    if st.button("Build this week's report"):
        with st.spinner("Checking all locations..."):
            rep = weekly_report()
        t = rep["totals"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Locations", t["locations"])
        c2.metric(f"Revenue {t['month']}", f"{t['revenue_eur']:,} €", f"{t['revenue_change_pct']:+} %")
        c3.metric("Customers", f"{t['customers']:,}")
        c4.metric("New customers", f"{t['new_customers']:,}")
        st.info(rep["summary"])
        st.caption(f"Summary written by: {rep['summary_source']}. "
                   f"{rep['young_locations']} locations in ramp-up are only checked for cash burn.")
        icons = {"high": "🔴", "medium": "🟠", "info": "🟢"}
        for a in rep["alerts"]:
            st.write(f"{icons[a['level']]} {a['text']}")
