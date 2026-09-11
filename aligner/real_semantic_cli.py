"""CLI for the exact real EPH/CPV semantic review and feature plane."""
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
        description="Exact-release real EPH/CPV semantic review and canonical feature-plane materialization.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("review-real", "materialize-real"):
        cmd = sub.add_parser(name)
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
            )
        else:
            output = materialize_real_plane(
                args.eph_release_root,
                args.census_sample_root,
                args.output_dir,
            )
    except RealSemanticPlaneError as exc:
        _emit({"status": "failed", "reason": str(exc)})
        raise SystemExit(2) from exc
    _emit({"status": "complete", **output})


if __name__ == "__main__":
    main()
