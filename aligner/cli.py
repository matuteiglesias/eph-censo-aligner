"""Command line interface for a versioned crosswalk release."""
import argparse
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--direction", required=True, choices=["eph-to-censo", "censo-to-eph"])
    parser.add_argument("--entity", required=True, choices=["hogar", "individual"])
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--source-vintage", required=True)
    parser.add_argument("--region", type=Path)
    parser.add_argument("--release-id", default="crosswalk-v1")
    parser.add_argument("--sample-limit", type=int, default=10)
    args = parser.parse_args()
    # Keep `--help` and offline interface checks independent of heavy runtime
    # dependencies; actual release execution still requires the installed extra.
    from .release import create_release

    create_release(args.input, args.output_dir, args.direction, args.entity, args.source_vintage, args.region, args.release_id, args.sample_limit)


if __name__ == "__main__":
    main()
