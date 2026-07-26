from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class R14HomeCleanupTests(unittest.TestCase):
    def test_app_is_renamed_to_church_prayers(self):
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        widget = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/widget/DailyAgendaWidget.java").read_text(encoding="utf-8")
        library = json.loads((ROOT / "app/src/main/assets/data/library.json").read_text(encoding="utf-8"))
        self.assertIn("الصلوات الكنسية", home)
        self.assertIn("الصلوات الكنسية", widget)
        self.assertEqual("الصلوات الكنسية", library["app_name"]["ar"])
        self.assertEqual("Church Prayers", library["app_name"]["en"])

    def test_duplicate_home_sections_are_hidden(self):
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        create_view = home[home.index("public View createView()") : home.index("private void addUpdateBanner")]
        date_card = home[home.index("private void addDateCard") : home.index("private String fastingValue")]
        self.assertNotIn("addStatusCard", create_view)
        self.assertNotIn("addTodayFastingGuide", create_view)
        self.assertNotIn('today.optJSONObject("feast")', date_card)
        self.assertNotIn("تفاصيل صوم اليوم", home)
        self.assertIn("عرض تفاصيل الأيام السبعة", home)
        self.assertIn("الأحد القادم", home)

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
            "الأيام السبعة القادمة",
            "الكنائس والبث المباشر",
            "البحث",
            "المفضلة",
            "آخر قراءة",
            "اللغات",
            "الإعدادات",
        ):
            self.assertIn(retained, home)

    def test_home_shows_a_light_seven_day_fasting_table(self):
        base = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BaseScreen.java").read_text(encoding="utf-8")
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        upcoming = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/UpcomingScreen.java").read_text(encoding="utf-8")
        self.assertIn("✓ مسموح   ✕ ممنوع", base)
        self.assertIn('!fasting.optBoolean("is_fast", false)', base)
        self.assertIn("جدول الصيام للأيام السبعة", home)
        self.assertIn('host.navigate("calendar_day", date)', home)
        self.assertIn('"calendar", null', home)
        self.assertIn("addCompactFastingItems(card, fasting)", upcoming)

    def test_settings_hide_call_and_privacy_actions_only(self):
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        self.assertNotIn("الاتصال بالرقم", settings)
        self.assertNotIn("Call phone number", settings)
        self.assertNotIn("سياسة الخصوصية", settings)
        self.assertNotIn("Privacy policy", settings)
        self.assertNotIn("maen1977.github.io/orthodox_prayers/privacy", settings)
        self.assertIn("هذا البرنامج مجاني", settings)
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
