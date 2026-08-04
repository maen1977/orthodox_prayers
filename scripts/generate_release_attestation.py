#!/usr/bin/env python3
"""Generate a deterministic release qualification attestation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".gradle", "build", "__pycache__", ".pytest_cache"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".class", ".apk", ".aab"}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_manifest(root: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    count = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        if relative.parts and relative.parts[0] == "release":
            continue
        file_hash = digest(path)
        h.update(relative.as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(file_hash.encode("ascii"))
        h.update(b"\n")
        count += 1
    return h.hexdigest(), count


def gradle_contract() -> dict:
    text = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
    def number(name: str) -> int:
        match = re.search(rf"\b{name}\s*=\s*(\d+)", text)
        if not match:
            raise SystemExit(f"Missing {name} in app/build.gradle.kts")
        return int(match.group(1))
    version = re.search(r'versionName\s*=\s*"([^"]+)"', text)
    app_id = re.search(r'applicationId\s*=\s*"([^"]+)"', text)
    if not version or not app_id:
        raise SystemExit("Missing applicationId/versionName")
    return {
        "application_id": app_id.group(1),
        "version_name": version.group(1),
        "version_code": number("versionCode"),
        "min_sdk": number("minSdk"),
        "target_sdk": number("targetSdk"),
        "compile_sdk": number("compileSdk"),
    }


def artifact_subject(path: Path) -> dict:
    return {"name": path.name, "digest": {"sha256": digest(path)}, "bytes": path.stat().st_size}


def load_optional(path: Path | None) -> dict | None:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--aab", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--artifact-report", type=Path)
    parser.add_argument("--size-report", type=Path)
    parser.add_argument("--sbom", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    for path in (args.apk, args.aab, args.source_zip):
        if not path.is_file():
            raise SystemExit(f"Missing artifact: {path}")

    calendar = json.loads((ROOT / "canonical/calendar_2026_2050_lock.json").read_text(encoding="utf-8"))
    source_sha, source_files = source_manifest(ROOT)
    app = gradle_contract()
    subjects = [artifact_subject(args.apk), artifact_subject(args.aab), artifact_subject(args.source_zip)]
    if args.sbom is not None:
        subjects.append(artifact_subject(args.sbom))

    timestamp = os.environ.get("SOURCE_DATE_EPOCH")
    if timestamp:
        generated = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat()
    else:
        generated = datetime.now(timezone.utc).isoformat()

    statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": subjects,
        "predicateType": "https://orthodox-prayers.example/release-qualification/v1",
        "predicate": {
            "generated_at": generated,
            "application": app,
            "source": {"sha256": source_sha, "file_count": source_files},
            "calendar_lock": {
                "policy": calendar["policy"],
                "start": calendar["civil_range"]["start"],
                "end": calendar["civil_range"]["end"],
                "day_count": calendar["civil_range"]["day_count"],
                "file_count": calendar["file_count"],
                "aggregate_sha256": calendar["aggregate_sha256"],
            },
            "quality": {
                "artifact_report": load_optional(args.artifact_report),
                "size_report": load_optional(args.size_report),
            },
            "builder": {
                "github_repository": os.environ.get("GITHUB_REPOSITORY"),
                "github_run_id": os.environ.get("GITHUB_RUN_ID"),
                "github_sha": os.environ.get("GITHUB_SHA"),
                "github_ref": os.environ.get("GITHUB_REF"),
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(statement, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"RELEASE_ATTESTATION_CREATED output={args.output} subjects={len(subjects)} source_files={source_files}")


if __name__ == "__main__":
    main()
