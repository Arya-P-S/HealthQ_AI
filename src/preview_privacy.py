"""Helpers for reducing identifier exposure in dashboard previews only."""

import pandas as pd


SENSITIVE_COLUMN_NAMES = {
    "patientid",
    "appointmentid",
    "encounterid",
    "visitid",
    "admissionid",
    "resultid",
    "orderid",
    "recordid",
    "sampleid",
    "testid",
    "claimid",
    "personid",
    "userid",
    "providerid",
    "id",
    "medicalrecordnumber",
    "mrn",
    "firstname",
    "lastname",
    "fullname",
    "patientname",
    "surname",
    "email",
    "phone",
    "phonenumber",
    "mobile",
    "mobilenumber",
    "address",
    "nationalid",
    "ssn",
    "identifier",
}


def mask_identifiers(frame):
    """Return a display copy with likely direct identifiers masked.

    This is a convenience for on-screen previews, not de-identification.
    Downloaded datasets and stored source records are not changed.
    """
    preview = frame.copy()
    masked_columns = []
    for column in preview.columns:
        normalized = "".join(character.lower() for character in str(column) if character.isalnum())
        if (
            normalized in SENSITIVE_COLUMN_NAMES
            or normalized.endswith("identifier")
            or normalized.endswith("idnumber")
        ):
            preview[column] = preview[column].map(
                lambda value: value if pd.isna(value) else "[masked]"
            )
            masked_columns.append(str(column))
    return preview, masked_columns
