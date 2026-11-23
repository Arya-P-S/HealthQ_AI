# HealthQ AI — Final Project Report

**Project title:** HealthQ AI — Healthcare Data Quality Monitoring Assistant  
**Dataset:** Kaggle Medical Appointment No Shows (`KaggleV2-May-2016.csv`)  
**Project type:** Local data quality dashboard prototype  
**Prepared:** 18 November 2026

## Abstract

Healthcare data are often distributed across appointment, patient registration, laboratory, encounter, and medication datasets. Missing values, duplicate records, invalid dates, inconsistent categories, and invalid identifiers can reduce the reliability of operational reporting and downstream analysis. HealthQ AI is a Python-based prototype that lets a user upload a CSV, select its dataset type, run shared and domain-specific quality checks, calculate record-level data quality risk scores, review findings, and export a cleaned copy and aggregate report. The application uses Streamlit for its interface, pandas for analysis, and SQLite for local storage of the active data, dataset catalogue, issue reviews, and per-version snapshots. When configured with a Gemini API key, the assistant explains aggregate issue context and suggests human review actions; rule-based guidance remains available without the key. In the supplied appointment dataset, the dashboard showed 110,527 records, 14 fields, no exact duplicate rows, and six issue findings across six records: one age-range issue and five appointment date-order issues. The project demonstrates an explainable review workflow while keeping staff responsible for verifying and approving corrections.

## 1. Problem statement

Hospitals rely on multiple datasets and systems. A file can contain incomplete, duplicated, malformed, or inconsistent values that affect patient administration and the quality of operational analysis. Manual inspection of large files is slow and makes it difficult to track who reviewed an issue and what action was taken.

## 2. Purpose and objectives

HealthQ AI aims to provide a small, transparent workflow for identifying and improving healthcare data quality. Its objectives are to:

- Profile uploaded CSV data and summarize completeness and field characteristics.
- Detect common quality issues and apply additional rules for selected dataset types.
- Prioritize records for review with an explainable data quality risk score.
- Show the issue queue with severity, owner, status, and reviewer notes.
- Apply a limited set of conservative cleanup operations and preserve the source copy.
- Catalogue datasets and processing versions, retain local snapshots, and show quality trends.
- Export a cleaned CSV, an issue summary, and a project quality report.

## 3. Dataset

The project uses the Kaggle **Medical Appointment No Shows** CSV. The observed sample contains 110,527 appointment records and 14 fields, including patient and appointment identifiers, appointment dates, age, neighbourhood, health indicators, SMS receipt, and appointment attendance outcome (`No-show`). The dataset is used to demonstrate data quality analysis; the project does not predict attendance or make clinical decisions.

## 4. Architecture and workflow

**Workflow:** CSV upload -> dataset type and ownership details -> shared and dataset-specific checks -> weighted risk scoring -> conservative cleanup and human issue review -> version archives, trends, and reports.

## 5. Quality rules

Shared checks flag missing cells and exact duplicate rows. Additional checks are selected by dataset type:

| Dataset type | Example checks |
|---|---|
| Appointments | Age in range 0–120, unique appointment ID, date order, expected gender/no-show categories, binary indicator values |
| Patient registration | Age range, unique patient/MRN identifier, expected gender categories |
| Laboratory results | Unique result ID, collection/result date order, reference low bound not above high bound |
| Encounters or admissions | Unique encounter/visit/admission ID, admission date not after discharge date |
| Medications | Unique medication order ID, start/end date order, non-negative dose or quantity |
| Other | Shared missing value and exact duplicate checks |

Rules run when a recognized column name or alias is present. Unrecognized column names are not automatically mapped.

## 6. Risk scoring

Each issue category has a configured weight. For each record:

`Risk score = min(100, (sum of issue weights for the record / sum of all configured issue weights) × 100)`

The app groups non-zero scores into Low, Medium, and High review levels, with zero labeled No issues. This is a data quality prioritization score only; it is not a patient health risk score or a prediction.

## 7. Cleanup and review workflow

The cleaned copy currently trims whitespace and standardizes text casing in selected appointment fields, converts scheduling dates to UTC timestamps, sets invalid or out-of-range ages to blank for staff verification, and removes exact duplicate copies. Other findings are left for manual review. The source table is retained, cleanup actions are shown before download, and the user must acknowledge the summary before downloading from **Cleaning & Export**.

Findings can be assigned an owner, given a review note, and moved through New, In review, Resolved, or Accepted. With a Gemini API key, the assistant uses only the dataset type, issue category, generic rule details, and affected-record count to generate explanations. It does not send patient rows or identifiers. Rule-based guidance remains available as a fallback. AI explanations are advisory and do not autonomously correct the source record.

## 8. Storage and dashboard outputs

The app uses a local SQLite database at `database/healthq_ai.db`. It keeps latest-active tables for raw data, cleaned data, findings, and scores. Dataset metadata and review state are keyed by file content hash. Per-version raw, cleaned, issue, and risk snapshots are stored in version-named tables, with a run history for trend charts. The Dataset Catalogue exposes ownership details, expected processing cadence, saved versions, and masked previews. The Reports page generates an aggregate Markdown report and issue summary CSV. The multipage interface is launched from `Home.py`; validation logic is in `src/quality_pipeline.py`, preview masking is in `src/preview_privacy.py`, and database updates run through `Data_Upload.py`.

Likely direct identifiers are masked in selected on-screen previews. The stored dataset and downloaded CSV files are unchanged; this feature is not full de-identification.

## 9. Observed sample results

The supplied dashboard screenshots showed:

- **Records:** 110,527
- **Columns:** 14
- **Exact duplicate rows:** 0
- **Issue findings:** 6 across 6 records
- **Age out of range:** 1 record
- **Appointment date-order problems:** 5 records
- **Cleaned records:** 110,527
- **Exact duplicates removed:** 0
- **Cleaned completeness:** 99.9999% after the invalid age was set blank for verification
- **Average flagged risk score:** 20/100, categorized as Low for the flagged records

These values are the results visible in the user's project screenshots; the updated application was not executed as part of preparing this report. Re-run the app and review current outputs before presenting results if the input file has changed.

## 10. Tools and technologies

- **Python** — application logic
- **pandas** — CSV loading, profiling, validation, and transformations
- **Streamlit** — multipage user interface and charts
- **SQLite** — local database and dataset/review history
- **Google Gemini API and Google Gen AI Python SDK** — generated issue explanations when configured
- **CSV** — input and export format

## 11. Limitations and future work

- Generative assistance requires a valid Gemini API key, internet access, and API access to the configured model; rule-based guidance is available as a fallback.
- AI-generated suggestions can be incomplete or wrong and require staff review.
- Rules recognize known column aliases and need configurable mapping for new hospital schemas.
- The prototype is local and has no authentication, role-based permissions, or automated EHR/LIS integration.
- Identifier masking applies to selected previews only; it does not de-identify all possible sensitive fields.
- SQLite is appropriate for this demonstration, not a substitute for a hospital production data platform.
- Future work could add schema mapping, departmental access controls, configurable validation rules, integration with approved hospital systems, and privacy/security review before any real patient data is used.

## 12. Conclusion

HealthQ AI demonstrates an end-to-end data quality workflow for healthcare-style CSV files: profile, validate, score, review, clean conservatively, retain version snapshots, and report. Its main contribution is making data quality findings visible and actionable while keeping corrections under human review. The prototype provides a foundation for expanding to multiple hospital datasets and configurable operational rules.

