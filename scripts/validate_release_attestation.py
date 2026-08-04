#!/usr/bin/env python3
"""Validate release attestation subjects, application contract, and calendar lock."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_app() -> dict:
    text = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
    def get(pattern: str, cast=str):
        match = re.search(pattern, text)
        if not match:
            raise SystemExit(f"Missing Gradle contract pattern: {pattern}")
        return cast(match.group(1))
    return {
        "application_id": get(r'applicationId\s*=\s*"([^"]+)"'),
        "version_name": get(r'versionName\s*=\s*"([^"]+)"'),
        "version_code": get(r'versionCode\s*=\s*(\d+)', int),
        "min_sdk": get(r'minSdk\s*=\s*(\d+)', int),
        "target_sdk": get(r'targetSdk\s*=\s*(\d+)', int),
        "compile_sdk": get(r'compileSdk\s*=\s*(\d+)', int),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("attestation", type=Path)
    parser.add_argument("--artifact", type=Path, action="append", default=[])
    args = parser.parse_args()

    payload = json.loads(args.attestation.read_text(encoding="utf-8"))
    if payload.get("_type") != "https://in-toto.io/Statement/v1":
        raise SystemExit("Invalid attestation _type")
    if payload.get("predicateType") != "https://orthodox-prayers.example/release-qualification/v1":
        raise SystemExit("Invalid predicateType")
    predicate = payload.get("predicate") or {}
    if predicate.get("application") != expected_app():
        raise SystemExit("Attested application contract does not match Gradle")

    calendar = json.loads((ROOT / "canonical/calendar_2026_2050_lock.json").read_text(encoding="utf-8"))
    lock = predicate.get("calendar_lock") or {}
    expected_lock = {
        "policy": calendar["policy"],
        "start": calendar["civil_range"]["start"],
        "end": calendar["civil_range"]["end"],
        "day_count": calendar["civil_range"]["day_count"],
        "file_count": calendar["file_count"],
        "aggregate_sha256": calendar["aggregate_sha256"],
    }
    if lock != expected_lock:
        raise SystemExit("Attested calendar lock does not match immutable calendar lock")

    subjects = {item["name"]: item for item in payload.get("subject", [])}
    for artifact in args.artifact:
        if not artifact.is_file():
            raise SystemExit(f"Missing artifact: {artifact}")
        subject = subjects.get(artifact.name)
        if subject is None:
            raise SystemExit(f"Artifact is not attested: {artifact.name}")
        actual = digest(artifact)
        if subject.get("digest", {}).get("sha256") != actual:
            raise SystemExit(f"Artifact digest mismatch: {artifact.name}")
        if int(subject.get("bytes", -1)) != artifact.stat().st_size:
            raise SystemExit(f"Artifact size mismatch: {artifact.name}")

    print(
        "RELEASE_ATTESTATION_OK "
        f"version={predicate['application']['version_name']} "
        f"calendar_sha256={lock['aggregate_sha256']} subjects={len(subjects)}"
    )


if __name__ == "__main__":
    main()
