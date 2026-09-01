"""Compile a frozen transport feature inventory into a semantic review plane.

The compiler is intentionally conservative. Historical use is evidence that a
variable mattered to a model, not evidence that an EPH/CPV-2010 mapping is
valid. Real-vintage inputs therefore remain review-required until explicit
source semantics are attached and approved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = (
    ROOT / "aligner" / "review_inventories" / "historical_staged_v1.json"
)
CONTRACT = "research.eph-census-semantic-feature-plane@1"
SEMANTIC_CLASSES = {
    "shared_observable",
    "derived_shared",
    "stage_target",
    "unsupported",
    "research_only",
}
FORBIDDEN_EXTERNAL_INPUTS = {"AGLO_rk", "Reg_rk"}


class FeaturePlaneError(ValueError):
    """Raised when a semantic review plane would become ambiguous or unsafe."""


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
        raise FeaturePlaneError(f"invalid_inventory:{path}") from exc
    if not isinstance(value, dict):
        raise FeaturePlaneError("inventory_must_be_mapping")
    return value


def _ordered_features(inventory: dict[str, Any]) -> tuple[list[str], set[str]]:
    stages = inventory.get("stages")
    if not isinstance(stages, list) or not stages:
        raise FeaturePlaneError("inventory_requires_nonempty_stages")

    ordered: list[str] = []
    targets: set[str] = set()
    previous_targets: list[str] = []
    for index, stage in enumerate(stages, start=1):
        if not isinstance(stage, dict):
            raise FeaturePlaneError(f"stage_{index}_must_be_mapping")
        inputs = stage.get("inputs")
        stage_targets = stage.get("targets")
        if not isinstance(inputs, list) or not isinstance(stage_targets, list):
            raise FeaturePlaneError(f"stage_{index}_requires_input_target_lists")
        if index > 1:
            expected_tail = previous_targets
            if inputs[-len(expected_tail) :] != expected_tail:
                raise FeaturePlaneError(
                    f"stage_{index}_does_not_append_previous_targets_exactly"
                )
        for variable in [*inputs, *stage_targets]:
            if not isinstance(variable, str) or not variable:
                raise FeaturePlaneError(f"stage_{index}_has_invalid_variable")
            if variable not in ordered:
                ordered.append(variable)
        targets.update(stage_targets)
        previous_targets = [*previous_targets, *stage_targets]
    return ordered, targets


def _review_record(variable: str, targets: set[str]) -> dict[str, Any]:
    if variable in targets:
        semantic_class = "stage_target"
        review_status = "historical_stage_target_inventory_only"
        reason = (
            "Observed on the EPH side in the historical staged design. It may be "
            "a learned intermediate or terminal target, not a required Census input."
        )
    elif variable in FORBIDDEN_EXTERNAL_INPUTS:
        semantic_class = "research_only"
        review_status = "forbidden_external_census_input"
        reason = (
            "Historical geography rank retained only as compatibility evidence. "
            "Target-derived rank semantics cannot be treated as a Census observable."
        )
    else:
        semantic_class = "unsupported"
        review_status = "real_vintage_semantic_review_required"
        reason = (
            "Historical feature use does not establish EPH/CPV-2010 conceptual "
            "equivalence. Exact question, universe, reference period and recode "
            "evidence remain required."
        )

    return {
        "feature": variable,
        "semantic_class": semantic_class,
        "external_census_input_allowed": False,
        "review_status": review_status,
        "direction": "eph-to-census",
        "eph_source_fields": [],
        "census_source_fields": [],
        "question_evidence": None,
        "universe_evidence": None,
        "reference_period_evidence": None,
        "recode_or_derivation": None,
        "known_loss_or_ambiguity": None,
        "geography_release": None,
        "reason": reason,
    }


def validate_feature_plane(plane: dict[str, Any]) -> None:
    """Enforce fail-closed semantics for the review artifact."""
    if plane.get("contract") != CONTRACT:
        raise FeaturePlaneError("unexpected_feature_plane_contract")
    features = plane.get("features")
    if not isinstance(features, list) or not features:
        raise FeaturePlaneError("feature_plane_requires_features")

    names: set[str] = set()
    for record in features:
        if not isinstance(record, dict):
            raise FeaturePlaneError("feature_record_must_be_mapping")
        name = record.get("feature")
        semantic_class = record.get("semantic_class")
        if not isinstance(name, str) or not name:
            raise FeaturePlaneError("feature_name_required")
        if name in names:
            raise FeaturePlaneError(f"duplicate_feature:{name}")
        names.add(name)
        if semantic_class not in SEMANTIC_CLASSES:
            raise FeaturePlaneError(
                f"invalid_semantic_class:{name}:{semantic_class}"
            )
        allowed = record.get("external_census_input_allowed")
        if allowed and semantic_class not in {"shared_observable", "derived_shared"}:
            raise FeaturePlaneError(
                f"unsafe_external_input_approval:{name}:{semantic_class}"
            )
        if name in FORBIDDEN_EXTERNAL_INPUTS and allowed:
            raise FeaturePlaneError(f"forbidden_external_input_approved:{name}")

    missing_forbidden = FORBIDDEN_EXTERNAL_INPUTS - names
    if missing_forbidden:
        raise FeaturePlaneError(
            "historical_forbidden_inputs_missing:" + ",".join(sorted(missing_forbidden))
        )
    if plane.get("runtime_approval", {}).get("real_vintage") is True:
        raise FeaturePlaneError("review_plane_cannot_approve_real_vintage_runtime")


def compile_feature_plane(
    inventory_path: Path = DEFAULT_INVENTORY,
) -> dict[str, Any]:
    """Compile one frozen inventory into an explicit real-vintage review queue."""
    inventory_path = Path(inventory_path).resolve()
    inventory = _load(inventory_path)
    if inventory.get("spec_id") != "historical_staged_v1":
        raise FeaturePlaneError("unexpected_inventory_spec")
    ordered, targets = _ordered_features(inventory)
    features = [_review_record(variable, targets) for variable in ordered]
    plane = {
        "contract": CONTRACT,
        "spec_id": inventory["spec_id"],
        "status": "review_required",
        "inventory": {
            "path": str(inventory_path.relative_to(ROOT)),
            "sha256": _sha256(inventory_path),
            "source": inventory.get("source"),
        },
        "source_vintages": {
            "eph": "exact_real_vintage_pending_review_binding",
            "census": "CPV-2010_exact_release_pending_review_binding",
        },
        "runtime_approval": {
            "synthetic_fixture_v1": True,
            "real_vintage": False,
        },
        "features": features,
        "summary": {
            "feature_count": len(features),
            "external_census_inputs_approved": 0,
            "stage_targets": sum(
                record["semantic_class"] == "stage_target" for record in features
            ),
            "research_only": sum(
                record["semantic_class"] == "research_only" for record in features
            ),
            "unsupported": sum(
                record["semantic_class"] == "unsupported" for record in features
            ),
        },
        "limitations": [
            "This artifact is a review plane, not a real-vintage approval.",
            "Historical code/name similarity is not semantic evidence.",
            "Statistical transport validity is outside the aligner boundary.",
            "AGLO_rk and Reg_rk are forbidden as external Census inputs.",
        ],
    }
    validate_feature_plane(plane)
    return plane


def write_feature_plane(output_path: Path, inventory_path: Path = DEFAULT_INVENTORY) -> Path:
    plane = compile_feature_plane(inventory_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(plane, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(write_feature_plane(args.output, args.inventory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
