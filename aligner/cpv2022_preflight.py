"""Fail-closed CPV-2022 semantic *diagnostic* on exact Census v2 sample releases.

Never imports the CPV-2010 executable policy; source names collide across
vintages. This output is an evidence/commissioning artifact, not an approved
EPH-to-Census welfare feature plane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import pandas as pd
import pyarrow.parquet as pq

from .real_semantic_plane import _sha256, _json

POLICY = (
    Path(__file__).parent / "codebooks" / "real_2024q3_cpv2022_candidate_review_v1.json"
)
CONTRACT = "research.cpv2022-diagnostic-features/v1"


class CPV2022DiagnosticError(ValueError):
    """The source-bound commissioning preflight cannot proceed."""


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise CPV2022DiagnosticError(reason)


def _verify_input(root: Path) -> tuple[dict, dict, dict, dict]:
    from .real_semantic_plane import _load_json

    m = _load_json(root / "manifest.json")
    qa = _load_json(root / "qa.json")
    policy = _load_json(POLICY)
    require(
        policy.get("contract") == "research.cpv2022-semantic-candidate-review/v1",
        "cpv2022_candidate_policy_contract_invalid",
    )
    entries = policy.get("candidates")
    require(
        isinstance(entries, list)
        and len(entries) == 23
        and len({c.get("legacy_concept") for c in entries}) == 23,
        "cpv2022_candidate_policy_incomplete",
    )
    for e in entries:
        require(
            e.get("transport_approved") is False,
            "cpv2022_diagnostic_cannot_authorize_transport",
        )
    require(
        m.get("contract") == "research.census-target-year-sample/v2",
        "unexpected_sample_contract",
    )
    require(m.get("materialization") == "full-payload", "full_payload_sample_required")
    frame = m.get("frame") or {}
    require(frame.get("census_vintage") == 2022, "cpv2022_vintage_required")
    coverage = frame.get("source_coverage") or {}
    require(
        coverage.get("coverage_is_partial") is True
        and coverage.get("contract") == "rpo11-frame-coverage/v1",
        "partial_rpo11_source_coverage_required",
    )
    use = m.get("scientific_use")
    require(
        use
        == {
            "classification": "commissioning_only",
            "publication_allowed": False,
            "reason": "partial_donor_universe_diagnostic",
        }
        and qa.get("scientific_use") == use,
        "nonpromotable_commissioning_classification_required",
    )
    require(
        qa.get("complete_household_membership") is True,
        "household_membership_not_validated",
    )
    weights = m.get("weight_semantics") or {}
    require(
        weights.get("analysis_weight") is None
        and weights.get("generic_sample_weight") is None,
        "unapproved_analysis_weight",
    )
    artifacts = m.get("artifacts") or {}
    for name in (
        "selection.parquet",
        "person_membership.parquet",
        "persona.parquet",
        "hogar.parquet",
        "vivienda.parquet",
        "qa.json",
    ):
        f = root / name
        rec = artifacts.get(name)
        require(
            isinstance(rec, dict) and f.is_file() and rec.get("sha256") == _sha256(f),
            "sample_artifact_missing_or_checksum_mismatch:" + name,
        )
    return m, qa, policy, coverage


def _read_source_tables(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    needed = {
        "selection": [
            "sample_household_id",
            "frame_household_id",
            "household_person_count",
        ],
        "person_membership": [
            "sample_person_id",
            "frame_person_id",
            "sample_household_id",
            "frame_household_id",
        ],
        "persona": [
            "frame_person_id",
            "frame_household_id",
            "P02",
            "P02__mask",
            "EDAD",
            "EDAD__mask",
        ],
    }
    try:
        tables = [
            pd.read_parquet(root / (name + ".parquet"), columns=columns)
            for name, columns in needed.items()
        ]
    except (KeyError, OSError, ValueError) as exc:
        raise CPV2022DiagnosticError("required_cpv2022_source_column_missing") from exc
    return tables[0], tables[1], tables[2]


def _materialize(
    selection: pd.DataFrame, membership: pd.DataFrame, persons: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    require(
        not any(t.empty for t in (selection, membership, persons)),
        "empty_diagnostic_universe",
    )
    for label, df, key in (
        ("household", selection, "frame_household_id"),
        ("membership", membership, "frame_person_id"),
        ("person", persons, "frame_person_id"),
    ):
        require(
            df[key].notna().all() and df[key].is_unique, "duplicate_or_null_" + label
        )
    require(
        selection["sample_household_id"].is_unique
        and membership["sample_person_id"].is_unique,
        "sample_identity_not_unique",
    )
    require(
        (selection["household_person_count"] > 0).all(),
        "invalid_household_person_count",
    )
    actual = membership.groupby("frame_household_id").size()
    expected = selection.set_index("frame_household_id")["household_person_count"]
    require(
        set(actual.index) == set(expected.index)
        and all(int(actual[k]) == int(expected[k]) for k in expected.index),
        "incomplete_household_person_membership",
    )
    merged = membership.merge(
        persons,
        on=["frame_person_id", "frame_household_id"],
        how="left",
        validate="one_to_one",
        indicator=True,
    )
    require(
        merged["_merge"].eq("both").all() and len(merged) == len(persons),
        "orphan_or_extra_person_record",
    )
    merged = merged.drop(columns="_merge").merge(
        selection[
            ["sample_household_id", "frame_household_id", "household_person_count"]
        ],
        on=["sample_household_id", "frame_household_id"],
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    require(merged["_merge"].eq("both").all(), "orphan_member_household")
    require(
        merged["P02__mask"].eq(0).all() and merged["EDAD__mask"].eq(0).all(),
        "nonzero_source_mask_requires_specific_review",
    )
    require(
        merged["P02"].notna().all() and merged["P02"].isin([1, 2]).all(),
        "unexpected_cpv2022_sex_at_birth_code",
    )
    age = pd.to_numeric(merged["EDAD"], errors="coerce")
    require(
        age.notna().all()
        and age.between(0, 110).all()
        and (age.astype(int) == age).all(),
        "invalid_cpv2022_age_at_census",
    )
    output = pd.DataFrame(
        {
            "sample_person_id": merged["sample_person_id"].astype(str),
            "sample_household_id": merged["sample_household_id"].astype(str),
            # Explicitly a diagnostic binary proxy. 2022 P02 = female1/male2;
            # EPH CH04 = male1/female2. These are NOT identical questionnaires.
            "sex_birth_eph_binary_proxy": merged["P02"]
            .map({1: 2, 2: 1})
            .astype("int8"),
            "age_on_2022_05_18": age.astype("int16"),
            "donor_household_size": merged["household_person_count"].astype("int32"),
        }
    )
    require(len(output) == len(persons), "person_count_not_preserved")
    diagnostics = {
        "person_rows": len(output),
        "household_rows": len(selection),
        "sex_birth_cpv2022_raw_counts": {
            str(k): int(v) for k, v in merged["P02"].value_counts().items()
        },
        "sex_birth_eph_proxy_counts": {
            str(k): int(v)
            for k, v in output["sex_birth_eph_binary_proxy"].value_counts().items()
        },
        "age_2022_min": int(age.min()),
        "age_2022_max": int(age.max()),
        "age_2022_mean": round(float(age.mean()), 4),
        "source_p02_mask_nonzero": 0,
        "source_edad_mask_nonzero": 0,
        "complete_person_household_membership": True,
    }
    return output, diagnostics


def _source_domain_profile(sample_release: Path, table: str, field: str) -> dict:
    """Private aggregated source evidence; no person/household IDs or raw rows."""
    root = sample_release / (table + ".parquet")
    available = set(pq.read_schema(root).names)
    if field not in available:
        return {"available": False}
    mask_field = field + "__mask"
    columns = [field] + ([mask_field] if mask_field in available else [])
    frame = pd.read_parquet(root, columns=columns)
    values = frame[field]
    frequency = values.value_counts(dropna=True)
    return {
        "available": True,
        "total_rows": int(len(values)),
        "null_count": int(values.isna().sum()),
        "distinct_observed_codes": int(len(frequency)),
        "top_20_code_counts": {str(k): int(v) for k, v in frequency.head(20).items()},
        "mask_field": mask_field if mask_field in available else None,
        "source_mask_counts": (
            {
                str(k): int(v)
                for k, v in frame[mask_field].value_counts(dropna=False).items()
            }
            if mask_field in available
            else None
        ),
        "semantic_equivalence_approved": False,
    }


def materialize_cpv2022_diagnostic(sample_release: Path, output_root: Path) -> Path:
    sample_release = Path(sample_release).expanduser().resolve()
    output_root = Path(output_root).expanduser().resolve()
    require(
        output_root != sample_release
        and not output_root.is_relative_to(sample_release),
        "output_inside_source_release_forbidden",
    )
    m, qa, policy, coverage = _verify_input(sample_release)
    selection, membership, persons = _read_source_tables(sample_release)
    plane, diagnostics = _materialize(selection, membership, persons)

    # Show observed source field availability, not retroactive semantic approvals.
    schema = {
        name: set(pq.read_schema(sample_release / (name + ".parquet")).names)
        for name in ("vivienda", "hogar", "persona")
    }
    evidence = []
    for c in policy["candidates"]:
        name = c["legacy_concept"]
        source_table = (
            "persona"
            if name in {"P02", "P03", "P05", "P07", "P08", "P09", "P10", "CONDACT"}
            else ("vivienda" if name == "V01" else "hogar")
        )
        sources = c["cpv2022_candidate_sources"]
        available = (
            [v for v in sources if v in schema[source_table]]
            if name != "IX_TOT"
            else ["person_membership"]
        )
        evidence.append(
            {
                **c,
                "cpv2022_observed_source_fields": available,
                "candidate_sources_missing": [v for v in sources if v not in available],
                "source_domains": {
                    field: _source_domain_profile(sample_release, source_table, field)
                    for field in sources
                },
                "mapping_executed": name in ("IX_TOT", "P02", "P03"),
            }
        )
    source_manifest_hash = _sha256(sample_release / "manifest.json")
    policy_hash = _sha256(POLICY)
    digest = hashlib.sha256(
        (source_manifest_hash + policy_hash + CONTRACT).encode()
    ).hexdigest()[:16]
    destination = output_root / ("cpv2022-diagnostic-features-" + digest)
    require(not destination.exists(), "immutable_diagnostic_release_exists")
    output_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".cpv2022-preflight-", dir=output_root))
    try:
        plane.to_parquet(
            staging / "person_diagnostic.parquet", compression="zstd", index=False
        )
        _json(
            staging / "qa.json",
            {
                "contract": "research.cpv2022-source-preflight/v1",
                "status": "diagnostic_pass",
                "scientific_use": "commissioning_only_no_inference_or_publication",
                "eph_2024q3_actual_source_status": "not_examined_by_this_census_only_preflight",
                "sample_frame_coverage": coverage,
                "observed_domains": diagnostics,
                "concept_inventory": evidence,
            },
        )
        artifacts = {}
        for f in ("person_diagnostic.parquet", "qa.json"):
            artifacts[f] = {
                "sha256": _sha256(staging / f),
                "size_bytes": (staging / f).stat().st_size,
            }
        _json(
            staging / "manifest.json",
            {
                "contract": CONTRACT,
                "release_id": destination.name,
                "scientific_use": {
                    "classification": "commissioning_only",
                    "publication_allowed": False,
                    "welfare_scoring_allowed": False,
                    "transport_approved": False,
                },
                "source": {
                    "census_sample_release_id": m["release_id"],
                    "census_sample_manifest_sha256": source_manifest_hash,
                    "frame_release_id": m["frame"]["frame_release_id"],
                    "source_coverage": coverage,
                },
                "policy_sha256": policy_hash,
                "source_definitions": policy["official_source_urls"],
                "diagnostic_concepts": ["IX_TOT", "P02", "P03"],
                "payload_schema": list(plane.columns),
                "artifacts": artifacts,
            },
        )
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m aligner.cpv2022_preflight")
    parser.add_argument("--census-sample-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = materialize_cpv2022_diagnostic(args.census_sample_root, args.output_root)
    print(
        json.dumps({"status": "diagnostic_pass", "output": str(result)}, sort_keys=True)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
