from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path

from scripts.android_ui_resources import source_omits_text, source_references_text

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FastingGuidanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_module("fasting_update_test", "scripts/update_liturgical_data.py")
        cls.validator = load_module("fasting_guidance_validator_test", "scripts/validate_fasting_guidance.py")

    def profile(self, day: date) -> dict:
        return self.update.day_info(day)["fasting"]

    def test_strict_fast_explains_allowed_forbidden_and_duration(self):
        profile = self.profile(date(2026, 7, 22))  # Wednesday
        self.assertEqual("strict", profile["code"])
        self.assertIn("المسموح", profile["guidance"]["allowed_summary"]["ar"])
        self.assertIn("اللحوم والدواجن", profile["guidance"]["forbidden_summary"]["ar"])
        self.assertIn("لا يخمّن", profile["guidance"]["duration"]["ar"])
        self.assertFalse(profile["abstinence"]["applies"])
        self.assertIsNone(profile["abstinence"]["start_time"])
        self.assertEqual("NOT_INDICATED", profile["abstinence"]["verification"]["status"])

    def test_fish_allowance_is_explicit(self):
        transfiguration = self.update.julian_to_gregorian_date(2026, 8, 6)
        profile = self.profile(transfiguration)
        self.assertEqual("fish_allowed", profile["code"])
        self.assertTrue(profile["allowed"]["fish"])
        self.assertIn("السمك", profile["guidance"]["allowed_summary"]["ar"])
        self.assertIn("اللحوم والدواجن", profile["guidance"]["forbidden_summary"]["ar"])

    def test_fast_free_day_is_clear_for_new_believers(self):
        profile = self.profile(date(2026, 7, 23))
        self.assertEqual("fast_free", profile["code"])
        self.assertIn("جميع الأصناف", profile["guidance"]["allowed_summary"]["ar"])
        self.assertIn("لا توجد", profile["guidance"]["duration"]["ar"])

    def test_validator_rejects_food_code_contradiction(self):
        profile = self.profile(date(2026, 7, 22))
        profile["allowed"]["fish"] = True
        data = {
            "schema_version": 10,
            "fasting_guidance_version": 1,
            "fasting": profile,
            "upcoming": [{"fasting": copy.deepcopy(profile)} for _ in range(8)],
            "next_sunday": {"fasting": copy.deepcopy(profile)},
        }
        errors = self.validator.validate(data)
        self.assertTrue(any("contradicts fasting code strict" in error for error in errors))

    def test_documented_interval_requires_exact_evidence(self):
        profile = self.profile(date(2026, 7, 22))
        profile["abstinence"].update({
            "applies": True,
            "kind": "documented_interval",
            "start_time": "00:00",
            "end_time": "15:00",
            "verification": {"status": "DOCUMENTED_OVERRIDE", "source": "scripts/overrides/2026-07-22.json"},
        })
        data = {
            "schema_version": 10,
            "fasting_guidance_version": 1,
            "fasting": profile,
            "upcoming": [{"fasting": copy.deepcopy(profile)} for _ in range(8)],
            "next_sunday": {"fasting": copy.deepcopy(profile)},
        }
        self.assertEqual([], self.validator.validate(data))
        data["fasting"]["abstinence"]["start_time"] = "midnight"
        self.assertTrue(any("HH:MM required" in error for error in self.validator.validate(data)))

    def test_current_august_2026_asset_resolves_dormition_fast(self):
        asset = json.loads((ROOT / "app/src/main/assets/data/calendar/calendar_2026.json").read_text(encoding="utf-8"))
        profiles = asset["fasting_profiles"]
        day = next(item for item in asset["days"] if item["date_iso"] == "2026-08-22")
        fasting = dict(profiles[day["fasting"]["profile_id"]])
        fasting.update({key: value for key, value in day["fasting"].items() if key != "profile_id"})
        self.assertTrue(fasting["is_fast"])
        self.assertEqual("wine_oil", fasting["code"])
        self.assertIn("صوم السيدة والدة الإله", fasting["title"]["ar"])
        self.assertTrue(fasting["items"][4]["allowed"])
        self.assertTrue(fasting["items"][5]["allowed"])

    def test_stale_snapshot_surfaces_use_current_annual_calendar(self):
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        upcoming = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/UpcomingScreen.java").read_text(encoding="utf-8")
        worker = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/work/PrayerReminderWorker.java").read_text(encoding="utf-8")
        widget = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/widget/DailyAgendaWidget.java").read_text(encoding="utf-8")
        self.assertIn("currentDayForDisplay", repository)
        self.assertIn("JSONObject today = data.currentDayForDisplay();", home)
        self.assertIn("data.currentDayForDisplay().optJSONObject(\"fasting\")", upcoming)
        self.assertIn("app.repository().currentDayForDisplay()", worker)
        self.assertIn("app.repository().currentDayForDisplay()", widget)
        self.assertIn("data.currentAmmanDate()", home)

    def test_android_surfaces_render_fasting_guidance(self):
        base = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/BaseScreen.java").read_text(encoding="utf-8")
        home = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java").read_text(encoding="utf-8")
        upcoming = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/UpcomingScreen.java").read_text(encoding="utf-8")
        day = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarDayScreen.java").read_text(encoding="utf-8")
        self.assertIn("addFastingGuide", base)
        self.assertTrue(source_omits_text(home, "تفاصيل صوم اليوم", "ar"))
        self.assertTrue(source_omits_text(home, "جدول الصيام للأيام التسعة", "ar"))
        self.assertIn("String fastingDate = data.isTodayCurrent() ? data.dataDate() : data.currentAmmanDate();", home)
        self.assertIn("fastingDisplayTitle(today, fastingDate)", home)
        self.assertIn("data.currentDayForDisplay()", home)
        self.assertIn("if (isFastingDay(fasting))", upcoming)
        self.assertIn("addCompactFastingItems(card, fasting);", upcoming)
        self.assertIn("if (isFastingDay(fasting)) addFastingGuide(card, fasting, true);", day)
        self.assertIn('JSONObject guidance = fasting.optJSONObject("guidance");', base)
        self.assertIn('localized(fasting.optJSONObject("detail"), "")', base)

    def test_compact_annual_assets_keep_food_items_and_localized_detail(self):
        for year in (2026, 2027, 2050):
            asset = json.loads((ROOT / f"app/src/main/assets/data/calendar/calendar_{year}.json").read_text(encoding="utf-8"))
            profiles = asset["fasting_profiles"]
            fasting_ref = next(day["fasting"] for day in asset["days"] if day["fasting"].get("profile_id"))
            fasting = profiles[fasting_ref["profile_id"]]
            self.assertNotIn("guidance", fasting)
            self.assertEqual(6, len(fasting["items"]))
            for language in ("ar", "en", "el"):
                self.assertTrue(fasting["detail"][language].strip())
                self.assertTrue(fasting["title"][language].strip())

    def test_r15_patch_verifier_is_present(self):
        verifier = (ROOT / "scripts/verify_r15_patch.py").read_text(encoding="utf-8")
        self.assertIn("PATCH_R15_OK", verifier)
        self.assertIn('versionName = "5.0.11"', verifier)

    def test_generated_payload_marks_fasting_guidance_contract(self):
        old = self.update.os.environ.get("ORTHODOX_DISABLE_DISCOVERY_NETWORK")
        self.update.os.environ["ORTHODOX_DISABLE_DISCOVERY_NETWORK"] = "1"
        try:
            payload = self.update.build_day(date(2026, 7, 20))
        finally:
            if old is None:
                self.update.os.environ.pop("ORTHODOX_DISABLE_DISCOVERY_NETWORK", None)
            else:
                self.update.os.environ["ORTHODOX_DISABLE_DISCOVERY_NETWORK"] = old
        self.assertEqual(1, payload["fasting_guidance_version"])
        self.assertEqual([], self.validator.validate(payload))
        self.assertEqual(8, len(payload["upcoming"]))
        for item in payload["upcoming"]:
            self.assertIn("guidance", item["fasting"])
            self.assertIn("abstinence", item["fasting"])


if __name__ == "__main__":
    unittest.main()
