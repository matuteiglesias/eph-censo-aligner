from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from aligner.real_semantic_plane import (
    _review_row,
    _transform_series,
    _verify_eph_frame_period,
    load_review_policy,
    plane_fields,
)


def _record(concept: str) -> dict:
    for row in load_review_policy()["concepts"]:
        if row["concept"] == concept:
            return row
    raise AssertionError(concept)


def test_real_review_policy_is_exact_23_and_separates_temporal_planes() -> None:
    policy = load_review_policy()
    assert len(policy["concepts"]) == 23
    assert policy["parents"] == {
        "eph_release_id": "eph-2024-q3-3b6a7a15c4af",
        "census_frame_release_id": "arg-cpv2010-frame-ee6ada167c2d6429",
        "census_sample_release_id": "census-sample-2024-0839713eafea8d1b",
    }
    assert policy["clocks"] == {
        "eph_period": "2024-Q3",
        "census_vintage": 2010,
        "sampling_target_year": 2024,
    }
    assert policy["contracts"]["census_sample"] == "research.census-target-year-sample/v2"
    p1s, p1r, unresolved, rejected = plane_fields(policy)
    assert p1s == ["P02", "P05"]
    assert len(p1r) == 20
    assert set(unresolved) == {"H06", "H11", "H16"}
    assert rejected == []
    assert "CONDACT" in p1r
    assert "CONDACT" not in p1s


def test_valid_census_category_absent_from_quarter_is_support_diagnostic() -> None:
    record = _record("P02")
    eph = pd.DataFrame({"CH04": [1], "row_id": ["e1"], "household_id": ["h1"]})
    census = pd.DataFrame(
        {"P02": [1, 2], "row_id": ["c1", "c2"], "household_id": ["h1", "h2"]}
    )
    review, _, _, support = _review_row(record, eph, census)
    assert review["semantic_decision"] == "approve"
    assert support["violations"] == []
    assert support["diagnostics"] == [
        {
            "type": "census_canonical_category_absent_from_training",
            "concept": "P02",
            "detail": ["2"],
            "interpretation": "statistical_support_not_semantic_incompatibility",
        }
    ]


def test_expected_special_codes_become_null_but_unexpected_codes_are_reported() -> None:
    record = _record("P10")
    values, report = _transform_series(
        pd.Series([1, 2, 9, 7]),
        record["eph"],
        record["validation"],
    )
    assert values.iloc[0] == 1
    assert values.iloc[1] == 2
    assert pd.isna(values.iloc[2])
    assert pd.isna(values.iloc[3])
    assert report["expected_special_to_null"] == ["9"]
    assert report["expected_special_map"] == {}
    assert report["unmapped_codes"] == {"7": 1}


def test_condact_is_semantically_approved_but_not_target_year_stable() -> None:
    record = _record("CONDACT")
    assert record["semantic_decision"] == "approve"
    assert record["temporal_role"] == "target-period-state"
    assert set(record["eph"]["special_to_null"]) == {0, 4}
    assert record["census"]["universe"] == "age 14+"


def test_policy_loader_is_donor_vintage_neutral(tmp_path) -> None:
    source_policy = load_review_policy()
    policy_path = tmp_path / "review_policy_2022.json"
    codebook_path = tmp_path / "codebook_2022.json"
    person_codes_path = tmp_path / "person_codes.json"
    household_codes_path = tmp_path / "household_codes.json"

    policy = json.loads(json.dumps(source_policy))
    policy["release_id"] = "eph-cpv2022-semantic-plane-2024q3-fixture"
    policy["parents"] = {
        "eph_release_id": "eph-fixture-2024-q3",
        "census_frame_release_id": "arg-cpv2022-frame-fixture",
        "census_sample_release_id": "census-sample-2024-cpv2022-fixture",
    }
    policy["clocks"] = {
        "eph_period": "2024-Q3",
        "census_vintage": 2022,
        "sampling_target_year": 2024,
    }
    policy["evidence"] = {
        "codebook_pair": codebook_path.name,
        "person_codes": person_codes_path.name,
        "household_codes": household_codes_path.name,
    }

    original_codebook_path = (
        Path(__file__).parents[1]
        / "aligner"
        / "codebooks"
        / "real_2024q3_cpv2010_23.json"
    )
    codebook = json.loads(original_codebook_path.read_text(encoding="utf-8"))
    codebook["pair"] = dict(policy["parents"])
    codebook_path.write_text(json.dumps(codebook), encoding="utf-8")

    base = Path(__file__).parents[1] / "aligner" / "codebooks"
    person_codes_path.write_text(
        (base / "real_2024q3_cpv2010_person_codes.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    household_codes_path.write_text(
        (base / "real_2024q3_cpv2010_household_codes.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    policy_path.write_text(json.dumps(policy), encoding="utf-8")

    loaded = load_review_policy(policy_path)
    assert loaded["parents"]["census_frame_release_id"] == "arg-cpv2022-frame-fixture"
    assert loaded["clocks"]["census_vintage"] == 2022
    assert loaded["clocks"]["sampling_target_year"] == 2024


def test_eph_period_clock_is_executable_not_decorative() -> None:
    policy = load_review_policy()
    frame = pd.DataFrame({"ANO4": [2024, 2024], "TRIMESTRE": [3, 3]})
    _verify_eph_frame_period(frame, policy, role="fixture")

    bad = pd.DataFrame({"ANO4": [2024], "TRIMESTRE": [2]})
    with pytest.raises(Exception, match="eph_period_mismatch"):
        _verify_eph_frame_period(bad, policy, role="fixture")


def test_source_special_map_can_recode_without_turning_identity_into_closed_map() -> None:
    record = _record("P03")
    values, report = _transform_series(
        pd.Series([-1, 0, 1, 80]),
        record["eph"],
        record["validation"],
    )
    assert values.tolist() == [0, 0, 1, 80]
    assert report["expected_special_map"] == {"-1": 0}
    assert report["unmapped_codes"] == {}


def test_real_policy_carries_bounded_zero_sentinels_not_blanket_coercion() -> None:
    assert set(_record("P07")["census"]["special_to_null"]) == {0}
    assert set(_record("P09")["census"]["special_to_null"]) == {0}
    assert set(_record("P10")["census"]["special_to_null"]) == {0, 3}
    assert set(_record("CONDACT")["census"]["special_to_null"]) == {0}
    assert set(_record("H12")["census"]["special_to_null"]) == {0}
    assert set(_record("PROP")["census"]["special_to_null"]) == {0}
    assert set(_record("P07")["eph"]["special_to_null"]) == {0, 3}
    assert set(_record("P09")["eph"]["special_to_null"]) == {0, 99}
    assert set(_record("H12")["eph"]["special_to_null"]) == {0}


def test_final_real_policy_residuals_are_bounded_and_explicit() -> None:
    ix = _record("IX_TOT")
    assert ix["validation"] == {"kind": "integer", "min": 1}

    assert set(_record("P07")["eph"]["special_to_null"]) == {0, 3, 9}
    assert set(_record("P08")["eph"]["special_to_null"]) == {0, 9}
    assert set(_record("P10")["eph"]["special_to_null"]) == {0, 9}
    assert set(_record("H13")["eph"]["special_to_null"]) == {0, 4, 9}
    assert set(_record("H14")["eph"]["special_to_null"]) == {0, 9}
    assert set(_record("PROP")["eph"]["special_to_null"]) == {0}


def test_ix_tot_large_positive_counts_remain_canonical_not_clipped() -> None:
    record = _record("IX_TOT")
    values, report = _transform_series(
        pd.Series([1, 40, 43, 486]),
        record["census"],
        record["validation"],
    )
    assert values.tolist() == [1, 40, 43, 486]
    assert report["impossible_values"] == {}


def test_unreviewed_neighbor_codes_still_fail_closed() -> None:
    record = _record("P07")
    _, report = _transform_series(
        pd.Series([1, 2, 8, 9]),
        record["eph"],
        record["validation"],
    )
    assert report["unmapped_codes"] == {"8": 1}
    assert report["expected_special_to_null"] == ["0", "3", "9"]
