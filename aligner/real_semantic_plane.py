"""Policy-driven real-data semantic review and canonical feature-plane materialization.

Each reviewed policy pins its exact EPH release, Census donor frame/sample,
donor vintage, sampling target year and codebook evidence. Reusable compiler
logic is donor-vintage neutral: CPV-2010 and CPV-2022 are policy instances, not
separate pipelines.

Semantic approval and temporal admissibility remain separate. P1-S is the
stable/shared subset; P1-R is the broader approved research plane.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .codebook import load_codebook_pair

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "aligner" / "codebooks" / "real_2024q3_cpv2010_review_policy.json"
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


def _evidence_paths(policy: dict[str, Any], policy_path: Path) -> dict[str, Path]:
    evidence = policy.get("evidence")
    if not isinstance(evidence, dict):
        raise RealSemanticPlaneError("review_policy_evidence_missing")
    out: dict[str, Path] = {}
    for key in ("codebook_pair", "person_codes", "household_codes"):
        value = evidence.get(key)
        if not isinstance(value, str) or not value:
            raise RealSemanticPlaneError(f"review_policy_evidence_missing:{key}")
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = policy_path.parent / candidate
        out[key] = candidate.resolve()
    return out


def load_review_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    path = Path(path).expanduser().resolve()
    value = _load_json(path)
    if value.get("schema") != "research.eph-census-semantic-review-policy/v1":
        raise RealSemanticPlaneError("unexpected_review_policy_schema")

    parents = value.get("parents")
    if not isinstance(parents, dict):
        raise RealSemanticPlaneError("review_policy_parents_missing")
    for key in ("eph_release_id", "census_frame_release_id", "census_sample_release_id"):
        if not isinstance(parents.get(key), str) or not parents[key]:
            raise RealSemanticPlaneError(f"review_policy_parent_identity_missing:{key}")

    clocks = value.get("clocks")
    if not isinstance(clocks, dict):
        raise RealSemanticPlaneError("review_policy_clocks_missing")
    if not isinstance(clocks.get("eph_period"), str) or not clocks["eph_period"]:
        raise RealSemanticPlaneError("review_policy_eph_period_missing")
    if clocks.get("census_vintage") not in {2010, 2022}:
        raise RealSemanticPlaneError("review_policy_census_vintage_invalid")
    try:
        target_year = int(clocks.get("sampling_target_year"))
    except (TypeError, ValueError) as exc:
        raise RealSemanticPlaneError("review_policy_sampling_target_year_invalid") from exc
    if target_year < 2000:
        raise RealSemanticPlaneError("review_policy_sampling_target_year_invalid")

    contracts = value.get("contracts")
    if not isinstance(contracts, dict) or not contracts.get("census_sample"):
        raise RealSemanticPlaneError("review_policy_census_contract_missing")

    concepts = value.get("concepts")
    if not isinstance(concepts, list) or not concepts:
        raise RealSemanticPlaneError("review_policy_concepts_missing")
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

    donor_labor = value.get("donor_labor_handoff")
    if donor_labor is not None:
        if not isinstance(donor_labor, dict):
            raise RealSemanticPlaneError("review_policy_donor_labor_handoff_invalid")
        required = {
            "schema": "research.eph-census-donor-labor-handoff-policy/v1",
            "concept": "CONDACT",
            "source_side": "census",
            "source_field": "CONDACT",
            "value_field": "donor_condact",
            "vintage_field": "donor_condact_vintage",
            "semantic_status_field": "donor_condact_semantic_status",
            "vintage_clock": "census_vintage",
            "eph_training_analogue": "not_materialized_here",
            "target_period_current_state_claimed": False,
        }
        for key, expected in required.items():
            if donor_labor.get(key) != expected:
                raise RealSemanticPlaneError(
                    f"review_policy_donor_labor_handoff_invalid:{key}"
                )
        if donor_labor.get("age_field") != "P03":
            raise RealSemanticPlaneError("review_policy_donor_labor_age_field_invalid")
        try:
            minimum_age = int(donor_labor.get("minimum_age"))
        except (TypeError, ValueError) as exc:
            raise RealSemanticPlaneError(
                "review_policy_donor_labor_minimum_age_invalid"
            ) from exc
        if minimum_age < 0:
            raise RealSemanticPlaneError("review_policy_donor_labor_minimum_age_invalid")
        condact = next(
            (row for row in concepts if row.get("concept") == donor_labor["concept"]),
            None,
        )
        if condact is None or condact.get("semantic_decision") != "approve":
            raise RealSemanticPlaneError("review_policy_donor_labor_concept_not_approved")
        clock_semantics = condact.get("clock_semantics") or {}
        if (
            clock_semantics.get("eph") != "observed_at_eph_period"
            or clock_semantics.get("census") != "observed_at_census_donor_vintage"
            or clock_semantics.get(
                "shared_category_semantics_do_not_equal_shared_observation_clock"
            )
            is not True
        ):
            raise RealSemanticPlaneError("review_policy_donor_labor_clock_semantics_missing")

    paths = _evidence_paths(value, path)
    codebook = load_codebook_pair(paths["codebook_pair"], expected_concepts=seen)
    if codebook.get("pair") != parents:
        raise RealSemanticPlaneError("review_policy_codebook_parent_identity_mismatch")
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


def _expected_eph_year_quarter(policy: dict[str, Any]) -> tuple[int, int]:
    period = str(policy["clocks"]["eph_period"])
    try:
        year_text, quarter_text = period.split("-Q", 1)
        year = int(year_text)
        quarter = int(quarter_text)
    except (ValueError, TypeError) as exc:
        raise RealSemanticPlaneError("review_policy_eph_period_invalid") from exc
    if year < 2000 or quarter not in {1, 2, 3, 4}:
        raise RealSemanticPlaneError("review_policy_eph_period_invalid")
    return year, quarter


def _verify_eph_frame_period(
    frame: pd.DataFrame, policy: dict[str, Any], *, role: str
) -> None:
    for column in ("ANO4", "TRIMESTRE"):
        if column not in frame.columns:
            raise RealSemanticPlaneError(f"eph_period_column_missing:{role}:{column}")
    expected_year, expected_quarter = _expected_eph_year_quarter(policy)
    years = {
        int(value)
        for value in pd.to_numeric(frame["ANO4"], errors="raise").dropna().unique()
    }
    quarters = {
        int(value)
        for value in pd.to_numeric(frame["TRIMESTRE"], errors="raise").dropna().unique()
    }
    if years != {expected_year} or quarters != {expected_quarter}:
        raise RealSemanticPlaneError(
            f"eph_period_mismatch:{role}:observed_years={sorted(years)}:"
            f"observed_quarters={sorted(quarters)}:expected={expected_year}-Q{expected_quarter}"
        )


def _verify_eph_release(
    root: Path, policy: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    root = Path(root).expanduser().resolve()
    manifest = _load_json(root / "output-manifest.json")
    expected_release = policy["parents"]["eph_release_id"]
    if manifest.get("release_id") != expected_release:
        raise RealSemanticPlaneError(
            f"unexpected_eph_release:{manifest.get('release_id')}!={expected_release}"
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
    _verify_eph_frame_period(frames["individual"], policy, role="individual")
    _verify_eph_frame_period(frames["household"], policy, role="household")
    return frames["individual"], frames["household"], manifest


def _verify_census_release(
    root: Path, policy: dict[str, Any]
) -> tuple[dict[str, pd.DataFrame], dict[str, Any], dict[str, Any]]:
    root = Path(root).expanduser().resolve()
    manifest = _load_json(root / "manifest.json")
    qa = _load_json(root / "qa.json")
    expected_contract = policy["contracts"]["census_sample"]
    if manifest.get("contract") != expected_contract:
        raise RealSemanticPlaneError("unexpected_census_contract")
    expected_sample = policy["parents"]["census_sample_release_id"]
    if manifest.get("release_id") != expected_sample:
        raise RealSemanticPlaneError(
            f"unexpected_census_release:{manifest.get('release_id')}!={expected_sample}"
        )
    frame = manifest.get("frame") or {}
    expected_frame = policy["parents"]["census_frame_release_id"]
    if frame.get("frame_release_id") != expected_frame:
        raise RealSemanticPlaneError("unexpected_census_frame_parent")
    expected_vintage = int(policy["clocks"]["census_vintage"])
    if int(frame.get("census_vintage", -1)) != expected_vintage:
        raise RealSemanticPlaneError("unexpected_census_vintage")
    parent = manifest.get("target_population_parent") or {}
    expected_target_year = int(policy["clocks"]["sampling_target_year"])
    if int(parent.get("target_year", -1)) != expected_target_year:
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


def _load_policy_evidence(
    policy: dict[str, Any], policy_path: Path
) -> dict[str, Any]:
    paths = _evidence_paths(policy, Path(policy_path).expanduser().resolve())
    expected = {row["concept"] for row in policy["concepts"]}
    return {
        "paths": paths,
        "codebook_pair": load_codebook_pair(
            paths["codebook_pair"], expected_concepts=expected
        ),
        "supplemental_codes": [
            _load_json(paths["person_codes"]),
            _load_json(paths["household_codes"]),
        ],
    }


def _code_meanings(
    concept: str, side: str, evidence: dict[str, Any]
) -> dict[str, Any]:
    for value in evidence["supplemental_codes"]:
        record = (value.get("concepts") or {}).get(concept)
        if isinstance(record, dict):
            side_value = record.get(side)
            if isinstance(side_value, dict):
                return side_value
    for record in evidence["codebook_pair"]["concepts"]:
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
    special_map = {
        str(key): value for key, value in (spec.get("special_map") or {}).items()
    }
    special = {str(value) for value in spec.get("special_to_null", [])}
    transformed: list[Any] = []
    unmapped: Counter[str] = Counter()
    impossible: Counter[str] = Counter()
    for value in series.tolist():
        code = _norm_code(value)
        if code is None or code in special:
            transformed.append(np.nan)
            continue
        if code in special_map:
            out = special_map[code]
        elif mapping:
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
        "expected_special_map": dict(sorted(special_map.items())),
        "null_count": int(output.isna().sum()),
    }


def _review_row(
    record: dict[str, Any],
    eph: pd.DataFrame,
    census: pd.DataFrame,
    *,
    evidence: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], pd.Series, pd.Series, dict[str, Any]]:
    if evidence is None:
        default_policy = load_review_policy(POLICY_PATH)
        evidence = _load_policy_evidence(default_policy, POLICY_PATH)
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
    diagnostics: list[dict[str, Any]] = []
    if record["semantic_decision"] == "approve" and census_only:
        diagnostics.append({
            "type": "census_canonical_category_absent_from_training",
            "concept": concept,
            "detail": census_only,
            "interpretation": "statistical_support_not_semantic_incompatibility",
        })

    review = {
        "canonical_concept_id": concept,
        "eph_raw_source": eph_spec["field"],
        "census_raw_source": census_spec["field"],
        "eph_universe": eph_spec.get("universe"),
        "census_universe": census_spec.get("universe"),
        "eph_code_meanings": _code_meanings(concept, "eph", evidence),
        "census_code_meanings": _code_meanings(concept, "census", evidence),
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
        "diagnostics": diagnostics,
    }
    return review, eph_out, census_out, support


def _value_counts(series: pd.Series) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for value in series.tolist():
        code = _norm_code(value)
        counts["<missing>" if code is None else code] += 1
    return dict(sorted(counts.items()))


def _donor_labor_handoff(
    result: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    policy = result["policy"]
    handoff_policy = policy.get("donor_labor_handoff")
    if not isinstance(handoff_policy, dict):
        raise RealSemanticPlaneError("donor_labor_handoff_policy_required")

    concept = handoff_policy["concept"]
    census = result["census_frame"]
    transformed = result["transformed_census"].get(concept)
    if transformed is None:
        raise RealSemanticPlaneError("donor_labor_transformed_concept_missing")
    support = next(
        (row for row in result["support_rows"] if row.get("concept") == concept),
        None,
    )
    if support is None:
        raise RealSemanticPlaneError("donor_labor_support_report_missing")

    identity_columns = [
        "row_id",
        "household_id",
        "sample_person_id",
        "sample_household_id",
        "frame_person_id",
        "frame_household_id",
        "frame_dwelling_id",
    ]
    missing_identity = [column for column in identity_columns if column not in census.columns]
    if missing_identity:
        raise RealSemanticPlaneError(
            "donor_labor_identity_columns_missing:" + ",".join(missing_identity)
        )
    if len(census) != len(transformed):
        raise RealSemanticPlaneError("donor_labor_row_count_mismatch")
    if census["row_id"].astype(str).duplicated().any():
        raise RealSemanticPlaneError("donor_labor_row_identity_not_unique")
    if census["sample_person_id"].astype(str).duplicated().any():
        raise RealSemanticPlaneError("donor_labor_sample_person_identity_not_unique")

    age_field = handoff_policy["age_field"]
    if age_field not in census.columns:
        raise RealSemanticPlaneError(f"donor_labor_age_field_missing:{age_field}")
    age = pd.to_numeric(census[age_field], errors="coerce")
    minimum_age = int(handoff_policy["minimum_age"])
    eligible = age.ge(minimum_age)
    outside_universe_nonnull = (~eligible) & transformed.notna()
    if outside_universe_nonnull.any():
        raise RealSemanticPlaneError(
            "donor_labor_nonnull_outside_reviewed_universe:"
            f"{int(outside_universe_nonnull.sum())}"
        )

    source_field = handoff_policy["source_field"]
    if source_field not in census.columns:
        raise RealSemanticPlaneError(f"donor_labor_source_field_missing:{source_field}")
    vintage = int(policy["clocks"][handoff_policy["vintage_clock"]])

    handoff = census.loc[:, identity_columns].copy()
    handoff[handoff_policy["value_field"]] = transformed.to_numpy()
    handoff[handoff_policy["vintage_field"]] = vintage
    handoff[handoff_policy["semantic_status_field"]] = np.where(
        transformed.notna(),
        handoff_policy["observed_status"],
        handoff_policy["missing_status"],
    )

    census_report = support["census"]
    qa = {
        "schema": "research.eph-census-donor-labor-qa/v1",
        "concept": concept,
        "source_side": "census",
        "source_field": source_field,
        "source_universe": next(
            row["census"].get("universe")
            for row in policy["concepts"]
            if row["concept"] == concept
        ),
        "donor_vintage": vintage,
        "eph_period": policy["clocks"]["eph_period"],
        "sampling_target_year": policy["clocks"]["sampling_target_year"],
        "rows": len(handoff),
        "identity_columns": identity_columns,
        "row_identity_unique": not handoff["row_id"].astype(str).duplicated().any(),
        "sample_person_identity_unique": not handoff[
            "sample_person_id"
        ].astype(str).duplicated().any(),
        "identity_row_count_preserved": len(handoff) == len(census),
        "source_value_counts": _value_counts(census[source_field]),
        "canonical_value_counts": _value_counts(transformed),
        "raw_support": census_report["raw_support"],
        "canonical_support": census_report["canonical_support"],
        "expected_special_to_null": census_report["expected_special_to_null"],
        "unexpected_source_codes": census_report["unmapped_codes"],
        "impossible_canonical_values": census_report["impossible_values"],
        "canonical_null_count": census_report["null_count"],
        "age_universe": {
            "field": age_field,
            "minimum_age": minimum_age,
            "eligible_rows": int(eligible.sum()),
            "outside_universe_rows": int((~eligible).sum()),
            "nonnull_outside_universe_rows": int(outside_universe_nonnull.sum()),
        },
        "clock_separation": {
            "donor_observation_clock": {
                "kind": "census_donor_vintage",
                "value": vintage,
            },
            "eph_observation_clock": {
                "kind": "eph_period",
                "value": policy["clocks"]["eph_period"],
            },
            "same_clock": False,
            "target_period_current_state_claimed": False,
        },
        "training_analogue": {
            "materialized_here": False,
            "forbidden_shortcut": "do_not_copy_current_eph_estado_or_condact_into_donor_condact",
            "owner": "repo.encuestador-de-hogares",
        },
    }
    return handoff, qa


def build_real_review(
    eph_release_root: Path,
    census_sample_root: Path,
    *,
    policy_path: Path = POLICY_PATH,
) -> dict[str, Any]:
    policy_path = Path(policy_path).expanduser().resolve()
    policy = load_review_policy(policy_path)
    evidence = _load_policy_evidence(policy, policy_path)
    individual, household, eph_manifest = _verify_eph_release(eph_release_root, policy)
    census_tables, census_manifest, census_qa = _verify_census_release(
        census_sample_root, policy
    )
    eph = _eph_person_frame(individual, household)
    census = _census_person_frame(census_tables)

    rows: list[dict[str, Any]] = []
    supports: list[dict[str, Any]] = []
    transformed_eph: dict[str, pd.Series] = {}
    transformed_census: dict[str, pd.Series] = {}
    for record in policy["concepts"]:
        row, eph_out, census_out, support = _review_row(
            record, eph, census, evidence=evidence
        )
        rows.append(row)
        supports.append(support)
        transformed_eph[record["concept"]] = eph_out
        transformed_census[record["concept"]] = census_out

    return {
        "policy": policy,
        "policy_path": policy_path,
        "evidence": evidence,
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


def _semantic_compatibility_payload(result: dict[str, Any]) -> dict[str, Any]:
    _, p1r, _, _ = plane_fields(result["policy"])
    approved = set(p1r)
    violations = [
        violation
        for support in result["support_rows"]
        for violation in support["violations"]
        if support["concept"] in approved
    ]
    diagnostics = [
        diagnostic
        for support in result["support_rows"]
        for diagnostic in support.get("diagnostics", [])
        if support["concept"] in approved
    ]
    return {
        "schema": "research.eph-census-semantic-compatibility/v1",
        "release_id": result["policy"]["release_id"],
        "parents": result["policy"]["parents"],
        "clocks": result["policy"]["clocks"],
        "status": "fail" if violations else "pass",
        "eph_rows": len(result["eph_frame"]),
        "census_rows": len(result["census_frame"]),
        "concepts": result["support_rows"],
        "violations": violations,
        "diagnostics": diagnostics,
    }


def write_real_review(
    eph_release_root: Path,
    census_sample_root: Path,
    output_dir: Path,
    *,
    policy_path: Path = POLICY_PATH,
) -> dict[str, Any]:
    result = build_real_review(
        eph_release_root, census_sample_root, policy_path=policy_path
    )
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    review_path = output_dir / "semantic_review_matrix.json"
    compatibility_path = output_dir / "semantic_compatibility_report.json"
    _json(review_path, {
        "schema": "research.eph-census-semantic-review-matrix/v1",
        "release_id": result["policy"]["release_id"],
        "parents": result["policy"]["parents"],
        "clocks": result["policy"]["clocks"],
        "rows": result["review_rows"],
    })
    compatibility = _semantic_compatibility_payload(result)
    _json(compatibility_path, compatibility)
    return {
        "release_id": result["policy"]["release_id"],
        "review_matrix": str(review_path),
        "semantic_compatibility_report": str(compatibility_path),
        "semantic_compatibility_status": compatibility["status"],
        "violations": compatibility["violations"],
    }


def materialize_real_plane(
    eph_release_root: Path,
    census_sample_root: Path,
    output_dir: Path,
    *,
    policy_path: Path = POLICY_PATH,
) -> dict[str, Any]:
    result = build_real_review(
        eph_release_root, census_sample_root, policy_path=policy_path
    )
    policy = result["policy"]
    p1s, p1r, unresolved, rejected = plane_fields(policy)
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    review_path = output_dir / "semantic_review_matrix.json"
    compatibility_path = output_dir / "semantic_compatibility_report.json"
    manifest_path = output_dir / "feature_plane_manifest.json"
    eph_path = output_dir / "eph_p1.parquet"
    census_path = output_dir / "census_p1.parquet"
    donor_labor_path = output_dir / "census_donor_labor_state.parquet"
    donor_labor_qa_path = output_dir / "donor_labor_qa.json"

    _json(review_path, {
        "schema": "research.eph-census-semantic-review-matrix/v1",
        "release_id": policy["release_id"],
        "parents": policy["parents"],
        "clocks": policy["clocks"],
        "rows": result["review_rows"],
    })
    compatibility = _semantic_compatibility_payload(result)
    _json(compatibility_path, compatibility)
    if compatibility["violations"]:
        raise RealSemanticPlaneError(
            "semantic_compatibility_gate_failed:"
            + ",".join(
                f"{violation['type']}:{violation['concept']}"
                for violation in compatibility["violations"][:20]
            )
        )

    eph_plane = _canonical_frame(result["eph_frame"], result["transformed_eph"], p1r)
    census_plane = _canonical_frame(result["census_frame"], result["transformed_census"], p1r)
    if tuple(eph_plane.columns) != tuple(census_plane.columns):
        compatibility["status"] = "fail"
        compatibility["violations"].append({
            "type": "schema_disagreement",
            "eph_columns": list(eph_plane.columns),
            "census_columns": list(census_plane.columns),
        })
        _json(compatibility_path, compatibility)
        raise RealSemanticPlaneError("canonical_plane_schema_disagreement")

    donor_labor, donor_labor_qa = _donor_labor_handoff(result)

    try:
        eph_plane.to_parquet(eph_path, index=False)
        census_plane.to_parquet(census_path, index=False)
        donor_labor.to_parquet(donor_labor_path, index=False)
    except Exception as exc:
        raise RealSemanticPlaneError("canonical_parquet_write_failed:install_pyarrow") from exc
    _json(donor_labor_qa_path, donor_labor_qa)

    manifest = {
        "schema": "research.eph-census-semantic-feature-plane/v1",
        "release_id": policy["release_id"],
        "status": "semantic_review_materialized_transport_not_authorized",
        "parents": policy["parents"],
        "clocks": policy["clocks"],
        "contracts": policy["contracts"],
        "canonical_schema": list(eph_plane.columns),
        "p1_s_fields": p1s,
        "p1_r_fields": p1r,
        "rejected_fields": rejected,
        "unresolved_fields": unresolved,
        "donor_labor_handoff": {
            "schema": "research.eph-census-donor-labor-handoff/v1",
            "path": donor_labor_path.name,
            "sha256": _sha256(donor_labor_path),
            "qa_path": donor_labor_qa_path.name,
            "qa_sha256": _sha256(donor_labor_qa_path),
            "rows": len(donor_labor),
            "value_field": policy["donor_labor_handoff"]["value_field"],
            "vintage_field": policy["donor_labor_handoff"]["vintage_field"],
            "semantic_status_field": policy["donor_labor_handoff"][
                "semantic_status_field"
            ],
            "source_concept": policy["donor_labor_handoff"]["concept"],
            "source_field": policy["donor_labor_handoff"]["source_field"],
            "source_release": policy["parents"]["census_sample_release_id"],
            "frame_parent": policy["parents"]["census_frame_release_id"],
            "donor_vintage": policy["clocks"]["census_vintage"],
            "source_clock": "census_vintage",
            "target_period_current_state_claimed": False,
            "eph_training_analogue_materialized": False,
        },
        "transformations": {
            "eph_raw_to_canonical_plane": {
                "source_release": policy["parents"]["eph_release_id"],
                "policy": result["policy_path"].name,
                "matrix": eph_path.name,
                "rows": len(eph_plane),
                "columns": len(eph_plane.columns),
                "sha256": _sha256(eph_path),
            },
            "census_raw_to_canonical_plane": {
                "source_release": policy["parents"]["census_sample_release_id"],
                "frame_parent": policy["parents"]["census_frame_release_id"],
                "census_vintage": policy["clocks"]["census_vintage"],
                "sampling_target_year": policy["clocks"]["sampling_target_year"],
                "policy": result["policy_path"].name,
                "matrix": census_path.name,
                "rows": len(census_plane),
                "columns": len(census_plane.columns),
                "sha256": _sha256(census_path),
            },
        },
        "review_matrix": {
            "path": review_path.name,
            "sha256": _sha256(review_path),
            "row_count": len(policy["concepts"]),
        },
        "semantic_compatibility_report": {
            "path": compatibility_path.name,
            "sha256": _sha256(compatibility_path),
            "status": compatibility["status"],
        },
        "consumer_handoff": {
            "identity_columns": ["row_id", "household_id"],
            "planes": {"P1-S": p1s, "P1-R": p1r},
            "temporal_roles": {
                row["concept"]: row["temporal_role"] for row in policy["concepts"]
            },
            "donor_labor_state": {
                "artifact": donor_labor_path.name,
                "value_field": policy["donor_labor_handoff"]["value_field"],
                "vintage_field": policy["donor_labor_handoff"]["vintage_field"],
                "semantic_status_field": policy["donor_labor_handoff"][
                    "semantic_status_field"
                ],
                "clock": "census_vintage",
                "legacy_common_plane_field": "CONDACT",
                "legacy_field_is_not_current_target_truth": True,
                "eph_training_analogue_materialized_here": False,
            },
            "semantic_alignment_only": True,
            "statistical_transport_authorized": False,
            "reason": (
                "Semantic comparability and temporal-role evidence are upstream "
                "inputs; model family, weighting, support qualification and "
                "transport promotion belong to the transport consumer."
            ),
        },
    }
    _json(manifest_path, manifest)
    return manifest
