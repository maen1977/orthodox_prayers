from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_local_daily_engine_validation_gate():
    result = subprocess.run(
        [sys.executable, "scripts/validate_local_daily_engine.py", "--date", "2026-08-06"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "LOCAL_DAILY_ENGINE_OK" in result.stdout
    assert "network_required=false" in result.stdout
    assert "window=9" in result.stdout


def test_daily_worker_and_schedule_are_network_independent():
    coordinator = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/UpdateCoordinator.java").read_text(encoding="utf-8")
    worker = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/work/DailyUpdateWorker.java").read_text(encoding="utf-8")
    assert "NetworkType" not in coordinator
    assert "setRequiredNetworkType" not in coordinator
    assert "Result.retry" not in worker
    assert "LOCAL_REFRESH_HOUR = 0" in coordinator
    assert "LOCAL_REFRESH_MINUTE = 3" in coordinator


def test_local_scripture_assets_are_packaged_for_all_language_lanes():
    for language in ("ar", "en", "el"):
        assert (ROOT / f"app/src/main/assets/data/scripture/verses_{language}.json").is_file()
        assert (ROOT / f"app/src/main/assets/data/scripture/manifest_{language}.json").is_file()


def test_scheduled_github_daily_update_is_removed():
    workflows = ROOT / ".github/workflows"
    assert {p.name for p in workflows.glob("*.yml")} == {"church-prayers.yml"}
    build = (workflows / "church-prayers.yml").read_text(encoding="utf-8")
    assert "schedule:" not in build
    assert "Daily Update" not in build
