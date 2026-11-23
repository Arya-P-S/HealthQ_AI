from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st
from src.preview_privacy import mask_identifiers

st.title("Cleaning & Export")
st.caption("Review the automated cleanup actions before downloading the cleaned copy.")

database_file = Path(__file__).resolve().parents[1] / "database" / "healthq_ai.db"
if not database_file.exists():
    st.info("Run the main app first so it can create the database.")
    st.stop()

with sqlite3.connect(database_file) as connection:
    tables = pd.read_sql_query(
        "SELECT name FROM sqlite_master WHERE type='table'", connection
    )["name"].tolist()
    if not {"records_raw", "records_clean"}.issubset(tables):
        st.info("Load a dataset first to prepare the cleaned copy.")
        st.stop()
    cleaned = pd.read_sql_query("SELECT * FROM records_clean", connection)
    raw_count = int(pd.read_sql_query(
        "SELECT COUNT(*) AS total FROM records_raw", connection
    ).loc[0, "total"])
    issues = (
        pd.read_sql_query("SELECT * FROM quality_issues", connection)
        if "quality_issues" in tables
        else pd.DataFrame(columns=["Record", "Column", "Issue", "Details"])
    )

removed_rows = max(raw_count - len(cleaned), 0)
age_changes = (
    int(issues.loc[issues["Issue"] == "Age out of range", "Record"].nunique())
    if not issues.empty and "Issue" in issues.columns
    else 0
)

raw_col, clean_col, removed_col = st.columns(3)
raw_col.metric("Source records", f"{raw_count:,}")
clean_col.metric("Cleaned records", f"{len(cleaned):,}")
removed_col.metric("Exact duplicate rows removed", f"{removed_rows:,}")

st.subheader("What cleanup changes were applied?")
actions = pd.DataFrame([
    {"Field or data": "Exact duplicate rows", "Automated action": "Removed duplicate copies; one copy is retained.", "Affected records": removed_rows},
    {"Field or data": "Age", "Automated action": "Values outside 0–120 or not numeric are set blank for staff verification.", "Affected records": age_changes},
    {"Field or data": "Gender and No-show", "Automated action": "Whitespace is trimmed and text casing is standardized.", "Affected records": "See source and cleaned preview"},
    {"Field or data": "ScheduledDay and AppointmentDay", "Automated action": "Values are parsed as dates; unparseable values become blank.", "Affected records": "See Issue Explorer"},
    {"Field or data": "Other flagged issues", "Automated action": "Kept for manual review; no automatic correction is applied here.", "Affected records": "See Issue Explorer"},
])
st.dataframe(actions, use_container_width=True, hide_index=True)
st.info("The source table is retained in SQLite. Review flagged items in Issue Explorer; this cleaned file is a working copy, not a replacement for the hospital source record.")

st.subheader("Cleaned dataset preview")
if cleaned.empty:
    st.warning("The cleaned dataset currently has no rows.")
else:
    preview, masked_columns = mask_identifiers(cleaned.head(20))
    if masked_columns:
        st.caption(f"Likely identifiers hidden in this preview: {', '.join(masked_columns)}. The downloaded CSV remains unchanged.")
    st.dataframe(preview, use_container_width=True)

reviewed = st.checkbox("I reviewed the cleanup summary and understand flagged values may need staff verification.")
st.download_button(
    "Download cleaned CSV",
    data=cleaned.to_csv(index=False).encode("utf-8"),
    file_name="healthq_ai_cleaned.csv",
    mime="text/csv",
    disabled=not reviewed or cleaned.empty,
)
