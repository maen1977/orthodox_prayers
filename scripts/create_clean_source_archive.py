#!/usr/bin/env python3
"""Create a deterministic, secret-safe source ZIP without Git history or caches."""
from __future__ import annotations

import argparse
import hashlib
import os
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".gradle", ".idea", ".pytest_cache", "pytest-of-root", "__pycache__", ".cache", "build", ".venv", "venv"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".jks", ".keystore", ".p12", ".pfx", ".pem", ".key", ".zip", ".apk", ".aab"}
EXCLUDED_NAMES = {"local.properties", ".DS_Store"}


def include(path: Path) -> bool:
    rel = path.relative_to(ROOT)
    if rel.parts and (
        rel.parts[0].startswith("tmp")
        or rel.parts[0].startswith("orthodox-calendar-cleanup-")
        or rel.parts[0].startswith("orthodox-r17-")
    ):
        return False
    # Preserve only stable, public branding sources from release/. Generated
    # APKs, reports, checksums, and signing material remain excluded.
    if rel.parts and rel.parts[0] == "release":
        if len(rel.parts) < 3 or rel.parts[1] != "branding":
            return False
    if any(part in EXCLUDED_DIRS for part in rel.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.name.startswith("COMMIT_MESSAGE") or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.name.endswith((".zip.sha256", ".apk.sha256", ".aab.sha256")):
        return False
    if path.name.endswith(".tmp") or path.name.endswith("~"):
        return False
    return path.is_file()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_positional", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prefix", default="orthodox_prayers")
    parser.add_argument(
        "--root-layout",
        action="store_true",
        help="store repository-relative paths without a wrapper directory",
    )
    args = parser.parse_args()
    selected = args.output or args.output_positional
    if selected is None:
        parser.error("an output ZIP path is required")
    output = selected if selected.is_absolute() else ROOT / selected
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_name(output.name + ".tmp")

    files = sorted((path for path in ROOT.rglob("*") if include(path)), key=lambda p: p.as_posix())
    with zipfile.ZipFile(temporary_output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            archive_name = relative if args.root_layout else f"{args.prefix.strip('/')}/{relative}"
            info = zipfile.ZipInfo(archive_name, date_time=(2026, 7, 17, 0, 0, 0))
            mode = 0o755 if path.name == "gradlew" or os.access(path, os.X_OK) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    # Publish the completed archive atomically. Explicit fsync avoids a caller
    # observing a delayed/truncated ZIP on hosted and synchronized filesystems.
    with temporary_output.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary_output, output)
    directory_fd = os.open(output.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    with checksum.open("rb") as handle:
        os.fsync(handle.fileno())
    print(f"Clean source archive created: {output} ({len(files)} files; sha256={digest})")


if __name__ == "__main__":
    main()
