# HealthQ AI

**Healthcare Data Quality Monitoring Assistant**

HealthQ AI is a local Streamlit prototype for profiling hospital-style CSV files, flagging data quality issues, prioritizing findings for review, recording issue ownership and status, and exporting cleaned datasets and reports.

## Run the project on Windows

Open PowerShell in the `HealthQ_AI` folder and run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run Home.py
```

If `.venv` does not exist yet, create it first:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run Home.py
```

The app opens in a browser. The Kaggle appointment dataset is loaded by default when `data/raw/KaggleV2-May-2016.csv` is present. You can also upload a CSV from **Data Upload**.

## Configure the generative AI assistant

The AI Assistant uses the Gemini API when a key is configured. Create a key in [Google AI Studio](https://aistudio.google.com/app/apikey), then copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and replace the placeholder:

```powershell
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
notepad .streamlit\secrets.toml
```

If `.streamlit\secrets.toml` already exists, open it directly in Notepad and replace the old OpenAI settings with the Gemini settings below; do not overwrite your file by copying the example.

Set the file contents to:

```toml
GEMINI_API_KEY = "paste-your-Gemini-API-key-here"
GEMINI_MODEL = "gemini-3.5-flash-lite"
```

Install the updated package and restart the app:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Keep `secrets.toml` private and do not share or commit it. The app uses `GEMINI_API_KEY` from the environment first, then the secrets file, and defaults to `gemini-3.5-flash-lite` for short explanations. Without a key, rule-based explanations remain available. Each API request sends only the selected issue category, dataset type, generic rule details, and count of affected records. It does not send patient rows or identifiers. AI suggestions require staff verification. Check Google AI Studio usage and quota if Gemini reports a rate or quota limit.

## Main workflow

1. Open **Data Upload**, choose the dataset type, and optionally enter its department, source system, steward, and expected refresh frequency.
2. Review the summary in **Overview** and the column statistics in **Data Profile**.
3. Use **Issue Explorer** to filter findings, assign an owner, add a note, and update review status.
4. Check the record-level data quality scores in **Risk Scores**. These are data quality review priorities, not patient health scores.
5. Review cleanup actions in **Cleaning & Export**, acknowledge the summary, and download the cleaned CSV.
6. Use **AI Assistant** for Gemini-generated explanations and suggested review steps, or rule-based guidance when no API key is configured.
7. Use **Quality Trends** to compare saved source and cleaned snapshots across versions.
8. Use **Dataset Catalogue** to view ownership, processing cadence, dataset versions, and archived raw/cleaned previews. **Database & Reports** provides aggregate reports and database previews.

## Checks included

All dataset types receive missing value and exact duplicate row checks. Additional checks depend on the selected type and recognized column names:

- **Appointments:** age range, appointment identifier uniqueness, appointment date order, gender/no-show categories, and binary indicators.
- **Patient registration:** age range, patient identifier uniqueness, and gender categories.
- **Laboratory results:** result identifier uniqueness, date order, and reference bound order.
- **Encounters or admissions:** encounter identifier uniqueness and admission/discharge date order.
- **Medications:** medication order uniqueness, date order, and non-negative dose or quantity.
- **Other:** shared completeness and duplicate checks.

The current rules use column-name aliases. Datasets with different field names may need a custom mapping or an additional rule.

## Risk score

Each finding adds a configured number of issue points. A row's score is `min(100, issue points / total configured issue weights × 100)`. The current categories are **No issues**, **Low**, **Medium**, and **High**. The score helps staff prioritize data review; it is not a clinical assessment.

## Storage and outputs

- SQLite database: `database/healthq_ai.db`
- Latest active tables: `records_raw`, `records_clean`, `quality_issues`, `risk_scores`
- Dataset catalogue and issue review history: `dataset_catalog`, `issue_reviews`
- Per-version snapshots: tables named `dataset_raw_<hash>`, `dataset_clean_<hash>`, `dataset_issues_<hash>`, and `dataset_risk_<hash>`
- Run history: `dataset_run_history`
- Latest cleaned CSV: `data/processed/healthq_ai_cleaned.csv`
- Submission report: `reports/HealthQ_AI_Final_Project_Report.docx` and `.pdf`
- Editable report source: `reports/HealthQ_AI_Final_Project_Report.md`

Likely direct identifiers are masked in selected on-screen previews. Stored data and downloaded CSV exports are not masked by this preview helper.

## Project scope

This is an academic local prototype. Generative AI requires the user's own Gemini API key and internet access; without it, the assistant falls back to predefined rules. The app does not connect to an EHR/LIS, provide user accounts or role-based access, or replace staff approval of source corrections. Validate rules and access controls before using any real hospital data.
