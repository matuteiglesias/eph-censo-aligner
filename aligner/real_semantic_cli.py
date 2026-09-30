"""CLI for exact semantic review and named longitudinal composition profiles."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .composition_profiles import (
    PROFILE_REGISTRY_PATH,
    CompositionProfileError,
    load_profile_registry,
    profile_summary,
)
from .longitudinal_composition import (
    LongitudinalCompositionError,
    materialize_longitudinal_profile,
)
from .real_semantic_plane import (
    POLICY_PATH,
    RealSemanticPlaneError,
    load_review_policy,
    materialize_real_plane,
    write_real_review,
)


def _emit(value: object) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _policy_kwargs(args: argparse.Namespace) -> dict:
    return {"policy_path": args.policy} if getattr(args, "policy", None) is not None else {}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="semantic-plane",
        description=(
            "Exact-release EPH/Census semantic review plus named longitudinal "
            "canonical composition-plane materialization."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("review-real", "materialize-real"):
        cmd = sub.add_parser(name)
        cmd.add_argument(
            "--policy",
            type=Path,
            help=(
                "Reviewed semantic policy. Defaults to the qualified "
                "2024-Q3/CPV-2010 policy."
            ),
        )
        cmd.add_argument("--eph-release-root", required=True, type=Path)
        cmd.add_argument("--census-sample-root", required=True, type=Path)
        cmd.add_argument("--output-dir", required=True, type=Path)

    profiles = sub.add_parser(
        "profiles", help="list and validate named C5 composition profiles"
    )
    profiles.add_argument("--policy", type=Path, default=POLICY_PATH)
    profiles.add_argument("--profile-registry", type=Path, default=PROFILE_REGISTRY_PATH)

    longitudinal = sub.add_parser(
        "materialize-longitudinal",
        help="compile one named C5 profile from an exact C2 longitudinal release",
    )
    longitudinal.add_argument("--c2-release-root", required=True, type=Path)
    longitudinal.add_argument("--profile", required=True)
    longitudinal.add_argument("--output-root", required=True, type=Path)
    longitudinal.add_argument("--policy", type=Path, default=POLICY_PATH)
    longitudinal.add_argument(
        "--profile-registry", type=Path, default=PROFILE_REGISTRY_PATH
    )
    longitudinal.add_argument("--chunksize", type=int, default=100_000)
    args = parser.parse_args()

    try:
        if args.command == "review-real":
            output = write_real_review(
                args.eph_release_root,
                args.census_sample_root,
                args.output_dir,
                **_policy_kwargs(args),
            )
        elif args.command == "materialize-real":
            output = materialize_real_plane(
                args.eph_release_root,
                args.census_sample_root,
                args.output_dir,
                **_policy_kwargs(args),
            )
        elif args.command == "profiles":
            policy = load_review_policy(args.policy)
            registry = load_profile_registry(args.profile_registry)
            output = {
                "schema": registry["schema"],
                "profiles": [
                    profile_summary(profile_id, policy, registry=registry)
                    for profile_id in registry["profiles"]
                ],
            }
        else:
            output = materialize_longitudinal_profile(
                args.c2_release_root,
                args.output_root,
                args.profile,
                policy_path=args.policy,
                registry_path=args.profile_registry,
                chunksize=args.chunksize,
            )
    except (
        RealSemanticPlaneError,
        CompositionProfileError,
        LongitudinalCompositionError,
    ) as exc:
        _emit({"status": "failed", "reason": str(exc)})
        raise SystemExit(2) from exc
    if isinstance(output, dict):
        _emit({"status": "complete", **output})
    else:
        _emit({"status": "complete", "output": output})


if __name__ == "__main__":
    main()
