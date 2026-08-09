import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = json.loads((ROOT / "canonical/internal_calendar_2026_2050.json").read_text(encoding="utf-8"))
INDEX = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_index.json").read_text(encoding="utf-8"))
BY_DATE = {item["date_iso"]: item for item in CANONICAL["days"]}


def test_internal_calendar_covers_every_day_through_2050():
    expected = (date(2050, 12, 31) - date(2026, 1, 1)).days + 1
    assert CANONICAL["civil_range"] == {
        "start": "2026-01-01",
        "end": "2050-12-31",
        "day_count": expected,
    }
    assert len(CANONICAL["days"]) == expected == 9131
    assert CANONICAL["days"][0]["date_iso"] == "2026-01-01"
    assert CANONICAL["days"][-1]["date_iso"] == "2050-12-31"


def test_internal_calendar_preserves_nine_day_twice_daily_policy():
    assert CANONICAL["visible_window_days"] == 9
    assert CANONICAL["update_schedule"] == {
        "timezone": "Asia/Amman",
        "times": ["04:23", "16:43"],
    }


def test_year_assets_are_split_for_low_memory_devices():
    assert set(INDEX["years"]) == {str(year) for year in range(2026, 2051)}
    for year in range(2026, 2051):
        meta = INDEX["years"][str(year)]
        path = ROOT / "app/src/main/assets" / meta["asset"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["year"] == year
        assert payload["days"][0]["date_iso"] == f"{year}-01-01"
        assert payload["days"][-1]["date_iso"] == f"{year}-12-31"


def test_pascha_and_year_boundary_are_available_offline():
    assert "الفصح" in BY_DATE["2026-04-12"]["feast"]["ar"]
    assert "الفصح" in BY_DATE["2027-05-02"]["feast"]["ar"]
    assert "الفصح" in BY_DATE["2050-04-17"]["feast"]["ar"]
    assert BY_DATE["2026-12-31"]["date_iso"] == "2026-12-31"
    assert BY_DATE["2027-01-01"]["date_iso"] == "2027-01-01"


def test_future_days_have_offline_commemoration_without_inventing_named_saints():
    day = BY_DATE["2040-08-02"]
    assert day["occasion_status"] in {"PINNED_INTERNAL_RULE", "PINNED_INTERNAL_OLD_CALENDAR_DATE"}
    commemoration = day["commemoration"]
    assert commemoration["status"] == day["commemoration_status"]
    for language in ("ar", "en", "el"):
        assert commemoration["name"][language].strip()
    if not day["reading_references"]:
        assert day["reference_status"] == "REFERENCE_PENDING_TWICE_DAILY_VERIFICATION"
    assert CANONICAL["policy"]["named_saints_require_verified_native_source"] is True
    assert CANONICAL["policy"]["machine_translation"] is False
    assert CANONICAL["policy"]["cross_language_fallback"] is False


def test_android_uses_year_index_and_exact_nine_day_contract():
    repo = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    manifest = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/UpdateManifest.java").read_text(encoding="utf-8")
    screen = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarScreen.java").read_text(encoding="utf-8")
    assert 'data/calendar/calendar_index.json' in repo
    assert 'calendarDays(int year)' in repo
    assert 'MAX_ROLLING_WINDOW_DAYS = 9' in repo
    assert 'dayCount == 9' in manifest
    assert 'MIN_MONTH = YearMonth.of(2026, 1)' in screen
    assert 'MAX_MONTH = YearMonth.of(2050, 12)' in screen
    assert 'previous.setEnabled(month.isAfter(MIN_MONTH))' in screen
    assert 'next.setEnabled(month.isBefore(MAX_MONTH))' in screen
