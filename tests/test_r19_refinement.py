from __future__ import annotations

import unittest
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class R19RefinementTests(unittest.TestCase):
    def test_release_version_and_native_pack_coverage_are_current(self):
        build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")
        repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        self.assertIn('versionName = "5.0.15"', build)
        self.assertIn("versionCode = 50015", build)
        self.assertIn("libraryForLanguage(language)", repository)
        self.assertIn("nativeContentCoverage", repository)
        self.assertNotIn('aggregate.put("library", library())', repository)

    def test_settings_measure_all_three_independent_packs(self):
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        for language in ("ar", "en", "el"):
            self.assertIn(f'data.nativeContentCoverage("{language}")', settings)
        self.assertIn("اكتمال حزم النصوص الأصلية", settings)
        self.assertIn("Native source-pack completeness", settings)

    def test_settings_keep_diagnostics_optional_and_use_real_time_picker(self):
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        preferences = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/AppPreferences.java").read_text(encoding="utf-8")
        self.assertIn("advancedDiagnosticsExpanded", settings)
        self.assertIn("if (preferences.advancedDiagnosticsExpanded())", settings)
        self.assertIn("new TimePicker", settings)
        self.assertIn('setTitle(local("اختيار الوقت", "Choose time", "Ἐπιλογὴ ὥρας"))', settings)
        self.assertNotIn("+ 30) % 1440", settings)
        self.assertIn("resetReaderPreferences", preferences)

    def test_selected_locale_and_greek_font_labels_do_not_fall_back_to_english(self):
        settings = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java").read_text(encoding="utf-8")
        locale_policy = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/LocalePolicy.java").read_text(encoding="utf-8")
        self.assertIn("LocalePolicy.formatTimestamp", settings)
        self.assertIn('local("كتاب", "Serif", "Μὲ πατούρες")', settings)
        self.assertIn('local("ثابت العرض", "Monospace", "Σταθεροῦ πλάτους")', settings)
        self.assertIn("isolateTechnical", locale_policy)

    def test_current_documentation_matches_signed_snapshot_and_pack_counts(self):
        readme = (ROOT / "README_AR.md").read_text(encoding="utf-8")
        readiness = (ROOT / "RELEASE_READINESS_AR.md").read_text(encoding="utf-8")
        self.assertIn("533/533", readme)
        self.assertIn("770/770", readme)
        self.assertIn("762/762", readme)
        self.assertIn("17 يوليو 2026", readiness)

    def test_source_registry_build_is_reproducible_and_does_not_fabricate_verification_dates(self):
        builder = (ROOT / "scripts/build_public_source_registry.py").read_text(encoding="utf-8")
        self.assertNotIn("date.today()", builder)
        self.assertIn('"last_verified": latest[:10]', builder)

    def test_publication_contract_matches_the_single_scheduled_workflow(self):
        contract = json.loads((ROOT / "canonical/source_native_contract.json").read_text(encoding="utf-8"))
        publication = contract["publication"]
        self.assertEqual("00:00 Asia/Amman", publication["daily_update_time"])
        self.assertEqual("same_workflow_after_publish", publication["verification_mode"])
        self.assertNotIn("verification_time", publication)


if __name__ == "__main__":
    unittest.main()
