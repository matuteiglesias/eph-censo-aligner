from __future__ import annotations

import json
from pathlib import Path

import pytest

from aligner.feature_plane import (
    CONTRACT,
    FeaturePlaneError,
    compile_feature_plane,
    validate_feature_plane,
)

ROOT = Path(__file__).parents[1]
INVENTORY = ROOT / "aligner" / "review_inventories" / "historical_staged_v1.json"


def _by_name(plane: dict) -> dict[str, dict]:
    return {record["feature"]: record for record in plane["features"]}


def test_historical_staged_v1_is_frozen_as_exact_four_stage_inventory() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))

    assert inventory["spec_id"] == "historical_staged_v1"
    assert len(inventory["stages"]) == 4
    assert inventory["stages"][0]["inputs"] == [
        "IX_TOT",
        "P02",
        "P03",
        "AGLO_rk",
        "Reg_rk",
        "V01",
        "H05",
        "H06",
        "H07",
        "H08",
        "H09",
        "H10",
        "H11",
        "H12",
        "H16",
        "H15",
        "PROP",
        "H14",
        "H13",
        "P07",
        "P08",
        "P09",
        "P10",
        "P05",
        "CONDACT",
    ]
    assert inventory["stages"][0]["targets"] == ["CAT_OCUP", "CAT_INAC", "CH07"]
    assert inventory["stages"][1]["targets"] == [
        "INGRESO",
        "INGRESO_NLB",
        "INGRESO_JUB",
        "INGRESO_SBS",
    ]
    assert inventory["stages"][2]["targets"] == [
        "PP07G1",
        "PP07G_59",
        "PP07I",
        "PP07J",
        "PP07K",
    ]
    assert inventory["stages"][3]["targets"] == [
        "P21",
        "P47T",
        "PP08D1",
        "TOT_P12",
        "T_VI",
        "V12_M",
        "V2_M",
        "V3_M",
        "V5_M",
    ]


def test_review_plane_covers_every_feature_without_approving_real_inputs() -> None:
    plane = compile_feature_plane(INVENTORY)
    records = _by_name(plane)

    assert plane["contract"] == CONTRACT
    assert plane["status"] == "review_required"
    assert plane["runtime_approval"] == {
        "synthetic_fixture_v1": True,
        "real_vintage": False,
    }
    assert len(records) == 46
    assert plane["summary"] == {
        "feature_count": 46,
        "external_census_inputs_approved": 0,
        "stage_targets": 21,
        "research_only": 2,
        "unsupported": 23,
    }
    assert not any(record["external_census_input_allowed"] for record in records.values())


def test_target_derived_geography_ranks_are_forbidden_external_inputs() -> None:
    records = _by_name(compile_feature_plane(INVENTORY))

    for feature in ("AGLO_rk", "Reg_rk"):
        assert records[feature]["semantic_class"] == "research_only"
        assert records[feature]["review_status"] == "forbidden_external_census_input"
        assert records[feature]["external_census_input_allowed"] is False


def test_all_historical_learned_outputs_are_stage_targets() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    expected = {
        target
        for stage in inventory["stages"]
        for target in stage["targets"]
    }
    records = _by_name(compile_feature_plane(INVENTORY))

    assert {
        name
        for name, record in records.items()
        if record["semantic_class"] == "stage_target"
    } == expected


def test_validator_rejects_unsafe_approval() -> None:
    plane = compile_feature_plane(INVENTORY)
    record = _by_name(plane)["AGLO_rk"]
    record["external_census_input_allowed"] = True

    with pytest.raises(FeaturePlaneError, match="unsafe_external_input_approval"):
        validate_feature_plane(plane)
