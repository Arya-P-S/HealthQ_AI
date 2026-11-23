from pathlib import Path

import pandas as pd
import streamlit as st
import sqlite3

st.set_page_config(page_title="HealthQ AI", page_icon="🩺")

st.title("HealthQ AI")
st.write("Healthcare Data Quality Monitoring Assistant")

# uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])

# if uploaded_file is not None:
#     data = pd.read_csv(uploaded_file)
# else:
#     if not data_file.exists():
#         st.error(f"Dataset not found: {data_file}")
#         st.stop()

#     data = pd.read_csv(data_file)

data_file = (
    Path(__file__).parent
    / "data"
    / "raw"
    / "KaggleV2-May-2016.csv"
)

if not data_file.exists():
    st.error(f"Dataset not found: {data_file}")
    st.stop()

data = pd.read_csv(data_file)

st.success(f"Loaded {len(data):,} appointment records.")
st.write(f"Number of columns: {len(data.columns)}")
st.subheader("First 10 records")
st.dataframe(data.head(10), use_container_width=True)

# missing values

st.subheader("Missing values by column")

missing_counts = data.isna().sum()
missing_counts = missing_counts[missing_counts > 0]

if missing_counts.empty:
    st.success("No missing values found.")
else:
    st.dataframe(
        missing_counts.rename("Missing values").to_frame(),
        use_container_width=True,
    )

# Duplicates Records

st.subheader("Duplicate records")

duplicate_mask = data.duplicated()
duplicate_count = int(duplicate_mask.sum())

st.metric("Exact duplicate rows", duplicate_count)

if duplicate_count == 0:
    st.success("No exact duplicate rows found.")
else:
    st.warning(f"Found {duplicate_count:,} duplicate rows.")
    st.dataframe(data[duplicate_mask].head(10), use_container_width=True)

# Age Validation

st.subheader("Age validation")

if "Age" in data.columns:
    age = pd.to_numeric(data["Age"], errors="coerce")
    invalid_age = age.notna() & ((age < 0) | (age > 120))

    st.metric("Ages outside 0–120", int(invalid_age.sum()))

    if invalid_age.any():
        st.dataframe(data[invalid_age].head(10), use_container_width=True)
    else:
        st.success("All recorded ages are within 0–120.")
else:
    st.info("This dataset has no 'Age' column, so the age check was skipped.")

# Validate Appointment Dates

st.subheader("Appointment date validation")

required_dates = {"ScheduledDay", "AppointmentDay"}

if required_dates.issubset(data.columns):
    scheduled = pd.to_datetime(data["ScheduledDay"], errors="coerce", utc=True)
    appointment = pd.to_datetime(data["AppointmentDay"], errors="coerce", utc=True)

    invalid_dates = (
        (data["ScheduledDay"].notna() & scheduled.isna())
        | (data["AppointmentDay"].notna() & appointment.isna())
    )

    appointment_before_scheduling = (
        scheduled.notna()
        & appointment.notna()
        & (appointment.dt.normalize() < scheduled.dt.normalize())
    )

    st.metric("Invalid date values", int(invalid_dates.sum()))
    st.metric(
        "Appointment before scheduling date",
        int(appointment_before_scheduling.sum()),
    )

    flagged_dates = invalid_dates | appointment_before_scheduling
    if flagged_dates.any():
        st.dataframe(data[flagged_dates].head(10), use_container_width=True)
    else:
        st.success("No date problems found by these checks.")
else:
    st.info("This dataset lacks the expected appointment date columns.")

# check categories and binary fields

st.subheader("Category and indicator validation")

category_rules = {
    "Gender": {"F", "M"},
    "No-show": {"Yes", "No"},
}

binary_columns = [
    "Scholarship",
    "Hipertension",
    "Diabetes",
    "Alcoholism",
    "SMS_received",
]

category_issues = []

for column, allowed_values in category_rules.items():
    if column in data.columns:
        values = data[column].astype("string").str.strip().str.title()
        invalid = data[column].notna() & ~values.isin(allowed_values)

        if invalid.any():
            category_issues.append(
                {"Column": column, "Issue": "Unexpected category",
                 "Records": int(invalid.sum())}
            )

for column in binary_columns:
    if column in data.columns:
        values = pd.to_numeric(data[column], errors="coerce")
        invalid = data[column].notna() & ~values.isin([0, 1])

        if invalid.any():
            category_issues.append(
                {"Column": column, "Issue": "Expected 0 or 1",
                 "Records": int(invalid.sum())}
            )

if category_issues:
    st.dataframe(pd.DataFrame(category_issues), hide_index=True)
else:
    st.success("No unexpected categories or indicator values found.")

# quality issues table

st.subheader("Combined quality issues")

issue_rows = []

def add_issues(mask, issue_type, column, details):
    for row_index in data.index[mask.fillna(False)]:
        issue_rows.append({
            "Record": int(row_index) + 1,
            "Column": column,
            "Issue": issue_type,
            "Details": details,
        })

# Missing values
for column in data.columns:
    add_issues(
        data[column].isna(),
        "Missing value",
        column,
        f"{column} is blank",
    )

# Exact duplicate rows
add_issues(
    data.duplicated(),
    "Duplicate row",
    "All columns",
    "Exact duplicate of an earlier row",
)

# Implausible ages
if "Age" in data.columns:
    age = pd.to_numeric(data["Age"], errors="coerce")
    add_issues(
        age.notna() & ((age < 0) | (age > 120)),
        "Age out of range",
        "Age",
        "Expected an age from 0 to 120",
    )

# Invalid dates and appointment dates before scheduled dates
if {"ScheduledDay", "AppointmentDay"}.issubset(data.columns):
    scheduled = pd.to_datetime(data["ScheduledDay"], errors="coerce", utc=True)
    appointment = pd.to_datetime(data["AppointmentDay"], errors="coerce", utc=True)

    add_issues(
        data["ScheduledDay"].notna() & scheduled.isna(),
        "Invalid date",
        "ScheduledDay",
        "Could not parse the scheduled date",
    )
    add_issues(
        data["AppointmentDay"].notna() & appointment.isna(),
        "Invalid date",
        "AppointmentDay",
        "Could not parse the appointment date",
    )
    add_issues(
        scheduled.notna()
        & appointment.notna()
        & (appointment.dt.normalize() < scheduled.dt.normalize()),
        "Date order problem",
        "AppointmentDay",
        "Appointment is before the scheduled date",
    )

quality_issues = pd.DataFrame(issue_rows)

if quality_issues.empty:
    st.success("No issues found by the current checks.")
else:
    st.metric("Total issue findings", len(quality_issues))
    st.metric("Records with issues", quality_issues["Record"].nunique())
    st.dataframe(quality_issues.head(50), use_container_width=True)

# calculate a data quality risk score

st.subheader("Data quality risk score")

issue_weights = {
    "Missing value": 2,
    "Duplicate row": 1,
    "Age out of range": 3,
    "Invalid date": 3,
    "Date order problem": 3,
    "Unexpected category": 1,
    "Invalid binary value": 2,
}

# Start with every record, including those with no issues
risk_scores = pd.DataFrame({
    "Record": range(1, len(data) + 1)
})

if not quality_issues.empty:
    weighted_issues = quality_issues.copy()
    weighted_issues["Weight"] = (
        weighted_issues["Issue"].map(issue_weights).fillna(1)
    )

    points_by_record = weighted_issues.groupby("Record")["Weight"].sum()
    risk_scores["Issue points"] = (
        risk_scores["Record"].map(points_by_record).fillna(0)
    )
else:
    risk_scores["Issue points"] = 0

# The denominator is the sum of the defined issue weights.
maximum_points = sum(issue_weights.values())

risk_scores["Risk score"] = (
    risk_scores["Issue points"]
    .div(maximum_points)
    .mul(100)
    .clip(upper=100)
    .round(1)
)

risk_scores["Risk level"] = pd.cut(
    risk_scores["Risk score"],
    bins=[-0.1, 0, 25, 60, 100.1],
    labels=["No issues", "Low", "Medium", "High"],
)

st.dataframe(
    risk_scores.sort_values("Risk score", ascending=False).head(20),
    use_container_width=True,
    hide_index=True,
)


# add a risk summary chart

st.subheader("Risk score summary")

risk_counts = (
    risk_scores.loc[risk_scores["Risk level"] != "No issues", "Risk level"]
    .value_counts()
    .reindex(["Low", "Medium", "High"], fill_value=0)
)

st.bar_chart(risk_counts)

flagged_scores = risk_scores.loc[
    risk_scores["Risk score"] > 0, "Risk score"
]

average_flagged_score = (
    flagged_scores.mean() if not flagged_scores.empty else 0
)

col1, col2, col3 = st.columns(3)
col1.metric("Total records", f"{len(risk_scores):,}")
col2.metric("Records with issues", f"{len(flagged_scores):,}")
col3.metric("Average score of flagged records", f"{average_flagged_score:.1f}/100")

# Inspect the flagged records

st.subheader("Review flagged records")

data_context = data.reset_index(drop=True).copy()
data_context.insert(0, "Record", range(1, len(data_context) + 1))

context_columns = [
    column
    for column in [
        "AppointmentID",
        "Age",
        "ScheduledDay",
        "AppointmentDay",
        "Gender",
        "No-show",
    ]
    if column in data_context.columns
]

if quality_issues.empty:
    st.success("There are no flagged records to review.")
else:
    review_table = quality_issues.merge(
        data_context[["Record"] + context_columns],
        on="Record",
        how="left",
    )

    st.dataframe(review_table, use_container_width=True, hide_index=True)

# create a cleaned copy

st.subheader("Create cleaned dataset")

cleaned_data = data.copy()

# Standardize formatting in these category columns
for column in ["Gender", "No-show"]:
    if column in cleaned_data.columns:
        cleaned_data[column] = (
            cleaned_data[column].astype("string").str.strip().str.title()
        )

# Keep impossible or unparseable ages as missing; do not guess an age
if "Age" in cleaned_data.columns:
    age = pd.to_numeric(cleaned_data["Age"], errors="coerce")
    invalid_age = cleaned_data["Age"].notna() & (
        age.isna() | (age < 0) | (age > 120)
    )
    cleaned_data["Age"] = age.mask(invalid_age)

# Parse dates; unparseable date strings become missing
for column in ["ScheduledDay", "AppointmentDay"]:
    if column in cleaned_data.columns:
        cleaned_data[column] = pd.to_datetime(
            cleaned_data[column], errors="coerce", utc=True
        )

# Remove exact duplicate rows from the cleaned copy only
rows_before = len(cleaned_data)
cleaned_data = cleaned_data.drop_duplicates().copy()
duplicates_removed = rows_before - len(cleaned_data)

st.success(f"Cleaned copy created: {len(cleaned_data):,} records.")
st.write(f"Exact duplicate rows removed: {duplicates_removed:,}")
st.dataframe(cleaned_data.head(10), use_container_width=True)

# provide a download button:

output_dir = Path(__file__).parent / "data" / "processed"
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "healthq_ai_cleaned.csv"
cleaned_data.to_csv(output_file, index=False)

st.success(f"Saved cleaned dataset to: {output_file}")

st.download_button(
    "Download cleaned CSV",
    data=cleaned_data.to_csv(index=False).encode("utf-8"),
    file_name="healthq_ai_cleaned.csv",
    mime="text/csv",
)

# save results in a SQLite database

st.subheader("Save project data to SQLite")

database_dir = Path(__file__).parent / "database"
database_dir.mkdir(parents=True, exist_ok=True)
database_file = database_dir / "healthq_ai.db"

# Prepare copies for SQLite
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
if "Risk level" in risk_for_db.columns:
    risk_for_db["Risk level"] = risk_for_db["Risk level"].astype("string")

with sqlite3.connect(database_file) as connection:
    data.to_sql(
        "appointments_raw", connection, if_exists="replace", index=False
    )
    cleaned_for_db.to_sql(
        "appointments_clean", connection, if_exists="replace", index=False
    )
    issues_for_db.to_sql(
        "quality_issues", connection, if_exists="replace", index=False
    )
    risk_for_db.to_sql(
        "risk_scores", connection, if_exists="replace", index=False
    )

st.success(f"Database saved: {database_file}")

# Database Explorer

st.subheader("Explore database tables")

table_options = [
    "appointments_raw",
    "appointments_clean",
    "quality_issues",
    "risk_scores",
]

with sqlite3.connect(database_file) as connection:
    table_counts = {}

    for table in table_options:
        result = pd.read_sql_query(
            f"SELECT COUNT(*) AS total FROM {table}",
            connection,
        )
        table_counts[table] = int(result.loc[0, "total"])

    selected_table = st.selectbox("Choose a table", table_options)

    preview = pd.read_sql_query(
        f"SELECT * FROM {selected_table} LIMIT 20",
        connection,
    )

st.write(f"Rows in **{selected_table}**: {table_counts[selected_table]:,}")
st.dataframe(preview, use_container_width=True, hide_index=True)

# add a downloadable quality report

st.subheader("Generate quality report")

issue_counts = (
    quality_issues["Issue"].value_counts()
    if not quality_issues.empty
    else pd.Series(dtype="int64")
)

flagged_records = (
    int(quality_issues["Record"].nunique())
    if not quality_issues.empty
    else 0
)

flagged_scores = risk_scores.loc[
    risk_scores["Risk score"] > 0, "Risk score"
]

average_flagged_score = (
    flagged_scores.mean() if not flagged_scores.empty else 0
)

report_lines = [
    "# HealthQ AI — Data Quality Report",
    "",
    f"Generated: {pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d %H:%M UTC')}",
    "",
    "## Dataset summary",
    f"- Source records: {len(data):,}",
    f"- Cleaned records: {len(cleaned_data):,}",
    f"- Exact duplicates removed: {duplicates_removed:,}",
    f"- Records with quality issues: {flagged_records:,}",
    f"- Average risk score among flagged records: {average_flagged_score:.1f}/100",
    "",
    "## Issues found",
]

if issue_counts.empty:
    report_lines.append("- No issues found by the current checks.")
else:
    for issue_name, count in issue_counts.items():
        report_lines.append(f"- {issue_name}: {int(count):,}")

report_lines += [
    "",
    "## Score interpretation",
    "Risk scores prioritize data quality review. They do not represent patient health risk or predict appointment attendance.",
]

report_text = "\n".join(report_lines)

st.download_button(
    "Download quality report",
    data=report_text.encode("utf-8"),
    file_name="healthq_ai_quality_report.md",
    mime="text/markdown",
)