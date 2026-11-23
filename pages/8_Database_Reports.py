from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st
from src.preview_privacy import mask_identifiers

st.title("Database & Reports")

database_file = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "healthq_ai.db"
)

if not database_file.exists():
    st.info("Run the main app first to create the database.")
else:
    with sqlite3.connect(database_file) as connection:
        tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'",
            connection,
        )["name"].tolist()

        required = [
            "records_raw",
            "records_clean",
            "quality_issues",
            "risk_scores",
            "dataset_catalog",
            "issue_reviews",
        ]

        if not all(table in tables for table in required):
            st.warning("Some database tables are missing. Run the main app again.")
        else:
            raw_count = pd.read_sql_query(
                "SELECT COUNT(*) AS n FROM records_raw", connection
            ).loc[0, "n"]
            clean_count = pd.read_sql_query(
                "SELECT COUNT(*) AS n FROM records_clean", connection
            ).loc[0, "n"]
            issues = pd.read_sql_query(
                "SELECT * FROM quality_issues", connection
            )
            scores = pd.read_sql_query(
                "SELECT * FROM risk_scores", connection
            )

            st.metric("Raw records", f"{raw_count:,}")
            st.metric("Cleaned records", f"{clean_count:,}")

            st.subheader("Browse a saved table")
            selected = st.selectbox("Table", required)
            preview = pd.read_sql_query(
                f"SELECT * FROM {selected} LIMIT 100", connection
            )
            preview_display, masked_columns = mask_identifiers(preview)
            if masked_columns:
                st.caption(f"Likely identifiers masked in this preview: {', '.join(masked_columns)}.")
            st.dataframe(preview_display, use_container_width=True, hide_index=True)

    if all(table in tables for table in required):
        issue_summary = (
            issues.groupby("Issue", dropna=False)
            .agg(Findings=("Record", "size"), Affected_records=("Record", "nunique"))
            .reset_index()
            .rename(columns={"Issue": "Issue type"})
            if not issues.empty
            else pd.DataFrame(columns=["Issue type", "Findings", "Affected_records"])
        )

        metadata = st.session_state.get("dataset_metadata", {})
        active_hash = metadata.get("dataset_hash")
        with sqlite3.connect(database_file) as connection:
            if active_hash:
                review_summary = pd.read_sql_query(
                    """SELECT issue_type AS issue_type, severity AS severity,
                              status AS status, COUNT(*) AS findings
                       FROM issue_reviews WHERE dataset_hash = ?
                       GROUP BY issue_type, severity, status""",
                    connection,
                    params=(active_hash,),
                )
                dataset_row = pd.read_sql_query(
                    "SELECT dataset_name, dataset_type, source_file FROM dataset_catalog WHERE dataset_hash = ?",
                    connection,
                    params=(active_hash,),
                )
            else:
                review_summary = pd.DataFrame(
                    columns=["issue_type", "severity", "status", "findings"]
                )
                dataset_row = pd.DataFrame()

        dataset_name = (
            str(dataset_row.loc[0, "dataset_name"])
            if not dataset_row.empty
            else str(metadata.get("dataset_name", "Current dataset"))
        )
        dataset_type = (
            str(dataset_row.loc[0, "dataset_type"])
            if not dataset_row.empty
            else str(metadata.get("dataset_type", "Not recorded"))
        )
        open_rows = int(review_summary.loc[review_summary["status"].isin(["New", "In review"]), "findings"].sum()) if not review_summary.empty else 0
        high_rows = int(review_summary.loc[review_summary["severity"] == "High", "findings"].sum()) if not review_summary.empty else 0
        flagged_scores = scores.loc[scores["Risk score"] > 0, "Risk score"] if not scores.empty and "Risk score" in scores else pd.Series(dtype=float)
        risk_mean = float(flagged_scores.mean()) if not flagged_scores.empty else 0.0

        st.subheader("Quality report")
        st.caption(f"Dataset: {dataset_name} · Type: {dataset_type}")
        st.dataframe(issue_summary, use_container_width=True, hide_index=True)
        if not review_summary.empty:
            st.markdown("**Review workload by issue, severity, and status**")
            st.dataframe(review_summary, use_container_width=True, hide_index=True)

        generated = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC")
        report = [
            "# HealthQ AI — Data Quality Report",
            "",
            f"Generated: {generated}",
            f"Dataset: {dataset_name}",
            f"Dataset type: {dataset_type}",
            "",
            "## Summary",
            f"- Source records: {raw_count:,}",
            f"- Cleaned records: {clean_count:,}",
            f"- Issue findings: {len(issues):,}",
            f"- Records with findings: {int(issues['Record'].nunique()) if not issues.empty else 0:,}",
            f"- Open review findings: {open_rows:,}",
            f"- High severity review findings: {high_rows:,}",
            f"- Average flagged-record data-quality risk score: {risk_mean:.1f}/100",
            "",
            "## Findings by issue type",
        ]
        if issue_summary.empty:
            report.append("- No issues found.")
        else:
            report.extend(
                f"- {row['Issue type']}: {int(row['Findings']):,} findings across {int(row['Affected_records']):,} records"
                for _, row in issue_summary.iterrows()
            )
        report.extend([
            "",
            "## Recommended next action",
            "Review open findings in Issue Explorer, verify values against the authorized source system, and record the assigned owner and outcome. Apply corrections only after staff verification.",
            "",
            "Risk scores prioritize data-quality review. They do not measure patient health or predict appointment attendance.",
            "This report contains aggregate counts and does not include patient-level rows.",
        ])

        report_col, csv_col = st.columns(2)
        report_col.download_button(
            "Download quality report (Markdown)",
            data="\n".join(report).encode("utf-8"),
            file_name="healthq_ai_quality_report.md",
            mime="text/markdown",
        )
        csv_col.download_button(
            "Download issue summary (CSV)",
            data=issue_summary.to_csv(index=False).encode("utf-8"),
            file_name="healthq_ai_issue_summary.csv",
            mime="text/csv",
        )

