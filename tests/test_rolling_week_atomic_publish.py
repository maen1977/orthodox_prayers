from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_builder():
    scripts = ROOT / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        path = scripts / "build_rolling_week.py"
        spec = importlib.util.spec_from_file_location("rolling_week_atomic_test", path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_failed_future_generation_restores_anchor_and_never_commits_partial_package(tmp_path, monkeypatch):
    builder = load_builder()
    calendar_dir = tmp_path / "data" / "calendar"
    calendar_dir.mkdir(parents=True)
    today = calendar_dir / "today.json"
    dated = calendar_dir / "2026-07-30.json"
    anchor = {"date_iso": "2026-07-30", "services": [], "publication": {}}
    original = json.dumps(anchor, ensure_ascii=False, indent=2) + "\n"
    today.write_text(original, encoding="utf-8")
    dated.write_text(original, encoding="utf-8")

    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(builder, "CALENDAR", today)
    monkeypatch.setattr(builder, "CACHE_DIR", tmp_path / "build" / "rolling-week" / "days")
    monkeypatch.setattr(builder, "require_full_day", lambda payload, expected: None)
    monkeypatch.setattr(builder, "generator_fingerprint", lambda: "test-fingerprint")
    monkeypatch.setattr(builder, "load_cached_day", lambda day, fingerprint: None)
    monkeypatch.setattr(builder, "save_cached_day", lambda day, fingerprint, payload: None)

    def fail_generation(day, offline):
        # Simulate the real generator mutating today.json before a missing native
        # Scripture source causes the future day to fail.
        today.write_text(json.dumps({"date_iso": day.isoformat()}) + "\n", encoding="utf-8")
        raise RuntimeError("future day unavailable")

    monkeypatch.setattr(builder, "generate_future_day", fail_generation)
    monkeypatch.setattr(sys, "argv", ["build_rolling_week.py", "--start-date", "2026-07-30", "--days", "9", "--offline"])

    with pytest.raises(RuntimeError, match="future day unavailable"):
        builder.main()

    assert today.read_text(encoding="utf-8") == original
    assert dated.read_text(encoding="utf-8") == original
    assert not list(calendar_dir.glob(".*.rolling-window.tmp"))
    restored = json.loads(today.read_text(encoding="utf-8"))
    assert "rolling_week" not in restored
    assert "weekly_days" not in restored
