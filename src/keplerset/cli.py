from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from .models import ElementSetProfile
from .service import export_profile
from .storage import load_profiles


def _find_profile(name: str) -> ElementSetProfile:
    for profile in load_profiles():
        if profile.name.casefold() == name.casefold():
            return profile
    raise SystemExit(f"No saved profile named {name!r} was found.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export a saved KeplerSet profile using the Space-Track GP API."
    )
    parser.add_argument("--profile", required=True, help="Saved profile name")
    parser.add_argument(
        "--identity",
        default=os.environ.get("SPACETRACK_IDENTITY", ""),
        help="Space-Track username/e-mail (or SPACETRACK_IDENTITY)",
    )
    parser.add_argument(
        "--password-env",
        default="SPACETRACK_PASSWORD",
        help="Environment variable containing the password (default: SPACETRACK_PASSWORD)",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        help="Base directory for relative output paths (default: current directory)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    identity = args.identity.strip()
    if not identity:
        identity = input("Space-Track identity: ").strip()
    password = os.environ.get(args.password_env, "")
    if not password:
        password = getpass.getpass("Space-Track password: ")
    profile = _find_profile(args.profile)
    base_dir = args.base_dir if args.base_dir is not None else Path.cwd()
    try:
        outcome = export_profile(
            profile,
            identity,
            password,
            base_dir=base_dir,
            progress=lambda msg: print(msg, file=sys.stderr),
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(str(outcome.output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
