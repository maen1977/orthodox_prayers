from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load(path: str) -> dict:
    return json.loads(read(path))


def service(pack: dict, service_id: str) -> dict:
    return next(item for item in pack["services"] if item["id"] == service_id)


def test_compact_home_card_omits_commemoration_but_keeps_date_calendar_and_fast():
    home = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java")
    date_card = home[home.index("private void addDateCard"):home.index("private void addRollingWeekStatus")]
    assert "civilDateLabel(today)" in date_card
    assert "ui_old_church_calendar_home_format" in date_card
    assert "fastingDisplayTitle(today, fastingDate)" in date_card
    assert "displayableCommemoration" not in date_card
    assert "ui_today_commemoration_home_format" not in date_card


def test_fast_notice_has_first_day_last_three_days_and_last_day_states():
    home = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java")
    for key in (
        "ui_fast_notice_first_day_format",
        "ui_fast_notice_ends_in_one_day_format",
        "ui_fast_notice_ends_in_two_days_format",
        "ui_fast_notice_ends_in_days_format",
        "ui_fast_notice_last_day_format",
    ):
        assert key in home
    assert "notice.dayNumber == 1" in home
    assert "notice.daysRemaining <= 3" in home


def test_daily_prayer_list_has_no_external_prayer_navigation():
    screen = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ServiceListScreen.java")
    assert "Intent.ACTION_VIEW" not in screen
    assert "addOfficialDailyPrayerResources" not in screen
    assert "openOfficialUrl" not in screen


def test_arabic_before_meal_prayer_is_complete_and_hash_pinned():
    registry = load("canonical/static_prayer_sources.json")["services"]["before_food"]
    assert registry["complete_text"] is True
    assert "completeness_note_ar" not in registry
    for path in (
        "data/services/library.json",
        "app/src/main/assets/data/library.json",
        "data/services/native/library_ar.json",
        "app/src/main/assets/data/native/library_ar.json",
    ):
        item = service(load(path), "before_food")
        texts = [segment["text"]["ar"] for segment in item["segments"] if segment["text"].get("ar")]
        assert len(texts) == 3
        digest = hashlib.sha256("\n".join(texts).encode("utf-8")).hexdigest()
        assert digest == registry["arabic_sha256"]
        assert "اعين الكل اياك تترجى" in texts[1]
        assert "ياكل البائسون ويشبعون" in texts[2]


def test_meal_additions_are_arabic_lane_only_without_empty_foreign_segments():
    for language in ("en", "el"):
        item = service(load(f"app/src/main/assets/data/native/library_{language}.json"), "before_food")
        assert len(item["segments"]) == 1
        assert all((segment.get("text") or {}).get(language, "").strip() for segment in item["segments"])


def test_authorized_liturgy_lanes_ship_complete_native_text_and_enter_search():
    imported = {
        "ar": {"orthros", "divine_liturgy_basil", "presanctified_liturgy"},
        "el": {"divine_liturgy_basil"},
    }
    minimum_segments = {
        ("ar", "orthros"): 150,
        ("ar", "divine_liturgy_basil"): 200,
        ("ar", "presanctified_liturgy"): 3000,
        ("el", "divine_liturgy_basil"): 220,
    }
    for language, service_ids in imported.items():
        pack = load(f"app/src/main/assets/data/native/library_{language}.json")
        search_ids = {
            item["target_id"]
            for item in load(f"app/src/main/assets/data/search/search_index_{language}.json")["documents"]
            if item["type"] == "service"
        }
        for service_id in service_ids:
            item = service(pack, service_id)
            assert item["displayable"] is True
            assert item["publication_status"] == "DISPLAYABLE_COMPLETE_AUTHORIZED_NATIVE_SOURCE"
            assert len(item["segments"]) >= minimum_segments[(language, service_id)]
            assert item["native_source"]["permission_confirmed"] is True
            assert service_id in search_ids


def test_completion_reports_match_the_completed_authorized_liturgy_audit():
    manifest = load("canonical/religious_completeness_manifest.json")
    assert manifest["languages"]["ar"]["orthros"] == "complete_exact_native_edition"
    assert manifest["languages"]["ar"]["basil_liturgy"] == "complete_native_source_compilation"
    assert manifest["languages"]["ar"]["presanctified_liturgy"] == "complete_exact_native_edition"
    assert manifest["languages"]["el"]["basil_liturgy"] == "complete_exact_native_edition"
    headline = load("canonical/all_languages_15_of_15_report.json")
    assert headline["technical_language_scores"] == {"ar": "15/15", "en": "15/15", "el": "15/15"}
    assert headline["total_complete_lanes"] == "45/45"
