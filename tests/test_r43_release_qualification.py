from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_r43_version_android8_floor_and_calendar_immutability() -> None:
    gradle = read("app/build.gradle.kts")
    assert 'versionName = "5.2.0"' in gradle
    assert "versionCode = 50200" in gradle
    assert "minSdk = 26" in gradle
    subprocess.run([sys.executable, "scripts/validate_calendar_immutability.py"], cwd=ROOT, check=True)


def test_launcher_shortcuts_are_lightweight_and_localized() -> None:
    source = read("app/src/main/java/com/orthodoxprayers/privateapp/AppShortcuts.java")
    app = read("app/src/main/java/com/orthodoxprayers/privateapp/OrthodoxPrayersApp.java")
    assert "ShortcutManager" in source
    assert "setDynamicShortcuts" in source
    assert "daily_readings" in source and "divine_liturgy" in source and "morning_prayer" in source
    assert "AppShortcuts.install(this, repository);" in app
    for directory in ("values", "values-en", "values-el"):
        strings = read(f"app/src/main/res/{directory}/ui_strings.xml")
        assert "ui_shortcut_daily_readings_r43" in strings
        assert "ui_shortcut_divine_liturgy_r43" in strings
        assert "ui_shortcut_morning_prayer_r43" in strings


def test_upgrade_qualification_preserves_user_state() -> None:
    workflow = read(".github/workflows/build.yml")
    test = read("app/src/androidTest/java/com/orthodoxprayers/privateapp/UpgradePersistenceTest.java")
    runner = read("scripts/run_android_upgrade_ci.sh")
    assert "android_upgrade:" in workflow
    assert "In-place upgrade from previous revision on Android 8" in workflow
    assert "git worktree add" in workflow
    assert "run_android_upgrade_ci.sh 26" in workflow
    assert "adb install -r -t" in runner
    for value in ("favorites_csv", "reader_position_morning_prayer", "last_search_query", "upgrade-sentinel-r43.txt"):
        assert value in test
    subprocess.run(["bash", "-n", str(ROOT / "scripts/run_android_upgrade_ci.sh")], check=True)


def test_compatibility_and_resilience_jobs_block_release() -> None:
    workflow = read(".github/workflows/build.yml")
    assert "api: [29, 33]" in workflow
    assert "run_android_failure_recovery_ci.sh 35" in workflow
    assert "android_compatibility, android_upgrade, android_resilience" in workflow
    assert "DailyPresentationSmokeTest" in read("scripts/run_android_emulator_ci.sh")
    assert "FailureRecoverySmokeTest" in read("scripts/run_android_emulator_ci.sh")
    subprocess.run(["bash", "-n", str(ROOT / "scripts/run_android_failure_recovery_ci.sh")], check=True)


def test_extended_performance_parser_enforces_screen_specific_budgets(tmp_path: Path) -> None:
    files = {}
    for name, text in {
        "cold": "Status: ok\nTotalTime: 1200\nWaitTime: 1300\n",
        "warm": "Status: ok\nTotalTime: 500\nWaitTime: 550\n",
        "home": "TOTAL PSS: 50000\n",
        "reader": "TOTAL PSS: 65000\n",
        "search": "TOTAL PSS: 70000\n",
        "gfx": "Janky frames: 3 (4.5%)\n",
    }.items():
        path = tmp_path / f"{name}.txt"; path.write_text(text, encoding="utf-8"); files[name] = path
    output = tmp_path / "metrics.json"
    subprocess.run([
        sys.executable, "scripts/parse_android_runtime_metrics.py",
        "--api-level", "26", "--start-output", str(files["cold"]),
        "--warm-start-output", str(files["warm"]), "--meminfo-output", str(files["home"]),
        "--reader-meminfo-output", str(files["reader"]), "--search-meminfo-output", str(files["search"]),
        "--gfxinfo-output", str(files["gfx"]), "--output", str(output),
    ], cwd=ROOT, check=True)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["reader_total_pss_kb"] == 65000
    assert payload["search_total_pss_kb"] == 70000
    assert payload["janky_frames_percent"] == 4.5


def test_release_size_budget_validator(tmp_path: Path) -> None:
    apk = tmp_path / "app.apk"; apk.write_bytes(b"a" * 2048)
    aab = tmp_path / "app.aab"; aab.write_bytes(b"b" * 4096)
    source = tmp_path / "source.zip"; source.write_bytes(b"c" * 1024)
    report = tmp_path / "size.json"
    subprocess.run([sys.executable, "scripts/validate_release_size.py", "--apk", str(apk), "--aab", str(aab), "--source-zip", str(source), "--report", str(report)], cwd=ROOT, check=True)
    assert json.loads(report.read_text(encoding="utf-8"))["status"] == "PASS"
    assert "validate_release_size.py" in read(".github/workflows/build.yml")


def test_play_internal_workflow_is_manual_protected_and_dry_run_capable(tmp_path: Path) -> None:
    workflow = read(".github/workflows/play-internal.yml")
    uploader = read("scripts/upload_play_internal.py")
    yaml.safe_load(workflow)
    assert "workflow_dispatch" in workflow
    assert "environment: play-internal" in workflow
    assert "PLAY_SERVICE_ACCOUNT_JSON" in workflow
    assert "inputs.publish == true" in workflow
    assert "androidpublisher.googleapis.com/upload/androidpublisher/v3" in uploader
    aab = tmp_path / "sample.aab"; aab.write_bytes(b"bundle" * 300)
    report = tmp_path / "dry-run.json"
    subprocess.run([sys.executable, "scripts/upload_play_internal.py", "--aab", str(aab), "--release-name", "R43", "--dry-run", "--report", str(report)], cwd=ROOT, check=True)
    assert json.loads(report.read_text(encoding="utf-8"))["result"] == "VALIDATED_ONLY"


def test_weekly_health_and_device_qualification_contract(tmp_path: Path) -> None:
    workflow = read(".github/workflows/weekly-health.yml")
    yaml.safe_load(workflow)
    assert "Weekly Release Health" in workflow
    assert "gh issue create" in workflow
    report = tmp_path / "device.json"
    subprocess.run([sys.executable, "scripts/validate_device_qualification.py", "--report", str(report)], cwd=ROOT, check=True)
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["automated_apis"] == [26, 29, 33, 35]


def test_workflow_validator_accepts_all_protected_workflows() -> None:
    subprocess.run([sys.executable, "scripts/validate_workflows.py"], cwd=ROOT, check=True)
