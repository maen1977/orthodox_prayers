import json
import subprocess
import sys
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


def test_fixed_feasts_are_named_in_every_in_horizon_asset():
    from scripts.update_liturgical_data import julian_to_gregorian_date

    fixed = {
        (1, 1): "ختان",
        (1, 6): "الظهور",
        (2, 2): "دخول",
        (3, 25): "البشارة",
        (6, 24): "يوحنا",
        (6, 29): "بطرس وبولس",
        (8, 6): "تجلي",
        (8, 15): "رقاد",
        (9, 8): "ميلاد",
        (9, 14): "رفع الصليب",
        (11, 21): "دخول",
        (12, 25): "ميلاد",
    }
    for year in range(2026, 2051):
        for (month, day_number), anchor in fixed.items():
            civil = julian_to_gregorian_date(year, month, day_number)
            if civil.year > 2050:
                continue
            asset_path = ROOT / "app/src/main/assets/data/calendar" / f"calendar_{civil.year}.json"
            payload = json.loads(asset_path.read_text(encoding="utf-8"))
            item = next(day for day in payload["days"] if day["date_iso"] == civil.isoformat())
            feast = item["feast"]
            occasion_titles = [feast["ar"]]
            occasion_titles.extend(
                occasion.get("title", {}).get("ar", "")
                for occasion in item.get("occasions", [])
                if isinstance(occasion, dict)
            )
            assert anchor in " ".join(occasion_titles), (year, month, day_number, civil, item)
            for language in ("ar", "en", "el"):
                assert feast[language].strip(), (year, month, day_number, language)


def test_2026_transfiguration_and_fasting_detail_are_packaged():
    asset = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_2026.json").read_text(encoding="utf-8"))
    item = next(day for day in asset["days"] if day["date_iso"] == "2026-08-19")
    assert item["feast"] == {
        "ar": "عيد تجلي ربنا وإلهنا ومخلصنا يسوع المسيح",
        "en": "The Holy Transfiguration of our Lord, God and Savior Jesus Christ",
        "el": "Ἡ Ἁγία Μεταμόρφωσις τοῦ Κυρίου καὶ Θεοῦ καὶ Σωτῆρος ἡμῶν Ἰησοῦ Χριστοῦ",
    }
    fasting_ref = item["fasting"]
    fasting = asset["fasting_profiles"][fasting_ref["profile_id"]]
    assert fasting["code"] == "fish_allowed"
    assert "السمك" in fasting["detail"]["ar"]
    assert "Fish" in fasting["detail"]["en"]
    assert "ψάρι" in fasting["detail"]["el"]
    assert len(fasting["items"]) == 6
    assert not fasting["abstinence"].get("applies", False)


def test_commemoration_policy_renders_multiple_same_day_occasions():
    policy = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/CommemorationDisplayPolicy.java").read_text(encoding="utf-8")
    assert "displayOccasions" in policy
    assert 'day.optJSONArray("occasions")' in policy
    assert 'result.append("\\n")' in policy
    item = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_2026.json").read_text(encoding="utf-8"))
    item = next(day for day in item["days"] if day["date_iso"] == "2026-02-15")
    titles = [occasion["title"]["ar"] for occasion in item["occasions"]]
    assert any("الدينونة" in title for title in titles)
    assert any("دخول السيد" in title for title in titles)


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


def test_every_day_has_semantically_valid_fasting_rule_through_2050():
    result = subprocess.run(
        [sys.executable, "scripts/validate_fasting_calendar_2050.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "FASTING_CALENDAR_2050_OK days=9131 years=25" in result.stdout
    assert "dormition_feast=fish_allowed" in result.stdout


def test_android_uses_year_index_and_exact_nine_day_contract():
    repo = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    asset = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_2026.json").read_text(encoding="utf-8"))
    assert asset["fasting_profiles"]
    assert all("profile_id" in day["fasting"] for day in asset["days"])
    assert "resolveFastingProfile" in repo
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
