from __future__ import annotations

import unittest
import json
from pathlib import Path

from scripts.android_ui_resources import source_references_text


ROOT = Path(__file__).resolve().parents[1]


class R19RefinementTests(unittest.TestCase):
    def test_release_version_and_native_pack_coverage_are_current(self):
        build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        self.assertIn('versionName = "5.5.1"', build)
        self.assertIn("versionCode = 50501", build)
        self.assertIn("libraryForLanguage(language)", repository)
        self.assertIn("nativeContentCoverage", repository)
        self.assertNotIn('aggregate.put("library", library())', repository)

    def test_settings_hide_internal_book_completeness_from_ordinary_users(self):
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        self.assertNotIn("religiousCompleteServiceCount", settings)
        self.assertNotIn("religiousRequiredServiceCount", settings)
        self.assertNotIn("الاكتمال الكنسي المثبت", settings)
        self.assertNotIn("Verified ecclesiastical completeness", settings)
        self.assertNotIn("Native source-pack completeness", settings)

    def test_settings_keep_diagnostics_optional_and_use_real_time_picker(self):
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        preferences = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java").read_text(encoding="utf-8")
        self.assertIn("advancedDiagnosticsExpanded", settings)
        self.assertIn("if (preferences.advancedDiagnosticsExpanded())", settings)
        self.assertIn("new TimePicker", settings)
        self.assertTrue(source_references_text(settings, "اختيار الوقت", "ar", exact=True))
        self.assertTrue(source_references_text(settings, "Choose time", "en", exact=True))
        self.assertTrue(source_references_text(settings, "Ἐπιλογὴ ὥρας", "el", exact=True))
        self.assertNotIn("+ 30) % 1440", settings)
        self.assertIn("resetReaderPreferences", preferences)

    def test_selected_locale_and_greek_font_labels_do_not_fall_back_to_english(self):
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        locale_policy = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/LocalePolicy.java").read_text(encoding="utf-8")
        self.assertIn("LocalePolicy.formatTimestamp", settings)
        for language, serif, monospace in (
            ("ar", "كتاب", "ثابت العرض"),
            ("en", "Serif", "Monospace"),
            ("el", "Μὲ πατούρες", "Σταθεροῦ πλάτους"),
        ):
            self.assertTrue(source_references_text(settings, serif, language, exact=True))
            self.assertTrue(source_references_text(settings, monospace, language, exact=True))
        self.assertIn("isolateTechnical", locale_policy)

    def test_current_documentation_matches_the_follow_along_product_scope(self):
        readme = (ROOT / "README_AR.md").read_text(encoding="utf-8")
        readiness = (ROOT / "RELEASE_READINESS_AR.md").read_text(encoding="utf-8")
        self.assertIn("قداس اليوم الكامل", readme)
        self.assertIn("canonical/follow_along_liturgy_contract.json", readme)
        self.assertIn("04:23", readme)
        self.assertIn("لا توجد ترجمة بين القنوات", readme)
        self.assertIn("نطاق الإصدار الفعلي", readiness)
        self.assertIn("ليست شرطًا لهذا المنتج", readiness)

    def test_source_registry_build_is_reproducible_and_does_not_fabricate_verification_dates(self):
        builder = (ROOT / "scripts/build_public_source_registry.py").read_text(encoding="utf-8")
        self.assertNotIn("date.today()", builder)
        self.assertIn('"last_verified": latest[:10]', builder)

    def test_publication_contract_matches_the_single_scheduled_workflow(self):
        contract = json.loads((ROOT / "canonical/source_native_contract.json").read_text(encoding="utf-8"))
        publication = contract["publication"]
        self.assertEqual("04:23 and 16:43 Asia/Amman every 24 hours", publication["daily_update_time"])
        self.assertEqual(["04:23", "16:43"], publication["daily_update_windows"])
        self.assertEqual("same_workflow_after_publish", publication["verification_mode"])
        self.assertNotIn("verification_time", publication)


if __name__ == "__main__":
    unittest.main()
