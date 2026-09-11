"""Executable real-data semantic review and canonical feature-plane materialization.

Pinned real pair:
- EPH: eph-2024-q3-3b6a7a15c4af
- Census: census-sample-2024-0839713eafea8d1b

Semantic approval and temporal admissibility remain separate. The module emits
one person-level canonical schema on both sides, but only approved concepts are
compiled into the plane. P1-S is the stable/shared subset; P1-R is the broader
approved research plane.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .codebook import load_real_codebook_pair

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "aligner" / "codebooks" / "real_2024q3_cpv2010_review_policy.json"
PERSON_CODES_PATH = ROOT / "aligner" / "codebooks" / "real_2024q3_cpv2010_person_codes.json"
HOUSEHOLD_CODES_PATH = ROOT / "aligner" / "codebooks" / "real_2024q3_cpv2010_household_codes.json"

EPH_RELEASE_ID = "eph-2024-q3-3b6a7a15c4af"
CENSUS_SAMPLE_ID = "census-sample-2024-0839713eafea8d1b"
CENSUS_FRAME_ID = "arg-cpv2010-frame-ee6ada167c2d6429"
CENSUS_CONTRACT = "research.census-target-year-sample/v2"

DECISIONS = {"approve", "needs-judgment", "reject"}
TEMPORAL_ROLES = {"stable/shared", "target-period-state", "research-only", "unresolved"}


class RealSemanticPlaneError(ValueError):
    """Raised when the exact real alignment cannot proceed truthfully."""


def _json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RealSemanticPlaneError(f"invalid_json:{path}") from exc
    if not isinstance(value, dict):
        raise RealSemanticPlaneError(f"json_object_required:{path}")
    return value


def load_review_policy() -> dict[str, Any]:
    value = _load_json(POLICY_PATH)
    if value.get("schema") != "research.eph-census-semantic-review-policy/v1":
        raise RealSemanticPlaneError("unexpected_review_policy_schema")
    parents = value.get("parents") or {}
    expected = {
        "eph_release_id": EPH_RELEASE_ID,
        "census_frame_release_id": CENSUS_FRAME_ID,
        "census_sample_release_id": CENSUS_SAMPLE_ID,
    }
    if parents != expected:
        raise RealSemanticPlaneError("review_policy_parent_identity_mismatch")
    concepts = value.get("concepts")
    if not isinstance(concepts, list) or len(concepts) != 23:
        raise RealSemanticPlaneError("review_policy_requires_exact_23_concepts")
    seen: set[str] = set()
    for row in concepts:
        concept = str(row.get("concept", ""))
        if not concept or concept in seen:
            raise RealSemanticPlaneError("review_policy_concept_duplicate_or_empty")
        seen.add(concept)
        if row.get("semantic_decision") not in DECISIONS:
            raise RealSemanticPlaneError(f"invalid_semantic_decision:{concept}")
        if row.get("temporal_role") not in TEMPORAL_ROLES:
            raise RealSemanticPlaneError(f"invalid_temporal_role:{concept}")
        for side in ("eph", "census"):
            spec = row.get(side)
            if not isinstance(spec, dict) or not spec.get("field"):
                raise RealSemanticPlaneError(f"review_policy_side_missing:{concept}:{side}")
    codebook_names = {row["concept"] for row in load_real_codebook_pair()["concepts"]}
    if seen != codebook_names:
        raise RealSemanticPlaneError("review_policy_codebook_surface_mismatch")
    return value


def _read_delimited(path: Path, *, delimiter: str, encoding: str) -> pd.DataFrame:
    try:
        return pd.read_csv(
            path,
            sep=delimiter,
            encoding=encoding,
            dtype="string",
            keep_default_na=False,
            na_values=[],
            low_memory=False,
        )
    except Exception as exc:
        raise RealSemanticPlaneError(f"source_table_read_failed:{path}") from exc


def _verify_eph_release(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    root = Path(root).expanduser().resolve()
    manifest = _load_json(root / "output-manifest.json")
    if manifest.get("release_id") != EPH_RELEASE_ID:
        raise RealSemanticPlaneError(
            f"unexpected_eph_release:{manifest.get('release_id')}!={EPH_RELEASE_ID}"
        )
    files = manifest.get("files")
    if not isinstance(files, list):
        raise RealSemanticPlaneError("eph_manifest_files_missing")
    by_role: dict[str, dict[str, Any]] = {}
    for record in files:
        role = record.get("role")
        if role in {"individual", "household"}:
            if role in by_role:
                raise RealSemanticPlaneError(f"multiple_eph_tables_for_role:{role}")
            by_role[role] = record
    if set(by_role) != {"individual", "household"}:
        raise RealSemanticPlaneError("eph_individual_household_tables_required")
    frames: dict[str, pd.DataFrame] = {}
    for role, record in by_role.items():
        path = root / str(record["file"])
        if not path.is_file():
            raise RealSemanticPlaneError(f"eph_table_missing:{role}:{path}")
        if _sha256(path) != record.get("sha256"):
            raise RealSemanticPlaneError(f"eph_table_hash_mismatch:{role}")
        frames[role] = _read_delimited(
            path,
            delimiter=str(record.get("delimiter") or ";"),
            encoding=str(record.get("encoding") or "utf-8"),
        )
    return frames["individual"], frames["household"], manifest


def _verify_census_release(
    root: Path,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], dict[str, Any]]:
    root = Path(root).expanduser().resolve()
    manifest = _load_json(root / "manifest.json")
    qa = _load_json(root / "qa.json")
    if manifest.get("contract") != CENSUS_CONTRACT:
        raise RealSemanticPlaneError("unexpected_census_contract")
    if manifest.get("release_id") != CENSUS_SAMPLE_ID:
        raise RealSemanticPlaneError(
            f"unexpected_census_release:{manifest.get('release_id')}!={CENSUS_SAMPLE_ID}"
        )
    frame = manifest.get("frame") or {}
    if frame.get("frame_release_id") != CENSUS_FRAME_ID:
        raise RealSemanticPlaneError("unexpected_census_frame_parent")
    if str(frame.get("census_vintage")) != "2010":
        raise RealSemanticPlaneError("unexpected_census_vintage")
    parent = manifest.get("target_population_parent") or {}
    if int(parent.get("target_year", -1)) != 2024:
        raise RealSemanticPlaneError("unexpected_census_target_year")
    if manifest.get("materialization") != "full-payload":
        raise RealSemanticPlaneError("census_full_payload_required")
    weights = manifest.get("weight_semantics") or {}
    if weights.get("analysis_weight") is not None or weights.get("generic_sample_weight") is not None:
        raise RealSemanticPlaneError("census_model_weight_must_be_unset")
    if qa.get("complete_household_membership") is not True:
        raise RealSemanticPlaneError("census_complete_household_membership_required")

    artifacts = manifest.get("artifacts") or {}
    required = (
        "selection.parquet",
        "person_membership.parquet",
        "persona.parquet",
        "hogar.parquet",
        "vivienda.parquet",
        "qa.json",
    )
    for name in required:
        record = artifacts.get(name)
        path = root / name
        if not isinstance(record, dict) or not path.is_file():
            raise RealSemanticPlaneError(f"census_artifact_missing:{name}")
        if _sha256(path) != record.get("sha256"):
            raise RealSemanticPlaneError(f"census_artifact_hash_mismatch:{name}")
    try:
        tables = {
            name.removesuffix(".parquet"): pd.read_parquet(root / name)
            for name in required
            if name.endswith(".parquet")
        }
    except Exception as exc:
        raise RealSemanticPlaneError(
            "census_parquet_read_failed:install_pyarrow_and_verify_payload"
        ) from exc
    return tables, manifest, qa


def _eph_person_frame(individual: pd.DataFrame, household: pd.DataFrame) -> pd.DataFrame:
    for name in ("CODUSU", "NRO_HOGAR", "COMPONENTE"):
        if name not in individual.columns:
            raise RealSemanticPlaneError(f"eph_identity_missing:{name}")
    for name in ("CODUSU", "NRO_HOGAR"):
        if name not in household.columns:
            raise RealSemanticPlaneError(f"eph_household_identity_missing:{name}")
    if household.duplicated(["CODUSU", "NRO_HOGAR"]).any():
        raise RealSemanticPlaneError("eph_household_identity_not_unique")
    joined = individual.merge(
        household,
        on=["CODUSU", "NRO_HOGAR"],
        how="left",
        suffixes=("", "__household"),
        validate="many_to_one",
        indicator=True,
    )
    if (joined["_merge"] != "both").any():
        raise RealSemanticPlaneError("eph_person_household_join_incomplete")
    joined = joined.drop(columns=["_merge"])
    joined["row_id"] = (
        joined["CODUSU"].astype(str)
        + ":"
        + joined["NRO_HOGAR"].astype(str)
        + ":"
        + joined["COMPONENTE"].astype(str)
    )
    joined["household_id"] = (
        joined["CODUSU"].astype(str) + ":" + joined["NRO_HOGAR"].astype(str)
    )
    if joined["row_id"].duplicated().any():
        raise RealSemanticPlaneError("eph_person_identity_not_unique")
    return joined


def _census_person_frame(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    membership = tables["person_membership"].copy()
    persona = tables["persona"].copy()
    hogar = tables["hogar"].copy()
    vivienda = tables["vivienda"].copy()
    required_membership = {
        "sample_person_id",
        "frame_person_id",
        "sample_household_id",
        "frame_household_id",
    }
    if not required_membership.issubset(membership.columns):
        raise RealSemanticPlaneError("census_membership_identity_columns_missing")
    if membership["sample_person_id"].astype(str).duplicated().any():
        raise RealSemanticPlaneError("census_sample_person_identity_not_unique")
    if persona["frame_person_id"].astype(str).duplicated().any():
        raise RealSemanticPlaneError("census_frame_person_identity_not_unique")
    if hogar["frame_household_id"].astype(str).duplicated().any():
        raise RealSemanticPlaneError("census_frame_household_identity_not_unique")
    if vivienda["frame_dwelling_id"].astype(str).duplicated().any():
        raise RealSemanticPlaneError("census_frame_dwelling_identity_not_unique")

    person = membership.merge(
        persona,
        on=["frame_person_id", "frame_household_id"],
        how="left",
        validate="one_to_one",
        indicator="_persona_merge",
    )
    if (person["_persona_merge"] != "both").any():
        raise RealSemanticPlaneError("census_membership_persona_join_incomplete")
    person = person.drop(columns=["_persona_merge"])
    person = person.merge(
        hogar,
        on="frame_household_id",
        how="left",
        validate="many_to_one",
        suffixes=("", "__hogar"),
        indicator="_hogar_merge",
    )
    if (person["_hogar_merge"] != "both").any():
        raise RealSemanticPlaneError("census_person_hogar_join_incomplete")
    person = person.drop(columns=["_hogar_merge"])
    if "frame_dwelling_id" not in person.columns:
        raise RealSemanticPlaneError("census_frame_dwelling_id_missing_after_hogar_join")
    person = person.merge(
        vivienda,
        on="frame_dwelling_id",
        how="left",
        validate="many_to_one",
        suffixes=("", "__vivienda"),
        indicator="_vivienda_merge",
    )
    if (person["_vivienda_merge"] != "both").any():
        raise RealSemanticPlaneError("census_person_vivienda_join_incomplete")
    person = person.drop(columns=["_vivienda_merge"])
    counts = membership.groupby("sample_household_id", sort=False).size()
    person["membership_count"] = person["sample_household_id"].map(counts)
    if person["membership_count"].isna().any():
        raise RealSemanticPlaneError("census_membership_count_missing")
    person["row_id"] = person["sample_person_id"].astype(str)
    person["household_id"] = person["sample_household_id"].astype(str)
    return person


def _norm_code(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        number = float(text)
        if np.isfinite(number) and number.is_integer():
            return str(int(number))
    except ValueError:
        pass
    return text


def _observed_support(series: pd.Series) -> list[str]:
    values = {_norm_code(value) for value in series.tolist()}
    values.discard(None)
    return sorted(values, key=lambda value: (not value.lstrip("-").isdigit(), value))


def _code_meanings(concept: str, side: str) -> dict[str, Any]:
    for path in (PERSON_CODES_PATH, HOUSEHOLD_CODES_PATH):
        value = _load_json(path)
        record = (value.get("concepts") or {}).get(concept)
        if isinstance(record, dict):
            side_value = record.get(side)
            if isinstance(side_value, dict):
                return side_value
    for record in load_real_codebook_pair()["concepts"]:
        if record["concept"] == concept:
            source = record[side]
            return {
                "field": source.get("field"),
                "label": source.get("label"),
                "type": source.get("type"),
            }
    return {}


def _series_for(frame: pd.DataFrame, field: str, concept: str, side: str) -> pd.Series:
    if field not in frame.columns:
        raise RealSemanticPlaneError(f"raw_source_missing:{concept}:{side}:{field}")
    return frame[field]


def _transform_series(
    series: pd.Series,
    spec: dict[str, Any],
    validation: dict[str, Any],
) -> tuple[pd.Series, dict[str, Any]]:
    raw_support = _observed_support(series)
    mapping = {str(key): value for key, value in (spec.get("map") or {}).items()}
    special = {str(value) for value in spec.get("special_to_null", [])}
    transformed: list[Any] = []
    unmapped: Counter[str] = Counter()
    impossible: Counter[str] = Counter()
    for value in series.tolist():
        code = _norm_code(value)
        if code is None or code in special:
            transformed.append(np.nan)
            continue
        if mapping:
            if code not in mapping:
                unmapped[code] += 1
                transformed.append(np.nan)
                continue
            out = mapping[code]
        else:
            try:
                out = int(code) if "." not in code else float(code)
            except ValueError:
                out = code
        allowed = validation.get("allowed")
        if allowed is not None and out not in allowed:
            impossible[str(out)] += 1
        if validation.get("kind") == "integer":
            try:
                number = float(out)
                if not number.is_integer():
                    impossible[str(out)] += 1
                low = validation.get("min")
                high = validation.get("max")
                if low is not None and number < low:
                    impossible[str(out)] += 1
                if high is not None and number > high:
                    impossible[str(out)] += 1
                out = int(number) if number.is_integer() else number
            except (TypeError, ValueError):
                impossible[str(out)] += 1
        transformed.append(out)
    output = pd.Series(transformed, index=series.index)
    return output, {
        "raw_support": raw_support,
        "canonical_support": _observed_support(output),
        "unmapped_codes": dict(sorted(unmapped.items())),
        "impossible_values": dict(sorted(impossible.items())),
        "expected_special_to_null": sorted(special),
        "null_count": int(output.isna().sum()),
    }


def _review_row(
    record: dict[str, Any],
    eph: pd.DataFrame,
    census: pd.DataFrame,
) -> tuple[dict[str, Any], pd.Series, pd.Series, dict[str, Any]]:
    concept = record["concept"]
    eph_spec = dict(record["eph"])
    census_spec = dict(record["census"])
    validation = record.get("validation") or {}
    eph_raw = _series_for(eph, str(eph_spec["field"]), concept, "eph")
    census_raw = _series_for(census, str(census_spec["field"]), concept, "census")
    eph_out, eph_report = _transform_series(eph_raw, eph_spec, validation)
    census_out, census_report = _transform_series(census_raw, census_spec, validation)

    violations: list[dict[str, Any]] = []
    if eph_report["unmapped_codes"]:
        violations.append({"type": "unexpected_eph_code", "concept": concept, "detail": eph_report["unmapped_codes"]})
    if census_report["unmapped_codes"]:
        violations.append({"type": "unexpected_census_code", "concept": concept, "detail": census_report["unmapped_codes"]})
    if eph_report["impossible_values"]:
        violations.append({"type": "impossible_eph_value", "concept": concept, "detail": eph_report["impossible_values"]})
    if census_report["impossible_values"]:
        violations.append({"type": "impossible_census_value", "concept": concept, "detail": census_report["impossible_values"]})
    eph_support = set(eph_report["canonical_support"])
    census_support = set(census_report["canonical_support"])
    census_only = sorted(census_support - eph_support)
    if record["semantic_decision"] == "approve" and census_only:
        violations.append({
            "type": "census_canonical_category_absent_from_training",
            "concept": concept,
            "detail": census_only,
        })

    review = {
        "canonical_concept_id": concept,
        "eph_raw_source": eph_spec["field"],
        "census_raw_source": census_spec["field"],
        "eph_universe": eph_spec.get("universe"),
        "census_universe": census_spec.get("universe"),
        "eph_code_meanings": _code_meanings(concept, "eph"),
        "census_code_meanings": _code_meanings(concept, "census"),
        "observed_eph_support": eph_report["raw_support"],
        "observed_census_support": census_report["raw_support"],
        "proposed_common_representation": record.get("common_representation"),
        "information_lost_eph": (record.get("information_loss") or {}).get("eph"),
        "information_lost_census": (record.get("information_loss") or {}).get("census"),
        "semantic_decision": record["semantic_decision"],
        "temporal_role": record["temporal_role"],
        "reviewer_reason": record.get("reviewer_reason"),
        "canonical_eph_support": eph_report["canonical_support"],
        "canonical_census_support": census_report["canonical_support"],
    }
    support = {
        "concept": concept,
        "eph": eph_report,
        "census": census_report,
        "violations": violations,
    }
    return review, eph_out, census_out, support


def build_real_review(eph_release_root: Path, census_sample_root: Path) -> dict[str, Any]:
    policy = load_review_policy()
    individual, household, eph_manifest = _verify_eph_release(eph_release_root)
    census_tables, census_manifest, census_qa = _verify_census_release(census_sample_root)
    eph = _eph_person_frame(individual, household)
    census = _census_person_frame(census_tables)

    rows: list[dict[str, Any]] = []
    supports: list[dict[str, Any]] = []
    transformed_eph: dict[str, pd.Series] = {}
    transformed_census: dict[str, pd.Series] = {}
    for record in policy["concepts"]:
        row, eph_out, census_out, support = _review_row(record, eph, census)
        rows.append(row)
        supports.append(support)
        transformed_eph[record["concept"]] = eph_out
        transformed_census[record["concept"]] = census_out

    return {
        "policy": policy,
        "review_rows": rows,
        "support_rows": supports,
        "eph_frame": eph,
        "census_frame": census,
        "transformed_eph": transformed_eph,
        "transformed_census": transformed_census,
        "eph_manifest": eph_manifest,
        "census_manifest": census_manifest,
        "census_qa": census_qa,
    }


def plane_fields(policy: dict[str, Any]) -> tuple[list[str], list[str], list[str], list[str]]:
    p1s = [
        row["concept"]
        for row in policy["concepts"]
        if row["semantic_decision"] == "approve" and row["temporal_role"] == "stable/shared"
    ]
    p1r = [
        row["concept"]
        for row in policy["concepts"]
        if row["semantic_decision"] == "approve"
        and row["temporal_role"] in {"stable/shared", "target-period-state", "research-only"}
    ]
    unresolved = [row["concept"] for row in policy["concepts"] if row["semantic_decision"] == "needs-judgment"]
    rejected = [row["concept"] for row in policy["concepts"] if row["semantic_decision"] == "reject"]
    return p1s, p1r, unresolved, rejected


def _canonical_frame(
    source: pd.DataFrame,
    transformed: dict[str, pd.Series],
    fields: list[str],
) -> pd.DataFrame:
    data: dict[str, Any] = {
        "row_id": source["row_id"].astype(str).to_numpy(),
        "household_id": source["household_id"].astype(str).to_numpy(),
    }
    for field in fields:
        data[field] = transformed[field].to_numpy()
    return pd.DataFrame(data, columns=["row_id", "household_id", *fields])


def _support_payload(result: dict[str, Any]) -> dict[str, Any]:
    _, p1r, _, _ = plane_fields(result["policy"])
    approved = set(p1r)
    violations = [
        violation
        for support in result["support_rows"]
        for violation in support["violations"]
        if support["concept"] in approved
    ]
    return {
        "schema": "research.eph-census-feature-plane-support/v1",
        "release_id": result["policy"]["release_id"],
        "status": "fail" if violations else "pass",
        "eph_rows": len(result["eph_frame"]),
        "census_rows": len(result["census_frame"]),
        "concepts": result["support_rows"],
        "violations": violations,
    }


def write_real_review(
    eph_release_root: Path,
    census_sample_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    result = build_real_review(eph_release_root, census_sample_root)
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    review_path = output_dir / "semantic_review_matrix.json"
    support_path = output_dir / "support_report.json"
    _json(review_path, {
        "schema": "research.eph-census-semantic-review-matrix/v1",
        "release_id": result["policy"]["release_id"],
        "parents": result["policy"]["parents"],
        "rows": result["review_rows"],
    })
    support = _support_payload(result)
    _json(support_path, support)
    return {
        "release_id": result["policy"]["release_id"],
        "review_matrix": str(review_path),
        "support_report": str(support_path),
        "support_status": support["status"],
        "violations": support["violations"],
    }


def materialize_real_plane(
    eph_release_root: Path,
    census_sample_root: Path,
    output_dir: Path,
) -> dict[str, Any]:
    result = build_real_review(eph_release_root, census_sample_root)
    policy = result["policy"]
    p1s, p1r, unresolved, rejected = plane_fields(policy)
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    review_path = output_dir / "semantic_review_matrix.json"
    support_path = output_dir / "support_report.json"
    manifest_path = output_dir / "feature_plane_manifest.json"
    eph_path = output_dir / "eph_p1.parquet"
    census_path = output_dir / "census_p1.parquet"

    _json(review_path, {
        "schema": "research.eph-census-semantic-review-matrix/v1",
        "release_id": policy["release_id"],
        "parents": policy["parents"],
        "rows": result["review_rows"],
    })
    support = _support_payload(result)
    _json(support_path, support)
    if support["violations"]:
        raise RealSemanticPlaneError(
            "support_gate_failed:"
            + ",".join(
                f"{violation['type']}:{violation['concept']}"
                for violation in support["violations"][:20]
            )
        )

    eph_plane = _canonical_frame(result["eph_frame"], result["transformed_eph"], p1r)
    census_plane = _canonical_frame(result["census_frame"], result["transformed_census"], p1r)
    if tuple(eph_plane.columns) != tuple(census_plane.columns):
        support["status"] = "fail"
        support["violations"].append({
            "type": "schema_disagreement",
            "eph_columns": list(eph_plane.columns),
            "census_columns": list(census_plane.columns),
        })
        _json(support_path, support)
        raise RealSemanticPlaneError("canonical_plane_schema_disagreement")

    try:
        eph_plane.to_parquet(eph_path, index=False)
        census_plane.to_parquet(census_path, index=False)
    except Exception as exc:
        raise RealSemanticPlaneError("canonical_parquet_write_failed:install_pyarrow") from exc

    manifest = {
        "schema": "research.eph-census-semantic-feature-plane/v1",
        "release_id": policy["release_id"],
        "status": "candidate_for_encuestador_eph_adjudication",
        "parents": policy["parents"],
        "canonical_schema": list(eph_plane.columns),
        "p1_s_fields": p1s,
        "p1_r_fields": p1r,
        "rejected_fields": rejected,
        "unresolved_fields": unresolved,
        "transformations": {
            "eph_raw_to_canonical_plane": {
                "source_release": EPH_RELEASE_ID,
                "policy": POLICY_PATH.name,
                "matrix": eph_path.name,
                "rows": len(eph_plane),
                "columns": len(eph_plane.columns),
                "sha256": _sha256(eph_path),
            },
            "cpv_raw_to_canonical_plane": {
                "source_release": CENSUS_SAMPLE_ID,
                "frame_parent": CENSUS_FRAME_ID,
                "policy": POLICY_PATH.name,
                "matrix": census_path.name,
                "rows": len(census_plane),
                "columns": len(census_plane.columns),
                "sha256": _sha256(census_path),
            },
        },
        "review_matrix": {
            "path": review_path.name,
            "sha256": _sha256(review_path),
            "row_count": 23,
        },
        "support_report": {
            "path": support_path.name,
            "sha256": _sha256(support_path),
            "status": "pass",
        },
        "encuestador_contract": {
            "identity_columns": ["row_id", "household_id"],
            "weighting": "none",
            "terminal_formulation": "hurdle_gamma",
            "required_outer_grouping": "household_id",
            "planes": {"P1-S": p1s, "P1-R": p1r},
            "census_scoring_authorized": False,
            "reason": "Run and adjudicate EPH P0 vs P1-S vs P1-R first.",
        },
    }
    _json(manifest_path, manifest)
    return manifest
