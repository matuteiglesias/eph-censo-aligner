"""CLI for exact real EPH/Census semantic review and feature-plane policies."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .real_semantic_plane import (
    RealSemanticPlaneError,
    materialize_real_plane,
    write_real_review,
)


def _emit(value: object) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="semantic-plane",
        description=(
            "Exact-release real EPH/Census semantic review and canonical "
            "feature-plane materialization from a pinned review policy."
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
    args = parser.parse_args()

    try:
        if args.command == "review-real":
            output = write_real_review(
                args.eph_release_root,
                args.census_sample_root,
                args.output_dir,
                **({"policy_path": args.policy} if args.policy is not None else {}),
            )
        else:
            output = materialize_real_plane(
                args.eph_release_root,
                args.census_sample_root,
                args.output_dir,
                **({"policy_path": args.policy} if args.policy is not None else {}),
            )
    except RealSemanticPlaneError as exc:
        _emit({"status": "failed", "reason": str(exc)})
        raise SystemExit(2) from exc
    _emit({"status": "complete", **output})


if __name__ == "__main__":
    main()
