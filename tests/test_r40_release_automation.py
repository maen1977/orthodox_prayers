from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_release_permission_gate_accepts_only_declared_minimum(tmp_path: Path):
    allowed = tmp_path / "allowed.txt"
    allowed.write_text(
        "\n".join([
            "android.permission.INTERNET",
            "android.permission.ACCESS_NETWORK_STATE",
            "android.permission.POST_NOTIFICATIONS",
            "android.permission.RECEIVE_BOOT_COMPLETED",
        ]),
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_release_permissions.py"), str(allowed)],
        check=True,
        capture_output=True,
        text=True,
    )

    forbidden = tmp_path / "forbidden.txt"
    forbidden.write_text("android.permission.ACCESS_FINE_LOCATION\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_release_permissions.py"), str(forbidden)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "forbidden release permissions" in (result.stdout + result.stderr)


def test_play_package_builder_collects_automated_release_inputs(tmp_path: Path, monkeypatch):
    module = load_module("r40_play_package", ROOT / "scripts/build_play_store_release_package.py")
    project = tmp_path / "project"
    for relative in (
        "play-store/assets",
        "play-store/assets/screenshots/ar",
        "play-store/assets/screenshots/en",
        "play-store/assets/screenshots/el",
        "docs/privacy",
    ):
        (project / relative).mkdir(parents=True, exist_ok=True)

    for relative in (
        "play-store/assets/app-icon-512.png",
        "play-store/assets/feature-graphic-1024x500.png",
        "play-store/assets/screenshots/ar/01-home.png",
        "play-store/assets/screenshots/ar/02-readings.png",
        "play-store/assets/screenshots/en/01-home.png",
        "play-store/assets/screenshots/en/02-readings.png",
        "play-store/assets/screenshots/el/01-home.png",
        "play-store/assets/screenshots/el/02-readings.png",
    ):
        (project / relative).write_bytes(b"png-test-data")
    for relative in (
        "play-store/STORE_LISTING_AR.md",
        "play-store/STORE_LISTING_EN.md",
        "play-store/STORE_LISTING_EL.md",
        "play-store/DATA_SAFETY_AR.md",
        "play-store/PLAY_CONSOLE_CHECKLIST_AR.md",
        "CONTENT_RIGHTS.md",
        "PRIVACY.md",
        "docs/privacy/index.html",
    ):
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("validated release metadata", encoding="utf-8")

    aab = tmp_path / "app-release.aab"
    aab.write_bytes(b"signed-aab-placeholder-for-unit-test")
    output = tmp_path / "output"
    monkeypatch.setattr(module, "ROOT", project)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_play_store_release_package.py",
            "--aab", str(aab),
            "--output-dir", str(output),
            "--support-email", "support@example.org",
        ],
    )
    module.main()

    metadata = json.loads((output / "PLAY_RELEASE_METADATA.json").read_text(encoding="utf-8"))
    assert metadata["screenshots_generated_by_android_instrumentation"] is True
    assert metadata["human_religious_review_required"] is False
    assert metadata["languages"] == ["ar", "en", "el"]
    assert (output / "app-release.aab").is_file()
    assert (output / "SHA256SUMS.txt").is_file()


def test_build_workflow_tests_old_and_new_android_offline_and_packages_play_release():
    workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    assert (ROOT / "app/src/androidTest/java/com/orthodoxprayers/privateapp/StoreScreenshotTest.java").is_file()
    for marker in (
        "api_level: [29, 35]",
        "adb shell svc wifi disable",
        "connectedDebugAndroidTest",
        "play-store-screenshots",
        "validate_release_permissions.py",
        "build_play_store_release_package.py",
        "PLAY_SUPPORT_EMAIL",
    ):
        assert marker in workflow


def test_calendar_boundary_validator_covers_every_year_transition_through_2050():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_calendar_boundaries_2050.py")],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "year_transitions=24" in result.stdout
    assert "leap_windows=6" in result.stdout


def test_store_and_privacy_texts_describe_r40_automatic_source_comparison():
    privacy = (ROOT / "docs/privacy/index.html").read_text(encoding="utf-8")
    arabic = (ROOT / "play-store/STORE_LISTING_AR.md").read_text(encoding="utf-8")
    english = (ROOT / "play-store/STORE_LISTING_EN.md").read_text(encoding="utf-8")
    greek = (ROOT / "play-store/STORE_LISTING_EL.md").read_text(encoding="utf-8")
    assert "2 أغسطس 2026" in privacy
    assert "مقارنة آلية" in arabic
    assert "Automated church-source comparison" in english
    assert "Αὐτοματοποιημένη σύγκριση" in greek
