"""Partnerhandbuch-Assistent. Start: python -m streamlit run dashboard.py --server.port 8503"""
from collections import Counter

import streamlit as st

from app import assistant

st.set_page_config(page_title="HOMECARE Partnerhandbuch-Assistent", page_icon="📘", layout="wide")
st.title("📘 Partnerhandbuch-Assistent")
st.caption("Demo mit einem fiktiven Handbuch. Antworten kommen nur aus dem Handbuch, mit Quelle. "
           "Alles läuft lokal; keine Daten verlassen den Rechner.")

ask_tab, gaps_tab, book_tab = st.tabs(["Frage stellen", "Wissenslücken", "Handbuch"])

BEISPIELE = [
    "Bis wann muss ich mit der Pflegekasse abrechnen?",
    "Darf ich als Alltagshelfer ein Geschenk von einer Kundin annehmen?",
    "Was mache ich, wenn ein Kunde nicht die Tür öffnet?",
    "Eine Anfrage kommt aus dem Gebiet eines anderen Partners. Was tun?",
    "Welche Software empfiehlt die Zentrale für die Buchhaltung?",
    "Meine Kundin ist gestürzt und atmet schwer!",
]
STATUS = {"answered": "✅ Antwort aus dem Handbuch", "excerpt_shown": "📄 Originaltext aus dem Handbuch "
          "(die KI-Antwort hat die Prüfung nicht bestanden)", "not_found": "❔ Nicht im Handbuch",
          "emergency": "🚨 Notfall"}

with ask_tab:
    wahl = st.selectbox("Beispielfragen", ["(eigene Frage unten eingeben)"] + BEISPIELE)
    frage = st.text_input("Deine Frage (Deutsch oder Englisch)", value="" if wahl.startswith("(") else wahl)
    if st.button("Fragen", type="primary") and frage.strip():
        with st.spinner("Suche im Handbuch..."):
            try:
                st.session_state["result"] = assistant.ask(frage)
            except RuntimeError as e:
                st.error(str(e))
    r = st.session_state.get("result")
    if r:
        st.caption(STATUS.get(r["status"], r["status"]))
        if r["status"] == "emergency":
            st.error(r["answer"])
        elif r["status"] == "not_found":
            st.warning(r["answer"])
        else:
            st.success(r["answer"])
        for s in r["sources"]:
            with st.expander(f"Quelle: {s['doc']} › {s['section']}  (verantwortlich: {s['owner']}, Stand {s['date']})"):
                st.markdown(s["text"])
        c1, c2, _ = st.columns([1, 1, 6])
        if c1.button("👍 Hilfreich", key=f"up{r['id']}"):
            assistant.feedback(r["id"], True)
            st.toast("Danke!")
        if c2.button("👎 Nicht hilfreich", key=f"down{r['id']}"):
            assistant.feedback(r["id"], False)
            st.toast("Notiert: erscheint unter Wissenslücken.")
        with st.expander("Wie die Antwort entstanden ist"):
            st.write("**Gefundene Abschnitte** (Suche nach Bedeutung + exakten Wörtern):")
            for h in r["retrieved"]:
                st.write(f"- {h['section']} (Ähnlichkeit {h['cosine']}, Wort-Treffer {h['bm25']})")
            st.write(f"**Prüfung der KI-Antwort:** {r['check']}")

with gaps_tab:
    st.write("Fragen, die das Handbuch nicht beantworten konnte, und Antworten mit 👎. "
             "So sieht die Zentrale, welche Themen im Handbuch fehlen.")
    gaps = assistant.knowledge_gaps()
    if not gaps:
        st.info("Noch keine offenen Fragen.")
    else:
        st.metric("Offene Fragen", len(gaps))
        counts = Counter(g["question"].strip().lower() for g in gaps)
        st.dataframe([{"Frage": g["question"], "Gestellt am": g["asked_at"][:16].replace("T", " "),
                       "Grund": "nicht im Handbuch" if g["status"] == "not_found" else "als nicht hilfreich markiert",
                       "Wie oft": counts[g["question"].strip().lower()]} for g in gaps],
                     hide_index=True, use_container_width=True)

with book_tab:
    sections = assistant.index().sections
    docs = {}
    for s in sections:
        docs.setdefault(s["doc"], []).append(s)
    for doc, parts in docs.items():
        with st.expander(f"{doc}  ·  {parts[0]['owner']}  ·  Stand {parts[0]['date']}"):
            for p in parts:
                st.markdown(f"**{p['section']}**\n\n{p['text']}")
