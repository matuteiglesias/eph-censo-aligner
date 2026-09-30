from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROFILE_REGISTRY_PATH = ROOT / "aligner" / "codebooks" / "longitudinal_composition_profiles_v1.json"
PROFILE_REGISTRY_SCHEMA = "research.eph-longitudinal-composition-profile-registry/v1"


class CompositionProfileError(ValueError):
    """Raised when a named composition profile is incomplete or semantically unsafe."""


def load_profile_registry(path: Path = PROFILE_REGISTRY_PATH) -> dict[str, Any]:
    path = Path(path).expanduser().resolve()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompositionProfileError(f"invalid_profile_registry:{path}") from exc
    if not isinstance(value, dict) or value.get("schema") != PROFILE_REGISTRY_SCHEMA:
        raise CompositionProfileError("unexpected_profile_registry_schema")
    profiles = value.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise CompositionProfileError("profile_registry_profiles_missing")
    for profile_id, profile in profiles.items():
        if not isinstance(profile_id, str) or not profile_id:
            raise CompositionProfileError("invalid_profile_id")
        if not isinstance(profile, dict):
            raise CompositionProfileError(f"invalid_profile_definition:{profile_id}")
        features = profile.get("features")
        if not isinstance(features, list) or not features:
            raise CompositionProfileError(f"profile_features_missing:{profile_id}")
        seen: set[str] = set()
        for feature in features:
            if not isinstance(feature, dict):
                raise CompositionProfileError(f"invalid_profile_feature:{profile_id}")
            feature_id = feature.get("feature_id")
            raw_alias = feature.get("eph_source_alias")
            if not isinstance(feature_id, str) or not feature_id or feature_id in seen:
                raise CompositionProfileError(f"duplicate_or_empty_profile_feature:{profile_id}")
            if not isinstance(raw_alias, str) or not raw_alias:
                raise CompositionProfileError(f"profile_feature_missing_eph_alias:{profile_id}:{feature_id}")
            seen.add(feature_id)
            concept = feature.get("semantic_concept")
            source_only = feature.get("eph_source_only") is True
            if (concept is None) == (not source_only):
                raise CompositionProfileError(
                    f"profile_feature_semantic_mode_invalid:{profile_id}:{feature_id}"
                )
            if concept is not None and (not isinstance(concept, str) or not concept):
                raise CompositionProfileError(
                    f"profile_feature_semantic_concept_invalid:{profile_id}:{feature_id}"
                )
    return value


def profile_definition(
    profile_id: str,
    *,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry or load_profile_registry()
    profiles = registry["profiles"]
    try:
        return profiles[profile_id]
    except KeyError as exc:
        raise CompositionProfileError(f"unknown_profile:{profile_id}") from exc


def _policy_by_concept(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    concepts = policy.get("concepts")
    if not isinstance(concepts, list):
        raise CompositionProfileError("semantic_policy_concepts_missing")
    by_concept: dict[str, dict[str, Any]] = {}
    for row in concepts:
        concept = row.get("concept") if isinstance(row, dict) else None
        if not isinstance(concept, str) or not concept or concept in by_concept:
            raise CompositionProfileError("semantic_policy_concept_identity_invalid")
        by_concept[concept] = row
    return by_concept


def validated_profile_features(
    profile_id: str,
    policy: dict[str, Any],
    *,
    side: str = "eph",
    registry: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if side not in {"eph", "census"}:
        raise CompositionProfileError(f"invalid_profile_side:{side}")
    registry = registry or load_profile_registry()
    profile = profile_definition(profile_id, registry=registry)
    by_concept = _policy_by_concept(policy)
    validated: list[dict[str, Any]] = []
    excluded = set(profile.get("excluded_by_design") or []) | set(profile.get("excluded_unresolved") or [])
    selected_ids = {feature["feature_id"] for feature in profile["features"]}
    forbidden_selected = sorted(selected_ids & excluded)
    if forbidden_selected:
        raise CompositionProfileError(
            f"profile_explicit_exclusion_violated:{profile_id}:{','.join(forbidden_selected)}"
        )
    for excluded_concept in profile.get("excluded_by_design") or []:
        record = by_concept.get(excluded_concept)
        if record is None or record.get("semantic_decision") != "approve":
            raise CompositionProfileError(
                f"profile_design_exclusion_policy_mismatch:{profile_id}:{excluded_concept}"
            )
    for unresolved in profile.get("excluded_unresolved") or []:
        record = by_concept.get(unresolved)
        if record is None or record.get("semantic_decision") != "needs-judgment":
            raise CompositionProfileError(
                f"profile_unresolved_exclusion_policy_mismatch:{profile_id}:{unresolved}"
            )
    if profile.get("policy_basis") == "P1-R":
        approved_p1r = [
            row["concept"]
            for row in policy["concepts"]
            if row.get("semantic_decision") == "approve"
            and row.get("temporal_role")
            in {"stable/shared", "target-period-state", "research-only"}
        ]
        expected = [
            concept
            for concept in approved_p1r
            if concept not in set(profile.get("excluded_by_design") or [])
        ]
        selected_semantic = [
            feature.get("semantic_concept")
            for feature in profile["features"]
            if feature.get("semantic_concept") is not None
        ]
        if set(selected_semantic) != set(expected) or len(selected_semantic) != len(expected):
            raise CompositionProfileError(
                f"profile_policy_basis_mismatch:{profile_id}:"
                f"selected={','.join(selected_semantic)}:expected={','.join(expected)}"
            )
    for feature in profile["features"]:
        feature_id = feature["feature_id"]
        concept = feature.get("semantic_concept")
        if concept is None:
            if side == "census":
                raise CompositionProfileError(
                    f"profile_not_census_compatible:{profile_id}:{feature_id}"
                )
            allowed = feature.get("allowed_raw_codes")
            if not isinstance(allowed, list) or not allowed:
                raise CompositionProfileError(
                    f"source_only_feature_domain_missing:{profile_id}:{feature_id}"
                )
            validated.append(dict(feature))
            continue
        record = by_concept.get(concept)
        if record is None:
            raise CompositionProfileError(
                f"profile_semantic_concept_missing_from_policy:{profile_id}:{concept}"
            )
        if record.get("semantic_decision") != "approve":
            raise CompositionProfileError(
                f"profile_semantic_concept_not_approved:{profile_id}:{concept}:"
                f"{record.get('semantic_decision')}"
            )
        spec = record.get(side)
        if not isinstance(spec, dict) or not isinstance(spec.get("field"), str):
            raise CompositionProfileError(
                f"profile_semantic_side_missing:{profile_id}:{concept}:{side}"
            )
        if side == "eph" and spec["field"] != feature["eph_source_alias"]:
            raise CompositionProfileError(
                f"profile_eph_alias_policy_mismatch:{profile_id}:{concept}:"
                f"{feature['eph_source_alias']}!={spec['field']}"
            )
        if feature_id != concept:
            raise CompositionProfileError(
                f"approved_profile_feature_must_use_canonical_id:{profile_id}:{feature_id}:{concept}"
            )
        enriched = dict(feature)
        enriched["policy_record"] = record
        validated.append(enriched)
    return validated


def profile_feature_ids(
    profile_id: str,
    policy: dict[str, Any],
    *,
    side: str = "eph",
    registry: dict[str, Any] | None = None,
) -> list[str]:
    return [
        feature["feature_id"]
        for feature in validated_profile_features(
            profile_id, policy, side=side, registry=registry
        )
    ]


def profile_summary(
    profile_id: str,
    policy: dict[str, Any],
    *,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = registry or load_profile_registry()
    eph = validated_profile_features(profile_id, policy, side="eph", registry=registry)
    try:
        census_fields = profile_feature_ids(
            profile_id, policy, side="census", registry=registry
        )
        census_compatible = True
        census_blocker = None
    except CompositionProfileError as exc:
        census_fields = []
        census_compatible = False
        census_blocker = str(exc)
    return {
        "profile_id": profile_id,
        "features": [feature["feature_id"] for feature in eph],
        "census_compatible": census_compatible,
        "census_fields": census_fields,
        "census_blocker": census_blocker,
    }
