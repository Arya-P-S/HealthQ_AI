from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st
from src.preview_privacy import mask_identifiers

st.title("Dataset Catalogue")
st.caption("A hospital-wide register of datasets processed in HealthQ AI.")

database_file = Path(__file__).resolve().parents[1] / "database" / "healthq_ai.db"
if not database_file.exists():
    st.info("Load a dataset first. Its details will appear here.")
    st.stop()

with sqlite3.connect(database_file) as connection:
    table_names = pd.read_sql_query(
        "SELECT name FROM sqlite_master WHERE type='table'", connection
    )["name"].tolist()
    if "dataset_catalog" not in table_names:
        st.info("Load a dataset first to create the catalogue.")
        st.stop()

    catalog_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(dataset_catalog)")
    }
    catalog_select = [
        "dataset_hash", "dataset_name", "dataset_type", "source_file",
        "record_count", "field_count", "captured_utc",
    ]
    catalog_select.extend(
        column for column in ["department", "steward", "source_system", "refresh_frequency"]
        if column in catalog_columns
    )
    catalog = pd.read_sql_query(
        f"SELECT {', '.join(catalog_select)} FROM dataset_catalog ORDER BY captured_utc DESC",
        connection,
    )
    for column in ["department", "steward", "source_system", "refresh_frequency"]:
        if column not in catalog.columns:
            catalog[column] = ""
    if "issue_reviews" in table_names:
        review_summary = pd.read_sql_query(
            """SELECT dataset_hash,
                      COUNT(*) AS findings,
                      SUM(CASE WHEN severity='High' THEN 1 ELSE 0 END) AS high,
                      SUM(CASE WHEN status IN ('New','In review') THEN 1 ELSE 0 END) AS open
               FROM issue_reviews GROUP BY dataset_hash""",
            connection,
        )
    else:
        review_summary = pd.DataFrame(
            columns=["dataset_hash", "findings", "high", "open"]
        )

catalog = catalog.merge(review_summary, on="dataset_hash", how="left")
for column in ["findings", "high", "open"]:
    catalog[column] = catalog[column].fillna(0).astype(int)

catalog["processed_at"] = pd.to_datetime(catalog["captured_utc"], utc=True, errors="coerce")
latest_time = catalog.groupby(["dataset_name", "dataset_type"])["processed_at"].transform("max")
catalog["is_latest"] = catalog["processed_at"] == latest_time
now_utc = pd.Timestamp.now(tz="UTC")
cadence_days = {"Daily": 1, "Weekly": 7, "Monthly": 30, "Quarterly": 90}

def review_cadence(row):
    if not row["is_latest"]:
        return "Historical version"
    days = cadence_days.get(row["refresh_frequency"])
    if days is None:
        return "No scheduled cadence"
    if pd.isna(row["processed_at"]):
        return "Unknown"
    age_days = (now_utc - row["processed_at"]).total_seconds() / 86400
    if age_days >= days:
        return "Overdue"
    if age_days >= days * 0.8:
        return "Due soon"
    return "Current"

catalog["cadence_status"] = (
    catalog.apply(review_cadence, axis=1)
    if not catalog.empty
    else pd.Series(dtype="string")
)
latest_catalog = catalog[catalog["is_latest"]]
scheduled_latest = latest_catalog[latest_catalog["refresh_frequency"].isin(cadence_days)]

active = st.session_state.get("dataset_metadata", {})
if active:
    st.info(f"Currently loaded: **{active.get('dataset_name', 'Dataset')}** · {active.get('dataset_type', 'Unknown type')}")

total_col, type_col, open_col = st.columns(3)
total_col.metric("Registered datasets", f"{len(catalog):,}")
type_col.metric("Dataset types", f"{catalog['dataset_type'].nunique():,}")
open_col.metric("Open findings", f"{catalog['open'].sum():,}")
cadence_col, overdue_col = st.columns(2)
cadence_col.metric("Latest datasets on a schedule", f"{len(scheduled_latest):,}")
overdue_col.metric(
    "Due or overdue for reprocessing",
    int(scheduled_latest["cadence_status"].isin(["Due soon", "Overdue"]).sum()),
)
st.caption("Cadence status uses the last HealthQ AI processing time. It does not confirm when the source system last updated its data.")

st.subheader("Find a dataset")
filter_col, search_col = st.columns([1, 2])
types = ["All types"] + sorted(catalog["dataset_type"].dropna().unique().tolist())
selected_type = filter_col.selectbox("Dataset type", types)
search = search_col.text_input("Search by dataset or source file")
filtered = catalog.copy()
if selected_type != "All types":
    filtered = filtered[filtered["dataset_type"] == selected_type]
if search.strip():
    term = search.strip().casefold()
    mask = filtered["dataset_name"].str.casefold().str.contains(term, na=False)
    mask |= filtered["source_file"].str.casefold().str.contains(term, na=False)
    mask |= filtered["department"].str.casefold().str.contains(term, na=False)
    mask |= filtered["steward"].str.casefold().str.contains(term, na=False)
    filtered = filtered[mask]

view = filtered.rename(columns={
    "dataset_name": "Dataset",
    "dataset_type": "Type",
    "source_file": "Source file",
    "record_count": "Records",
    "field_count": "Fields",
    "findings": "Findings",
    "high": "High severity",
    "open": "Open findings",
    "captured_utc": "Last processed (UTC)",
    "department": "Department / unit",
    "steward": "Data steward",
    "source_system": "Source system",
    "refresh_frequency": "Expected refresh",
    "cadence_status": "Processing cadence status",
})
st.dataframe(
    view[["Dataset", "Type", "Department / unit", "Data steward", "Source system", "Expected refresh", "Processing cadence status", "Source file", "Records", "Fields", "Findings", "High severity", "Open findings", "Last processed (UTC)"]],
    use_container_width=True,
    hide_index=True,
)
st.download_button(
    "Download catalogue CSV",
    data=view.drop(
        columns=[column for column in ["dataset_hash", "processed_at", "is_latest"] if column in view.columns]
    ).to_csv(index=False).encode("utf-8"),
    file_name="healthq_ai_dataset_catalogue.csv",
    mime="text/csv",
)

if not catalog.empty:
    st.subheader("Inspect a saved dataset version")
    version_options = {
        f"{row.dataset_name} · {row.dataset_type} · {str(row.dataset_hash)[:8]}": str(row.dataset_hash)
        for row in catalog.itertuples(index=False)
    }
    selected_hash = st.selectbox("Dataset version", list(version_options))
    suffix = "".join(
        character for character in version_options[selected_hash].lower()
        if character in "0123456789abcdef"
    )[:16]
    raw_table = f"dataset_raw_{suffix}"
    clean_table = f"dataset_clean_{suffix}"
    with sqlite3.connect(database_file) as connection:
        saved_tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'", connection
        )["name"].tolist()
        raw_tab, clean_tab = st.tabs(["Raw snapshot", "Cleaned snapshot"])
        for tab, table_name, title in [
            (raw_tab, raw_table, "Raw records"),
            (clean_tab, clean_table, "Cleaned records"),
        ]:
            with tab:
                if table_name not in saved_tables:
                    st.info("This older version predates per-version data archiving. Re-upload it to create an archive.")
                    continue
                count = int(pd.read_sql_query(
                    f"SELECT COUNT(*) AS total FROM {table_name}", connection
                ).loc[0, "total"])
                preview = pd.read_sql_query(
                    f"SELECT * FROM {table_name} LIMIT 20", connection
                )
                preview, masked_columns = mask_identifiers(preview)
                st.caption(f"{title}: {count:,} rows. Likely identifiers are masked in this preview.")
                st.dataframe(preview, use_container_width=True, hide_index=True)
                if table_name == clean_table:
                    export_key = f"archive_clean_csv_{suffix}"
                    if st.button("Prepare cleaned CSV", key=f"prepare_{suffix}"):
                        export_frame = pd.read_sql_query(
                            f"SELECT * FROM {table_name}", connection
                        )
                        st.session_state[export_key] = export_frame.to_csv(index=False).encode("utf-8")
                    if export_key in st.session_state:
                        st.download_button(
                            "Download this cleaned version",
                            data=st.session_state[export_key],
                            file_name=f"healthq_ai_{suffix}_cleaned.csv",
                            mime="text/csv",
                            key=f"download_{suffix}",
                        )

st.caption("Dataset versions, raw and cleaned snapshots, and review history are stored locally in SQLite. The active tables continue to show the latest processed dataset.")
