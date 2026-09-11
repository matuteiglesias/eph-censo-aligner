"""Machine-native official source semantics for exact EPH/Census review pairs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REAL_2024Q3_CPV2010 = ROOT / "aligner" / "codebooks" / "real_2024q3_cpv2010_23.json"
EXPECTED_CONCEPTS = {
    "IX_TOT", "P02", "P03", "CONDACT", "V01",
    "H05", "H06", "H07", "H08", "H09", "H10", "H11", "H12",
    "H13", "H14", "H15", "H16", "PROP",
    "P07", "P08", "P09", "P10", "P05",
}


class CodebookError(ValueError):
    """Raised when semantic evidence is incomplete or internally ambiguous."""


def validate_codebook_pair(value: dict[str, Any]) -> None:
    if value.get("schema") != "research.eph-census-codebook-pair/v1":
        raise CodebookError("unexpected_codebook_schema")
    pair = value.get("pair")
    if not isinstance(pair, dict):
        raise CodebookError("codebook_pair_missing")
    for key in ("eph_release_id", "census_frame_release_id", "census_sample_release_id"):
        if not isinstance(pair.get(key), str) or not pair[key]:
            raise CodebookError(f"codebook_pair_identity_missing:{key}")
    sources = value.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise CodebookError("codebook_sources_missing")
    for source_id, source in sources.items():
        if not isinstance(source, dict) or not str(source.get("url", "")).startswith("https://"):
            raise CodebookError(f"codebook_source_invalid:{source_id}")

    concepts = value.get("concepts")
    if not isinstance(concepts, list):
        raise CodebookError("codebook_concepts_missing")
    names = [record.get("concept") for record in concepts if isinstance(record, dict)]
    if len(names) != len(concepts) or len(set(names)) != len(names):
        raise CodebookError("codebook_concepts_duplicate_or_invalid")
    if set(names) != EXPECTED_CONCEPTS:
        missing = sorted(EXPECTED_CONCEPTS - set(names))
        extra = sorted(set(names) - EXPECTED_CONCEPTS)
        raise CodebookError(f"codebook_concept_surface_mismatch:missing={missing}:extra={extra}")

    for record in concepts:
        concept = record["concept"]
        if record.get("review_status") not in {"pending", "approved", "rejected"}:
            raise CodebookError(f"codebook_review_status_invalid:{concept}")
        for side in ("eph", "census"):
            evidence = record.get(side)
            if not isinstance(evidence, dict):
                raise CodebookError(f"codebook_side_missing:{concept}:{side}")
            for required in ("field", "table", "label"):
                if not evidence.get(required):
                    raise CodebookError(f"codebook_evidence_missing:{concept}:{side}:{required}")


def load_real_codebook_pair() -> dict[str, Any]:
    value = json.loads(REAL_2024Q3_CPV2010.read_text(encoding="utf-8"))
    validate_codebook_pair(value)
    return value


def concept_evidence(concept: str) -> dict[str, Any]:
    """Return one exact concept record; no fuzzy or alias lookup is allowed."""
    codebook = load_real_codebook_pair()
    for record in codebook["concepts"]:
        if record["concept"] == concept:
            return record
    raise CodebookError(f"unknown_codebook_concept:{concept}")
