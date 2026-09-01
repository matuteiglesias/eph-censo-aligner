from __future__ import annotations

import json
from pathlib import Path

import pytest

from aligner.legacy_bridge_review import (
    DEFAULT_BRIDGE_EVIDENCE,
    LegacyBridgeReviewError,
    compile_legacy_bridge_gap_report,
)

ROOT = Path(__file__).parents[1]
INVENTORY = ROOT / "aligner" / "review_inventories" / "historical_staged_v1.json"


def _by_name(report: dict) -> dict[str, dict]:
    return {record["feature"]: record for record in report["features"]}


def test_historical_bridge_evidence_shrinks_unknown_provenance_not_semantic_gap() -> None:
    report = compile_legacy_bridge_gap_report(INVENTORY, DEFAULT_BRIDGE_EVIDENCE)

    assert report["status"] == "semantic_evidence_required"
    assert report["runtime_approval"]["real_vintage"] is False
    assert report["summary"] == {
        "feature_count": 46,
        "legacy_bridge_evidence_attached": 23,
        "external_census_inputs_approved": 0,
        "question_evidence_missing": 23,
        "universe_evidence_missing": 23,
        "reference_period_evidence_missing": 23,
        "category_domain_evidence_missing": 23,
        "forbidden_external_inputs": 2,
        "learned_stage_outputs": 21,
    }
    assert report["next_gate"]["automatic_name_match_approval"] is False
    assert report["next_gate"]["lossy_or_asymmetric_recodes_require_explicit_review"] is True


def test_key_legacy_aliases_are_attached_with_native_eph_sources() -> None:
    records = _by_name(
        compile_legacy_bridge_gap_report(INVENTORY, DEFAULT_BRIDGE_EVIDENCE)
    )

    assert records["P02"]["eph_source_fields"] == ["CH04"]
    assert records["P02"]["census_source_fields"] == ["P02"]
    assert records["P03"]["eph_source_fields"] == ["CH06"]
    assert records["CONDACT"]["eph_source_fields"] == ["ESTADO"]
    assert records["V01"]["eph_source_fields"] == ["IV1"]
    assert records["PROP"]["eph_source_fields"] == ["II7"]
    assert "7, 8 and 9" in records["PROP"]["known_loss_or_ambiguity"]
    assert records["P05"]["eph_source_fields"] == ["CH15"]

    for feature in ("P02", "P03", "CONDACT", "V01", "PROP", "P05"):
        assert records[feature]["semantic_class"] == "unsupported"
        assert records[feature]["external_census_input_allowed"] is False
        assert records[feature]["question_evidence"] == "missing"


def test_target_derived_ranks_remain_permanently_forbidden() -> None:
    records = _by_name(
        compile_legacy_bridge_gap_report(INVENTORY, DEFAULT_BRIDGE_EVIDENCE)
    )

    for feature in ("AGLO_rk", "Reg_rk"):
        assert records[feature]["review_state"] == "forbidden_external_census_input"
        assert records[feature]["external_census_input_allowed"] is False
        assert records[feature]["semantic_class"] == "research_only"


def test_every_unsupported_external_feature_has_exactly_one_bridge_record() -> None:
    evidence = json.loads(DEFAULT_BRIDGE_EVIDENCE.read_text(encoding="utf-8"))
    names = [record["feature"] for record in evidence["features"]]
    assert len(names) == len(set(names)) == 23

    records = _by_name(
        compile_legacy_bridge_gap_report(INVENTORY, DEFAULT_BRIDGE_EVIDENCE)
    )
    assert set(names) == {
        feature
        for feature, record in records.items()
        if record["semantic_class"] == "unsupported"
    }


def test_missing_bridge_evidence_fails_closed(tmp_path: Path) -> None:
    evidence = json.loads(DEFAULT_BRIDGE_EVIDENCE.read_text(encoding="utf-8"))
    evidence["features"] = evidence["features"][1:]
    broken = tmp_path / "bridge.json"
    broken.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(
        LegacyBridgeReviewError,
        match="unsupported_features_missing_bridge_evidence",
    ):
        compile_legacy_bridge_gap_report(INVENTORY, broken)
