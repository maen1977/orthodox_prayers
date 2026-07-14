#!/usr/bin/env python3
"""Validate the two-workflow GitHub Actions contract used by the repository."""
from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github/workflows"
EXPECTED = {"build.yml", "update.yml"}
FULL_SHA = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


def fail(message: str) -> None:
    raise SystemExit(message)


def require_all(text: str, items: tuple[str, ...], label: str) -> None:
    for item in items:
        if item not in text:
            fail(f"{label} is missing: {item}")


def main() -> None:
    files = {path.name: path for path in WORKFLOW_DIR.glob("*.yml")}
    if set(files) != EXPECTED:
        fail(f"Expected exactly {sorted(EXPECTED)}; found {sorted(files)}")

    for name, path in sorted(files.items()):
        text = path.read_text(encoding="utf-8")
        try:
            yaml.compose(text)
        except yaml.YAMLError as exc:
            fail(f"Invalid YAML in {name}: {exc}")
        if "\t" in text:
            fail(f"Tabs are not allowed in {name}")
        for action in re.findall(r"uses:\s*([^\s#]+)", text):
            if not FULL_SHA.match(action):
                fail(f"Action is not pinned to a full SHA in {name}: {action}")

    build = files["build.yml"].read_text(encoding="utf-8")
    require_all(
        build,
        (
            "scripts/run_quality_gate.py --strict-native-lanes",
            "wrapper-validation@",
            "name: Android unit tests",
            "testDebugUnitTest --stacktrace",
            "name: Android debug lint",
            "lintDebug --stacktrace",
            "name: Build debug APK",
            "assembleDebug --stacktrace",
            "app/build/outputs/apk/debug/app-debug.apk",
            "SHA256SUMS.txt",
            "chmod +x ./gradlew",
            "environment: production",
            "ANDROID_KEYSTORE_B64",
            "assembleRelease bundleRelease",
            "apksigner",
            "RELEASE_VERSION",
            "origin/verified-data",
            "--require-current --strict-native-lanes",
            "Tag/version mismatch",
            "publish_release",
        ),
        "Build workflow",
    )
    for forbidden in (
        "github/codeql-action/",
        "android-emulator-runner@",
        "connectedDebugAndroidTest",
        "assembleDebugAndroidTest",
        "testDebugUnitTest lintDebug lintRelease",
    ):
        if forbidden in build:
            fail(f"Build workflow still contains temporarily disabled behavior: {forbidden}")

    update = files["update.yml"].read_text(encoding="utf-8")
    require_all(
        update,
        (
            "name: 00:00 update, validate, sign, publish",
            "name: 00:15 verify published update",
            "scripts/update_liturgical_data.py",
            "scripts/orthodox_integrity.py --apply",
            "scripts/enforce_native_daily_lanes.py",
            "scripts/build_search_index.py",
            "scripts/validate_native_source_contract.py",
            "scripts/validate_daily_native_content.py",
            "scripts/verify_published_daily.py",
            "DATA_SIGNING_PRIVATE_KEY_B64",
            "scripts/sign_daily_data.py",
            "VERIFIED_DATA_BRANCH: verified-data",
            "HEAD:refs/heads/$VERIFIED_DATA_BRANCH",
            'timezone: "Asia/Amman"',
            'cron: "0 0 * * *"',
            'cron: "15 0 * * *"',
            "Enforce independent native-language lanes",
            "Trigger one repair attempt",
            "gh workflow run update.yml",
            "Open or update failure alert",
        ),
        "Update workflow",
    )
    for forbidden in (
        "\n  push:\n",
        "git push origin main",
        "HEAD:main",
        "GEMINI_API_KEY",
        "pull-requests: write",
    ):
        if forbidden in update:
            fail(f"Update workflow contains forbidden behavior: {forbidden.strip()}")

    if (ROOT / ".github/dependabot.yml").exists():
        fail("Dependabot version-update configuration must remain disabled")

    print(
        "Workflow validation passed: exactly Build and Update; no Dependabot version updates; "
        "debug checks are separated; Update runs only manually or at 00:00/00:15 Asia/Amman"
    )


if __name__ == "__main__":
    main()
