from pathlib import Path
from io import BytesIO
import hashlib
import sqlite3
import uuid

import pandas as pd
import streamlit as st

from src.quality_pipeline import find_quality_issues


st.title("HealthQ AI")
st.caption("Healthcare Data Quality Monitoring Assistant")

project_dir = Path(__file__).parent
default_csv = project_dir / "data" / "raw" / "KaggleV2-May-2016.csv"
uploaded_file = st.file_uploader("Upload a dataset CSV", type=["csv"])

if uploaded_file is not None:
    csv_bytes = uploaded_file.getvalue()
    source_name = uploaded_file.name
elif default_csv.exists():
    csv_bytes = default_csv.read_bytes()
    source_name = default_csv.name
else:
    st.info("Upload a CSV file to begin.")
    st.stop()

try:
    data = pd.read_csv(BytesIO(csv_bytes))
except Exception as error:
    st.error(f"Could not read this CSV: {error}")
    st.stop()

if data.empty:
    st.error("The selected CSV has no data rows.")
    st.stop()

dataset_hash = hashlib.sha256(csv_bytes).hexdigest()
dataset_types = [
    "Select dataset type",
    "Appointments",
    "Patient registration",
    "Laboratory results",
    "Encounters or admissions",
    "Medications",
    "Other",
]
type_default = 1 if source_name == default_csv.name else 0
dataset_type = st.selectbox(
    "Dataset type",
    dataset_types,
    index=type_default,
    key=f"dataset_type_{dataset_hash[:12]}",
)
dataset_name = st.text_input(
    "Dataset name",
    value=Path(source_name).stem,
    key=f"dataset_name_{dataset_hash[:12]}",
).strip()
with st.expander("Dataset ownership & refresh details", expanded=False):
    owner_col, source_col = st.columns(2)
    department = owner_col.text_input(
        "Hospital department / unit",
        key=f"department_{dataset_hash[:12]}",
        placeholder="e.g., Laboratory, Outpatient Clinic",
    ).strip()
    steward = owner_col.text_input(
        "Data steward / contact role",
        key=f"steward_{dataset_hash[:12]}",
        placeholder="e.g., Lab data coordinator",
    ).strip()
    source_system = source_col.text_input(
        "Source system",
        value=Path(source_name).stem,
        key=f"source_system_{dataset_hash[:12]}",
        placeholder="e.g., EHR, LIS, scheduling system",
    ).strip()
    refresh_frequency = source_col.selectbox(
        "Expected refresh frequency",
        ["As needed", "Daily", "Weekly", "Monthly", "Quarterly"],
        key=f"refresh_frequency_{dataset_hash[:12]}",
    )

if dataset_type == "Select dataset type":
    st.info("Choose the dataset type to continue.")
    st.stop()
if not dataset_name:
    st.error("Enter a dataset name.")
    st.stop()

dataset_metadata = {
    "dataset_hash": dataset_hash,
    "dataset_name": dataset_name,
    "dataset_type": dataset_type,
    "source_file": source_name,
    "department": department,
    "steward": steward,
    "source_system": source_system,
    "refresh_frequency": refresh_frequency,
}
st.session_state["dataset_metadata"] = dataset_metadata
st.session_state["healthq_data"] = data
quality_issues = find_quality_issues(data, dataset_type)
st.session_state["healthq_issues"] = quality_issues

issue_weights = {
    "Missing value": 2,
    "Duplicate row": 1,
    "Age out of range": 3,
    "Invalid date": 3,
    "Date order problem": 3,
    "Unexpected category": 1,
    "Invalid binary value": 2,
    "Duplicate identifier": 3,
    "Invalid numeric value": 2,
    "Reference range problem": 2,
}

risk_scores = pd.DataFrame({"Record": range(1, len(data) + 1)})
risk_scores["Issue points"] = 0

if not quality_issues.empty:
    weighted_issues = quality_issues.copy()
    weighted_issues["Weight"] = (
        weighted_issues["Issue"].map(issue_weights).fillna(1)
    )
    points_by_record = weighted_issues.groupby("Record")["Weight"].sum()
    risk_scores["Issue points"] = (
        risk_scores["Record"].map(points_by_record).fillna(0)
    )

risk_scores["Risk score"] = (
    risk_scores["Issue points"]
    .div(sum(issue_weights.values()))
    .mul(100)
    .clip(upper=100)
    .round(1)
)
risk_scores["Risk level"] = pd.cut(
    risk_scores["Risk score"],
    bins=[-0.1, 0, 25, 60, 100.1],
    labels=["No issues", "Low", "Medium", "High"],
)
st.session_state["healthq_risk_scores"] = risk_scores

cleaned_data = data.copy()

for column in ["Gender", "No-show"]:
    if column in cleaned_data.columns:
        cleaned_data[column] = (
            cleaned_data[column].astype("string").str.strip().str.title()
        )

if "Age" in cleaned_data.columns:
    age = pd.to_numeric(cleaned_data["Age"], errors="coerce")
    invalid_age = cleaned_data["Age"].notna() & (
        age.isna() | (age < 0) | (age > 120)
    )
    cleaned_data["Age"] = age.mask(invalid_age)

for column in ["ScheduledDay", "AppointmentDay"]:
    if column in cleaned_data.columns:
        cleaned_data[column] = pd.to_datetime(
            cleaned_data[column], errors="coerce", utc=True
        )

cleaned_data = cleaned_data.drop_duplicates().copy()
st.session_state["healthq_cleaned_data"] = cleaned_data

processed_dir = project_dir / "data" / "processed"
processed_dir.mkdir(parents=True, exist_ok=True)
cleaned_csv = processed_dir / "healthq_ai_cleaned.csv"
cleaned_data.to_csv(cleaned_csv, index=False)

database_dir = project_dir / "database"
database_dir.mkdir(parents=True, exist_ok=True)
database_file = database_dir / "healthq_ai.db"

cleaned_for_db = cleaned_data.copy()
for column in ["ScheduledDay", "AppointmentDay"]:
    if column in cleaned_for_db.columns:
        cleaned_for_db[column] = cleaned_for_db[column].astype("string")

issues_for_db = quality_issues.copy()
if issues_for_db.empty:
    issues_for_db = pd.DataFrame(
        columns=["Record", "Column", "Issue", "Details"]
    )

risk_for_db = risk_scores.copy()
risk_for_db["Risk level"] = risk_for_db["Risk level"].astype("string")

dataset_hash = hashlib.sha256(csv_bytes).hexdigest()
captured_utc = pd.Timestamp.now(tz="UTC").isoformat()
run_signature = "|".join([
    dataset_hash,
    dataset_name,
    dataset_type,
    department,
    steward,
    source_system,
    refresh_frequency,
])
is_new_processing_run = (
    st.session_state.get("last_quality_run_signature") != run_signature
)
run_id = uuid.uuid4().hex[:12] if is_new_processing_run else ""
trend_rows = []
run_history_rows = []

for phase, frame in [("Source", data), ("Cleaned", cleaned_data)]:
    missing_cells = int(frame.isna().sum().sum())
    total_cells = max(len(frame) * len(frame.columns), 1)
    completeness = round(100 * (1 - missing_cells / total_cells), 4)
    trend_rows.append((
        dataset_hash[:12],
        dataset_hash,
        phase,
        len(frame),
        missing_cells,
        int(frame.duplicated().sum()),
        completeness,
        captured_utc,
    ))
    if is_new_processing_run:
        run_history_rows.append((
            run_id,
            dataset_hash,
            dataset_name,
            dataset_type,
            phase,
            len(frame),
            missing_cells,
            int(frame.duplicated().sum()),
            completeness,
            captured_utc,
        ))

with sqlite3.connect(database_file) as connection:
    data.to_sql("records_raw", connection, if_exists="replace", index=False)
    cleaned_for_db.to_sql(
        "records_clean", connection, if_exists="replace", index=False
    )
    issues_for_db.to_sql(
        "quality_issues", connection, if_exists="replace", index=False
    )
    risk_for_db.to_sql("risk_scores", connection, if_exists="replace", index=False)

    # Keep one local snapshot per source-file version alongside the active tables.
    archive_suffix = dataset_hash[:16]
    data.to_sql(f"dataset_raw_{archive_suffix}", connection, if_exists="replace", index=False)
    cleaned_for_db.to_sql(
        f"dataset_clean_{archive_suffix}", connection, if_exists="replace", index=False
    )
    issues_for_db.to_sql(
        f"dataset_issues_{archive_suffix}", connection, if_exists="replace", index=False
    )
    risk_for_db.to_sql(
        f"dataset_risk_{archive_suffix}", connection, if_exists="replace", index=False
    )

    connection.execute("""
        CREATE TABLE IF NOT EXISTS dataset_catalog (
            dataset_hash TEXT PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            dataset_type TEXT NOT NULL,
            source_file TEXT NOT NULL,
            record_count INTEGER,
            field_count INTEGER,
            captured_utc TEXT,
            department TEXT DEFAULT '',
            steward TEXT DEFAULT '',
            source_system TEXT DEFAULT '',
            refresh_frequency TEXT DEFAULT 'As needed'
        )
    """)
    catalog_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(dataset_catalog)")
    }
    for column_name, column_type, default_sql in [
        ("department", "TEXT", "''"),
        ("steward", "TEXT", "''"),
        ("source_system", "TEXT", "''"),
        ("refresh_frequency", "TEXT", "'As needed'"),
    ]:
        if column_name not in catalog_columns:
            connection.execute(
                f"ALTER TABLE dataset_catalog ADD COLUMN {column_name} {column_type} DEFAULT {default_sql}"
            )
    connection.execute("""
        INSERT OR REPLACE INTO dataset_catalog
        (dataset_hash, dataset_name, dataset_type, source_file, record_count,
         field_count, captured_utc, department, steward, source_system,
         refresh_frequency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        dataset_hash,
        dataset_name,
        dataset_type,
        source_name,
        len(data),
        len(data.columns),
        captured_utc,
        department,
        steward,
        source_system,
        refresh_frequency,
    ))
    connection.execute("""
        CREATE TABLE IF NOT EXISTS trend_history (
            dataset_version TEXT,
            dataset_hash TEXT,
            phase TEXT,
            record_count INTEGER,
            missing_cells INTEGER,
            duplicate_rows INTEGER,
            completeness_percent REAL,
            captured_utc TEXT,
            UNIQUE(dataset_hash, phase)
        )
    """)
    connection.executemany("""
        INSERT OR IGNORE INTO trend_history
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, trend_rows)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS dataset_run_history (
            run_id TEXT NOT NULL,
            dataset_hash TEXT NOT NULL,
            dataset_name TEXT NOT NULL,
            dataset_type TEXT NOT NULL,
            phase TEXT NOT NULL,
            record_count INTEGER,
            missing_cells INTEGER,
            duplicate_rows INTEGER,
            completeness_percent REAL,
            captured_utc TEXT NOT NULL,
            PRIMARY KEY (run_id, phase)
        )
    """)
    connection.executemany("""
        INSERT INTO dataset_run_history
        (run_id, dataset_hash, dataset_name, dataset_type, phase, record_count,
         missing_cells, duplicate_rows, completeness_percent, captured_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, run_history_rows)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS issue_reviews (
            issue_id TEXT PRIMARY KEY,
            dataset_hash TEXT NOT NULL,
            record INTEGER NOT NULL,
            column_name TEXT,
            issue_type TEXT NOT NULL,
            details TEXT,
            severity TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'New',
            owner TEXT DEFAULT '',
            note TEXT DEFAULT '',
            first_seen_utc TEXT,
            last_updated_utc TEXT
        )
    """)
    review_rows = []
    for issue in quality_issues.itertuples(index=False):
        issue_type = str(issue.Issue)
        weight = issue_weights.get(issue_type, 1)
        severity = "High" if weight >= 3 else ("Medium" if weight == 2 else "Low")
        issue_id = hashlib.sha256(
            f"{dataset_hash}|{issue.Record}|{issue.Column}|{issue_type}".encode("utf-8")
        ).hexdigest()
        review_rows.append((
            issue_id,
            dataset_hash,
            int(issue.Record),
            str(issue.Column),
            issue_type,
            str(issue.Details),
            severity,
            "New",
            "",
            "",
            captured_utc,
            captured_utc,
        ))

    connection.executemany("""
        INSERT OR IGNORE INTO issue_reviews
        (issue_id, dataset_hash, record, column_name, issue_type, details,
         severity, status, owner, note, first_seen_utc, last_updated_utc)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, review_rows)

st.session_state["last_quality_run_signature"] = run_signature


flagged_count = (
    int(quality_issues["Record"].nunique())
    if not quality_issues.empty
    else 0
)
flagged_scores = risk_scores.loc[risk_scores["Risk score"] > 0, "Risk score"]
average_flagged_score = (
    float(flagged_scores.mean()) if not flagged_scores.empty else 0.0
)

st.success(f"Loaded {len(data):,} records from {source_name}.")
st.caption(f"Dataset: {dataset_name} · Type: {dataset_type}")
col1, col2, col3 = st.columns(3)
col1.metric("Columns", f"{len(data.columns):,}")
col2.metric("Records with issues", f"{flagged_count:,}")
col3.metric("Average flagged score", f"{average_flagged_score:.1f}/100")
st.caption("Analysis and database tables are refreshed for this dataset.")
st.caption(f"Cleaned CSV: {cleaned_csv}")
st.caption(f"SQLite database: {database_file}")






