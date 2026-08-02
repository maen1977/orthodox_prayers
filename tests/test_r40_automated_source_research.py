from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CONNECTORS = load_module("r40_source_connectors", ROOT / "scripts/source_connectors.py")
RESEARCH = load_module("r40_source_window_research", ROOT / "scripts/source_window_research.py")


def policy() -> dict:
    return json.loads((ROOT / "canonical/source_comparison_policy.json").read_text(encoding="utf-8"))


def test_policy_is_nine_day_automatic_and_fail_closed():
    value = policy()
    assert value["visible_window_days"] == 9
    assert value["human_review_required"] is False
    assert value["decision_mode"] == "AUTOMATED_FAIL_CLOSED"
    assert "BLOCK_AUTOMATED_CONFLICT" in value["publication_decisions"]


def test_goarch_month_parser_extracts_dated_references_without_overriding_calendar():
    _, definitions = CONNECTORS.load_registry()
    definition = next(item for item in definitions if item.id == "goarch_calendar_month")
    raw = b"""
    <html><body><article>
    <h2>Sunday August 02, 2026</h2>
    <p>Holy Martyr Example</p>
    <h3>Epistle Reading</h3><p>Romans 15:1-7</p>
    <h3>Gospel Reading</h3><p>Matthew 15:32-39</p>
    </article></body></html>
    """
    observation = CONNECTORS.observe_connector(definition, date(2026, 8, 2), raw=raw)
    assert observation.status == "current"
    assert observation.detected_date == "2026-08-02"
    assert CONNECTORS.normalize_reference(observation.epistle_reference) == "romans 15:1-7"
    assert CONNECTORS.normalize_reference(observation.gospel_reference) == "matthew 15:32-39"
    assert any("never overrides" in warning for warning in observation.warnings)
    assert observation.structure_sha256


def test_new_calendar_difference_is_warning_not_override():
    result = RESEARCH.compare_reference(
        "epistle_reference",
        "Romans 15:1-7",
        "Romans 15:1-7",
        "PINNED_JORDAN_2026",
        [{
            "connector_id": "goarch_calendar_month",
            "source_id": "goarch_online_chapel",
            "calendar_profile": "ecumenical_patriarchate_new_calendar",
            "target_date": "2026-08-02",
            "detected_date": "2026-08-02",
            "status": "current",
            "epistle_reference": "1 Corinthians 1:1-9",
            "confidence": 0.82,
            "url": "https://www.goarch.org/chapel/calendar",
        }],
        policy()["calendar_groups"],
        "orthodox_jordan_daily",
    )
    assert result["status"] != "BLOCK"
    assert result["warnings"]
    assert not result["errors"]


def test_local_authority_difference_blocks_publication():
    result = RESEARCH.compare_reference(
        "gospel_reference",
        "Matthew 15:32-39",
        "Matthew 15:32-39",
        "PINNED_JORDAN_2026",
        [{
            "connector_id": "orthodox_jordan_daily",
            "source_id": "orthodox_jordan",
            "calendar_profile": "jerusalem_old_calendar",
            "target_date": "2026-08-02",
            "detected_date": "2026-08-02",
            "status": "current",
            "gospel_reference": "Luke 1:1-10",
            "confidence": 0.9,
            "url": "https://orthodoxjordan.org/",
        }],
        policy()["calendar_groups"],
        "orthodox_jordan_daily",
    )
    assert result["status"] == "BLOCK"
    assert any("local authority" in error for error in result["errors"])


def test_undated_reference_cannot_create_a_false_conflict():
    result = RESEARCH.compare_reference(
        "gospel_reference",
        "Matthew 15:32-39",
        "Matthew 15:32-39",
        "PINNED_JORDAN_2026",
        [{
            "connector_id": "goarch_online_chapel_daily",
            "source_id": "goarch_online_chapel",
            "calendar_profile": "ecumenical_patriarchate_new_calendar",
            "target_date": "2026-08-02",
            "detected_date": None,
            "status": "undated",
            "gospel_reference": "Luke 1:1-10",
            "confidence": 0.45,
        }],
        policy()["calendar_groups"],
        "orthodox_jordan_daily",
    )
    assert result["status"] == "CONFIRMED_AUTHORITY"
    assert result["conflicts"] == []


def test_workflows_use_automatic_gate_and_android_emulator():
    update = (ROOT / ".github/workflows/update.yml").read_text(encoding="utf-8")
    build = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "validate_automated_religious_evidence.py" in update
    assert "validate_source_comparison.py" in update
    assert "compare_source_snapshots.py" in update
    assert "--require-reviewed-propers" not in update
    assert "human review" not in update.lower()
    assert "Require all three publishable language lanes" in update
    assert 'test "$ok" -eq 3' in update
    emulator_script = (ROOT / "scripts/run_android_emulator_ci.sh").read_text(encoding="utf-8")
    assert "assembleDebug assembleDebugAndroidTest --stacktrace" in build
    assert "am instrument -w -r" in emulator_script
    assert "script: bash scripts/run_android_emulator_ci.sh 35" in build
    assert "api-level: 35" in build
    assert "api_level: [29, 35]" not in build
    assert "script: |" not in build.split("Run instrumentation and capture Arabic, English, and Greek screens", 1)[1].split("Upload generated Play Store screenshots", 1)[0]
    emulator_script = (ROOT / "scripts/run_android_emulator_ci.sh").read_text(encoding="utf-8")
    assert "wait-for-device" in emulator_script
    assert "sys.boot_completed" in emulator_script
    assert "ro.build.version.sdk" in emulator_script
    assert "pm path android" in emulator_script
    assert "stable >= 5" in emulator_script
    assert "svc wifi disable" not in emulator_script
    reader_smoke = (
        ROOT / "app/src/androidTest/java/com/orthodoxprayers/privateapp/ReaderSmokeTest.java"
    ).read_text(encoding="utf-8")
    assert 'runShellCommand("svc wifi disable")' in reader_smoke
    assert 'runShellCommand("svc data disable")' in reader_smoke
    assert "NET_CAPABILITY_VALIDATED" in reader_smoke
    assert "set -euo pipefail" in emulator_script
    assert "play-store-screenshots" in build
    assert "validate_play_store_assets.py --require-screenshots" in build


def test_source_snapshot_drift_is_machine_readable(tmp_path: Path):
    current = tmp_path / "current.json"
    previous = tmp_path / "previous.json"
    output = tmp_path / "drift.json"
    previous.write_text(json.dumps({"observations": [{
        "connector_id": "orthodox_jordan_daily",
        "status": "current",
        "structure_sha256": "a",
    }]}), encoding="utf-8")
    current.write_text(json.dumps({"observations": [{
        "connector_id": "orthodox_jordan_daily",
        "status": "poisoned",
        "structure_sha256": "b",
    }]}), encoding="utf-8")
    subprocess.run([
        sys.executable, str(ROOT / "scripts/compare_source_snapshots.py"),
        "--current", str(current), "--previous", str(previous), "--output", str(output),
    ], check=True)
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["change_count"] == 1
    assert result["regression_count"] == 1


def test_same_month_source_url_is_fetched_once(monkeypatch):
    _, definitions = CONNECTORS.load_registry()
    definition = next(item for item in definitions if item.id == "goarch_calendar_month")
    calls = []
    raw = b"<html><body><h2>August 02, 2026</h2><p>Epistle Reading Romans 15:1-7</p><p>Gospel Reading Matthew 15:32-39</p></body></html>"

    def fake_fetch(url, timeout_seconds, max_bytes):
        calls.append(url)
        return 200, raw, url

    monkeypatch.setattr(CONNECTORS, "safe_fetch", fake_fetch)
    cache = {}
    CONNECTORS.observe_connector(definition, date(2026, 8, 2), fetch_cache=cache)
    CONNECTORS.observe_connector(definition, date(2026, 8, 3), fetch_cache=cache)
    assert len(calls) == 1
