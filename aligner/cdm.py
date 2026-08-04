"""Versioned common-data-model contract used by release manifests."""

CDM_VERSION = "1.0.0"

CDM_FIELDS = {
    "household": {
        "IX_TOT": "integer", "sex": "integer", "age": "integer",
        "activity": "integer", "agglomeration": "integer",
    },
    "individual": {
        "record_id": "string", "age": "integer", "school_attendance": "integer",
        "activity": "integer",
    },
}
