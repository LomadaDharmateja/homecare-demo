"""Staff dashboard. Start with: streamlit run dashboard.py"""
from collections import Counter

import streamlit as st

from app import db

URGENCY_RANK = {"high": 0, "medium": 1, "low": 2}

st.set_page_config(page_title="HOMECARE intake", layout="wide")
st.title("HOMECARE intake: demo dashboard")
st.caption("Synthetic data only. Nothing is sent to customers: approving a draft only changes its status.")

db.init_db()
records = db.list_requests()
overdue = db.list_overdue()
open_tab, approval_tab, metrics_tab = st.tabs(["Open requests", "Approval queue", "Metrics"])

with open_tab:
    open_records = [r for r in records if r["followup_status"] != "approved"]
    sort_by = st.radio("Sort by", ["Urgency (high first)", "Newest first"], horizontal=True)
    if sort_by.startswith("Urgency"):
        open_records.sort(key=lambda r: (URGENCY_RANK.get(r["urgency"], 3), r["received_at"]))
    else:
        open_records.sort(key=lambda r: r["received_at"], reverse=True)
    st.dataframe(
        [
            {
                "id": r["id"], "urgency": r["urgency"], "priority": r["priority"], "service": r["service_type"],
                "location": r["location"], "callback": r["callback_requested"],
                "contact time": r["preferred_contact_time"], "missing": ", ".join(r["missing_info"]),
                "summary": r["summary"], "follow-up": r["followup_status"], "received": r["received_at"],
            }
            for r in open_records
        ],
        hide_index=True,
        use_container_width=True,
    )
    st.write(f"{len(open_records)} open requests")

with approval_tab:
    pending = [r for r in records if r["followup_status"] == "pending_approval"]
    pending.sort(key=lambda r: (URGENCY_RANK.get(r["urgency"], 3), r["received_at"]))
    if not pending:
        st.info("No drafts waiting for approval.")
    for r in pending:
        with st.container(border=True):
            st.markdown(f"**#{r['id']}** · urgency **{r['urgency']}** · {r['service_type']} · {r['location'] or 'no location'}")
            st.markdown(f"**Customer wrote:** {r['text']}")
            st.markdown(f"**Drafted reply:** {r['followup_draft']}")
            approve_col, reject_col, _ = st.columns([1, 1, 6])
            if approve_col.button("Approve", key=f"approve-{r['id']}", type="primary"):
                db.review_followup(r["id"], "approved")
                st.rerun()
            if reject_col.button("Reject", key=f"reject-{r['id']}"):
                db.review_followup(r["id"], "rejected")
                st.rerun()

with metrics_tab:
    total_col, high_col, overdue_col = st.columns(3)
    total_col.metric("Requests", len(records))
    high_col.metric("High urgency", sum(r["urgency"] == "high" for r in records))
    overdue_col.metric("Overdue follow-ups", len(overdue), help="Callback requested, >24 h old, no approved follow-up")
    per_day_col, urgency_col = st.columns(2)
    with per_day_col:
        st.subheader("Requests per day")
        per_day = Counter(r["received_at"][:10] for r in records)
        st.bar_chart([{"day": day, "requests": n} for day, n in sorted(per_day.items())], x="day", y="requests")
    with urgency_col:
        st.subheader("Requests by urgency")
        st.bar_chart(
            [{"urgency": level, "requests": sum(r["urgency"] == level for r in records)} for level in URGENCY_RANK],
            x="urgency", y="requests",
        )
    st.subheader("Overdue follow-ups")
    if overdue:
        st.dataframe(
            [{"id": r["id"], "received": r["received_at"], "urgency": r["urgency"], "summary": r["summary"],
              "follow-up": r["followup_status"]} for r in overdue],
            hide_index=True, use_container_width=True,
        )
    else:
        st.write("None.")
