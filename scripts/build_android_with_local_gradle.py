#!/usr/bin/env python3
"""Build Android with a locally supplied, hash-verified Gradle distribution."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROPERTIES = ROOT / "gradle/wrapper/gradle-wrapper.properties"


def wrapper_values() -> tuple[str, str]:
    text = PROPERTIES.read_text(encoding="utf-8")
    url = re.search(r"^distributionUrl=(.+)$", text, re.MULTILINE)
    sha = re.search(r"^distributionSha256Sum=([0-9a-f]{64})$", text, re.MULTILINE)
    if not url or not sha:
        raise RuntimeError("wrapper URL or SHA-256 is missing")
    return url.group(1).replace("\\:", ":"), sha.group(1)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_distribution(path: Path, expected_sha256: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"Gradle distribution not found: {path}")
    actual = file_sha256(path)
    if actual != expected_sha256:
        raise RuntimeError(f"Gradle SHA-256 mismatch: expected {expected_sha256}, got {actual}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if not any(name.endswith("/bin/gradle") for name in names):
            raise RuntimeError("Gradle ZIP has no bin/gradle launcher")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gradle-zip", type=Path, required=True)
    parser.add_argument("--task", default=":app:assembleDebug")
    parser.add_argument("--evidence", type=Path, default=ROOT / "release/android/build-evidence.json")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    distribution_url, expected = wrapper_values()
    verify_distribution(args.gradle_zip, expected)
    if args.verify_only:
        print(f"LOCAL_GRADLE_VERIFIED_OK sha256={expected}")
        return
    with tempfile.TemporaryDirectory(prefix="orthodox-gradle-") as directory:
        work = Path(directory)
        with zipfile.ZipFile(args.gradle_zip) as archive:
            archive.extractall(work)
        launchers = list(work.glob("gradle-*/bin/gradle"))
        if len(launchers) != 1:
            raise RuntimeError("Unable to locate exactly one Gradle launcher")
        launcher = launchers[0]
        launcher.chmod(0o755)
        command = [str(launcher), args.task, "--offline", "--no-daemon", "--stacktrace"]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    apk_files = sorted((ROOT / "app/build/outputs/apk").rglob("*.apk")) if (ROOT / "app/build/outputs/apk").exists() else []
    evidence = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "distribution_url": distribution_url,
        "gradle_sha256": expected,
        "task": args.task,
        "return_code": completed.returncode,
        "success": completed.returncode == 0 and bool(apk_files),
        "apk_files": [{"path": str(path.relative_to(ROOT)), "sha256": file_sha256(path), "bytes": path.stat().st_size} for path in apk_files],
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:]
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not evidence["success"]:
        raise SystemExit(f"Android build failed; evidence written to {args.evidence}")
    print(f"ANDROID_LOCAL_GRADLE_BUILD_OK apks={len(apk_files)} evidence={args.evidence}")


if __name__ == "__main__":
    main()
