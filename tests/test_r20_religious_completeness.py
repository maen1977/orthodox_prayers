from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class R20ReligiousCompletenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "r20_update_liturgical_data",
            ROOT / "scripts/update_liturgical_data.py",
        )
        assert spec and spec.loader
        cls.update = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.update)

    def test_declaration_is_valid_but_production_gate_is_honestly_blocked(self):
        normal = subprocess.run(
            [sys.executable, "scripts/validate_religious_completeness.py"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, normal.returncode, normal.stdout + normal.stderr)
        production = subprocess.run(
            [
                sys.executable,
                "scripts/validate_religious_completeness.py",
                "--require-production-complete",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(0, production.returncode)
        self.assertIn("production completeness", production.stdout + production.stderr)

    def test_manifest_covers_fifteen_required_services_for_each_language(self):
        manifest = json.loads(
            (ROOT / "canonical/religious_completeness_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        required = set(manifest["required_services"])
        self.assertEqual(15, len(required))
        for language in ("ar", "en", "el"):
            self.assertEqual(required, set(manifest["languages"][language]))
            self.assertNotIn(
                "complete_exact_native_edition",
                set(manifest["languages"][language].values()),
            )

    def test_ui_does_not_present_field_coverage_as_religious_completeness(self):
        settings = (
            ROOT
            / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/SettingsScreen.java"
        ).read_text(encoding="utf-8")
        home = (
            ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/HomeScreen.java"
        ).read_text(encoding="utf-8")
        self.assertIn("religiousCompleteServiceCount", settings)
        self.assertNotIn("Native source-pack completeness", settings)
        self.assertNotIn("Full Divine Liturgy", home)
        repository = (
            ROOT
            / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java"
        ).read_text(encoding="utf-8")
        self.assertIn("legacyDynamicSlots", repository)

    def test_all_native_liturgies_expose_daily_scripture_slots(self):
        expected = {"prokeimenon", "epistle", "gospel"}
        for language in ("ar", "en", "el"):
            pack = json.loads(
                (ROOT / f"data/services/native/library_{language}.json").read_text(
                    encoding="utf-8"
                )
            )
            liturgy = next(
                service
                for service in pack["services"]
                if service["id"] == "divine_liturgy"
            )
            slots = {
                segment.get("dynamic_slot")
                for segment in liturgy["segments"]
                if isinstance(segment, dict) and segment.get("dynamic_slot")
            }
            self.assertTrue(expected.issubset(slots), (language, slots))
            self.assertTrue(
                any(
                    segment.get("dynamic_inline_slot")
                    == "gospel_evangelist_name"
                    for segment in liturgy["segments"]
                    if isinstance(segment, dict)
                ),
                language,
            )

    def test_daily_overlay_carries_same_language_text_for_every_slot(self):
        current = json.loads(
            (ROOT / "data/calendar/today.json").read_text(encoding="utf-8")
        )
        day = self.update.date.fromisoformat(current["date_iso"])
        info = self.update.day_info(day)
        readings = current["readings"]
        overlay = self.update.build_liturgy_service(
            "divine_liturgy", day, info, readings, "خدمة اليوم"
        )
        for slot in ("prokeimenon", "epistle", "gospel"):
            replacement = overlay["slot_replacements"][slot]
            for language in ("ar", "en", "el"):
                self.assertTrue(replacement[language].strip(), (slot, language))


if __name__ == "__main__":
    unittest.main()
