from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from aligner import longitudinal_composition as lc
from aligner.census_profile_hook import census_named_profile_frame
from aligner.composition_profiles import (
    CompositionProfileError,
    profile_feature_ids,
    profile_summary,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _policy() -> dict:
    rec = []

    def add(
        concept,
        field,
        *,
        mapping=None,
        special=None,
        special_map=None,
        validation=None,
        role="target-period-state",
    ):
        rec.append(
            {
                "concept": concept,
                "semantic_decision": "approve",
                "temporal_role": role,
                "eph": {
                    "field": field,
                    "map": mapping or {},
                    "special_to_null": special or [],
                    "special_map": special_map or {},
                },
                "census": {"field": concept, "map": {}, "special_to_null": []},
                "validation": validation or {},
            }
        )

    add("IX_TOT", "IX_TOT", validation={"kind": "integer", "min": 1})
    add("P02", "CH04", validation={"allowed": [1, 2]}, role="stable/shared")
    add(
        "P03",
        "CH06",
        special_map={-1: 0},
        validation={"kind": "integer", "min": 0, "max": 120},
    )
    add(
        "P05",
        "CH15",
        mapping={1: 1, 2: 1, 3: 1, 4: 2, 5: 2},
        special=[9],
        validation={"allowed": [1, 2]},
        role="stable/shared",
    )
    add(
        "P07",
        "CH09",
        mapping={1: 1, 2: 2},
        special=[0, 3, 9],
        validation={"allowed": [1, 2]},
    )
    add("P08", "CH10", special=[0, 9], validation={"allowed": [1, 2, 3]})
    add(
        "P09",
        "CH12",
        special=[0, 99],
        validation={"allowed": list(range(1, 10))},
    )
    add(
        "P10",
        "CH13",
        mapping={1: 1, 2: 2},
        special=[0, 9],
        validation={"allowed": [1, 2]},
    )
    add(
        "CONDACT",
        "ESTADO",
        mapping={1: 1, 2: 2, 3: 3},
        special=[0, 4],
        validation={"allowed": [1, 2, 3]},
    )
    add("V01", "IV1", validation={"allowed": [1, 2, 3, 4, 5, 6]}, role="research-only")
    add("H05", "IV3", validation={"allowed": [1, 2, 3, 4]}, role="research-only")
    for concept, field in [("H07", "IV5"), ("H10", "IV8")]:
        add(concept, field, validation={"allowed": [1, 2]}, role="research-only")
    add("H08", "IV6", validation={"allowed": [1, 2, 3]}, role="research-only")
    add("H09", "IV7", validation={"allowed": [1, 2, 3, 4]}, role="research-only")
    add("H12", "IV11", special=[0], validation={"allowed": [1, 2, 3, 4]}, role="research-only")
    add(
        "H13",
        "II9",
        mapping={1: 1, 2: 2, 3: 2},
        special=[0, 4, 9],
        validation={"allowed": [1, 2]},
        role="research-only",
    )
    add(
        "H14",
        "II8",
        mapping={1: 1, 2: 2, 3: 3, 4: 4},
        special=[0, 9],
        validation={"allowed": [1, 2, 3, 4]},
        role="research-only",
    )
    add(
        "H15",
        "II2",
        validation={"kind": "integer", "min": 0, "max": 30},
        role="research-only",
    )
    add(
        "PROP",
        "II7",
        mapping={1: 1, 2: 2, 3: 3, 4: 5, 5: 4, 6: 5, 7: 5, 8: 5, 9: 5},
        special=[0],
        validation={"allowed": [1, 2, 3, 4, 5]},
        role="research-only",
    )
    for concept, field in [("H06", "IV4"), ("H11", "IV10"), ("H16", "II1")]:
        rec.append(
            {
                "concept": concept,
                "semantic_decision": "needs-judgment",
                "temporal_role": "unresolved",
                "eph": {"field": field},
                "census": {"field": concept},
                "validation": {},
            }
        )
    return {"concepts": rec}


def _fixture(tmp_path: Path, *, bad_code=None, remove_support=None) -> Path:
    root = tmp_path / "c2"
    root.mkdir()
    person_fields = [
        "CH04", "CH06", "CH07", "CH09", "CH10", "CH12", "CH13", "CH15", "ESTADO"
    ]
    hh_fields = [
        "IX_TOT", "IV1", "IV3", "IV5", "IV6", "IV7", "IV8",
        "IV11", "II9", "II8", "II2", "II7",
    ]
    rows = []
    for period in lc.expected_periods():
        row = {
            "row_id": f"{period}|A|1|1",
            "household_observation_id": f"{period}|A|1",
            "panel_household_id": "A|1",
            "period": period,
            "region_id": "gran_buenos_aires",
            "source_release_id": f"eph-{period}",
            "source_row_identity": f"eph-{period}|A|1|1",
            "CH04": "1",
            "CH06": "30",
            "CH07": "2",
            "CH09": "1",
            "CH10": "1",
            "CH12": "4",
            "CH13": "1",
            "CH15": "1",
            "ESTADO": "1",
            "HH__IX_TOT": "2",
            "HH__IV1": "1",
            "HH__IV3": "1",
            "HH__IV5": "1",
            "HH__IV6": "1",
            "HH__IV7": "1",
            "HH__IV8": "1",
            "HH__IV11": "1",
            "HH__II9": "1",
            "HH__II8": "1",
            "HH__II2": "2",
            "HH__II7": "4",
            "P47T_real": "999",
        }
        if bad_code and period == bad_code[0]:
            row[bad_code[1]] = bad_code[2]
        rows.append(row)
    pd.DataFrame(rows).to_csv(root / "persons.csv", index=False)

    schema_rows = []
    current_p, current_h = set(), set()
    for i, period in enumerate(lc.expected_periods()):
        person = set(person_fields)
        household = set(hh_fields)
        if remove_support and period == remove_support[0]:
            (person if remove_support[1] == "person" else household).discard(remove_support[2])
        for role, fields, current in [
            ("person", person, current_p),
            ("household", household, current_h),
        ]:
            if i == 0:
                added, removed, drift = sorted(fields), [], "initial"
            else:
                added, removed = sorted(fields - current), sorted(current - fields)
                drift = "optional_column_set_change" if added or removed else "identical"
            schema_rows.append(
                {
                    "period": period,
                    "role": role,
                    "column_count": str(len(fields)),
                    "schema_fingerprint": f"{period}-{role}",
                    "drift_kind": drift,
                    "added_columns": ";".join(added),
                    "removed_columns": ";".join(removed),
                    "missing_required_columns": "",
                    "harmonization_action": "identity_preserve",
                }
            )
            if role == "person":
                current_p = set(fields)
            else:
                current_h = set(fields)
    pd.DataFrame(schema_rows).to_csv(root / "schema_inventory.csv", index=False)

    manifest = {
        "contract": lc.C2_CONTRACT,
        "release_id": "c2-fixture",
        "coverage": {
            "period_start": "2017-Q1",
            "period_end": "2026-Q1",
            "period_count": 37,
            "all_expected_periods_present": True,
        },
        "identity": {
            "row_id": "period|CODUSU|NRO_HOGAR|COMPONENTE",
            "household_observation_id": "period|CODUSU|NRO_HOGAR",
            "permanent_person_identity_claim": False,
        },
        "qa": {"persons": 37, "source_person_rows_accounted": True},
        "artifacts": {},
    }
    for name in ["persons.csv", "schema_inventory.csv"]:
        manifest["artifacts"][name] = {
            "sha256": _sha(root / name),
            "size_bytes": (root / name).stat().st_size,
        }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def _patch(monkeypatch):
    monkeypatch.setattr(lc, "load_review_policy", lambda path: _policy())
    monkeypatch.setattr(lc, "POLICY_PATH", lc.PROFILE_REGISTRY_PATH)


def _release(result: dict) -> Path:
    return Path(result["release_dir"])


def test_profiles_lock_p1r_minus_labor_and_unresolved():
    policy = _policy()
    fields = profile_feature_ids("P1R_NOLAB_LONG", policy)
    assert len(fields) == 19
    assert "CONDACT" not in fields
    assert not {"H06", "H11", "H16"} & set(fields)
    assert profile_summary("P1R_NOLAB_LONG", policy)["census_compatible"] is True
    p0 = profile_summary("P0_LONG", policy)
    assert p0["census_compatible"] is False
    assert p0["census_blocker"] == "profile_not_census_compatible:P0_LONG:CH07"


def test_registry_matches_repository_exact_review_policy_when_available():
    policy_path = (
        Path(__file__).resolve().parents[1]
        / "aligner"
        / "codebooks"
        / "real_2024q3_cpv2010_review_policy.json"
    )
    if not policy_path.is_file():
        pytest.skip("local isolated draft does not include the repository policy bundle")
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    fields = profile_feature_ids("P1R_NOLAB_LONG", policy)
    assert fields == [
        "IX_TOT", "P02", "P03", "P05", "P07", "P08", "P09", "P10",
        "V01", "H05", "H07", "H08", "H09", "H10", "H12", "H13",
        "H14", "H15", "PROP",
    ]
    assert not {"CONDACT", "H06", "H11", "H16"} & set(fields)


def test_materialize_preserves_c2_identity_and_reuses_recode(monkeypatch, tmp_path):
    _patch(monkeypatch)
    root = _fixture(tmp_path)
    result = lc.materialize_longitudinal_profile(
        root,
        tmp_path / "out",
        "P1R_NOLAB_LONG",
        policy_path=lc.PROFILE_REGISTRY_PATH,
        chunksize=7,
    )
    release = _release(result)
    parent = pd.read_csv(root / "persons.csv", dtype="string", keep_default_na=False)
    out = pd.read_csv(
        release / "composition_plane.csv", dtype="string", keep_default_na=False
    )
    support = pd.read_csv(
        release / "support_inventory.csv", dtype="string", keep_default_na=False
    )
    manifest = json.loads((release / "manifest.json").read_text())
    qa = json.loads((release / "qa.json").read_text())

    assert out[lc.IDENTITY_COLUMNS].equals(parent[lc.IDENTITY_COLUMNS])
    assert len(support) == 37 * 19
    assert out.loc[out["period"] == "2017-Q1", "PROP"].iloc[0] == "5"
    assert "CONDACT" not in out.columns
    assert "ESTADO" not in out.columns
    assert "P47T_real" not in out.columns
    assert qa["identity_sequence_preserved_exactly"] is True
    assert manifest["semantic_policy"]["longitudinal_2017_2026_approval_claimed"] is True
    assert manifest["coverage"]["real_longitudinal_support_approval"] == "pass_L3B"
    assert manifest["longitudinal_special_policy"]["sha256"]
    assert (release / "checksums.sha256").is_file()


def test_unknown_code_fails_closed(monkeypatch, tmp_path):
    _patch(monkeypatch)
    root = _fixture(tmp_path, bad_code=("2021-Q2", "CH09", "8"))
    with pytest.raises(
        lc.LongitudinalCompositionError, match=r"unexpected_code:2021-Q2:P07"
    ):
        lc.materialize_longitudinal_profile(
            root,
            tmp_path / "out",
            "P1R_NOLAB_LONG",
            policy_path=lc.PROFILE_REGISTRY_PATH,
            chunksize=5,
        )


def test_missing_period_source_support_fails_closed(monkeypatch, tmp_path):
    _patch(monkeypatch)
    root = _fixture(tmp_path, remove_support=("2020-Q3", "household", "IV5"))
    with pytest.raises(
        lc.LongitudinalCompositionError,
        match=r"profile_concept_unsupported_in_period:2020-Q3:IV5",
    ):
        lc.materialize_longitudinal_profile(
            root,
            tmp_path / "out",
            "P1R_NOLAB_LONG",
            policy_path=lc.PROFILE_REGISTRY_PATH,
        )


def test_longitudinal_specials_preserve_rows_and_null_features(monkeypatch, tmp_path):
    _patch(monkeypatch)
    root = _fixture(tmp_path, bad_code=("2019-Q4", "CH07", "9"))
    result = lc.materialize_longitudinal_profile(root, tmp_path / "out", "P0_LONG", policy_path=lc.PROFILE_REGISTRY_PATH)
    out = pd.read_csv(Path(result["release_dir"]) / "composition_plane.csv", dtype="string", keep_default_na=False)
    row = out.loc[out["period"] == "2019-Q4"].iloc[0]
    assert row["CH07"] == ""
    assert len(out) == 37


def test_p0_materializes_but_is_explicitly_not_census_compatible(
    monkeypatch, tmp_path
):
    _patch(monkeypatch)
    root = _fixture(tmp_path)
    result = lc.materialize_longitudinal_profile(
        root,
        tmp_path / "out",
        "P0_LONG",
        policy_path=lc.PROFILE_REGISTRY_PATH,
    )
    release = _release(result)
    out = pd.read_csv(
        release / "composition_plane.csv", dtype="string", keep_default_na=False
    )
    profile = json.loads((release / "profile.json").read_text())
    assert "CH07" in out.columns
    assert profile["summary"]["census_compatible"] is False
    assert profile["summary"]["census_blocker"] == "profile_not_census_compatible:P0_LONG:CH07"


def test_immutable_release_and_parent_hash_drift_fail(monkeypatch, tmp_path):
    _patch(monkeypatch)
    root = _fixture(tmp_path)
    out_root = tmp_path / "out"
    lc.materialize_longitudinal_profile(
        root,
        out_root,
        "P1R_NOLAB_LONG",
        policy_path=lc.PROFILE_REGISTRY_PATH,
    )
    with pytest.raises(lc.LongitudinalCompositionError, match="immutable_release_exists"):
        lc.materialize_longitudinal_profile(
            root,
            out_root,
            "P1R_NOLAB_LONG",
            policy_path=lc.PROFILE_REGISTRY_PATH,
        )
    (root / "persons.csv").write_text(
        (root / "persons.csv").read_text() + "\n", encoding="utf-8"
    )
    with pytest.raises(
        lc.LongitudinalCompositionError, match="c2_artifact_hash_mismatch:persons.csv"
    ):
        lc.materialize_longitudinal_profile(
            root,
            tmp_path / "out2",
            "P1R_NOLAB_LONG",
            policy_path=lc.PROFILE_REGISTRY_PATH,
        )


def test_census_hook_selects_same_p1r_profile_and_refuses_p0():
    policy = _policy()
    fields = profile_feature_ids("P1R_NOLAB_LONG", policy, side="census")
    source = pd.DataFrame({"row_id": ["r1"], "household_id": ["h1"]})
    transformed = {field: pd.Series([1]) for field in fields}
    frame = census_named_profile_frame(
        {"policy": policy, "census_frame": source, "transformed_census": transformed},
        "P1R_NOLAB_LONG",
    )
    assert list(frame.columns) == ["row_id", "household_id", *fields]
    with pytest.raises(
        CompositionProfileError, match="profile_not_census_compatible:P0_LONG:CH07"
    ):
        census_named_profile_frame(
            {"policy": policy, "census_frame": source, "transformed_census": transformed},
            "P0_LONG",
        )
