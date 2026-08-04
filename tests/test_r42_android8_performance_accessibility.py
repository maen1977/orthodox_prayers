from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_branding_assets_are_present_in_clean_source() -> None:
    branding = ROOT / "release/branding"
    assert (branding / "Church-Prayers.ico").stat().st_size > 10_000
    assert (branding / "Church-Prayers-icon-512.png").stat().st_size > 10_000
    assert (branding / "Church-Prayers-transparent-1024.png").stat().st_size > 10_000


def test_android8_low_memory_runtime_lane_blocks_release() -> None:
    workflow = read(".github/workflows/build.yml")
    legacy = workflow.split("  android_legacy:", 1)[1].split("\n  release:", 1)[0]
    assert "api-level: 26" in legacy
    assert "ram-size: 1024M" in legacy
    assert "heap-size: 192M" in legacy
    assert "script: bash scripts/run_android_emulator_ci.sh 26 smoke" in legacy
    assert "AccessibilitySmokeTest" not in legacy  # Class filtering belongs in the runner.
    assert "android_compatibility" in workflow
    assert "android_upgrade" in workflow
    assert "android_resilience" in workflow


def test_runtime_runner_supports_android8_and_current_android() -> None:
    runner = read("scripts/run_android_emulator_ci.sh")
    assert "26|29|33|35" in runner
    assert "full|smoke" in runner
    assert "AccessibilitySmokeTest" in runner
    assert "collect_android_runtime_metrics.sh" in runner
    subprocess.run(["bash", "-n", str(ROOT / "scripts/run_android_emulator_ci.sh")], check=True)
    subprocess.run(["bash", "-n", str(ROOT / "scripts/collect_android_runtime_metrics.sh")], check=True)


def test_accessibility_runtime_guard_and_48dp_reader_toggle() -> None:
    reader = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ReaderScreen.java")
    test = read("app/src/androidTest/java/com/orthodoxprayers/privateapp/AccessibilitySmokeTest.java")
    assert "controlsHandle.setMinHeight(ui.dp(48));" in reader
    assert "controlsHandle.setMinimumHeight(ui.dp(48));" in reader
    assert "MINIMUM_TOUCH_TARGET_DP = 48" in test
    assert '.putFloat("font_scale", 1.65f)' in test
    assert "homeAndReaderKeepAccessibleTouchTargetsAtLargeText" in test


def test_performance_parser_enforces_api_specific_budgets(tmp_path: Path) -> None:
    start = tmp_path / "start.txt"
    meminfo = tmp_path / "meminfo.txt"
    output = tmp_path / "metrics.json"
    start.write_text(
        "Status: ok\nLaunchState: COLD\nTotalTime: 1234\nWaitTime: 1260\n",
        encoding="utf-8",
    )
    meminfo.write_text(" App Summary\n TOTAL PSS: 54321\n", encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/parse_android_runtime_metrics.py"),
            "--api-level",
            "26",
            "--start-output",
            str(start),
            "--meminfo-output",
            str(meminfo),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
    )
    metrics = json.loads(output.read_text(encoding="utf-8"))
    assert metrics["status"] == "PASS"
    assert metrics["cold_start_total_time_ms"] == 1234
    assert metrics["total_pss_kb"] == 54321


def test_android8_security_floor_and_calendar_lock_remain_unchanged() -> None:
    build = read("app/build.gradle.kts")
    assert "minSdk = 26" in build
    assert "targetSdk = 36" in build
    assert "compileSdk = 36" in build
    subprocess.run(
        [sys.executable, "scripts/validate_calendar_immutability.py"],
        cwd=ROOT,
        check=True,
    )


def test_future_update_manifests_gain_bounded_expiry_without_breaking_legacy_signature() -> None:
    builder = read("scripts/build_update_manifest.py")
    parser = read("app/src/main/java/com/orthodoxprayers/privateapp/data/UpdateManifest.java")
    policy = read("app/src/main/java/com/orthodoxprayers/privateapp/data/ManifestSecurityPolicy.java")
    verifier = read("scripts/verify_update_manifest.py")
    assert '"valid_until_utc": valid_until' in builder
    assert "args.valid_for_hours < 6 or args.valid_for_hours > 72" in builder
    assert "ManifestSecurityPolicy.validatePublicationWindow" in parser
    assert "manifest_expired" in policy
    assert "Duration.ofHours(72)" in policy
    assert "manifest validity window must be between 6 and 72 hours" in verifier


def test_invalid_signed_manifest_fails_closed_instead_of_bypassing_revision_protection() -> None:
    repository = read("app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java")
    policy = read("app/src/main/java/com/orthodoxprayers/privateapp/data/ManifestSecurityPolicy.java")
    classifier = read("app/src/main/java/com/orthodoxprayers/privateapp/data/RefreshErrorClassifier.java")
    assert "ManifestSecurityPolicy.mustFailClosed(manifestError)" in repository
    assert 'message.startsWith("signature_")' in policy
    assert 'message.startsWith("manifest_")' in policy
    assert 'message.startsWith("manifest_expired")' in classifier
    assert "manifest_unavailable_after_acceptance" in repository


def test_lightweight_baseline_profile_is_pinned_and_app_only():
    profile = (ROOT / "app/src/main/baseline-prof.txt").read_text(encoding="utf-8")
    gradle = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
    gate = (ROOT / "scripts/run_quality_gate.py").read_text(encoding="utf-8")

    assert "HSPLcom/orthodoxprayers/privateapp/MainActivity;->**(**)**" in profile
    assert "HPLcom/orthodoxprayers/privateapp/ui/screens/ReaderScreen;->**(**)**" in profile
    assert "HPLcom/orthodoxprayers/privateapp/data/SearchEngine;->**(**)**" in profile
    assert "Landroidx/" not in profile
    assert len(profile.encode("utf-8")) <= 16 * 1024
    assert 'implementation("androidx.profileinstaller:profileinstaller:1.4.1")' in gradle
    assert "validate_baseline_profile.py" in gate


def test_release_workflow_verifies_compiled_baseline_profile():
    workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    verifier = (ROOT / "scripts/verify_packaged_baseline_profile.py").read_text(encoding="utf-8")

    assert "Verify packaged Baseline Profile" in workflow
    assert "--apk app/build/outputs/apk/release/app-release.apk" in workflow
    assert "--aab app/build/outputs/bundle/release/app-release.aab" in workflow
    assert "dexopt/baseline.prof" in verifier
    assert "dexopt/baseline.profm" in verifier
    assert "1536 * 1024" in verifier
