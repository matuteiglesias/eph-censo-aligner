"""CPV-2022 diagnostic source review: frozen vintage, provenance, safety gates."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from aligner.cpv2022_preflight import (
    CPV2022DiagnosticError,
    POLICY,
    materialize_cpv2022_diagnostic,
)
from aligner.real_semantic_plane import _sha256


def _make_sample(tmp_path: Path) -> Path:
    root = tmp_path / "sample"
    root.mkdir()
    tables = {
        "selection": pd.DataFrame(
            {
                "sample_household_id": ["s-hh1", "s-hh2"],
                "frame_household_id": ["f-hh1", "f-hh2"],
                "household_person_count": [2, 1],
            }
        ),
        "person_membership": pd.DataFrame(
            {
                "sample_person_id": ["s-p1", "s-p2", "s-p3"],
                "frame_person_id": ["f-p1", "f-p2", "f-p3"],
                "sample_household_id": ["s-hh1", "s-hh1", "s-hh2"],
                "frame_household_id": ["f-hh1", "f-hh1", "f-hh2"],
            }
        ),
        "persona": pd.DataFrame(
            {
                "frame_person_id": ["f-p1", "f-p2", "f-p3"],
                "frame_household_id": ["f-hh1", "f-hh1", "f-hh2"],
                "P02": [1, 2, 1],
                "P02__mask": [0, 0, 0],
                "EDAD": [0, 110, 32],
                "EDAD__mask": [0, 0, 0],
            }
        ),
        "hogar": pd.DataFrame(
            {
                "frame_household_id": ["f-hh1", "f-hh2"],
                "H10": [1, 2],
            }
        ),
        "vivienda": pd.DataFrame(
            {
                "frame_dwelling_id": ["f-v1", "f-v2"],
                "V01": [1, 2],
            }
        ),
    }
    artifacts = {}
    for name, frame in tables.items():
        frame.to_parquet(root / (name + ".parquet"), index=False)
        p = root / (name + ".parquet")
        artifacts[p.name] = {"sha256": _sha256(p)}
    qa = {
        "complete_household_membership": True,
        "scientific_use": {
            "classification": "commissioning_only",
            "publication_allowed": False,
            "reason": "partial_donor_universe_diagnostic",
        },
    }
    (root / "qa.json").write_text(json.dumps(qa) + "\n")
    artifacts["qa.json"] = {"sha256": _sha256(root / "qa.json")}
    manifest = {
        "contract": "research.census-target-year-sample/v2",
        "release_id": "census-sample-test",
        "materialization": "full-payload",
        "frame": {
            "frame_release_id": "2022-frame-test",
            "census_vintage": 2022,
            "source_coverage": {
                "contract": "rpo11-frame-coverage/v1",
                "coverage_is_partial": True,
                "attempted_radios": 2,
                "committed_radios": 1,
                "included_radios": ["061471101"],
                "needs_local_radios": ["061471102"],
            },
        },
        "scientific_use": qa["scientific_use"],
        "weight_semantics": {"analysis_weight": None, "generic_sample_weight": None},
        "artifacts": artifacts,
    }
    (root / "manifest.json").write_text(json.dumps(manifest) + "\n")
    return root


def _edit_sample(root: Path, name: str, func) -> None:
    m = json.loads((root / "manifest.json").read_text())
    path = root / name
    if name.endswith(".parquet"):
        data = pd.read_parquet(path)
        data = func(data)
        data.to_parquet(path, index=False)
    else:
        data = json.loads(path.read_text())
        func(data)
        path.write_text(json.dumps(data) + "\n")
    if name != "manifest.json":
        m["artifacts"][name]["sha256"] = _sha256(path)
        (root / "manifest.json").write_text(json.dumps(m) + "\n")


def test_vintage_specific_review_is_23_concepts_with_explicit_collision_guards() -> (
    None
):
    p = json.loads(POLICY.read_text())
    entries = {x["legacy_concept"]: x for x in p["candidates"]}
    assert len(entries) == 23
    assert all(x["transport_approved"] is False for x in entries.values())
    assert entries["P02"]["cpv2022_candidate_sources"] == ["P02"]
    assert entries["P03"]["cpv2022_candidate_sources"] == ["EDAD"]
    assert entries["H05"]["cpv2022_candidate_sources"] == ["H10"]
    assert entries["H14"]["cpv2022_candidate_sources"] == ["H19"]
    assert entries["H16"]["cpv2022_candidate_sources"] == ["H20"]
    assert all(
        entries[x]["qualification"] == "bounded_diagnostic_only"
        for x in ("P02", "P03", "IX_TOT")
    )
    assert all(
        entries[x]["qualification"] == "needs_scientific_review"
        for x in ("H10", "H13", "H14", "H16", "P07", "P08", "P09", "P10")
    )


def test_diagnostic_recode_and_membership_no_inference(tmp_path: Path) -> None:
    source = _make_sample(tmp_path)
    release = materialize_cpv2022_diagnostic(source, tmp_path / "diagnostics")
    manifest = json.loads((release / "manifest.json").read_text())
    qa = json.loads((release / "qa.json").read_text())
    assert manifest["contract"] == "research.cpv2022-diagnostic-features/v1"
    assert manifest["scientific_use"]["transport_approved"] is False
    assert manifest["scientific_use"]["publication_allowed"] is False
    assert manifest["source"]["source_coverage"]["coverage_is_partial"]
    data = pd.read_parquet(release / "person_diagnostic.parquet")
    assert list(data["sex_birth_eph_binary_proxy"]) == [2, 1, 2]
    assert list(data["age_on_2022_05_18"]) == [0, 110, 32]
    assert list(data["donor_household_size"]) == [2, 2, 1]
    assert "P03" not in data.columns
    assert len(data) == 3
    assert qa["observed_domains"]["person_rows"] == 3
    concepts = {row["legacy_concept"]: row for row in qa["concept_inventory"]}
    assert concepts["P02"]["source_domains"]["P02"]["top_20_code_counts"] == {
        "1": 2,
        "2": 1,
    }
    assert concepts["P03"]["source_domains"]["EDAD"]["null_count"] == 0
    assert concepts["H15"]["cpv2022_candidate_sources"] == []
    assert "person_diagnostic.parquet" in manifest["artifacts"]
    with pytest.raises(
        CPV2022DiagnosticError, match="immutable_diagnostic_release_exists"
    ):
        materialize_cpv2022_diagnostic(source, tmp_path / "diagnostics")


def test_fails_on_2010_frame_or_missing_commissioning(tmp_path: Path) -> None:
    source = _make_sample(tmp_path)
    _edit_sample(
        source, "manifest.json", lambda d: d["frame"].update({"census_vintage": 2010})
    )
    with pytest.raises(CPV2022DiagnosticError, match="cpv2022_vintage_required"):
        materialize_cpv2022_diagnostic(source, tmp_path / "out")
    _edit_sample(
        source, "manifest.json", lambda d: d["frame"].update({"census_vintage": 2022})
    )
    _edit_sample(source, "manifest.json", lambda d: d.pop("scientific_use"))
    with pytest.raises(CPV2022DiagnosticError, match="nonpromotable_commissioning"):
        materialize_cpv2022_diagnostic(source, tmp_path / "out")


def test_fails_on_corrupted_sample_artifact(tmp_path: Path) -> None:
    source = _make_sample(tmp_path)
    with (source / "persona.parquet").open("ab") as file:
        file.write(b"corrupt")
    with pytest.raises(
        CPV2022DiagnosticError, match="sample_artifact_missing_or_checksum_mismatch"
    ):
        materialize_cpv2022_diagnostic(source, tmp_path / "out")


def test_fails_on_household_membership_mismatch(tmp_path: Path) -> None:
    source = _make_sample(tmp_path)
    _edit_sample(
        source, "selection.parquet", lambda df: df.assign(household_person_count=[1, 1])
    )
    with pytest.raises(
        CPV2022DiagnosticError, match="incomplete_household_person_membership"
    ):
        materialize_cpv2022_diagnostic(source, tmp_path / "out")


def test_fails_on_unreviewed_masks_or_categories(tmp_path: Path) -> None:
    source = _make_sample(tmp_path)
    _edit_sample(source, "persona.parquet", lambda df: df.assign(P02__mask=[0, 1, 0]))
    with pytest.raises(CPV2022DiagnosticError, match="nonzero_source_mask"):
        materialize_cpv2022_diagnostic(source, tmp_path / "out")
    _edit_sample(
        source,
        "persona.parquet",
        lambda df: df.assign(P02__mask=[0, 0, 0], P02=[1, 3, 1]),
    )
    with pytest.raises(
        CPV2022DiagnosticError, match="unexpected_cpv2022_sex_at_birth_code"
    ):
        materialize_cpv2022_diagnostic(source, tmp_path / "out")


def test_refuses_writing_inside_original_release(tmp_path: Path) -> None:
    source = _make_sample(tmp_path)
    with pytest.raises(CPV2022DiagnosticError, match="output_inside_source_release"):
        materialize_cpv2022_diagnostic(source, source / "diagnostic")
