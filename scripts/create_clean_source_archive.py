#!/usr/bin/env python3
"""Create a deterministic clean source ZIP without VCS, caches, builds, or secrets."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".gradle",
    ".idea",
    "build",
    "release",
    "reports",
    "__pycache__",
    ".pytest_cache",
    ".cache",
}
EXCLUDED_SUFFIXES = {".jks", ".keystore", ".p12", ".pfx", ".pem", ".key", ".pyc", ".pyo"}
EXCLUDED_NAMES = {
    "FILE_SHA256SUMS.txt",
    "VERIFICATION_AR.txt",
    "local.properties",
    "GITHUB_SECRETS.txt",
    "اقرأني-أولا-الحزمة-الكاملة.txt",
    ".env",
    ".env.local",
    "id_rsa",
    "id_ed25519",
}
EXCLUDED_PREFIXES = ("COMMIT_MESSAGE", "GITHUB_DESKTOP_COMMIT_MESSAGE")
PUBLIC_SIGNING_KEYS = {"data_signing_public_key.der", "data_signing_public_key.pub"}
SENSITIVE_FRAGMENTS = ("private_key", "private-key", "privatekey", "keystore_password", "signing_secret")


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.is_symlink():
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.name in EXCLUDED_NAMES or path.name.startswith(EXCLUDED_PREFIXES):
        return False

    lower = path.name.lower()
    if any(fragment in lower for fragment in SENSITIVE_FRAGMENTS):
        return False
    if lower.startswith("local.properties") or lower.startswith(".env"):
        return False

    # The data-signing directory may contain local key-generation output. Only
    # the committed public keys are safe and required by the Android client.
    if "data-signing" in relative.parts[:-1]:
        return path.name in PUBLIC_SIGNING_KEYS
    return True


def zip_timestamp() -> tuple[int, int, int, int, int, int]:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw:
        value = dt.datetime.fromtimestamp(int(raw), tz=dt.timezone.utc)
        year = max(1980, min(value.year, 2107))
        return (year, value.month, value.day, value.hour, value.minute, value.second // 2 * 2)
    return (1980, 1, 1, 0, 0, 0)


def unsafe_archive_name(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return not normalized or normalized.startswith("/") or ".." in path.parts or "\x00" in normalized


def validate_archive(output: Path) -> None:
    with zipfile.ZipFile(output) as archive:
        infos = archive.infolist()
        if not infos:
            raise SystemExit("Refusing to publish an empty source archive")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise SystemExit("Duplicate paths found in generated source archive")

        for info in infos:
            name = info.filename
            path = PurePosixPath(name.replace("\\", "/"))
            if unsafe_archive_name(name):
                raise SystemExit(f"Unsafe path in generated archive: {name}")
            if any(part in EXCLUDED_DIRS for part in path.parts):
                raise SystemExit(f"Excluded directory leaked into generated archive: {name}")
            if Path(name).suffix.lower() in EXCLUDED_SUFFIXES:
                raise SystemExit(f"Excluded file type leaked into generated archive: {name}")
            if Path(name).name in EXCLUDED_NAMES or Path(name).name.startswith(EXCLUDED_PREFIXES):
                raise SystemExit(f"Excluded file leaked into generated archive: {name}")
            if any(fragment in Path(name).name.lower() for fragment in SENSITIVE_FRAGMENTS):
                raise SystemExit(f"Sensitive filename leaked into generated archive: {name}")

            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_IFMT(mode) == stat.S_IFLNK:
                raise SystemExit(f"Symbolic link leaked into generated archive: {name}")
            if path.name == "gradlew" and not mode & 0o111:
                raise SystemExit("gradlew is not executable in generated source archive")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--root-name", default="orthodox_prayers")
    args = parser.parse_args()
    if not args.root_name or "/" in args.root_name or "\\" in args.root_name or args.root_name in {".", ".."}:
        raise SystemExit("--root-name must be one safe directory name")

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and included(path) and path.resolve() != output
    )
    timestamp = zip_timestamp()

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = Path(args.root_name) / path.relative_to(ROOT)
            info = zipfile.ZipInfo(relative.as_posix(), date_time=timestamp)
            mode = path.stat().st_mode
            # Always record gradlew as executable. Windows/GitHub web uploads
            # cannot reliably preserve its POSIX execute bit in the worktree.
            is_gradlew = path.relative_to(ROOT).as_posix() == "gradlew"
            permissions = 0o755 if is_gradlew or mode & stat.S_IXUSR else 0o644
            info.create_system = 3
            info.external_attr = (permissions & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())

    validate_archive(output)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    checksum = output.with_suffix(output.suffix + ".sha256")
    checksum.write_text(f"{digest}  {output.name}\n", encoding="utf-8")
    print(f"Created {output}\nFiles: {len(files)}\nSHA-256: {digest}")


if __name__ == "__main__":
    main()
