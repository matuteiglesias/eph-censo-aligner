from __future__ import annotations

import pandas as pd

from aligner.real_semantic_plane import (
    _review_row,
    _transform_series,
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
    p1s, p1r, unresolved, rejected = plane_fields(policy)
    assert p1s == ["P02", "P05"]
    assert len(p1r) == 20
    assert set(unresolved) == {"H06", "H11", "H16"}
    assert rejected == []
    assert "CONDACT" in p1r
    assert "CONDACT" not in p1s


def test_unknown_codes_fail_support_instead_of_silent_coercion() -> None:
    record = _record("P02")
    eph = pd.DataFrame({"CH04": [1], "row_id": ["e1"], "household_id": ["h1"]})
    census = pd.DataFrame({"P02": [1, 2], "row_id": ["c1", "c2"], "household_id": ["h1", "h2"]})
    review, _, _, support = _review_row(record, eph, census)
    assert review["semantic_decision"] == "approve"
    assert support["violations"] == [
        {
            "type": "census_canonical_category_absent_from_training",
            "concept": "P02",
            "detail": ["2"],
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
    assert report["unmapped_codes"] == {"7": 1}


def test_condact_is_semantically_approved_but_not_target_year_stable() -> None:
    record = _record("CONDACT")
    assert record["semantic_decision"] == "approve"
    assert record["temporal_role"] == "target-period-state"
    assert set(record["eph"]["special_to_null"]) == {0, 4}
    assert record["census"]["universe"] == "age 14+"
