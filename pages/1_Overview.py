from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st
from src.preview_privacy import mask_identifiers

st.title("🩺 HealthQ AI")
st.caption("Healthcare Data Quality Monitoring Assistant")

data = st.session_state.get("healthq_data")

if data is None:
    st.info("Open the main app and load a CSV first.")
    st.stop()

database_file = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "healthq_ai.db"
)

issues = pd.DataFrame()
scores = pd.DataFrame()

if database_file.exists():
    with sqlite3.connect(database_file) as connection:
        tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'",
            connection,
        )["name"].tolist()

        if "quality_issues" in tables:
            issues = pd.read_sql_query(
                "SELECT * FROM quality_issues", connection
            )

        if "risk_scores" in tables:
            scores = pd.read_sql_query(
                "SELECT * FROM risk_scores", connection
            )

flagged_records = (
    int(issues["Record"].nunique()) if not issues.empty else 0
)
missing_cells = int(data.isna().sum().sum())
duplicate_rows = int(data.duplicated().sum())

col1, col2, col3, col4 = st.columns(4)
col1.metric("Records", f"{len(data):,}")
col2.metric("Columns", f"{len(data.columns):,}")
col3.metric("Missing cells", f"{missing_cells:,}")
col4.metric("Exact duplicate rows", f"{duplicate_rows:,}")

st.subheader("Quality overview")
st.metric("Records with issues", f"{flagged_records:,}")

if not scores.empty and "Risk level" in scores.columns:
    flagged_scores = scores[scores["Risk score"] > 0]
    counts = (
        flagged_scores["Risk level"]
        .value_counts()
        .reindex(["Low", "Medium", "High"], fill_value=0)
    )

    if flagged_scores.empty:
        st.success("No records currently have a risk score above zero.")
    else:
        st.bar_chart(counts)

st.subheader("Dataset preview")
preview, masked_columns = mask_identifiers(data.head(10))
if masked_columns:
    st.caption(f"Likely identifiers hidden in this preview: {', '.join(masked_columns)}. Source data and exports are unchanged.")
st.dataframe(preview, use_container_width=True)
