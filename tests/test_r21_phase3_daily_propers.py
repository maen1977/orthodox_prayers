from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")


def load_updater():
    spec = importlib.util.spec_from_file_location(
        "phase3_update_liturgical_data", ROOT / "scripts/update_liturgical_data.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class R21Phase3DailyPropersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_updater()
        cls.resurrectional = json.loads(
            (ROOT / "canonical/resurrectional_propers.json").read_text(encoding="utf-8")
        )
        cls.dated = json.loads(
            (ROOT / "canonical/dated_liturgical_propers.json").read_text(encoding="utf-8")
        )

    def test_all_eight_resurrectional_tones_have_native_hashed_text(self):
        self.assertEqual({str(i) for i in range(1, 9)}, set(self.resurrectional["tones"]))
        for number, entry in self.resurrectional["tones"].items():
            self.assertEqual(int(number), entry["tone"])
            for lang in LANGS:
                text = entry["troparion"][lang].strip()
                evidence = entry["verification"][lang]
                self.assertGreater(len(text), 45, (number, lang))
                self.assertIn(
                    evidence["status"],
                    {
                        "VERIFIED_EXACT_NATIVE_SOURCE",
                        "HASHED_NATIVE_TEXT_REQUIRES_FINAL_ECCLESIASTICAL_REVIEW",
                    },
                )
                self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), evidence["text_sha256"])
                self.assertFalse(evidence["ai_translation_used"])
                self.assertFalse(evidence["automatic_diacritization_used"])

    def test_eleven_eothina_references_are_complete(self):
        eothina = self.resurrectional["eothina"]
        self.assertEqual({str(i) for i in range(1, 12)}, set(eothina))
        self.assertEqual("John 20:11-18", eothina["8"])

    def test_dated_authority_resolves_july_26_without_discovery(self):
        day = date(2026, 7, 26)
        info = self.update.day_info(day)
        readings = self.update.discovery_readings(day, info)
        by_kind = {item["kind"]: item for item in readings}
        self.assertEqual("John 20:11-18", by_kind["matins_gospel"]["integrity"]["canonical_reference"])
        self.assertEqual("1 Corinthians 1:10-17", by_kind["epistle"]["integrity"]["canonical_reference"])
        self.assertEqual("Matthew 14:14-22", by_kind["gospel"]["integrity"]["canonical_reference"])
        for kind in ("matins_gospel", "epistle", "gospel"):
            for lang in LANGS:
                text = by_kind[kind]["body"][lang].strip()
                evidence = by_kind[kind]["native_source_verification"][lang]
                self.assertTrue(text)
                self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), evidence["text_sha256"])
                self.assertFalse(evidence["ai_translation_used"])

    def test_july_26_service_fills_all_expected_daily_slots(self):
        day = date(2026, 7, 26)
        info = self.update.day_info(day)
        readings = self.update.discovery_readings(day, info)
        service = self.update.build_liturgy_service("divine_liturgy", day, info, readings, "خدمة اليوم")
        contract = service["daily_reading_contract"]
        self.assertEqual(7, contract["resurrection_tone"])
        self.assertEqual(8, contract["eothinon"])
        self.assertEqual("dated:2026-07-26", contract["proper_id"])
        for slot in (
            "daily_hymns", "daily_troparion", "daily_kontakion",
            "prokeimenon", "epistle", "gospel", "communion_hymn",
        ):
            for lang in LANGS:
                self.assertTrue(service["slot_replacements"][slot][lang].strip(), (slot, lang))
        self.assertNotIn("matins_gospel", service["slot_replacements"])
        for lang in LANGS:
            combined = "\n".join(
                str(service["slot_replacements"][slot][lang])
                for slot in service["slot_replacements"]
            ).casefold()
            self.assertNotIn("optional note", combined)
            self.assertNotIn("ملاحظة اختيارية", combined)
            self.assertNotIn("unavailable", combined)

    def test_ordinary_sunday_uses_tone_troparion_but_does_not_invent_kontakion(self):
        day = date(2026, 8, 2)
        info = self.update.day_info(day)
        inserts = self.update.feast_inserts(info, day)
        self.assertEqual(8, inserts["resurrection_tone"])
        for lang in LANGS:
            self.assertTrue(inserts["troparion"][lang].strip())
            self.assertTrue(inserts["communion"][lang].strip())
            self.assertEqual("", inserts["kontakion"][lang])

    def test_main_liturgy_completion_claim_remains_blocked(self):
        manifest = json.loads(
            (ROOT / "canonical/religious_completeness_manifest.json").read_text(encoding="utf-8")
        )
        self.assertNotEqual(
            manifest["production_complete_status"],
            manifest["languages"]["ar"]["chrysostom_liturgy"],
        )
        for language in ("en", "el"):
            self.assertEqual(
                manifest["production_complete_status"],
                manifest["languages"][language]["chrysostom_liturgy"],
            )


if __name__ == "__main__":
    unittest.main()
