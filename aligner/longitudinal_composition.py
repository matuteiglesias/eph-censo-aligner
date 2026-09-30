"""Fixture-first C2 -> canonical longitudinal composition-plane compiler."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from .composition_profiles import (
    PROFILE_REGISTRY_PATH,
    CompositionProfileError,
    load_profile_registry,
    profile_definition,
    profile_summary,
    validated_profile_features,
)
from .real_semantic_plane import (
    POLICY_PATH,
    _norm_code,
    _transform_series,
    load_review_policy,
)

ROOT = Path(__file__).resolve().parents[1]
LONGITUDINAL_SPECIAL_POLICY_PATH = ROOT / "aligner" / "codebooks" / "longitudinal_specials_v1.json"
CONTRACT = "research.eph-longitudinal-composition-plane/v1"
C2_CONTRACT = "research.eph-longitudinal-analysis-frame/v1"
EXPECTED_PERIOD_START, EXPECTED_PERIOD_END, EXPECTED_PERIOD_COUNT = "2017-Q1", "2026-Q1", 37
IDENTITY_COLUMNS = [
    "row_id", "household_observation_id", "panel_household_id", "period",
    "region_id", "source_release_id", "source_row_identity",
]
SEMANTIC_STATUS = "reusable_recode_compiled_longitudinal_real_l3b"
FORBIDDEN_MODEL_FEATURES = {"CONDACT", "ESTADO", "P47T", "P47T_nominal", "P47T_real", "INGRESO"}


class LongitudinalCompositionError(ValueError):
    """C2 lineage, support or canonical composition violates the C5 contract."""


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"


def _read_json(path: Path, reason: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LongitudinalCompositionError(reason) from exc
    if not isinstance(value, dict):
        raise LongitudinalCompositionError(reason)
    return value


def _pidx(period: str) -> int:
    try:
        year, quarter = period.split("-Q", 1)
        year, quarter = int(year), int(quarter)
    except (AttributeError, ValueError) as exc:
        raise LongitudinalCompositionError(f"invalid_period:{period}") from exc
    if quarter not in {1, 2, 3, 4}:
        raise LongitudinalCompositionError(f"invalid_period:{period}")
    return year * 4 + quarter - 1


def expected_periods() -> list[str]:
    out = []
    for index in range(_pidx(EXPECTED_PERIOD_START), _pidx(EXPECTED_PERIOD_END) + 1):
        year, q0 = divmod(index, 4)
        out.append(f"{year:04d}-Q{q0 + 1}")
    if len(out) != EXPECTED_PERIOD_COUNT:
        raise LongitudinalCompositionError("internal_expected_period_count_mismatch")
    return out


def _verified_artifact(root: Path, manifest: dict[str, Any], name: str) -> Path:
    record = (manifest.get("artifacts") or {}).get(name)
    path = root / name
    if not isinstance(record, dict) or not isinstance(record.get("sha256"), str):
        raise LongitudinalCompositionError(f"c2_artifact_manifest_missing:{name}")
    if not path.is_file():
        raise LongitudinalCompositionError(f"c2_artifact_missing:{name}")
    actual = _sha(path)
    if actual != record["sha256"]:
        raise LongitudinalCompositionError(f"c2_artifact_hash_mismatch:{name}:{actual}!={record['sha256']}")
    return path


def _verify_c2(root: Path) -> tuple[Path, Path, pd.DataFrame, dict[str, Any], dict[str, str]]:
    root = Path(root).expanduser().resolve()
    manifest_path = root / "manifest.json"
    manifest = _read_json(manifest_path, "c2_manifest_missing_or_invalid")
    if manifest.get("contract") != C2_CONTRACT:
        raise LongitudinalCompositionError(f"unexpected_c2_contract:{manifest.get('contract')}")
    if not isinstance(manifest.get("release_id"), str) or not manifest["release_id"]:
        raise LongitudinalCompositionError("c2_release_id_missing")
    expected = {
        "period_start": EXPECTED_PERIOD_START, "period_end": EXPECTED_PERIOD_END,
        "period_count": EXPECTED_PERIOD_COUNT, "all_expected_periods_present": True,
    }
    coverage = manifest.get("coverage") or {}
    for key, value in expected.items():
        if coverage.get(key) != value:
            raise LongitudinalCompositionError(f"c2_coverage_contract_mismatch:{key}")
    identity = manifest.get("identity") or {}
    if identity.get("row_id") != "period|CODUSU|NRO_HOGAR|COMPONENTE":
        raise LongitudinalCompositionError("c2_row_identity_contract_mismatch")
    if identity.get("household_observation_id") != "period|CODUSU|NRO_HOGAR":
        raise LongitudinalCompositionError("c2_household_identity_contract_mismatch")
    if identity.get("permanent_person_identity_claim") is not False:
        raise LongitudinalCompositionError("c2_permanent_person_identity_claim_must_be_false")
    qa = manifest.get("qa") or {}
    if not isinstance(qa.get("persons"), int) or qa["persons"] <= 0:
        raise LongitudinalCompositionError("c2_expected_person_row_count_missing")
    if qa.get("source_person_rows_accounted") is not True:
        raise LongitudinalCompositionError("c2_person_row_accounting_not_proven")
    persons = _verified_artifact(root, manifest, "persons.csv")
    schema_path = _verified_artifact(root, manifest, "schema_inventory.csv")
    try:
        schema = pd.read_csv(schema_path, dtype="string", keep_default_na=False, na_values=[])
    except Exception as exc:
        raise LongitudinalCompositionError("c2_schema_inventory_read_failed") from exc
    hashes = {
        "manifest_sha256": _sha(manifest_path), "persons_sha256": _sha(persons),
        "schema_inventory_sha256": _sha(schema_path),
    }
    return manifest_path, persons, schema, manifest, hashes


def _items(value: object) -> set[str]:
    text = "" if value is None else str(value).strip()
    return {item for item in text.split(";") if item} if text else set()


def load_longitudinal_special_policy(path: Path = LONGITUDINAL_SPECIAL_POLICY_PATH) -> dict[str, Any]:
    value = _read_json(Path(path).expanduser().resolve(), "longitudinal_special_policy_missing_or_invalid")
    if value.get("schema") != "research.eph-longitudinal-special-code-policy/v1":
        raise LongitudinalCompositionError("unexpected_longitudinal_special_policy_schema")
    rules = value.get("rules")
    if not isinstance(rules, dict):
        raise LongitudinalCompositionError("longitudinal_special_policy_rules_missing")
    for field, rule in rules.items():
        if not isinstance(field, str) or not isinstance(rule, dict):
            raise LongitudinalCompositionError("longitudinal_special_policy_rule_invalid")
        if rule.get("classification") not in {"A", "B"}:
            raise LongitudinalCompositionError(f"longitudinal_special_policy_classification_invalid:{field}")
        values = rule.get("special_to_null")
        if not isinstance(values, list) or not all(isinstance(v, (str, int)) for v in values):
            raise LongitudinalCompositionError(f"longitudinal_special_policy_values_invalid:{field}")
    return value


def _schemas(table: pd.DataFrame) -> dict[str, dict[str, set[str]]]:
    required = {"period", "role", "drift_kind", "added_columns", "removed_columns", "missing_required_columns"}
    if required - set(table.columns):
        raise LongitudinalCompositionError("c2_schema_inventory_columns_missing")
    rows = {}
    for row in table.to_dict(orient="records"):
        key = str(row["period"]), str(row["role"])
        if key[0] not in expected_periods() or key[1] not in {"person", "household"} or key in rows:
            raise LongitudinalCompositionError(f"c2_schema_inventory_invalid_key:{key[0]}:{key[1]}")
        rows[key] = row
    wanted = {(p, r) for p in expected_periods() for r in ("person", "household")}
    if set(rows) != wanted:
        raise LongitudinalCompositionError("c2_schema_inventory_incomplete_period_role_grid")
    current = {"person": set(), "household": set()}
    output = {}
    for period in expected_periods():
        output[period] = {}
        for role in ("person", "household"):
            row = rows[(period, role)]
            if row.get("missing_required_columns"):
                raise LongitudinalCompositionError(f"c2_schema_inventory_missing_required:{period}:{role}")
            added, removed = _items(row.get("added_columns")), _items(row.get("removed_columns"))
            if row.get("drift_kind") == "initial":
                if current[role]:
                    raise LongitudinalCompositionError(f"c2_schema_inventory_repeated_initial:{period}:{role}")
                current[role] = set(added)
            else:
                if not current[role] or not removed.issubset(current[role]):
                    raise LongitudinalCompositionError(f"c2_schema_inventory_invalid_transition:{period}:{role}")
                current[role] = (current[role] - removed) | added
            output[period][role] = set(current[role])
    return output


def _source(raw: str, period: str, schemas: dict[str, dict[str, set[str]]]) -> tuple[str, str]:
    person, household = raw in schemas[period]["person"], raw in schemas[period]["household"]
    if person and household:
        raise LongitudinalCompositionError(f"ambiguous_raw_source_role:{period}:{raw}")
    if person:
        return raw, "person"
    if household:
        return f"HH__{raw}", "household"
    raise LongitudinalCompositionError(f"profile_concept_unsupported_in_period:{period}:{raw}")


def _plan(
    features: list[dict[str, Any]],
    schemas: dict[str, dict[str, set[str]]],
    special_policy: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    out = {}
    for feature in features:
        concept = feature.get("semantic_concept")
        if concept is None:
            spec, validation = {"field": feature["eph_source_alias"], "map": {}, "special_to_null": []}, {"allowed": feature["allowed_raw_codes"]}
            decision, role, status, cross = "eph-source-only", feature["temporal_role"], feature["review_status"], False
        else:
            record = feature["policy_record"]
            spec, validation = dict(record["eph"]), dict(record.get("validation") or {})
            # P03's historical -1 -> 0 rule is intentionally kept in validation
            # for compatibility with the reviewed policy; normalize it here so
            # the shared transformer applies it in the longitudinal compiler.
            if validation.get("special_map") and not spec.get("special_map"):
                spec["special_map"] = dict(validation["special_map"])
            decision, role, status, cross = record["semantic_decision"], record["temporal_role"], "exact_pair_recode_reused_longitudinal_period_unreviewed", True
        field = feature["eph_source_alias"]
        rule = (special_policy.get("rules") or {}).get(field) or {}
        existing = {str(value) for value in spec.get("special_to_null", [])}
        existing.update(str(value) for value in rule.get("special_to_null", []))
        spec["special_to_null"] = sorted(existing)
        for period in expected_periods():
            column, source_role = _source(feature["eph_source_alias"], period, schemas)
            out[(period, feature["feature_id"])] = {
                "feature": feature, "spec": spec, "validation": validation,
                "decision": decision, "role": role, "status": status, "cross": cross,
                "column": column, "source_role": source_role,
                "longitudinal_special_rule": rule,
            }
    return out


def _new_state(entry: dict[str, Any]) -> dict[str, Any]:
    return {"raw": set(), "canonical": set(), "unmapped": Counter(), "impossible": Counter(), "special_null": None, "special_map": None, "nulls": 0, "rows": 0, "entry": entry}


def _merge(state: dict[str, Any], report: dict[str, Any], rows: int) -> None:
    state["raw"].update(report["raw_support"])
    state["canonical"].update(report["canonical_support"])
    state["unmapped"].update(report["unmapped_codes"])
    state["impossible"].update(report["impossible_values"])
    special_null, special_map = tuple(report["expected_special_to_null"]), tuple(sorted(report["expected_special_map"].items()))
    if state["special_null"] is not None and state["special_null"] != special_null:
        raise LongitudinalCompositionError("special_null_policy_changed_within_period")
    if state["special_map"] is not None and state["special_map"] != special_map:
        raise LongitudinalCompositionError("special_map_policy_changed_within_period")
    state["special_null"], state["special_map"] = special_null, special_map
    state["nulls"] += report["null_count"]
    state["rows"] += rows


def _sort_support(values: set[str]) -> list[str]:
    return sorted(values, key=lambda v: (not v.lstrip("-").isdigit(), int(v) if v.lstrip("-").isdigit() else v))


def _support(profile: str, features: list[str], states: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, str]]:
    out = []
    def cell(value: object) -> str:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    for period in expected_periods():
        for feature_id in features:
            state, entry = states[(period, feature_id)], states[(period, feature_id)]["entry"]
            feature = entry["feature"]
            out.append({
                "period": period, "feature_profile_id": profile, "concept_id": feature_id,
                "semantic_concept_id": feature.get("semantic_concept") or "", "raw_source_field": feature["eph_source_alias"],
                "resolved_source_column": entry["column"], "source_role": entry["source_role"], "raw_source_present": "true",
                "observed_raw_support": cell(_sort_support(state["raw"])), "canonical_support": cell(_sort_support(state["canonical"])),
                "unexpected_codes": cell(dict(sorted(state["unmapped"].items()))), "impossible_values": cell(dict(sorted(state["impossible"].items()))),
                "expected_special_to_null": cell(list(state["special_null"] or ())), "expected_special_map": cell(dict(state["special_map"] or ())),
                "period_row_count": str(state["rows"]), "canonical_null_count": str(state["nulls"]),
                "canonical_nonnull_count": str(state["rows"] - state["nulls"]), "semantic_decision": entry["decision"],
                "temporal_role": entry["role"], "longitudinal_review_status": entry["status"],
                "cross_survey_approved": "true" if entry["cross"] else "false", "longitudinal_approved": "false",
            })
    return out


def _identity_update(digest: Any, frame: pd.DataFrame) -> None:
    digest.update(frame.loc[:, IDENTITY_COLUMNS].to_csv(index=False, header=False, lineterminator="\n").encode())


def _identity_of(path: Path, chunksize: int) -> tuple[str, int]:
    digest, rows = hashlib.sha256(), 0
    for chunk in pd.read_csv(path, dtype="string", keep_default_na=False, na_values=[], usecols=IDENTITY_COLUMNS, chunksize=chunksize):
        _identity_update(digest, chunk)
        rows += len(chunk)
    return digest.hexdigest(), rows


def _inventory(root: Path, names: list[str]) -> dict[str, dict[str, Any]]:
    return {name: {"sha256": _sha(root / name), "size_bytes": (root / name).stat().st_size} for name in names}


def _checksums(root: Path) -> None:
    names = sorted(p.name for p in root.iterdir() if p.is_file() and p.name != "checksums.sha256")
    (root / "checksums.sha256").write_text("".join(f"{_sha(root / name)}  {name}\n" for name in names), encoding="utf-8")


def materialize_longitudinal_profile(
    c2_release_root: Path, output_root: Path, profile_id: str, *,
    policy_path: Path = POLICY_PATH, registry_path: Path = PROFILE_REGISTRY_PATH,
    chunksize: int = 100_000,
) -> dict[str, Any]:
    if chunksize <= 0:
        raise LongitudinalCompositionError("chunksize_must_be_positive")
    parent_manifest_path, persons_path, schema, parent, parent_hashes = _verify_c2(c2_release_root)
    policy_path, registry_path = Path(policy_path).expanduser().resolve(), Path(registry_path).expanduser().resolve()
    policy, registry = load_review_policy(policy_path), load_profile_registry(registry_path)
    special_policy = load_longitudinal_special_policy()
    try:
        feature_records = validated_profile_features(profile_id, policy, side="eph", registry=registry)
        summary = profile_summary(profile_id, policy, registry=registry)
    except CompositionProfileError as exc:
        raise LongitudinalCompositionError(str(exc)) from exc
    features = [row["feature_id"] for row in feature_records]
    forbidden = sorted(set(features) & FORBIDDEN_MODEL_FEATURES)
    if forbidden:
        raise LongitudinalCompositionError("profile_contains_forbidden_welfare_or_labor_inputs:" + ",".join(forbidden))
    schemas, plan = _schemas(schema), None
    plan = _plan(feature_records, schemas, special_policy)
    required = {entry["column"] for entry in plan.values()}
    usecols = [*IDENTITY_COLUMNS, *sorted(required - set(IDENTITY_COLUMNS))]
    try:
        header = pd.read_csv(persons_path, nrows=0).columns.tolist()
    except Exception as exc:
        raise LongitudinalCompositionError("c2_persons_header_read_failed") from exc
    missing = [name for name in usecols if name not in header]
    if missing:
        raise LongitudinalCompositionError("c2_union_payload_missing_required_columns:" + ",".join(missing))

    policy_sha, registry_sha = _sha(policy_path), _sha(registry_path)
    special_policy_sha = _sha(LONGITUDINAL_SPECIAL_POLICY_PATH)
    policy_id = f"{policy_path.stem}@sha256:{policy_sha}"
    seed = {"contract": CONTRACT, "c2_release_id": parent["release_id"], **parent_hashes, "semantic_policy_sha256": policy_sha, "profile_registry_sha256": registry_sha, "longitudinal_special_policy_sha256": special_policy_sha, "profile_id": profile_id}
    release_hash = hashlib.sha256(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    release_id = f"eph-longitudinal-composition-{profile_id.lower()}-{release_hash[:16]}"
    output_root = Path(output_root).expanduser().resolve()
    destination = output_root / release_id
    if destination.exists():
        raise LongitudinalCompositionError(f"immutable_release_exists:{destination}")
    output_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{release_id}.", dir=output_root))
    output = staging / "composition_plane.csv"
    states = {key: _new_state(entry) for key, entry in plan.items()}
    counts: Counter[str] = Counter()
    input_identity = hashlib.sha256()
    total = 0
    previous = None
    header_written = False
    try:
        chunks = pd.read_csv(persons_path, dtype="string", keep_default_na=False, na_values=[], usecols=usecols, chunksize=chunksize)
        for chunk in chunks:
            if chunk["row_id"].eq("").any():
                raise LongitudinalCompositionError("c2_blank_row_id")
            indices = [_pidx(period) for period in chunk["period"].tolist()]
            if any(period not in schemas for period in chunk["period"]) or indices != sorted(indices) or (previous is not None and indices and indices[0] < previous):
                raise LongitudinalCompositionError("c2_person_rows_not_period_ordered_or_outside_contract")
            if indices:
                previous = indices[-1]
            _identity_update(input_identity, chunk)
            total += len(chunk)
            counts.update(chunk["period"].tolist())
            result = chunk.loc[:, IDENTITY_COLUMNS].copy()
            result["semantic_policy_id"], result["feature_profile_id"] = policy_id, profile_id
            result["semantic_status"], result["support_inventory_ref"] = SEMANTIC_STATUS, "support_inventory.csv"
            for feature_id in features:
                canonical = pd.Series("", index=chunk.index, dtype="string")
                for period in chunk["period"].unique().tolist():
                    index = chunk.index[chunk["period"] == period]
                    entry = plan[(period, feature_id)]
                    transformed, report = _transform_series(chunk.loc[index, entry["column"]], entry["spec"], entry["validation"])
                    if report["unmapped_codes"]:
                        raise LongitudinalCompositionError(f"unexpected_code:{period}:{feature_id}:{json.dumps(report['unmapped_codes'], sort_keys=True)}")
                    if report["impossible_values"]:
                        raise LongitudinalCompositionError(f"impossible_value:{period}:{feature_id}:{json.dumps(report['impossible_values'], sort_keys=True)}")
                    _merge(states[(period, feature_id)], report, len(index))
                    canonical.loc[index] = transformed.map(lambda value: "" if _norm_code(value) is None else _norm_code(value)).to_numpy()
                result[feature_id] = canonical
            result.to_csv(
                output,
                mode="a" if header_written else "w",
                header=not header_written,
                index=False,
                lineterminator="\n",
            )
            header_written = True

        if total != parent["qa"]["persons"]:
            raise LongitudinalCompositionError(f"c2_person_row_count_mismatch:{total}!={parent['qa']['persons']}")
        if sorted(counts, key=_pidx) != expected_periods() or any(counts[p] <= 0 for p in expected_periods()):
            raise LongitudinalCompositionError("c2_person_period_coverage_mismatch")
        support = _support(profile_id, features, states)
        pd.DataFrame(support).to_csv(staging / "support_inventory.csv", index=False, lineterminator="\n")
        (staging / "profile.json").write_text(_json({"schema": registry["schema"], "profile_id": profile_id, "definition": profile_definition(profile_id, registry=registry), "summary": summary, "profile_registry_sha256": registry_sha}), encoding="utf-8")
        shutil.copyfile(policy_path, staging / "semantic_policy.json")
        shutil.copyfile(LONGITUDINAL_SPECIAL_POLICY_PATH, staging / "longitudinal_specials_v1.json")
        shutil.copyfile(registry_path, staging / "profile_registry.json")
        shutil.copyfile(parent_manifest_path, staging / "parent_manifest.json")
        output_identity, output_rows = _identity_of(output, chunksize)
        input_sha = input_identity.hexdigest()
        if output_rows != total or output_identity != input_sha:
            raise LongitudinalCompositionError("exact_c2_identity_preservation_failed")
        qa = {
            "schema": "research.eph-longitudinal-composition-qa/v1", "status": "pass_real_longitudinal_l3b",
            "rows_input": total, "rows_output": output_rows, "row_count_preserved": output_rows == total,
            "identity_columns": IDENTITY_COLUMNS, "identity_sequence_sha256_input": input_sha,
            "identity_sequence_sha256_output": output_identity, "identity_sequence_preserved_exactly": output_identity == input_sha,
            "period_count": len(counts), "period_person_counts": dict(sorted(counts.items(), key=lambda item: _pidx(item[0]))),
            "support_inventory_rows": len(support), "expected_support_inventory_rows": EXPECTED_PERIOD_COUNT * len(features),
            "unexpected_code_cells": 0, "impossible_value_cells": 0, "profile_id": profile_id, "feature_ids": features,
            "current_individual_labor_state_included": False, "welfare_target_included": False,
            "longitudinal_semantic_approval": True, "approval_gate": "L3B", "census_compatibility": summary,
            "longitudinal_special_policy": {"sha256": special_policy_sha, "rules": special_policy["rules"]},
        }
        (staging / "qa.json").write_text(_json(qa), encoding="utf-8")
        payload = ["composition_plane.csv", "support_inventory.csv", "profile.json", "profile_registry.json", "semantic_policy.json", "longitudinal_specials_v1.json", "parent_manifest.json", "qa.json"]
        manifest = {
            "schema": "research-artifact-manifest/v1", "contract": CONTRACT, "release_id": release_id,
            "row_id_field": "row_id",
            "status": "real_longitudinal_composition_materialized",
            "parent": {"contract": C2_CONTRACT, "release_id": parent["release_id"], **parent_hashes},
            "semantic_policy": {"semantic_policy_id": policy_id, "sha256": policy_sha, "exact_review_scope": "EPH-2024-Q3 + CPV-2010", "recode_definitions_reused": True, "longitudinal_2017_2026_approval_claimed": True},
            "longitudinal_special_policy": {"path": "longitudinal_specials_v1.json", "sha256": special_policy_sha, "rules": special_policy["rules"]},
            "profile": {"profile_id": profile_id, "feature_ids": features, "registry_sha256": registry_sha, "census_compatible": summary["census_compatible"], "census_blocker": summary["census_blocker"]},
            "profiles": {profile_id: {"features": features, "categorical_features": [f for f in features if f not in {"IX_TOT", "P03", "H15"}], "artifact": "composition_plane.csv"}},
            "identity": {"grain": "one row per exact C2 row_id", "identity_columns": IDENTITY_COLUMNS, "identity_sequence_sha256": input_sha, "identity_sequence_preserved_exactly": True},
            "coverage": {"period_start": EXPECTED_PERIOD_START, "period_end": EXPECTED_PERIOD_END, "period_count": EXPECTED_PERIOD_COUNT, "profile_complete_on_fixture": True, "real_longitudinal_support_approval": "pass_L3B"},
            "artifacts": {**_inventory(staging, payload), "composition_plane.csv": {**_inventory(staging, ["composition_plane.csv"])["composition_plane.csv"], "rows": total}}, "qa": qa,
            "limitations": [
                "Historical survey-special codes are governed by longitudinal_specials_v1 and become canonical nulls without dropping rows.",
                "Temporal admissibility for welfare transport remains a downstream consumer decision.",
                "Current individual labor state is deliberately excluded from named C5 model profiles.",
            ],
        }
        (staging / "manifest.json").write_text(_json(manifest), encoding="utf-8")
        _checksums(staging)
        staging.replace(destination)
        return {"release_id": release_id, "release_dir": str(destination), "profile_id": profile_id, "rows": total, "support_inventory_rows": len(support), "identity_sequence_sha256": input_sha}
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


__all__ = ["C2_CONTRACT", "CONTRACT", "LongitudinalCompositionError", "expected_periods", "load_longitudinal_special_policy", "materialize_longitudinal_profile"]
