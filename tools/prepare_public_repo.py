"""Prepare an allowlisted public repository payload.

The generated directory is intended for a separate public GitHub repository that
hosts documentation, issue templates, screenshots, and release binaries without
exposing the private source tree.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "public_release" / "j1939-pcan-simulator-public"
PUBLIC_TEMPLATE_DIR = ROOT / "docs" / "public"
SCREENSHOT_DIR = ROOT / "docs" / "images"
EXE_PATH = ROOT / "dist" / "J1939_Simulator.exe"
RELEASE_NOTES = ROOT / "RELEASE_NOTES.md"

FORBIDDEN_SUFFIXES = {".py", ".pyc", ".pyo", ".spec"}
FORBIDDEN_NAMES = {
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "configs",
    "gui",
    "tests",
    "tools",
}


def prepare_public_repo(output: Path, include_exe: bool = False) -> None:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    _copy_tree(PUBLIC_TEMPLATE_DIR, output)

    if RELEASE_NOTES.exists():
        shutil.copy2(RELEASE_NOTES, output / "RELEASE_NOTES.md")

    if SCREENSHOT_DIR.exists():
        _copy_tree(SCREENSHOT_DIR, output / "docs" / "images")

    if include_exe and EXE_PATH.exists():
        release_dir = output / "release-assets"
        release_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(EXE_PATH, release_dir / EXE_PATH.name)

    _write_public_gitignore(output)
    _assert_no_forbidden_files(output)


def _copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    for path in source.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)


def _write_public_gitignore(output: Path) -> None:
    (output / ".gitignore").write_text(
        "\n".join(
            [
                "Thumbs.db",
                ".DS_Store",
                "*.log",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _assert_no_forbidden_files(output: Path) -> None:
    for path in output.rglob("*"):
        relative_parts = set(path.relative_to(output).parts)
        if relative_parts & FORBIDDEN_NAMES:
            raise RuntimeError(f"Forbidden path in public export: {path}")
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise RuntimeError(f"Forbidden source-like file in public export: {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory for the public repository payload.",
    )
    parser.add_argument(
        "--include-exe",
        action="store_true",
        help="Copy dist/J1939_Simulator.exe into release-assets when present.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prepare_public_repo(args.output, include_exe=args.include_exe)
    print(f"Prepared public repository payload: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
