from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.android_ui_resources import source_omits_text, source_references_text

ROOT = Path(__file__).resolve().parents[1]


class R14HomeCleanupTests(unittest.TestCase):
    def test_app_is_renamed_to_church_prayers(self):
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        widget = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/widget/DailyAgendaWidget.java").read_text(encoding="utf-8")
        library = json.loads((ROOT / "app/src/main/assets/data/library.json").read_text(encoding="utf-8"))
        self.assertTrue(source_references_text(home, "الصلوات الكنسية", "ar", exact=True))
        self.assertTrue(source_references_text(widget, "الصلوات الكنسية", "ar", exact=True))
        self.assertEqual("الصلوات الكنسية", library["app_name"]["ar"])
        self.assertEqual("Church Prayers", library["app_name"]["en"])

    def test_duplicate_home_sections_are_hidden(self):
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        create_view = home[home.index("public View createView()") : home.index("private void addUpdateBanner")]
        date_card = home[home.index("private void addDateCard") : home.index("private void addQuickAccess")]
        self.assertNotIn("addStatusCard", create_view)
        self.assertNotIn("addTodayFastingGuide", create_view)
        self.assertNotIn('today.optJSONObject("feast")', date_card)
        self.assertTrue(source_omits_text(home, "تفاصيل صوم اليوم", "ar"))
        self.assertTrue(source_omits_text(home, "عرض تفاصيل الأيام التسعة", "ar", exact=True))
        self.assertTrue(source_omits_text(home, "الأحد القادم", "ar", exact=True))

    def test_important_home_shortcuts_are_visible_and_routes_remain(self):
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        main = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/MainActivity.java").read_text(encoding="utf-8")
        for route in ('case "search"', 'case "favorites"', 'case "calendar"', 'case "language_packs"'):
            self.assertIn(route, main)
        for retained in (
            "قداس اليوم الكامل",
            "القراءات اليومية",
            "الصلوات اليومية",
            "التقويم والصيام",
            "خدمة الأيام التسعة تبدأ من اليوم ومكتملة",
            "الكنائس والبث المباشر",
        ):
            self.assertTrue(source_references_text(home, retained, "ar"), retained)
        for hidden in ("البحث", "المفضلة", "آخر قراءة", "اللغات", "الإعدادات"):
            self.assertTrue(source_omits_text(home, hidden, "ar"), hidden)

    def test_home_uses_a_compact_calendar_icon_for_the_nine_day_fasting_view(self):
        base = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BaseScreen.java").read_text(encoding="utf-8")
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        upcoming = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/UpcomingScreen.java").read_text(encoding="utf-8")
        self.assertTrue(source_references_text(base, "✓ مسموح   ✕ ممنوع", "ar", exact=True))
        self.assertIn('!fasting.optBoolean("is_fast", false)', base)
        self.assertTrue(source_omits_text(home, "جدول الصيام للأيام التسعة", "ar", exact=True))
        self.assertIn("R33_COMPACT_FASTING_HOME", home)
        self.assertIn('ui_calendar_and_fasting_51a9bf84), "upcoming", null', home)
        self.assertNotIn("int dayCount = Math.min(8, upcoming.length());", home)
        self.assertNotIn("private void addUpcoming", home)
        self.assertIn('host.navigate("calendar_day", itemDate)', upcoming)
        self.assertIn('host.navigate("calendar", null)', upcoming)
        self.assertIn("addCompactFastingItems(card, fasting)", upcoming)

    def test_settings_hide_call_and_privacy_actions_only(self):
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        self.assertTrue(source_omits_text(settings, "الاتصال بالرقم", "ar"))
        self.assertTrue(source_omits_text(settings, "Call phone number", "en"))
        self.assertTrue(source_omits_text(settings, "سياسة الخصوصية", "ar"))
        self.assertTrue(source_omits_text(settings, "Privacy policy", "en"))
        self.assertNotIn("maen1977.github.io/orthodox_prayers/privacy", settings)
        self.assertTrue(source_references_text(settings, "هذا البرنامج مجاني", "ar"))
        self.assertTrue((ROOT / "PRIVACY.md").is_file())

    def test_daily_prayer_components_remain_available(self):
        library = json.loads((ROOT / "data/services/library.json").read_text(encoding="utf-8"))
        service_ids = {service["id"] for service in library["services"]}
        self.assertTrue({
            "morning_prayer", "evening_prayer", "small_compline",
            "before_food", "after_food", "lord_prayer", "creed", "trisagion",
        }.issubset(service_ids))

    def test_r15_patch_verifier(self):
        verifier = (ROOT / "scripts/verify_r15_patch.py").read_text(encoding="utf-8")
        self.assertIn("PATCH_R15_OK", verifier)
        self.assertIn('versionName = "5.0.11"', verifier)


if __name__ == "__main__":
    unittest.main()
