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
            "scripts/ensure_gradlew_executable.py",
            "scripts/run_quality_gate.py --strict-native-lanes",
            "Import latest signed published data for debug APK",
            "origin/verified-data",
            'python scripts/verify.py --expected-date "$PUBLISHED_DATE"',
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

    normalizer = "python scripts/ensure_gradlew_executable.py"
    debug_gate = "python scripts/run_quality_gate.py --strict-native-lanes"
    release_gate = "python scripts/run_quality_gate.py --require-current --strict-native-lanes"
    if build.count(normalizer) < 2:
        fail("Build workflow must normalize gradlew before both quality gates")
    first_normalizer = build.index(normalizer)
    first_gate = build.index(debug_gate)
    second_normalizer = build.index(normalizer, first_normalizer + 1)
    second_gate = build.index(release_gate)
    if not (first_normalizer < first_gate < second_normalizer < second_gate):
        fail("Gradle wrapper normalization must occur before each quality gate")

    update = files["update.yml"].read_text(encoding="utf-8")
    require_all(
        update,
        (
            "scripts/update.py",
            "--unsigned",
            "Generate and validate today without signing key",
            "Validate unsigned language lanes independently",
            "Prepare publication worktree before restoring key",
            "Restore and match the one signing key",
            "Sign and verify generated data",
            "Remove private key before commit or network publication",
            'test ! -e "$RUNNER_TEMP/data-private.pem"',
            "scripts/verify.py",
            "DATA_SIGNING_PRIVATE_KEY_B64",
            "environment: production-data-signing",
            "canonical/signing/data_signing_public_key.pub",
            "cmp -s",
            "The GitHub secret does not match the public key",
            "VERIFIED_DATA_BRANCH: verified-data",
            'timezone: "Asia/Amman"',
            'cron: "0 0 * * *"',
            "Verify from origin after publishing",
            "scripts/sign_language_lanes.py",
            "verified-data-commit-check",
            "git archive HEAD",
            "Open failure alert",
        ),
        "Update workflow",
    )
    if 'cron: "15 0 * * *"' in update:
        fail("Update workflow must run only at 00:00 Asia/Amman, not at 00:15")

    for forbidden in (
        "\n  push:\n",
        "git push origin main",
        "HEAD:main",
        "GEMINI_API_KEY",
        "pull-requests: write",
    ):
        if forbidden in update:
            fail(f"Update workflow contains forbidden behavior: {forbidden.strip()}")

    for pattern in (
        r"scripts/update\.py[^\n]*--private-key",
        r"scripts/update_language_lane\.py[^\n]*--private-key",
    ):
        if re.search(pattern, update):
            fail(f"External-source generation must remain unsigned: {pattern}")

    ordered_markers = (
        "Generate and validate today without signing key",
        "Validate unsigned language lanes independently",
        "Prepare publication worktree before restoring key",
        "Restore and match the one signing key",
        "Sign and verify generated data",
        "Remove private key before commit or network publication",
        "Commit, verify Git blobs, and publish verified-data",
    )
    positions = [update.index(marker) for marker in ordered_markers]
    if positions != sorted(positions):
        fail("Signing key isolation steps are out of order in Update workflow")

    if (ROOT / ".github/dependabot.yml").exists():
        fail("Dependabot version-update configuration must remain disabled")

    print(
        "Workflow validation passed: exactly Build and Update; signing keys are isolated from "
        "external-source generation; debug checks are separated; Update runs only manually "
        "or at 00:00 Asia/Amman"
    )


if __name__ == "__main__":
    main()
