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
            'python scripts/validate_verified_data_contract.py --root "$VERIFIED_DIR"',
            'python scripts/verify.py --expected-date "$PUBLISHED_DATE" --allow-missing-manifest --allow-compatible-manifest-version',
            "verified-data requires a nine-day upgrade",
            "Building debug with the signed embedded bootstrap",
            "the next scheduled Rolling Liturgical Window Update will republish verified-data",
            "wrapper-validation@",
            "name: Android unit tests",
            "testDebugUnitTest --stacktrace",
            "Android emulator, offline fallback, and store screenshots",
            "play-store-screenshots",
            "actions/download-artifact@",
            "build_play_store_release_package.py",
            "PLAY_SUPPORT_EMAIL",
            "api_level: [29, 35]",
            "validate_release_permissions.py",
            "emulator-boot-timeout: 900",
            "ram-size: 2048M",
            "heap-size: 512M",
            'script: bash scripts/run_android_emulator_ci.sh "${{ matrix.api_level }}"',
            "name: Android debug lint",
            "lintDebug --stacktrace",
            "name: Build debug APK",
            "assembleDebug --stacktrace",
            "name: Prepare branded debug APK",
            'cp app/build/outputs/apk/debug/app-debug.apk "release/Church-Prayers-$APP_VERSION-debug.apk"',
            "Church-Prayers-${{ env.APP_VERSION }}-debug.apk",
            "Church-Prayers.ico",
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
            'release/Church-Prayers-$RELEASE_VERSION.apk',
            'release/Church-Prayers-$RELEASE_VERSION.aab',
            "name: Church-Prayers-${{ env.RELEASE_VERSION }}-signed",
        ),
        "Build workflow",
    )
    if "script: |" in build.split("Run instrumentation and capture Arabic, English, and Greek screens", 1)[1].split("Upload generated Play Store screenshots", 1)[0]:
        fail("android-emulator-runner must invoke one repository Bash script, not a multiline script block")

    emulator_script = ROOT / "scripts/run_android_emulator_ci.sh"
    if not emulator_script.is_file():
        fail("Missing scripts/run_android_emulator_ci.sh")
    emulator_text = emulator_script.read_text(encoding="utf-8")
    require_all(
        emulator_text,
        (
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "adb wait-for-device",
            "sys.boot_completed",
            "ro.build.version.sdk",
            "pm path android",
            "stable >= 3",
            "connectedDebugAndroidTest --stacktrace",
            "validate_play_store_assets.py --require-screenshots",
        ),
        "Android emulator CI script",
    )
    for forbidden in ("svc wifi disable", "svc data disable", "svc wifi enable", "svc data enable"):
        if forbidden in emulator_text:
            fail("Host emulator script must not mutate Android network services before DDMLib device discovery")

    reader_smoke = ROOT / "app/src/androidTest/java/com/orthodoxprayers/privateapp/ReaderSmokeTest.java"
    if not reader_smoke.is_file():
        fail("Missing ReaderSmokeTest.java")
    reader_text = reader_smoke.read_text(encoding="utf-8")
    require_all(
        reader_text,
        (
            "@BeforeClass",
            'runShellCommand("svc wifi disable")',
            'runShellCommand("svc data disable")',
            "NET_CAPABILITY_VALIDATED",
            "@AfterClass",
            'runShellCommand("svc wifi enable")',
            'runShellCommand("svc data enable")',
        ),
        "Offline reader instrumentation",
    )

    upload_debug_block = build.split("- name: Upload Church Prayers debug APK and reports", 1)[1].split("  release:", 1)[0]
    if "app/build/outputs/apk/debug/app-debug.apk" in upload_debug_block:
        fail("Raw app-debug.apk must not be exposed in the downloadable artifact")

    for forbidden in (
        "github/codeql-action/",
        "testDebugUnitTest lintDebug lintRelease",
    ):
        if forbidden in build:
            fail(f"Build workflow still contains temporarily disabled behavior: {forbidden}")

    normalizer = "python scripts/ensure_gradlew_executable.py"
    debug_gate = "python scripts/run_quality_gate.py --strict-native-lanes"
    release_gate = "python scripts/run_quality_gate.py --require-current --strict-native-lanes"
    if build.count(normalizer) < 2:
        fail("Build workflow must normalize gradlew before both quality gates")
    published_data_migration = 'python scripts/clean_legacy_calendar_snapshots.py --root "$VERIFIED_DIR"'
    if build.count(published_data_migration) < 2:
        fail("Build workflow must migrate legacy verified-data aliases in both debug and release imports")
    verified_contract = 'python scripts/validate_verified_data_contract.py --root "$VERIFIED_DIR"'
    if build.count(verified_contract) < 2:
        fail("Build workflow must preflight the rolling-window verified-data contract before both imports")
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
            "Prepare exact native Scripture horizon",
            "scripts/prepare_rolling_week_scripture_slice.py",
            "Generate and validate moving horizon without signing key",
            "--window-days",
            "ORTHODOX_ROLLING_WINDOW_DAYS",
            "Validate unsigned language lanes independently",
            "Prepare publication worktree before restoring key",
            "Preserve complete same-day language lanes",
            "scripts/preserve_same_day_language_lanes.py",
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
            'cron: "23 4 * * *"',
            'cron: "43 16 * * *"',
            "Verify from origin after publishing",
            "Verify public HTTPS update endpoint",
            "scripts/verify_public_update_endpoints.py",
            "scripts/sign_language_lanes.py",
            "scripts/build_update_manifest.py",
            "scripts/sign_update_manifest.py",
            "scripts/verify_update_manifest.py",
            "scripts/validate_publication_consistency.py",
            'rsync -a --delete "$SOURCE/scripts/" "$TARGET/scripts/"',
            'test -f "$TARGET/scripts/validate_rolling_week.py"',
            'test -f "$TARGET/scripts/validate_reader_services.py"',
            "canonical/update_contract.json",
            "Require one consistent unsigned publication date",
            "verified-data-commit-check",
            "git archive HEAD",
            "Automated religious evidence and cross-source decision gate",
            "scripts/validate_automated_religious_evidence.py",
            "scripts/validate_source_comparison.py",
            "scripts/compare_source_snapshots.py",
            "canonical/source_comparison_policy.json",
            "Close recovered source-update alert",
            "Open failure alert",
        ),
        "Update workflow",
    )

    for forbidden in (
        "--require-reviewed-propers",
        "Block signing until all daily propers are reviewed",
        "human review required",
    ):
        if forbidden.lower() in update.lower():
            fail(f"Update workflow still depends on manual religious review: {forbidden}")

    if update.count('timezone: "Asia/Amman"') != 2:
        fail("Both daily updates must use the Asia/Amman timezone")
    if update.count('cron: "23 4 * * *"') != 1 or update.count('cron: "43 16 * * *"') != 1:
        fail("Update workflow must publish exactly twice daily at 04:23 and 16:43 Asia/Amman")

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
        "Generate and validate moving horizon without signing key",
        "Validate unsigned language lanes independently",
        "Automated religious evidence and cross-source decision gate",
        "Prepare publication worktree before restoring key",
        "Preserve complete same-day language lanes",
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
        "external-source generation; automatic source comparison is fail-closed; Android "
        "instrumentation and multilingual screenshots are required; Update runs only manually "
        "or twice daily at 04:23 and 16:43 Asia/Amman"
    )


if __name__ == "__main__":
    main()
