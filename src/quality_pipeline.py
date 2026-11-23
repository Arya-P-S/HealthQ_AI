import re

import pandas as pd


def find_quality_issues(data, dataset_type="Other"):
    """Run shared checks plus rules selected for the dataset type."""
    rows = []

    def add(mask, issue, column, details):
        for index in data.index[mask.fillna(False).astype(bool)]:
            rows.append({
                "Record": int(index) + 1,
                "Column": column,
                "Issue": issue,
                "Details": details,
            })

    def get_column(*names):
        normalized = {
            re.sub(r"[^a-z0-9]", "", str(column).lower()): column
            for column in data.columns
        }
        for name in names:
            key = re.sub(r"[^a-z0-9]", "", name.lower())
            if key in normalized:
                return normalized[key]
        return None

    def check_age():
        column = get_column("Age")
        if column:
            age = pd.to_numeric(data[column], errors="coerce")
            invalid = data[column].notna() & (
                age.isna() | (age < 0) | (age > 120)
            )
            add(invalid, "Age out of range", column, "Expected age from 0 to 120")

    def check_unique_id(*aliases):
        column = get_column(*aliases)
        if column:
            duplicated = data[column].notna() & data[column].duplicated(keep=False)
            add(
                duplicated,
                "Duplicate identifier",
                column,
                f"{column} should identify one record in this dataset type",
            )

    def check_date_order(start_column, end_column):
        if not start_column or not end_column:
            return
        start = pd.to_datetime(data[start_column], errors="coerce", utc=True)
        end = pd.to_datetime(data[end_column], errors="coerce", utc=True)
        add(
            data[start_column].notna() & start.isna(),
            "Invalid date",
            start_column,
            f"Could not parse {start_column}",
        )
        add(
            data[end_column].notna() & end.isna(),
            "Invalid date",
            end_column,
            f"Could not parse {end_column}",
        )
        add(
            start.notna() & end.notna() & (end.dt.normalize() < start.dt.normalize()),
            "Date order problem",
            end_column,
            f"{end_column} is earlier than {start_column}",
        )

    def check_nonnegative_number(*aliases):
        column = get_column(*aliases)
        if column:
            number = pd.to_numeric(data[column], errors="coerce")
            invalid = data[column].notna() & (
                number.isna() | (number < 0)
            )
            add(
                invalid,
                "Invalid numeric value",
                column,
                f"{column} should be a non-negative number",
            )

    # Shared checks for every dataset.
    for column in data.columns:
        add(data[column].isna(), "Missing value", column, f"{column} is blank")
    add(
        data.duplicated(),
        "Duplicate row",
        "All columns",
        "Exact duplicate of an earlier row",
    )

    if dataset_type == "Appointments":
        check_age()
        check_unique_id("AppointmentID", "AppointmentId", "Appointment_ID")
        scheduled = get_column("ScheduledDay", "ScheduledDate")
        appointment = get_column("AppointmentDay", "AppointmentDate")
        check_date_order(scheduled, appointment)

        for column, allowed in {
            "Gender": {"F", "M"},
            "No-show": {"Yes", "No"},
        }.items():
            actual = get_column(column)
            if actual:
                values = data[actual].astype("string").str.strip().str.title()
                add(
                    data[actual].notna() & ~values.isin(allowed),
                    "Unexpected category",
                    actual,
                    f"Unexpected value in {actual}",
                )

        for name in [
            "Scholarship", "Hipertension", "Diabetes", "Alcoholism", "SMS_received"
        ]:
            actual = get_column(name)
            if actual:
                values = pd.to_numeric(data[actual], errors="coerce")
                add(
                    data[actual].notna() & ~values.isin([0, 1]),
                    "Invalid binary value",
                    actual,
                    f"{actual} should be 0 or 1",
                )

    elif dataset_type == "Patient registration":
        check_age()
        check_unique_id(
            "PatientID", "PatientId", "Patient_ID", "MRN", "MedicalRecordNumber"
        )
        gender = get_column("Gender", "Sex")
        if gender:
            allowed = {"F", "M", "Female", "Male", "Other", "Unknown", "U", "Nonbinary"}
            values = data[gender].astype("string").str.strip().str.title()
            add(
                data[gender].notna() & ~values.isin(allowed),
                "Unexpected category",
                gender,
                f"Unexpected value in {gender}",
            )

    elif dataset_type == "Laboratory results":
        check_unique_id("LabResultID", "ResultID", "ObservationID")
        collection = get_column("CollectionDate", "CollectedAt", "CollectedDate")
        result_date = get_column("ResultDate", "ObservedAt", "ObservationDate")
        if collection and result_date:
            check_date_order(collection, result_date)

        low = get_column("ReferenceLow", "NormalRangeLow", "ReferenceRangeLow")
        high = get_column("ReferenceHigh", "NormalRangeHigh", "ReferenceRangeHigh")
        if low and high:
            low_value = pd.to_numeric(data[low], errors="coerce")
            high_value = pd.to_numeric(data[high], errors="coerce")
            invalid_range = (
                low_value.notna() & high_value.notna() & (low_value > high_value)
            )
            add(
                invalid_range,
                "Reference range problem",
                high,
                f"{high} is lower than {low}",
            )

    elif dataset_type == "Encounters or admissions":
        check_unique_id("EncounterID", "VisitID", "AdmissionID")
        admission = get_column("AdmissionDate", "AdmitDate", "AdmittedAt")
        discharge = get_column("DischargeDate", "DischargedAt")
        if admission and discharge:
            check_date_order(admission, discharge)

    elif dataset_type == "Medications":
        check_unique_id("MedicationOrderID", "PrescriptionID", "OrderID")
        start = get_column("StartDate", "MedicationStartDate", "OrderStartDate")
        end = get_column("EndDate", "MedicationEndDate", "OrderEndDate")
        if start and end:
            check_date_order(start, end)
        check_nonnegative_number("Dose", "DoseAmount", "DoseValue", "Quantity")

    return pd.DataFrame(
        rows,
        columns=["Record", "Column", "Issue", "Details"],
    )

