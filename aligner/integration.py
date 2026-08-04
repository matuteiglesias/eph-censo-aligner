"""Consumer-side validation for immutable crosswalk release directories.

This module uses only the Python standard library so a downstream repository can
validate an artifact before importing pandas or starting preprocessing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

MANIFEST_SCHEMA = "research-artifact-manifest/v1"
ARTIFACT_TYPE = "research.eph-census-crosswalk"
APPROVED_STATUSES = {"reviewed", "approved"}


class CompatibilityError(ValueError):
    """The supplied immutable release cannot satisfy the requested run."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_release(
    manifest_path: Path,
    *,
    requested_mode: str = "synthetic",
    expected_vintage: str | None = None,
    expected_manifest_sha256: str | None = None,
    expected_input_manifests: Mapping[str, str] | None = None,
    geography_identifier_contract: str | None = None,
) -> dict[str, Any]:
    """Validate schema, identity, policy, compatibility, and every file hash."""
    if requested_mode not in {"synthetic", "real", "approved"}:
        raise CompatibilityError(f"Unknown requested mode: {requested_mode}")
    if expected_manifest_sha256 and _sha256(manifest_path) != expected_manifest_sha256:
        raise CompatibilityError("Manifest checksum mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("manifest_schema") != MANIFEST_SCHEMA:
        raise CompatibilityError(
            f"Unsupported manifest schema {manifest.get('manifest_schema')!r}; expected {MANIFEST_SCHEMA}"
        )
    if manifest.get("artifact_type") != ARTIFACT_TYPE:
        raise CompatibilityError(f"Unexpected artifact type: {manifest.get('artifact_type')!r}")
    if expected_vintage and manifest.get("data_vintage") != expected_vintage:
        raise CompatibilityError(
            f"Unsupported source vintage {manifest.get('data_vintage')!r}; expected {expected_vintage!r}"
        )
    if requested_mode == "approved" and (
        manifest.get("status") not in APPROVED_STATUSES
        or manifest.get("reviewer_status") != "approved"
    ):
        raise CompatibilityError("Approved mode requires an approved methodological release")
    if requested_mode in {"real", "approved"} and manifest.get("status") == "synthetic":
        raise CompatibilityError("A synthetic crosswalk cannot be consumed by a real run")

    root = manifest_path.resolve().parent
    for entry in manifest.get("files", []):
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise CompatibilityError(f"Unsafe artifact path: {relative}")
        path = (root / relative).resolve()
        if path.parent != root or not path.is_file():
            raise CompatibilityError(f"Artifact file is missing: {relative}")
        if path.stat().st_size != entry.get("bytes") or _sha256(path) != entry.get("sha256"):
            raise CompatibilityError(f"Artifact checksum mismatch: {relative}")

    inputs = {entry["role"]: entry for entry in manifest.get("inputs", [])}
    for role, expected_hash in (expected_input_manifests or {}).items():
        actual = inputs.get(role, {}).get("manifest_sha256")
        if actual != expected_hash:
            raise CompatibilityError(f"Input manifest checksum mismatch for role {role}")
    if geography_identifier_contract:
        actual = inputs.get("geography-lookup", {}).get("identifier_contract")
        if actual != geography_identifier_contract:
            raise CompatibilityError(
                f"Incompatible geography identifier contract {actual!r}; expected {geography_identifier_contract!r}"
            )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a self-contained crosswalk release")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--mode", choices=["synthetic", "real", "approved"], default="synthetic")
    parser.add_argument("--expected-vintage")
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--geography-identifier-contract")
    args = parser.parse_args()
    validate_release(
        args.manifest, requested_mode=args.mode,
        expected_vintage=args.expected_vintage,
        expected_manifest_sha256=args.expected_manifest_sha256,
        geography_identifier_contract=args.geography_identifier_contract,
    )


if __name__ == "__main__":
    main()
