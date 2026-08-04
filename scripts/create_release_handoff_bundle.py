#!/usr/bin/env python3
"""Create a deterministic, secret-free handoff ZIP for one qualified release."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

FORBIDDEN_SUFFIXES = {".jks", ".keystore", ".p12", ".pfx", ".pem", ".key", ".env"}
FORBIDDEN_NAMES = {"id_rsa", "id_ed25519", "service-account.json", "google-services.json"}
REQUIRED_TEMPLATES = (
    "Church-Prayers-{version}.apk",
    "Church-Prayers-{version}.aab",
    "Church-Prayers-{version}-source.zip",
    "Church-Prayers-{version}-sbom.cdx.json",
    "RELEASE_ARTIFACT_REPORT.json",
    "RELEASE_ATTESTATION.json",
    "RELEASE_SIZE_REPORT.json",
    "RELEASE_PERMISSIONS.txt",
)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_file(path: Path) -> bool:
    return path.name.lower() not in FORBIDDEN_NAMES and path.suffix.lower() not in FORBIDDEN_SUFFIXES


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", args.version):
        raise SystemExit(f"Invalid version: {args.version}")
    release_dir = args.release_dir.resolve()
    if not release_dir.is_dir():
        raise SystemExit(f"Missing release directory: {release_dir}")

    required = [release_dir / template.format(version=args.version) for template in REQUIRED_TEMPLATES]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing required release files: {missing}")

    files = sorted(
        path for path in release_dir.rglob("*")
        if path.is_file() and path.resolve() != args.output.resolve()
    )
    unsafe = [str(path.relative_to(release_dir)) for path in files if not safe_file(path)]
    if unsafe:
        raise SystemExit(f"Secret-like files are forbidden in release handoff: {unsafe}")

    manifest = {
        "schema_version": 1,
        "version": args.version,
        "files": [
            {
                "path": path.relative_to(release_dir).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
            for path in files
        ],
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(release_dir).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo("RELEASE_HANDOFF_MANIFEST.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, manifest_bytes)

    print(f"RELEASE_HANDOFF_OK output={args.output} files={len(files)} sha256={digest(args.output)}")


if __name__ == "__main__":
    main()
