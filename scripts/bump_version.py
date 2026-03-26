"""Semantic version helper for pyproject.toml."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VERSION_RE = re.compile(r'^(version\s*=\s*")(?P<ver>\d+\.\d+\.\d+)("\s*)$', re.MULTILINE)


def parse_version(version: str) -> tuple[int, int, int]:
    parts = version.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Invalid semver: {version}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump_semver(version: str, bump: str) -> str:
    major, minor, patch = parse_version(version)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Unsupported bump type: {bump}")


def read_current_version(pyproject_path: Path) -> str:
    content = pyproject_path.read_text(encoding="utf-8")
    match = VERSION_RE.search(content)
    if not match:
        raise RuntimeError("Could not locate project version in pyproject.toml")
    return match.group("ver")


def write_version(pyproject_path: Path, new_version: str) -> None:
    content = pyproject_path.read_text(encoding="utf-8")

    def _replace(match: re.Match[str]) -> str:
        return f"{match.group(1)}{new_version}{match.group(3)}"

    updated, count = VERSION_RE.subn(_replace, content, count=1)
    if count != 1:
        raise RuntimeError("Failed to update version in pyproject.toml")
    pyproject_path.write_text(updated, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump or set pyproject.toml version.")
    parser.add_argument("--file", default="pyproject.toml", help="Path to pyproject.toml")
    parser.add_argument("--bump", choices=["patch", "minor", "major"])
    parser.add_argument("--set-version")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--current", action="store_true")
    args = parser.parse_args()

    pyproject_path = Path(args.file)
    if not pyproject_path.exists():
        raise FileNotFoundError(pyproject_path)

    current_version = read_current_version(pyproject_path)
    if args.current:
        print(current_version)
        return 0

    if bool(args.bump) == bool(args.set_version):
        parser.error("Provide exactly one of --bump or --set-version")

    new_version = args.set_version or bump_semver(current_version, args.bump)
    parse_version(new_version)

    if args.write and new_version != current_version:
        write_version(pyproject_path, new_version)

    print(new_version)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
