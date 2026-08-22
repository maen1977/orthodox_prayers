from __future__ import annotations

import json
from pathlib import Path

from scripts.android_ui_resources import source_omits_text, source_references_text

ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT / "app/src/main/java/com/orthodoxprayers/privateapp"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_home_uses_specific_weekday_fast_and_plain_no_fast_labels() -> None:
    base = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BaseScreen.java")
    home = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java")
    assert '"weekly_wednesday_friday".equals(rule)' in base
    assert "DayOfWeek.WEDNESDAY" in base
    assert "DayOfWeek.FRIDAY" in base
    assert "ui_wednesday_fast" in base
    assert "ui_friday_fast" in base
    assert "ui_no_fast_plain" in base
    assert "fastingDisplayTitle(today, fastingDate)" in home


def test_fast_free_days_do_not_render_food_permissions_or_explanations() -> None:
    base = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BaseScreen.java")
    upcoming = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/UpcomingScreen.java")
    calendar = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarDayScreen.java")
    assert "if (!isFastingDay(fasting)) return;" in base
    assert "if (fasting == null || !fasting.optBoolean(\"is_fast\", false)) return \"\";" in base
    assert "if (isFastingDay(fasting))" in upcoming
    assert "if (isFastingDay(fasting)) addFastingGuide(card, fasting, true);" in calendar


def test_unavailable_commemorations_and_internal_selection_reasons_are_hidden() -> None:
    base = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BaseScreen.java")
    policy = read("app/src/main/java/com/orthodoxprayers/privateapp/data/CommemorationDisplayPolicy.java")
    upcoming = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/UpcomingScreen.java")
    calendar = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarDayScreen.java")
    month = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarScreen.java")
    widget = read("app/src/main/java/com/orthodoxprayers/privateapp/widget/DailyAgendaWidget.java")
    reminder = read("app/src/main/java/com/orthodoxprayers/privateapp/work/PrayerReminderWorker.java")
    assert "CommemorationDisplayPolicy.displayText" in base
    assert 'status.startsWith("UNAVAILABLE")' in policy
    assert 'status.startsWith("PENDING")' in policy
    assert "NO_VERIFIED" in policy
    assert "تذكار اليوم بحسب التقويم الكنسي القديم" in policy
    assert "displayableCommemoration" in upcoming
    assert "displayableCommemoration" in calendar
    assert "displayableCommemoration(item)" in month
    assert "View.GONE" in widget
    assert "CommemorationDisplayPolicy.displayText" in reminder
    assert "ui_selection_reason_label" not in upcoming
    assert "ui_selection_reason_label" not in calendar


def test_home_keeps_nine_day_access_behind_the_compact_calendar_icon() -> None:
    home = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java")
    upcoming = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/UpcomingScreen.java")
    assert "ui_nine_day_service_ready" in home
    assert "ui_content_ready_through_format" in home
    assert "R33_COMPACT_FASTING_HOME" in home
    assert 'ui_calendar_and_fasting_51a9bf84), "upcoming", null' in home
    assert "int dayCount = Math.min(8, upcoming.length());" not in home
    assert "private void addUpcoming" not in home
    assert 'host.navigate("calendar_day", itemDate)' in upcoming
    assert 'host.navigate("calendar", null)' in upcoming
    assert source_omits_text(home, "عرض تفاصيل الأيام التسعة", "ar")
    assert 'addShortcutCard(third, com.orthodoxprayers.privateapp.R.drawable.ic_action_search, searchTitle(), "search", null);' in home
    assert 'if ("ar".equals(language)) return "البحث";' in home
    assert source_omits_text(home, "آخر قراءة", "ar")
    assert source_omits_text(home, "اللغات", "ar")
    assert source_omits_text(home, "الإعدادات", "ar")


def test_back_navigation_restores_the_previous_prayer_list_scroll_position() -> None:
    main = read("app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java")
    assert main.count("captureCurrentScrollPosition();") >= 3
    assert "restoreEntryScrollPosition(entry, view);" in main
    assert "current.scrollY = Math.max(0, view.getScrollY());" in main
    assert 'object.put("scroll_y", scrollY);' in main
    assert 'object.optInt("scroll_y", 0)' in main


def test_settings_hide_language_and_coverage_implementation_details() -> None:
    settings = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java")
    assert source_omits_text(settings, "العربية والإنجليزية واليونانية ثلاث قنوات أصلية مستقلة", "ar")
    assert source_omits_text(settings, "اكتمال مكتبات النصوص الأصلية حاليًا", "ar")
    assert source_omits_text(settings, "إدارة اللغات النشطة", "ar")
    assert source_omits_text(settings, "إظهار النص الأصلي", "ar")
    assert "TranslationCoverage" not in settings
    assert "liturgyCoverageBadge" not in settings
    assert "addLanguageButton" in settings
    assert "addReminder" in settings


def test_official_live_resources_match_the_current_verified_source_registry() -> None:
    directory = json.loads(read("app/src/main/assets/data/churches.json"))
    resources = directory["live_resources"]
    assert [item["id"] for item in resources] == [
        "orthodox_tv_official",
        "orthodox_tv_radio",
        "jerusalem_patriarchate_radio",
    ]
    assert resources[0]["url"] == "https://orthodoxjo.tv/"
    assert resources[1]["url"].startswith("https://orthodoxjo.tv/audio/")
    assert resources[2]["url"].startswith("https://ar.jerusalem-patriarchate.info/")
    builder = read("scripts/build_church_directory.py")
    churches = read("app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/ChurchesScreen.java")
    for resource_id in ("orthodox_tv_official", "orthodox_tv_radio", "jerusalem_patriarchate_radio"):
        assert resource_id in builder
    assert "orthodox_jordan_tv_live" not in builder
    assert "Intent.CATEGORY_BROWSABLE" in churches
    assert "Intent.FLAG_ACTIVITY_NEW_DOCUMENT" in churches

def test_church_directory_offline_fallback_cannot_shrink_the_audited_snapshot() -> None:
    import sys

    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from build_church_directory import SEED, load_best_reviewed_fallback

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    churches, status, snapshot_date, metadata = load_best_reviewed_fallback(seed)
    assert len(seed["churches"]) == 5
    assert len(churches) == 57
    assert status == "official_directory_audited"
    assert snapshot_date == "2026-08-10"
    assert "orthodox_jordan" in metadata["authority"]
    builder = read("scripts/build_church_directory.py")
    assert "minimum_safe_live_count" in builder
    assert "fallback_count * 7" in builder
