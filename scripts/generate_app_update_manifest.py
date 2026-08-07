#!/usr/bin/env python3
"""Generate deterministic GitHub Release metadata for the in-app APK updater."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from release_version import current_release


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checksum-output", type=Path, required=True)
    parser.add_argument("--minimum-supported-version-code", type=int, default=0)
    parser.add_argument("--mandatory", action="store_true")
    args = parser.parse_args()

    apk = args.apk.resolve()
    if not apk.is_file() or apk.stat().st_size < 1:
        raise SystemExit("APP_UPDATE_APK_MISSING")

    version_name, version_code = current_release()
    digest = sha256(apk)
    payload = {
        "schemaVersion": 1,
        "versionCode": version_code,
        "versionName": version_name,
        "minimumSupportedVersionCode": max(0, args.minimum_supported_version_code),
        "mandatory": bool(args.mandatory),
        "apkAsset": "Church-Prayers.apk",
        "sha256": digest,
        "sizeBytes": apk.stat().st_size,
        "generatedAtUtc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.checksum_output.write_text(f"{digest}  Church-Prayers.apk\n", encoding="utf-8")
    print(f"APP_UPDATE_MANIFEST_OK version={version_name} code={version_code} bytes={apk.stat().st_size}")


if __name__ == "__main__":
    main()
