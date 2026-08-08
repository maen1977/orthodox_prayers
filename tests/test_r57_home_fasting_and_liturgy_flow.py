from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def calendar_days(year: int) -> dict[str, dict]:
    payload = json.loads((ROOT / f"app/src/main/assets/data/calendar/calendar_{year}.json").read_text(encoding="utf-8"))
    return {item["date_iso"]: item for item in payload["days"]}


def fast_title(day: dict) -> str:
    fasting = day.get("fasting") or {}
    title = fasting.get("title") or {}
    return str(title.get("en") or "")


def test_august_2026_old_calendar_and_dormition_window_are_exact():
    days = calendar_days(2026)
    today = days["2026-08-08"]
    assert today["julian_date"] == "2026-07-26"
    start = date(2026, 8, 14)
    end = date(2026, 8, 27)
    cursor = start
    fast_days = []
    while cursor <= end:
        item = days[cursor.isoformat()]
        assert item["fasting"]["is_fast"] is True
        assert "Dormition Fast" in fast_title(item)
        fast_days.append(item)
        cursor += timedelta(days=1)
    assert len(fast_days) == 14
    assert (start - date(2026, 8, 8)).days == 6
    assert (end - start).days == 13


def test_home_notice_is_calendar_driven_and_continue_reading_is_gone():
    home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
    engine = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/FastingNoticeEngine.java").read_text(encoding="utf-8")
    assert "FastingNoticeEngine.evaluate" in home
    assert "data.calendarDay(isoDate)" in home
    assert "addContinueReading" not in home
    assert "ui_old_church_calendar_home_format" in home
    lowered = engine.lower()
    for family in ("dormition fast", "nativity fast", "great lent", "apostles"):
        assert family in lowered
    assert "WEDNESDAY" in engine and "FRIDAY" in engine
    assert 'fasting.optBoolean("is_fast", false)' in engine


def test_liturgy_tab_opens_reader_directly_and_keeps_blocked_day_fallback():
    main = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
    assert 'case "liturgy": return canOpenTodayLiturgyDirectly()' in main
    assert 'new ReaderScreen(this, "divine_liturgy")' in main
    assert 'new LiturgyHubScreen(this)' in main
    assert '"no_divine_liturgy".equals(type)' in main
    assert '"typikon_override_required".equals(type)' in main


def test_reader_has_pre_liturgy_core_sunday_gospel_and_post_liturgy_phases():
    repo = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert 'appendNativePrayerService(continuous, "pre_communion_prayers", language)' in repo
    assert 'appendNativePrayerService(continuous, "proskomide", language)' in repo
    assert "appendSundayCycleGospel" in repo
    assert "إنجيل الدورة (إنجيل السَحَر)" in repo
    assert "thanksgivingSegmentsForLiturgy" in repo
    assert "CONTINUOUS_WORSHIP_PATH_SEPARATE_PHASES" in repo
    assert '"matins_gospel".equals(copy.optString("dynamic_slot", ""))' in repo


def test_daily_liturgy_reading_slots_include_name_reference_and_exact_body():
    engine = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/LocalDailyContentEngine.java").read_text(encoding="utf-8")
    assert 'String name = title == null ? "" : title.optString(language, "").trim();' in engine
    assert 'String ref = reference == null ? "" : reference.optString(language, "").trim();' in engine
    assert 'display.append(" — ")' in engine
    assert '"إنجيل الدورة (إنجيل السَحَر)"' in engine
