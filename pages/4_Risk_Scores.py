from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st

st.title("Data Quality Risk Scores")
st.caption("These scores prioritize data-quality review; they are not patient health scores.")

database_file = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "healthq_ai.db"
)

if not database_file.exists():
    st.info("Run the main app first so it can create the database.")
else:
    with sqlite3.connect(database_file) as connection:
        scores = pd.read_sql_query("SELECT * FROM risk_scores", connection)

    if scores.empty:
        st.info("No risk scores are available.")
    else:
        flagged = scores[scores["Risk score"] > 0]
        average = flagged["Risk score"].mean() if not flagged.empty else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("Total records", f"{len(scores):,}")
        col2.metric("Records with issues", f"{len(flagged):,}")
        col3.metric("Average flagged score", f"{average:.1f}/100")

        if not flagged.empty:
            counts = (
                flagged["Risk level"]
                .value_counts()
                .reindex(["Low", "Medium", "High"], fill_value=0)
            )
            st.subheader("Flagged records by risk level")
            st.bar_chart(counts)

            st.subheader("Records to review")
            st.dataframe(
                flagged.sort_values("Risk score", ascending=False),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("No records have a non-zero risk score.")