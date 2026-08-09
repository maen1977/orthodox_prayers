from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = json.loads((ROOT / "canonical/internal_calendar_2026_2050.json").read_text(encoding="utf-8"))


def test_every_day_through_2050_has_localized_commemoration():
    days = CANONICAL["days"]
    assert len(days) == 9131
    assert CANONICAL["coverage"]["days_with_offline_commemoration"] == 9131
    forbidden = (
        "يُستكمل من التحديث",
        "يستكمل من التحديث",
        "completed by the verified update",
        "συμπληρώνεται ἀπὸ τὴν ἐπαληθευμένη",
    )
    for day in days:
        commemoration = day.get("commemoration") or {}
        assert day.get("commemoration_status") in {
            "PINNED_INTERNAL_RULE",
            "PINNED_INTERNAL_OLD_CALENDAR_DATE",
        }
        assert commemoration.get("status") == day.get("commemoration_status")
        names = commemoration.get("name") or {}
        for language in ("ar", "en", "el"):
            value = str(names.get(language) or "").strip()
            assert value, f"{day['date_iso']} missing {language} commemoration"
            assert not any(token.casefold() in value.casefold() for token in forbidden)


def test_august_8_2026_has_old_calendar_commemoration_in_all_lanes():
    day = next(item for item in CANONICAL["days"] if item["date_iso"] == "2026-08-08")
    assert day["julian_date"] == "2026-07-26"
    names = day["commemoration"]["name"]
    assert "26 تموز" in names["ar"]
    assert "July 26" in names["en"]
    assert "26" in names["el"] and "Ἰουλίου" in names["el"]


def test_home_renders_commemoration_between_old_calendar_and_fast():
    home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
    old_pos = home.index("ui_old_church_calendar_home_format")
    comm_pos = home.index("ui_today_commemoration_home_format")
    fast_pos = home.index("fastingDisplayTitle(today, data.dataDate())")
    assert old_pos < comm_pos < fast_pos
    assert "displayableCommemoration(commemorationDay)" in home


def test_daily_package_missing_commemoration_uses_offline_calendar_fallback():
    repo = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    assert "CommemorationDisplayPolicy.displayText(complete, this::localizedValue)" in repo
    assert 'baseline.optJSONObject("feast")' in repo
    assert 'merged.put("feast"' in repo


def test_settings_merge_language_and_text_and_remove_church_duplicate():
    settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
    hub = settings[settings.index("private View createSettingsHubView"):settings.index("private View createLanguageAndTextSettingsView")]
    assert "SECTION_LANGUAGE_AND_TEXT" in hub
    assert "ui_language_and_text_settings_title" in hub
    assert "SECTION_FONT_SIZE" not in hub
    assert "churchesCard" not in settings
    assert 'host.navigate("churches", null)' not in settings
    combined = settings[settings.index("private void appendLanguageAndTextSettings"):settings.index("private void appendCalendarSettings")]
    assert "addLanguageButton" in combined
    assert 'ui.button("A−"' in combined
    assert 'ui.button("A+"' in combined
    assert "add(page.root, combinedCard" in combined


def test_new_ui_strings_exist_independently_in_all_languages():
    files = {
        "ar": ROOT / "app/src/main/res/values/ui_strings.xml",
        "en": ROOT / "app/src/main/res/values-en/ui_strings.xml",
        "el": ROOT / "app/src/main/res/values-el/ui_strings.xml",
    }
    for language, path in files.items():
        text = path.read_text(encoding="utf-8")
        assert 'name="ui_language_and_text_settings_title"' in text, language
        assert 'name="ui_today_commemoration_home_format"' in text, language
