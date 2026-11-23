from pathlib import Path
import json
import os
import sqlite3

import pandas as pd
import streamlit as st

st.title("HealthQ Assistant")
st.caption("AI-supported explanations and review suggestions for data quality findings.")

database_file = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "healthq_ai.db"
)

guidance = {
    "Missing value": (
        "A field is blank.",
        "Check the source record. If the value cannot be verified, keep it missing "
        "and document how downstream analysis should handle it.",
    ),
    "Duplicate row": (
        "A row appears to duplicate another record.",
        "Compare the records before removing one. Keep the original data and log "
        "any removal.",
    ),
    "Age out of range": (
        "The age is outside the expected 0–120 range.",
        "Check the source. Do not guess an age; use a missing value if it cannot "
        "be confirmed.",
    ),
    "Invalid date": (
        "A date could not be read in the expected format.",
        "Check the source date and its format. Do not replace it with an assumed date.",
    ),
    "Date order problem": (
        "The appointment date is earlier than the scheduled date.",
        "Check the original values and date/time conventions. Do not swap dates "
        "automatically.",
    ),
    "Unexpected category": (
        "A category value is outside the expected set.",
        "Check whether it is a spelling or formatting variation before standardizing it.",
    ),
    "Invalid binary value": (
        "A yes/no indicator contains a value other than 0 or 1.",
        "Verify the value from the source before correcting it.",
    ),
    "Duplicate identifier": (
        "A field expected to identify one record appears more than once.",
        "Confirm that the selected identifier is supposed to be unique for this dataset. Check for repeated imports or an incorrect record key. Do not delete rows automatically; a patient may legitimately have multiple visits or results.",
    ),
    "Invalid numeric value": (
        "A field expected to contain a non-negative number has text or a negative value.",
        "Check the source value, units, and field definition. Correct only from a verified source; do not guess, round, or replace the value automatically.",
    ),
    "Reference range problem": (
        "The configured lower reference bound is greater than the upper bound.",
        "Check the test, units, and reference interval configuration with the laboratory source. Do not change the patient result to make it fit the interval.",
    ),
}

if not database_file.exists():
    st.info("Run the main app first so it can create the database.")
else:
    with sqlite3.connect(database_file) as connection:
        issues = pd.read_sql_query(
            "SELECT * FROM quality_issues",
            connection,
        )
        table_names = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'", connection
        )["name"].tolist()

    if issues.empty:
        st.success("There are no saved issues to explain.")
    else:
        issue_types = sorted(issues["Issue"].dropna().unique())
        selected = st.selectbox("Choose an issue", issue_types)

        matching = issues[issues["Issue"] == selected]
        explanation, suggestion = guidance.get(
            selected,
            ("This issue was flagged by a validation rule.",
             "Review the source record and document any correction."),
        )

        st.metric("Records with this issue", matching["Record"].nunique())
        st.subheader("What it means")
        st.write(explanation)
        st.subheader("Suggested review action")
        st.write(suggestion)

        def setting(name, default=""):
            value = os.getenv(name)
            if value:
                return value
            try:
                return st.secrets.get(name, default)
            except Exception:
                return default

        api_key = setting("GEMINI_API_KEY")
        api_key_source = (
            "GEMINI_API_KEY environment variable"
            if os.getenv("GEMINI_API_KEY")
            else (".streamlit/secrets.toml" if api_key else "not configured")
        )
        model_name = setting("GEMINI_MODEL", "gemini-3.5-flash-lite")
        metadata_for_ai = st.session_state.get("dataset_metadata", {})
        dataset_key = str(metadata_for_ai.get("dataset_hash", "current"))[:12]
        dataset_type_for_ai = str(metadata_for_ai.get("dataset_type", "Unknown"))
        affected_count = int(matching["Record"].nunique())
        cache_key = f"healthq_gemini_explanation_v2_{dataset_key}_{selected}_{dataset_type_for_ai}_{affected_count}"
        st.subheader("Gemini AI explanation")
        st.caption("The request sends only the dataset type, issue category, generic rule details, and affected-record count. It does not send patient rows or identifiers.")
        if not api_key:
            st.info("Gemini API is not configured. Add GEMINI_API_KEY to .streamlit/secrets.toml, then restart HealthQ AI. Rule-based guidance above remains available.")
        else:
            st.success(f"Gemini API key loaded from {api_key_source} · model: {model_name}")
            if st.button("Generate Gemini explanation", type="primary"):
                context = {
                    "dataset_type": dataset_type_for_ai,
                    "issue_type": selected,
                    "rule_details": sorted(matching["Details"].dropna().astype(str).unique().tolist())[:3],
                    "affected_record_count": affected_count,
                    "rule_based_meaning": explanation,
                    "review_suggestion": suggestion,
                }
                try:
                    from google import genai
                    from google.genai import types

                    prompt = (
                        "You are the data-quality explanation assistant inside HealthQ AI. Do not introduce yourself or claim a personal name. "
                        "Start directly with the explanation. Explain only the supplied data-quality rule context. "
                        "Give a concise plain-language explanation and up to three safe review steps. Do not provide diagnosis, treatment, "
                        "or patient health advice. Never invent missing facts or recommend guessing, automatically changing, or deleting clinical data. "
                        "Tell staff to verify any correction against an authorized source and keep a human reviewer responsible.\n\n"
                        f"Issue context (aggregate only): {json.dumps(context, ensure_ascii=False)}"
                    )
                    with genai.Client(
                        api_key=api_key,
                        http_options=types.HttpOptions(
                            timeout=30000,
                            retry_options=types.HttpRetryOptions(attempts=1),
                        ),
                    ) as client:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=types.GenerateContentConfig(max_output_tokens=250, temperature=0.2),
                        )
                    ai_text = (response.text or "").strip()
                    if not ai_text:
                        st.warning("The AI returned no text. Try again or use the rule-based guidance above.")
                    else:
                        st.session_state[cache_key] = ai_text
                except ImportError:
                    st.error("The Gemini SDK is not installed. Run: .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt")
                except Exception as error:
                    if type(error).__name__ in {"Unauthenticated", "AuthenticationError"}:
                        st.error(
                            f"Gemini rejected the API key loaded from {api_key_source}. Replace it with a valid Gemini API key. "
                            "If you updated secrets.toml but the error continues, check for an old GEMINI_API_KEY environment variable; "
                            "the environment variable takes precedence. Restart the app after changing credentials."
                        )
                    elif type(error).__name__ in {"PermissionDenied", "PermissionDeniedError"}:
                        st.error("The Gemini key is recognized but cannot access this model or project. Check Google AI Studio model access.")
                    elif type(error).__name__ in {"ResourceExhausted", "TooManyRequests"}:
                        st.error("Gemini API quota or rate limit reached. Check Google AI Studio usage and limits, then try later.")
                    elif type(error).__name__ in {"ServerError", "InternalServerError"}:
                        st.error("Gemini is temporarily unavailable. Wait a minute and try again. This request stops after 30 seconds; repeated retries are disabled to avoid a long wait.")
                        st.markdown("[Check Google AI Studio API status](https://aistudio.google.com/status)")
                    elif type(error).__name__ in {"TimeoutError", "ReadTimeout", "ConnectTimeout"}:
                        st.error("Gemini did not respond within 30 seconds. Try again later or check Google AI Studio API status.")
                        st.markdown("[Check Google AI Studio API status](https://aistudio.google.com/status)")
                    else:
                        st.error(f"Gemini request failed ({type(error).__name__}). Check internet access and the configured model name.")

            if st.session_state.get(cache_key):
                st.markdown(st.session_state[cache_key])
                st.caption("AI suggestions are advisory. A staff member must verify and approve any correction.")

        metadata = st.session_state.get("dataset_metadata", {})
        active_hash = metadata.get("dataset_hash")
        if active_hash and "issue_reviews" in table_names:
            with sqlite3.connect(database_file) as connection:
                reviews = pd.read_sql_query(
                    """SELECT severity, status, COUNT(*) AS findings
                       FROM issue_reviews
                       WHERE dataset_hash = ? AND issue_type = ?
                       GROUP BY severity, status""",
                    connection,
                    params=(active_hash, selected),
                )
            open_count = int(reviews.loc[reviews["status"].isin(["New", "In review"]), "findings"].sum()) if not reviews.empty else 0
            high_count = int(reviews.loc[reviews["severity"] == "High", "findings"].sum()) if not reviews.empty else 0
            st.caption(f"Review queue for this issue: {open_count:,} open · {high_count:,} high severity")
            if not reviews.empty:
                st.dataframe(reviews, use_container_width=True, hide_index=True)
        st.subheader("Affected records")
        st.dataframe(matching, use_container_width=True, hide_index=True)
