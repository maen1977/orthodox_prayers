#!/usr/bin/env python3
"""Create a deterministic clean source ZIP without VCS, caches, builds, or secrets."""
from __future__ import annotations

import argparse
import hashlib
import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {".git", ".gradle", ".idea", "build", "release", "reports", "__pycache__", ".pytest_cache", ".cache"}
EXCLUDED_SUFFIXES = {".jks", ".keystore", ".p12", ".pem", ".key", ".pyc", ".pyo"}


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    lower = path.name.lower()
    return ("private_key" not in lower and not lower.startswith("local.properties")
            and lower not in {"file_sha256sums.txt", "verification_ar.txt"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and included(path) and path.resolve() != output)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = Path(ROOT.name) / path.relative_to(ROOT)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=(2026, 7, 14, 0, 0, 0))
            mode = path.stat().st_mode
            permissions = 0o755 if mode & stat.S_IXUSR else 0o644
            info.external_attr = (permissions & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"Created {output}\nSHA-256: {digest}")


if __name__ == "__main__":
    main()
