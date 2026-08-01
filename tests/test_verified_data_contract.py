from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_verified_data_contract",
    ROOT / "scripts/validate_verified_data_contract.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def loc(value: str) -> dict[str, str]:
    return {"ar": value, "en": value, "el": value}


def day(day_value: date, language: str | None = None) -> dict:
    reason = loc("Appointed by the current Typikon contract")
    if language:
        reason = {"ar": "", "en": "", "el": "", language: "Appointed"}
    return {
        "schema_version": 10,
        "date_iso": day_value.isoformat(),
        "language": language,
        "liturgy_service_selection": {
            "service_type": "john_chrysostom",
            "service_form": "morning_divine_liturgy",
            "reason": reason,
            "wrong_liturgy_fallback_allowed": False,
            "full_service_scope": MODULE.FULL_SCOPE,
            "displayable": True,
        },
        "services": [
            {
                "id": "divine_liturgy",
                "selected_liturgy_type": "john_chrysostom",
                "full_service_complete": True,
                "publication_status": MODULE.DISPLAYABLE,
            }
        ],
    }


def package(start: date, language: str | None = None, *, days: int = 9) -> dict:
    value = day(start, language)
    value["rolling_week"] = {
        "schema_version": 2,
        "policy": "ROLLING_FUTURE_WINDOW",
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=days - 1)).isoformat(),
        "day_count": days,
        "future_day_count": days - 1,
        "end_offset_days": days - 1,
        "timezone": "Asia/Amman",
        "status": "COMPLETE",
        "fail_closed": True,
    }
    value["weekly_days"] = [day(start + timedelta(days=i), language) for i in range(1, days)]
    return value


def test_current_moving_window_contract_is_accepted():
    assert MODULE.published_payload_errors(package(date(2026, 7, 30), days=9), "2026-07-30") == []


def test_too_short_window_contract_is_rejected():
    errors = MODULE.published_payload_errors(
        package(date(2026, 7, 30), days=8),
        "2026-07-30",
    )
    assert any("unsupported" in error or "between 9 and 9" in error for error in errors)


def test_legacy_twenty_one_day_window_contract_is_rejected():
    errors = MODULE.published_payload_errors(
        package(date(2026, 7, 30), days=21),
        "2026-07-30",
    )
    assert any("unsupported" in error or "between 9 and 9" in error for error in errors)


def test_root_contract_checks_canonical_and_language_lanes():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        start = date(2026, 7, 30)
        calendar = root / "data/calendar/today.json"
        calendar.parent.mkdir(parents=True)
        calendar.write_text(json.dumps(package(start, days=9)), encoding="utf-8")
        for language in ("ar", "en", "el"):
            dated = root / f"data/daily/{start.isoformat()}/{language}.json"
            current = root / f"data/daily/current/{language}.json"
            dated.parent.mkdir(parents=True, exist_ok=True)
            current.parent.mkdir(parents=True, exist_ok=True)
            content = json.dumps(package(start, language, days=9), ensure_ascii=False)
            dated.write_text(content, encoding="utf-8")
            current.write_text(content, encoding="utf-8")
        published_date, errors = MODULE.validate_root(root)
        assert published_date == start.isoformat()
        assert errors == []
