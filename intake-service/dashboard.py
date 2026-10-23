"""Staff dashboard (German UI). Start with: streamlit run dashboard.py"""
from collections import Counter

import streamlit as st

from app import db

URGENCY_RANK = {"high": 0, "medium": 1, "low": 2}
# Stored values stay English (code, API, n8n); only the display is German.
DE = {
    "high": "hoch", "medium": "mittel", "low": "niedrig",
    "shopping": "Einkauf", "transport": "Fahrdienst", "companionship": "Begleitung/Gesellschaft",
    "household": "Haushalt", "other": "Sonstiges",
    "morning": "vormittags", "afternoon": "nachmittags", "evening": "abends",
    "location": "Ort", "date": "Termin", "details": "Details",
    "pending_approval": "wartet auf Freigabe", "approved": "freigegeben", "rejected": "abgelehnt",
    "none": "keine nötig",
}


def de(value):
    return DE.get(value, value) if value else "–"


st.set_page_config(page_title="HOMECARE Anfragen", page_icon="📥", layout="wide")
st.title("📥 HOMECARE Kundenanfragen")
st.caption("Demo mit erfundenen Anfragen. Es wird nichts an Kunden gesendet: "
           "„Freigeben“ ändert nur den Status. Alles läuft lokal.")

db.init_db()
records = db.list_requests()
overdue = db.list_overdue()
open_tab, approval_tab, metrics_tab = st.tabs(["Offene Anfragen", "Freigabe", "Kennzahlen"])

with open_tab:
    open_records = [r for r in records if r["followup_status"] != "approved"]
    sort_by = st.radio("Sortieren nach", ["Dringlichkeit (hoch zuerst)", "Neueste zuerst"], horizontal=True)
    if sort_by.startswith("Dringlichkeit"):
        open_records.sort(key=lambda r: (URGENCY_RANK.get(r["urgency"], 3), r["received_at"]))
    else:
        open_records.sort(key=lambda r: r["received_at"], reverse=True)
    st.dataframe(
        [
            {
                "Nr.": r["id"], "Dringlichkeit": de(r["urgency"]), "Priorität": r["priority"],
                "Leistung": de(r["service_type"]), "Ort": r["location"] or "–",
                "Rückruf": "ja" if r["callback_requested"] else "nein",
                "Erreichbar": de(r["preferred_contact_time"]),
                "Fehlt": ", ".join(de(m) for m in r["missing_info"]) or "–",
                "Zusammenfassung": r["summary"], "Antwort": de(r["followup_status"]),
                "Eingang": r["received_at"][:16].replace("T", " "),
            }
            for r in open_records
        ],
        hide_index=True,
        use_container_width=True,
    )
    st.write(f"{len(open_records)} offene Anfragen")

with approval_tab:
    st.write("Jede Antwort ist ein Entwurf: Code schreibt ihn aus den geprüften Angaben, die KI hat nur die Anfrage gelesen. "
             "Ein Mensch prüft und gibt frei; erst dann würde sie verschickt.")
    pending = [r for r in records if r["followup_status"] == "pending_approval"]
    pending.sort(key=lambda r: (URGENCY_RANK.get(r["urgency"], 3), r["received_at"]))
    if not pending:
        st.info("Keine Entwürfe zur Freigabe.")
    for r in pending:
        with st.container(border=True):
            icon = "🔴" if r["urgency"] == "high" else "🟠" if r["urgency"] == "medium" else "🟢"
            st.markdown(f"{icon} **#{r['id']}** · Dringlichkeit **{de(r['urgency'])}** · "
                        f"{de(r['service_type'])} · {r['location'] or 'Ort fehlt'}")
            st.markdown(f"**Kunde schrieb:** {r['text']}")
            st.markdown(f"**Antwort-Entwurf:** {r['followup_draft']}")
            approve_col, reject_col, _ = st.columns([1, 1, 6])
            if approve_col.button("Freigeben", key=f"approve-{r['id']}", type="primary"):
                db.review_followup(r["id"], "approved")
                st.rerun()
            if reject_col.button("Ablehnen", key=f"reject-{r['id']}"):
                db.review_followup(r["id"], "rejected")
                st.rerun()

with metrics_tab:
    total_col, high_col, overdue_col = st.columns(3)
    total_col.metric("Anfragen", len(records))
    high_col.metric("Dringend", sum(r["urgency"] == "high" for r in records))
    overdue_col.metric("Überfällige Rückrufe", len(overdue),
                       help="Rückruf gewünscht, älter als 24 Stunden, keine freigegebene Antwort")
    per_day_col, urgency_col = st.columns(2)
    with per_day_col:
        st.subheader("Anfragen pro Tag")
        per_day = Counter(r["received_at"][:10] for r in records)
        st.bar_chart([{"Tag": day, "Anfragen": n} for day, n in sorted(per_day.items())], x="Tag", y="Anfragen")
    with urgency_col:
        st.subheader("Anfragen nach Dringlichkeit")
        st.bar_chart(
            [{"Dringlichkeit": de(level), "Anfragen": sum(r["urgency"] == level for r in records)}
             for level in URGENCY_RANK],
            x="Dringlichkeit", y="Anfragen",
        )
    st.subheader("Überfällige Rückrufe")
    if overdue:
        st.dataframe(
            [{"Nr.": r["id"], "Eingang": r["received_at"][:16].replace("T", " "), "Dringlichkeit": de(r["urgency"]),
              "Zusammenfassung": r["summary"], "Antwort": de(r["followup_status"])} for r in overdue],
            hide_index=True, use_container_width=True,
        )
    else:
        st.write("Keine.")
