from __future__ import annotations

from aligner.codebook import EXPECTED_CONCEPTS, concept_evidence, load_real_codebook_pair


def test_real_codebook_pair_covers_exact_23_concepts() -> None:
    codebook = load_real_codebook_pair()
    assert {record["concept"] for record in codebook["concepts"]} == EXPECTED_CONCEPTS
    assert codebook["pair"]["eph_release_id"] == "eph-2024-q3-3b6a7a15c4af"
    assert codebook["pair"]["census_sample_release_id"] == "census-sample-2024-0839713eafea8d1b"


def test_raw_census_fields_are_distinguished_from_redatam_aliases() -> None:
    for concept, raw_field in (("P07", "P07"), ("P08", "P08"), ("P09", "P09"), ("P10", "P10")):
        record = concept_evidence(concept)
        assert record["census"]["field"] == raw_field
        assert "REDATAM" in record["census"]["raw_field_note"]


def test_activity_status_records_universe_mismatch() -> None:
    record = concept_evidence("CONDACT")
    assert record["eph"]["field"] == "ESTADO"
    assert record["census"]["field"] == "CONDACT"
    assert "14+" in record["census"]["universe"]
    assert "temporal" in record["known_semantic_risk"]
