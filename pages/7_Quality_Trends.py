from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st

st.title("Quality Trends")
st.write("Compare source and cleaned data quality across repeated processing runs.")

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

        if "dataset_run_history" in tables:
            history = pd.read_sql_query(
                "SELECT * FROM dataset_run_history ORDER BY captured_utc",
                connection,
            )
            history_mode = "run"
        elif "trend_history" in tables:
            history = pd.read_sql_query(
                "SELECT * FROM trend_history ORDER BY captured_utc",
                connection,
            )
            history_mode = "legacy"
        else:
            history = pd.DataFrame()
            history_mode = "legacy"

    if history.empty:
        st.info("No trend snapshots yet. Load or process a dataset to save the first snapshot.")
    else:
        if history_mode == "run":
            dataset_options = {
                f"{row.dataset_name} · {row.dataset_type}": (row.dataset_name, row.dataset_type)
                for row in history[["dataset_name", "dataset_type"]].drop_duplicates().itertuples(index=False)
            }
            selected_label = st.selectbox("Dataset", list(dataset_options))
            selected_name, selected_type = dataset_options[selected_label]
            history = history[
                (history["dataset_name"] == selected_name)
                & (history["dataset_type"] == selected_type)
            ].copy()
            history["run_date"] = pd.to_datetime(history["captured_utc"], utc=True, errors="coerce")
            history["run_label"] = (
                history["run_date"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                + " · " + history["run_id"]
            )
            st.caption(f"Comparing {history['dataset_hash'].nunique():,} dataset version(s). A trend appears after multiple versions or processing runs are recorded.")
            run_col, version_col, latest_col = st.columns(3)
            run_col.metric("Processing runs", f"{history['run_id'].nunique():,}")
            version_col.metric("Dataset versions", f"{history['dataset_hash'].nunique():,}")
            latest_run_time = history["run_date"].max()
            latest_col.metric(
                "Latest processing time (UTC)",
                latest_run_time.strftime("%Y-%m-%d %H:%M")
                if pd.notna(latest_run_time)
                else "Unknown",
            )
        else:
            history["run_label"] = history["dataset_version"]

        metric_names = {
            "completeness_percent": "Completeness (%)",
            "missing_cells": "Missing cells",
            "duplicate_rows": "Duplicate rows",
            "record_count": "Record count",
        }

        metric = st.selectbox(
            "Choose a metric",
            list(metric_names),
            format_func=lambda value: metric_names[value],
            index=list(metric_names).index("missing_cells"),
        )
        if metric == "completeness_percent":
            st.caption("Completeness is near 100%, so small changes can look flat. Choose Missing cells to see small differences more clearly.")

        chart_data = history.pivot_table(
            index="run_label",
            columns="phase",
            values=metric,
            aggfunc="last",
        )

        st.subheader(metric_names[metric])
        st.line_chart(chart_data)

        st.subheader("Saved run snapshots")
        display_history = history.copy()
        if "dataset_hash" in display_history.columns:
            display_history["Dataset version"] = display_history["dataset_hash"].astype(str).str[:8]
        if "captured_utc" in display_history.columns:
            display_history["Run time (UTC)"] = pd.to_datetime(
                display_history["captured_utc"], utc=True, errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M:%S")
        display_history = display_history.drop(
            columns=[column for column in ["dataset_hash", "run_id", "run_date", "run_label", "captured_utc"] if column in display_history.columns]
        ).rename(columns={
            "dataset_name": "Dataset",
            "dataset_type": "Dataset type",
            "phase": "Data stage",
            "record_count": "Records",
            "missing_cells": "Missing cells",
            "duplicate_rows": "Duplicate rows",
            "completeness_percent": "Completeness (%)",
            "dataset_version": "Dataset version",
        })
        st.dataframe(
            display_history,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download trend history",
            data=history.to_csv(index=False).encode("utf-8"),
            file_name="healthq_ai_trend_history.csv",
            mime="text/csv",
        )
