"""Onboarding cockpit (German UI). Run: python -m streamlit run dashboard.py --server.port 8504"""
import json

import pandas as pd
import streamlit as st

from app import service
from app.checklist import PHASES, TASKS

st.set_page_config(page_title="HOMECARE Onboarding-Cockpit", page_icon="🧭", layout="wide")
st.title("🧭 HOMECARE Onboarding-Cockpit")
st.caption("Die ersten 90 Tage neuer Franchisepartner, nach der Checkliste im Partnerhandbuch. Erfundene Partner. "
           "Partner-Updates liest die lokale KI; jede Änderung gibt ein Mensch frei. Ampel und Prognosen rechnet Code.")

ICON = {"kritisch": "🔴", "Achtung": "🟠", "im Plan": "🟢"}
STATUS_ICON = {"erledigt": "✅", "blockiert": "⛔", "offen": "⬜"}
BEISPIELE = {
    "(eigene Nachricht)": "",
    "Münster: Antrag + Büro": "Hallo Herr Yıldız, der Antrag auf Anerkennung ist raus, haben ihn gestern beim Amt "
                              "eingereicht. Mit dem Büro klappt es leider nicht, der Vermieter hat abgesagt.",
    "Kassel: Versicherung": "Gute Nachricht: Die Betriebshaftpflicht ist jetzt abgeschlossen. Die Startschulung "
                            "machen wir im Dezember.",
    "Lübeck: Kunden ohne Zulassung": "Wir haben jetzt 4 Kunden! Die Zulassung ist leider immer noch nicht da.",
    "Essen (Englisch)": "Hi, our bank account is open now and we signed the office lease today.",
}

partners = service.overview()
by_id = {p["id"]: p for p in partners}
pending = service.pending()
tab1, tab2, tab3 = st.tabs(["Übersicht", f"Updates & Freigabe ({len(pending)})", "Protokoll"])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Partner im Onboarding", len(partners))
    c2.metric("🔴 kritisch", sum(p["level"] == "kritisch" for p in partners))
    c3.metric("🟠 Achtung", sum(p["level"] == "Achtung" for p in partners))
    c4.metric("Updates warten auf Freigabe", len(pending))
    table = pd.DataFrame([{
        "Ampel": f"{ICON[p['level']]} {p['level']}", "Standort": p["city"], "Partner": p["name"],
        "Tag": p["day"], "Phase": p["phase"], "Erledigt": f"{p['done']}/{p['total']}",
        "Kunden": p["active_customers"], "Bereit für Kunden": "ja" if p["ready_for_customers"] else "nein",
        "Wichtigster Hinweis": p["findings"][0]["text"] if p["findings"] else "-", "Betreuung": p["manager"],
    } for p in sorted(partners, key=lambda p: (["kritisch", "Achtung", "im Plan"].index(p["level"]), -p["day"]))])
    st.dataframe(table, hide_index=True, use_container_width=True)

    pick = st.selectbox("Partner ansehen", [p["id"] for p in partners],
                        format_func=lambda i: f"{by_id[i]['city']} - {by_id[i]['name']} (Tag {by_id[i]['day']})")
    p = by_id[pick]
    st.progress(min(p["day"], 90) / 90, text=f"Tag {p['day']} von 90 · Phase {p['phase']}: {PHASES[p['phase']]}")
    for f in p["findings"]:
        (st.error if f["level"] == "kritisch" else st.warning)(f["text"])
    if not p["findings"]:
        st.success("Alles im Plan.")
    cols = st.columns(3)
    for phase, col in zip(PHASES, cols):
        with col:
            st.markdown(f"**Phase {phase}: {PHASES[phase]}**")
            for t in [t for t in TASKS if t.phase == phase]:
                row = p["tasks"][t.id]
                late = row["status"] != "erledigt" and t.due_day < p["day"]
                st.write(f"{STATUS_ICON[row['status']]} {t.title}" + (" 🔒" if t.gate else "")
                         + f"  \n<small>bis Tag {t.due_day} · {t.owner}{' · **überfällig**' if late else ''}"
                         + (f" · {row['note']}" if row["note"] else "") + "</small>", unsafe_allow_html=True)
    st.caption("🔒 = muss vor dem ersten Kundeneinsatz erledigt sein (Checkliste im Handbuch).")
    with st.expander("Punkt manuell ändern (z. B. was die KI übersehen hat)"):
        m1, m2, m3 = st.columns(3)
        task = m1.selectbox("Punkt", [t.id for t in TASKS], format_func=lambda i: next(t.title for t in TASKS if t.id == i))
        status = m2.selectbox("Neuer Status", ["erledigt", "blockiert", "offen"])
        who = m3.text_input("Geändert von", key="manual_who")
        note = st.text_input("Notiz")
        if st.button("Ändern"):
            try:
                service.set_task(pick, task, status, who, note)
                st.rerun()
            except ValueError as e:
                st.error(str(e))

with tab2:
    st.subheader("Neues Partner-Update")
    st.write("So kommt eine E-Mail oder WhatsApp des Partners an. Die KI schlägt Änderungen vor; "
             "es ändert sich nichts, bis jemand freigibt.")
    u1, u2 = st.columns([1, 2])
    who_id = u1.selectbox("Von Partner", [p["id"] for p in partners],
                          format_func=lambda i: f"{by_id[i]['city']} - {by_id[i]['name']}", key="update_partner")
    example = u2.selectbox("Beispiel", list(BEISPIELE), key="example")
    message = st.text_area("Nachricht", value=BEISPIELE[example], height=100)
    if st.button("Vorschlag erstellen", type="primary") and message.strip():
        with st.spinner("Die lokale KI liest das Update..."):
            try:
                service.submit_update(who_id, message, "Dashboard")
                st.rerun()
            except RuntimeError as e:
                st.error(str(e))

    st.subheader(f"Warten auf Freigabe ({len(pending)})")
    if not pending:
        st.info("Keine offenen Vorschläge.")
    for prop in pending:
        with st.container(border=True):
            st.markdown(f"**{prop['city']}** · Vorschlag #{prop['id']} · eingegangen {prop['received_at'][:16]} UTC")
            st.markdown(f"> {prop['message']}")
            for w in prop["warnings"]:
                st.error("⚠️ " + w)
            chosen = []
            for c in prop["changes"]:
                label = (f"{STATUS_ICON[c['status']]} **{c['titel']}**: {c['vorher']} → {c['status']}  \n"
                         f"Beleg: „{c['satz']}“ · entschieden von: {c['entschieden_von']}")
                if st.checkbox(label, value=True, key=f"c{prop['id']}{c['task']}"):
                    chosen.append(c["task"])
            if prop["active_customers"] is not None:
                st.write(f"Kundenzahl: {by_id[prop['partner_id']]['active_customers']} → **{prop['active_customers']}**")
            if not prop["changes"] and prop["active_customers"] is None:
                st.write("Keine Änderung an der Checkliste erkannt.")
            if prop["dropped"]:
                with st.expander("Nicht übernommen (und warum)"):
                    for d in prop["dropped"]:
                        st.write(f"- „{d['satz']}“: {d['grund']}")
            d1, d2, d3 = st.columns([2, 1, 1])
            by = d1.text_input("Entschieden von", key=f"by{prop['id']}", placeholder="Name")
            if d2.button("Freigeben", key=f"ok{prop['id']}", type="primary"):
                try:
                    service.decide(prop["id"], True, by, chosen)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
            if d3.button("Ablehnen", key=f"no{prop['id']}"):
                try:
                    service.decide(prop["id"], False, by)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))

with tab3:
    st.write("Jede Änderung mit Zeit, Person, vorher/nachher und Beleg. Nichts wird überschrieben.")
    log = service.audit_log(200)
    st.dataframe(pd.DataFrame([{"Zeit (UTC)": a["at"][:16], "Standort": a["city"], "Wer": a["actor"],
                                "Was": a["action"], "Details": ", ".join(f"{k}: {v}" for k, v in json.loads(a["detail"]).items())}
                               for a in log]), hide_index=True, use_container_width=True)
