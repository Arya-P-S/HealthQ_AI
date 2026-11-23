from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st

st.title("Issue Explorer")
st.caption("Review, assign, and track data quality findings.")

database_file = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "healthq_ai.db"
)

if not database_file.exists():
    st.info("Run Data Upload first to create the database.")
    st.stop()

with sqlite3.connect(database_file) as connection:
    table_names = pd.read_sql_query(
        "SELECT name FROM sqlite_master WHERE type='table'",
        connection,
    )["name"].tolist()

    needed = {"issue_reviews", "dataset_catalog"}
    if not needed.issubset(table_names):
        st.info("Run Data Upload after selecting a dataset to create the review queue.")
        st.stop()

    queue = pd.read_sql_query("""
        SELECT
            r.issue_id,
            r.dataset_hash,
            c.dataset_name AS Dataset,
            c.dataset_type AS Type,
            r.record AS Record,
            r.column_name AS Column,
            r.issue_type AS Issue,
            r.details AS Details,
            r.severity AS Severity,
            r.status AS Status,
            COALESCE(r.owner, '') AS Owner,
            COALESCE(r.note, '') AS Note
        FROM issue_reviews AS r
        LEFT JOIN dataset_catalog AS c
            ON c.dataset_hash = r.dataset_hash
        ORDER BY
            CASE r.severity WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END,
            r.record
    """, connection)

if queue.empty:
    st.success("No issues are currently in the review queue.")
    st.stop()

st.subheader("Filter the queue")
dataset_labels = {
    "All datasets": None,
    **{
        f"{row.Dataset} · {str(row.dataset_hash)[:8]}": row.dataset_hash
        for row in queue[["Dataset", "dataset_hash"]].drop_duplicates().itertuples(index=False)
    },
}
selected_dataset_label = st.selectbox("Dataset", list(dataset_labels))
filtered = queue.copy()

dataset_hash = dataset_labels[selected_dataset_label]
if dataset_hash:
    filtered = filtered[filtered["dataset_hash"] == dataset_hash]

for label, column in [
    ("Issue type", "Issue"),
    ("Severity", "Severity"),
    ("Status", "Status"),
]:
    choices = ["All"] + sorted(filtered[column].dropna().unique().tolist())
    selected = st.selectbox(label, choices, key=f"filter_{column}")
    if selected != "All":
        filtered = filtered[filtered[column] == selected]

col1, col2, col3 = st.columns(3)
col1.metric("Findings shown", f"{len(filtered):,}")
col2.metric("High severity", int((filtered["Severity"] == "High").sum()))
col3.metric("Open", int(filtered["Status"].isin(["New", "In review"]).sum()))

display_columns = [
    "Dataset", "Type", "Record", "Column", "Issue",
    "Severity", "Status", "Owner", "Details",
]
st.dataframe(filtered[display_columns], use_container_width=True, hide_index=True)

st.download_button(
    "Download filtered issue queue",
    data=filtered[display_columns].to_csv(index=False).encode("utf-8"),
    file_name="healthq_ai_issue_queue.csv",
    mime="text/csv",
)

st.subheader("Update a review")
if not filtered.empty:
    issue_ids = filtered["issue_id"].tolist()
    labels = {
        row.issue_id: f"{row.Issue} · record {row.Record} · {row.Column}"
        for row in filtered.itertuples(index=False)
    }

    with st.form("update_issue_review"):
        selected_issue_id = st.selectbox(
            "Finding",
            issue_ids,
            format_func=lambda value: labels[value],
        )
        selected_row = filtered[filtered["issue_id"] == selected_issue_id].iloc[0]
        statuses = ["New", "In review", "Resolved", "Accepted"]
        current_status = (
            selected_row["Status"]
            if selected_row["Status"] in statuses
            else "New"
        )
        new_status = st.selectbox(
            "Review status",
            statuses,
            index=statuses.index(current_status),
        )
        owner = st.text_input("Assigned owner", value=selected_row["Owner"])
        note = st.text_area("Review note", value=selected_row["Note"])
        save = st.form_submit_button("Save review")

    if save:
        with sqlite3.connect(database_file) as connection:
            connection.execute("""
                UPDATE issue_reviews
                SET status = ?, owner = ?, note = ?, last_updated_utc = ?
                WHERE issue_id = ?
            """, (
                new_status,
                owner.strip(),
                note.strip(),
                pd.Timestamp.now(tz="UTC").isoformat(),
                selected_issue_id,
            ))
        st.success("Review update saved.")
        st.rerun()

