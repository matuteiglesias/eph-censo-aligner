"""Compile legacy EPH<->Census code evidence into a fail-closed review report.

Historical rename/recode code is evidence about what earlier models attempted.
It is not question-level semantic approval. This compiler makes that distinction
machine-readable so review can advance without silently promoting name matches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .feature_plane import (
    DEFAULT_INVENTORY,
    FORBIDDEN_EXTERNAL_INPUTS,
    FeaturePlaneError,
    compile_feature_plane,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRIDGE_EVIDENCE = (
    ROOT
    / "aligner"
    / "review_inventories"
    / "historical_staged_v1_legacy_bridge.json"
)
CONTRACT = "research.eph-census-legacy-bridge-gap-report@1"
EVIDENCE_SCHEMA = "research.transport-legacy-bridge-evidence/v1"


class LegacyBridgeReviewError(ValueError):
    """Raised when legacy bridge evidence is incomplete or unsafe."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegacyBridgeReviewError(f"invalid_bridge_evidence:{path}") from exc
    if not isinstance(value, dict):
        raise LegacyBridgeReviewError("bridge_evidence_must_be_mapping")
    return value


def _bridge_by_feature(evidence: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if evidence.get("schema") != EVIDENCE_SCHEMA:
        raise LegacyBridgeReviewError("unexpected_bridge_evidence_schema")
    if evidence.get("spec_id") != "historical_staged_v1":
        raise LegacyBridgeReviewError("unexpected_bridge_evidence_spec")
    if evidence.get("status") != "code_evidence_only_not_semantic_approval":
        raise LegacyBridgeReviewError("bridge_evidence_status_not_fail_closed")
    records = evidence.get("features")
    if not isinstance(records, list) or not records:
        raise LegacyBridgeReviewError("bridge_evidence_requires_features")

    output: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise LegacyBridgeReviewError("bridge_feature_record_must_be_mapping")
        feature = record.get("feature")
        if not isinstance(feature, str) or not feature:
            raise LegacyBridgeReviewError("bridge_feature_name_required")
        if feature in output:
            raise LegacyBridgeReviewError(f"duplicate_bridge_feature:{feature}")
        eph_fields = record.get("eph_source_fields")
        census_fields = record.get("census_source_fields")
        if not isinstance(eph_fields, list) or not eph_fields:
            raise LegacyBridgeReviewError(f"bridge_eph_fields_required:{feature}")
        if not isinstance(census_fields, list) or not census_fields:
            raise LegacyBridgeReviewError(f"bridge_census_fields_required:{feature}")
        if record.get("external_census_input_allowed") is True:
            raise LegacyBridgeReviewError(f"bridge_evidence_cannot_approve:{feature}")
        output[feature] = record
    return output


def compile_legacy_bridge_gap_report(
    inventory_path: Path = DEFAULT_INVENTORY,
    evidence_path: Path = DEFAULT_BRIDGE_EVIDENCE,
) -> dict[str, Any]:
    """Compile frozen code evidence into an explicit real-vintage semantic gap."""
    inventory_path = Path(inventory_path).resolve()
    evidence_path = Path(evidence_path).resolve()
    try:
        plane = compile_feature_plane(inventory_path)
    except FeaturePlaneError as exc:
        raise LegacyBridgeReviewError(str(exc)) from exc
    evidence = _load(evidence_path)
    bridge = _bridge_by_feature(evidence)

    unsupported = {
        record["feature"]
        for record in plane["features"]
        if record["semantic_class"] == "unsupported"
    }
    missing = sorted(unsupported - set(bridge))
    extra = sorted(set(bridge) - unsupported)
    if missing:
        raise LegacyBridgeReviewError(
            "unsupported_features_missing_bridge_evidence:" + ",".join(missing)
        )
    if extra:
        raise LegacyBridgeReviewError(
            "bridge_evidence_not_an_unsupported_external_feature:" + ",".join(extra)
        )

    records: list[dict[str, Any]] = []
    for feature_record in plane["features"]:
        feature = feature_record["feature"]
        semantic_class = feature_record["semantic_class"]
        if semantic_class == "unsupported":
            source = bridge[feature]
            records.append(
                {
                    "feature": feature,
                    "review_state": "legacy_code_bridge_evidence_attached",
                    "semantic_class": "unsupported",
                    "external_census_input_allowed": False,
                    "eph_source_fields": source["eph_source_fields"],
                    "census_source_fields": source["census_source_fields"],
                    "legacy_bridge": source.get("legacy_bridge"),
                    "known_loss_or_ambiguity": source.get(
                        "known_loss_or_ambiguity"
                    ),
                    "question_evidence": "missing",
                    "universe_evidence": "missing",
                    "reference_period_evidence": "missing",
                    "category_domain_evidence": "missing",
                    "approval_blocker": (
                        "Legacy implementation evidence is insufficient for semantic "
                        "approval; exact EPH and CPV-2010 source documentation is required."
                    ),
                }
            )
        elif semantic_class == "research_only":
            if feature not in FORBIDDEN_EXTERNAL_INPUTS:
                raise LegacyBridgeReviewError(
                    f"unexpected_research_only_feature:{feature}"
                )
            records.append(
                {
                    "feature": feature,
                    "review_state": "forbidden_external_census_input",
                    "semantic_class": semantic_class,
                    "external_census_input_allowed": False,
                    "approval_blocker": "Target-derived research rank cannot be a Census observable.",
                }
            )
        elif semantic_class == "stage_target":
            records.append(
                {
                    "feature": feature,
                    "review_state": "learned_stage_output_not_external_input",
                    "semantic_class": semantic_class,
                    "external_census_input_allowed": False,
                    "approval_blocker": None,
                }
            )
        else:
            raise LegacyBridgeReviewError(
                f"unexpected_feature_plane_state:{feature}:{semantic_class}"
            )

    report = {
        "contract": CONTRACT,
        "spec_id": "historical_staged_v1",
        "status": "semantic_evidence_required",
        "parents": {
            "inventory": {
                "path": str(inventory_path.relative_to(ROOT)),
                "sha256": _sha256(inventory_path),
            },
            "legacy_bridge_evidence": {
                "path": str(evidence_path.relative_to(ROOT)),
                "sha256": _sha256(evidence_path),
                "status": evidence["status"],
            },
        },
        "runtime_approval": {
            "real_vintage": False,
            "reason": (
                "Legacy operational mappings are now explicit, but exact source-question "
                "semantics remain unreviewed."
            ),
        },
        "features": records,
        "summary": {
            "feature_count": len(records),
            "legacy_bridge_evidence_attached": sum(
                record["review_state"]
                == "legacy_code_bridge_evidence_attached"
                for record in records
            ),
            "external_census_inputs_approved": 0,
            "question_evidence_missing": sum(
                record.get("question_evidence") == "missing" for record in records
            ),
            "universe_evidence_missing": sum(
                record.get("universe_evidence") == "missing" for record in records
            ),
            "reference_period_evidence_missing": sum(
                record.get("reference_period_evidence") == "missing"
                for record in records
            ),
            "category_domain_evidence_missing": sum(
                record.get("category_domain_evidence") == "missing"
                for record in records
            ),
            "forbidden_external_inputs": sum(
                record["review_state"] == "forbidden_external_census_input"
                for record in records
            ),
            "learned_stage_outputs": sum(
                record["review_state"]
                == "learned_stage_output_not_external_input"
                for record in records
            ),
        },
        "next_gate": {
            "required": (
                "Attach exact EPH and CPV-2010 question wording/codebook evidence, "
                "universe, reference period and category-domain relation per candidate feature."
            ),
            "automatic_name_match_approval": False,
            "lossy_or_asymmetric_recodes_require_explicit_review": True,
        },
        "limitations": [
            "This report upgrades provenance of the historical bridge, not semantic validity.",
            "No candidate external Census feature is approved by this artifact.",
            "AGLO_rk and Reg_rk remain permanently forbidden as external Census inputs.",
        ],
    }
    return report


def write_legacy_bridge_gap_report(
    output_path: Path,
    inventory_path: Path = DEFAULT_INVENTORY,
    evidence_path: Path = DEFAULT_BRIDGE_EVIDENCE,
) -> Path:
    report = compile_legacy_bridge_gap_report(inventory_path, evidence_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_BRIDGE_EVIDENCE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(
        write_legacy_bridge_gap_report(
            args.output,
            inventory_path=args.inventory,
            evidence_path=args.evidence,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
