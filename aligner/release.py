"""Deterministic alignment releases and bounded diagnostic reports."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .cdm import CDM_VERSION
from .censo_align import censo_to_eph_hogar, censo_to_eph_individual
from .eph_align import harmonize_hogar, harmonize_individual

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "aligner" / "mappings" / "registry.json"
COMPATIBILITY = ROOT / "aligner" / "compatibility.json"
IDENTIFIERS = ["CODUSU", "NRO_HOGAR", "COMPONENTE", "ANO4", "TRIMESTRE", "record_id"]
TERMINAL_DISPOSITIONS = ("emitted", "removed", "invalid", "unsupported", "unmatched", "failed")
COMPOSITIONS = {"filter_then_transform", "geography_join_then_override"}


class RegistryError(ValueError):
    """Raised when registry precedence would make a release ambiguous."""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _git_metadata() -> tuple[str, bool, str]:
    """Return commit, pre-release dirty state, and stable commit time."""
    commit_run = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True
    )
    commit = commit_run.stdout.strip() if commit_run.returncode == 0 else "unknown"
    dirty_run = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=normal"],
        cwd=ROOT, text=True, capture_output=True,
    )
    dirty = dirty_run.returncode != 0 or bool(dirty_run.stdout.strip())
    time_run = subprocess.run(
        ["git", "show", "-s", "--format=%ct", commit],
        cwd=ROOT, text=True, capture_output=True,
    )
    seconds = int(time_run.stdout.strip()) if time_run.returncode == 0 else 0
    created = datetime.fromtimestamp(seconds, timezone.utc).isoformat().replace("+00:00", "Z")
    return commit, dirty, created


def _json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_registry(registry: dict[str, Any]) -> None:
    """Reject duplicate precedence and undeclared multi-rule composition.

    Reverse-direction rules are deliberately validated in their own direction;
    this function never derives or inverts a rule.
    """
    required = {
        "mapping_id", "direction", "entity", "source_vintage",
        "source_variable", "target_variable", "rule_priority",
    }
    seen_ids: set[str] = set()
    precedence: dict[tuple[Any, ...], str] = {}
    source_rules: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for rule in registry.get("mappings", []):
        missing = required - rule.keys()
        if missing:
            raise RegistryError(f"{rule.get('mapping_id', '<unknown>')} lacks {sorted(missing)}")
        if rule["mapping_id"] in seen_ids:
            raise RegistryError(f"Duplicate mapping_id: {rule['mapping_id']}")
        seen_ids.add(rule["mapping_id"])
        composition = rule.get("composition")
        if composition is not None and composition not in COMPOSITIONS:
            raise RegistryError(
                f"Unknown composition {composition!r} in {rule['mapping_id']}"
            )
        override_conditions: set[str] = set()
        for override in rule.get("overrides", []):
            condition = json.dumps(override.get("when", {}), sort_keys=True)
            if condition in override_conditions:
                raise RegistryError(
                    f"Override condition is shadowed in {rule['mapping_id']}: {condition}"
                )
            override_conditions.add(condition)
        key = tuple(rule[k] for k in (
            "direction", "entity", "source_vintage", "source_variable",
            "target_variable", "rule_priority",
        ))
        if key in precedence:
            raise RegistryError(
                f"Equal-precedence rules {precedence[key]} and {rule['mapping_id']} conflict"
            )
        precedence[key] = rule["mapping_id"]
        source_key = tuple(rule[k] for k in (
            "direction", "entity", "source_vintage", "source_variable",
        ))
        source_rules.setdefault(source_key, []).append(rule)
    for key, rules in source_rules.items():
        compositions = {r.get("composition") for r in rules}
        priorities = {r["rule_priority"] for r in rules}
        if len(rules) > 1 and (
            None in compositions or len(compositions) != 1 or len(priorities) != len(rules)
        ):
            ids = sorted(r["mapping_id"] for r in rules)
            raise RegistryError(f"Multiple applicable rules lack unambiguous composition at {key}: {ids}")


def load_registry() -> dict[str, Any]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    validate_registry(registry)
    return registry


def _stable_frame(df: pd.DataFrame) -> pd.DataFrame:
    sort = [c for c in IDENTIFIERS if c in df.columns]
    out = df.sort_values(sort, kind="mergesort", na_position="last") if sort else df
    preferred = [c for c in IDENTIFIERS if c in out.columns]
    return out[preferred + sorted(c for c in out.columns if c not in preferred)].reset_index(drop=True)


def _normalize(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    return value


def build_reports(
    before: pd.DataFrame,
    after: pd.DataFrame,
    direction: str,
    entity: str,
    emitted_row_ids: set[int],
    sample_limit: int = 10,
) -> tuple[list[dict], dict]:
    rules = [
        r for r in load_registry()["mappings"]
        if r["direction"] == direction and r["entity"] in {entity, "both"}
    ]
    variable = []
    unmatched_categories: list[dict] = []
    collapsed: list[dict] = []
    unmatched_rows: set[int] = set()
    for rule in sorted(rules, key=lambda r: (r["rule_priority"], r["mapping_id"])):
        source, target = rule["source_variable"], rule["target_variable"]
        source_columns = (
            sorted(c for c in before if c.startswith(source[:-1]))
            if source.endswith("*") else ([source] if source in before else [])
        )
        present = bool(source_columns)
        source_values = {
            _normalize(v)
            for column in source_columns for v in before[column].dropna().unique()
        }
        known = set(rule.get("value_map", {}).keys())
        unknown = sorted((v for v in source_values if str(v) not in known), key=lambda x: str(x)) if known else []
        if unknown:
            unmatched_categories.append({"mapping_id": rule["mapping_id"], "values": unknown[:sample_limit], "count": len(unknown)})
            for column in source_columns:
                unmatched_rows.update(
                    int(i) for i in before.index[
                        before[column].map(_normalize).isin(unknown)
                    ] if int(i) in emitted_row_ids
                )
        if rule["status"] in {"collapsed", "ambiguous"}:
            collapsed.append({"mapping_id": rule["mapping_id"], "known_loss": rule["known_loss_or_ambiguity"]})
        variable.append({
            "mapping_id": rule["mapping_id"], "input_present": present,
            "selected_rule": rule["transformation_class"] if present else None,
            "output_present": target in after, "output_type": str(after[target].dtype) if target in after else None,
            "records_affected": int(before[source_columns].notna().any(axis=1).sum()) if present else 0,
            "unmatched_source_values": unknown[:sample_limit], "collapsed_values": rule.get("collapsed_values", {}),
            "nulls_introduced": max(0, int(after[target].isna().sum()) - int(before[source_columns].isna().all(axis=1).sum())) if present and target in after else 0,
            "validation_failures": 0, "status": rule["status"],
        })
    ids = [c for c in IDENTIFIERS if c in before]
    removed_rows = set(map(int, before.index)) - emitted_row_ids
    dispositions = {
        "emitted": emitted_row_ids - unmatched_rows,
        "removed": removed_rows,
        "invalid": set(), "unsupported": set(),
        "unmatched": unmatched_rows, "failed": set(),
    }
    counts = {name: len(dispositions[name]) for name in TERMINAL_DISPOSITIONS}
    accounted = sum(counts.values())
    loss = {
        "schema_version": 1, "sample_limit": sample_limit, "records_input": len(before), "records_output": len(after),
        "records_removed_or_invalidated": len(removed_rows), "removed_identifier_sample": before.loc[sorted(removed_rows), ids].head(sample_limit).to_dict("records") if removed_rows and ids else [],
        "unmatched_categories": unmatched_categories, "ambiguous_rules": [r["mapping_id"] for r in rules if r["status"] == "ambiguous"],
        "duplicate_or_conflicting_mappings": [], "collapsed_information": collapsed,
        "missingness_before": {c: int(before[c].isna().sum()) for c in sorted(before)},
        "missingness_after": {c: int(after[c].isna().sum()) for c in sorted(after)},
        "unsupported_or_skipped_variables": sorted(r["mapping_id"] for r in variable if not r["input_present"]),
        "terminal_dispositions": counts,
        "reconciliation": {
            "equation": "input = emitted + removed + invalid + unsupported + unmatched + failed",
            "input": len(before), "accounted_for": accounted,
            "difference": len(before) - accounted, "reconciled": accounted == len(before),
        },
    }
    return variable, loss


def create_release(input_path: Path, output_dir: Path, direction: str, entity: str, source_vintage: str, region_path: Path | None = None, release_id: str = "fixture-v1", sample_limit: int = 10) -> dict:
    registry = load_registry()
    commit, dirty_worktree, created_at = _git_metadata()
    supported = registry["supported_vintages"].get(direction.split("-to-")[0], [])
    if source_vintage not in supported:
        raise ValueError(f"Unsupported vintage {source_vintage!r}; supported: {supported}")
    before = pd.read_csv(input_path, keep_default_na=True).reset_index(drop=True)
    region = pd.read_csv(region_path) if region_path else None
    fn = {("eph-to-censo", "hogar"): harmonize_hogar, ("eph-to-censo", "individual"): harmonize_individual,
          ("censo-to-eph", "hogar"): censo_to_eph_hogar, ("censo-to-eph", "individual"): censo_to_eph_individual}[(direction, entity)]
    working = before.copy()
    working["_release_row_id"] = working.index
    aligned = fn(working, region)
    emitted_row_ids = set(map(int, aligned.pop("_release_row_id")))
    aligned = _stable_frame(aligned)
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "aligned.csv"
    aligned.to_csv(output, index=False, lineterminator="\n", na_rep="")
    variable, loss = build_reports(before, aligned, direction, entity, emitted_row_ids, sample_limit)
    variable_path, loss_path = output_dir / "variable-report.json", output_dir / "loss-report.json"
    _json(variable_path, variable); _json(loss_path, loss)
    compatibility_path = output_dir / "compatibility.json"
    shutil.copyfile(COMPATIBILITY, compatibility_path)
    inputs = {input_path.name: sha256(input_path)}
    if region_path: inputs[region_path.name] = sha256(region_path)
    artifact_status = "synthetic" if source_vintage.startswith("fixture-") else "candidate"
    file_entries = [
        {"role": role, "path": path.name, "sha256": sha256(path), "bytes": path.stat().st_size}
        for role, path in (
            ("aligned-data", output), ("variable-mapping-report", variable_path),
            ("loss-and-ambiguity-report", loss_path),
            ("compatibility-declaration", compatibility_path),
        )
    ]
    report_entries = [entry for entry in file_entries if entry["role"].endswith("report")]
    input_entries = [{
        "role": "source-data", "artifact_type": f"research.{direction.split('-to-')[0]}-source",
        "release_id": source_vintage, "manifest_sha256": None,
        "path": input_path.name, "sha256": sha256(input_path),
    }]
    if region_path:
        input_entries.append({
            "role": "geography-lookup", "artifact_type": "research.census-geography",
            "release_id": "unversioned-fixture", "manifest_sha256": None,
            "path": region_path.name, "sha256": sha256(region_path),
            "identifier_contract": "research.argentina-dpto/v1",
        })
    manifest = {
        # Shared, cross-repository artifact envelope.
        "manifest_schema": "research-artifact-manifest/v1",
        "artifact_type": "research.eph-census-crosswalk",
        "release_id": release_id, "status": artifact_status,
        "producer": {"repository": "matuteiglesias/eph-censo-aligner", "commit": commit, "dirty_worktree": dirty_worktree},
        "created_at_utc": created_at, "method_version": registry["registry_version"],
        "data_vintage": source_vintage, "inputs": input_entries,
        "files": file_entries, "reports": report_entries,
        "limitations": [
            "Only synthetic fixture-v1 is supported; real source vintages are unsupported.",
            "Mappings and geography overrides are pending methodological review.",
            "Cross-survey conceptual equivalence is not claimed.",
        ],
        "compatibility": {"declaration": compatibility_path.name, "sha256": sha256(compatibility_path)},
        # Crosswalk-specific extension retained for existing consumers.
        "schema_version": 1, "release_id": release_id, "direction": direction, "entity": entity,
        "source_dataset": direction.split("-to-")[0].upper(), "source_vintage": source_vintage,
        "input_hashes": inputs, "mapping_registry_version": registry["registry_version"], "mapping_registry_hash": sha256(REGISTRY),
        "cdm_version": CDM_VERSION, "cdm_hash": sha256(ROOT / "aligner" / "cdm.py"),
        "command": f"crosswalk-release --direction {direction} --entity {entity} --source-vintage {source_vintage}", "git_commit": commit,
        "output_hashes": {entry["path"]: entry["sha256"] for entry in file_entries},
        "row_count": len(aligned), "column_count": len(aligned.columns),
        "crosswalk_reports": {"variable": variable_path.name, "loss": loss_path.name},
        "reviewer_status": "pending",
    }
    _json(output_dir / "manifest.json", manifest)
    return manifest
