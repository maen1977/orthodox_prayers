from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")
PHASE4_SLOTS = (
    "first_antiphon", "second_antiphon", "third_antiphon", "entrance_hymn",
    "trisagion_hymn", "alleluia_verses", "theotokos_hymn", "dismissal",
)


def load_updater():
    spec = importlib.util.spec_from_file_location(
        "phase4_update_liturgical_data", ROOT / "scripts/update_liturgical_data.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class R21Phase4VariablePartsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_updater()
        cls.registry = json.loads(
            (ROOT / "canonical/liturgy_variable_parts.json").read_text(encoding="utf-8")
        )

    def test_eight_tones_have_native_hashed_alleluia_verses(self):
        self.assertEqual({str(i) for i in range(1, 9)}, set(self.registry["alleluia_by_tone"]))
        for tone, entry in self.registry["alleluia_by_tone"].items():
            for lang in LANGS:
                text = entry["verses"][lang].strip()
                evidence = entry["verification"][lang]
                self.assertGreater(len(text), 35, (tone, lang))
                self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), evidence["text_sha256"])
                self.assertFalse(evidence["ai_translation_used"])
                self.assertFalse(evidence["automatic_diacritization_used"])

    def test_variable_parts_do_not_use_ellipsis_or_placeholder_guidance(self):
        serialized = json.dumps(self.registry["variants"], ensure_ascii=False).casefold()
        for forbidden in ("...", "…", "optional note", "ملاحظة اختيارية", "unavailable", "قيد الإضافة"):
            self.assertNotIn(forbidden, serialized)

    def test_fixed_old_calendar_feasts_resolve_group_variants(self):
        cases = {
            (1, 6): ("theophany", "baptismal"),
            (9, 14): ("exaltation_cross", "cross"),
            (12, 25): ("nativity", "baptismal"),
        }
        for (month, day_num), expected in cases.items():
            civil = self.update.julian_to_gregorian_date(2026, month, day_num)
            info = self.update.day_info(civil)
            parts = self.update.feast_inserts(info, civil)
            self.assertIn(expected[0], parts["variant_ids"])
            for lang in LANGS:
                self.assertTrue(parts["trisagion_hymn"][lang].strip())
            if expected[0] in {"nativity", "theophany"}:
                for slot in ("first_antiphon", "second_antiphon", "third_antiphon", "entrance_hymn"):
                    for lang in LANGS:
                        self.assertTrue(parts[slot][lang].strip(), (expected[0], slot, lang))

    def test_paschal_cross_baptismal_and_theotokos_rules(self):
        pascha = self.update.orthodox_pascha_gregorian(2026)
        cases = {
            -28: ("third_sunday_lent", "cross"),
            -8: ("lazarus_saturday", "baptized"),
            -1: ("holy_saturday", "baptized"),
            0: ("pascha", "baptized"),
            3: ("bright_week", "baptized"),
            49: ("pentecost", "baptized"),
        }
        for offset, (rule_id, marker) in cases.items():
            civil = pascha + timedelta(days=offset)
            info = self.update.day_info(civil)
            parts = self.update.feast_inserts(info, civil)
            self.assertIn(rule_id, parts["variant_ids"])
            for lang in LANGS:
                self.assertTrue(parts["trisagion_hymn"][lang].strip(), (offset, lang))
            if offset == 0:
                for lang in LANGS:
                    self.assertTrue(parts["theotokos_hymn"][lang].strip())

    def test_reference_sunday_gets_tone_seven_alleluia_without_false_feast_groups(self):
        civil = date(2026, 7, 26)
        info = self.update.day_info(civil)
        readings = self.update.discovery_readings(civil, info)
        service = self.update.build_liturgy_service("divine_liturgy", civil, info, readings, "خدمة اليوم")
        self.assertEqual(7, service["daily_reading_contract"]["resurrection_tone"])
        self.assertEqual([], service["daily_reading_contract"]["variable_part_ids"])
        for lang in LANGS:
            self.assertTrue(service["slot_replacements"]["alleluia_verses"][lang].strip())
        for slot in ("first_antiphon", "second_antiphon", "third_antiphon", "entrance_hymn", "trisagion_hymn", "theotokos_hymn"):
            for lang in LANGS:
                self.assertEqual("", service["slot_replacements"][slot][lang], (slot, lang))

    def test_weekday_dismissal_replaces_sunday_opening(self):
        civil = date(2026, 7, 27)
        info = self.update.day_info(civil)
        parts = self.update.feast_inserts(info, civil)
        self.assertIn("weekday_dismissal", parts["variant_ids"])
        for lang in LANGS:
            self.assertTrue(parts["dismissal"][lang].strip())
        self.assertNotIn("القائم من بين الأموات", parts["dismissal"]["ar"])
        self.assertNotIn("rose from the dead", parts["dismissal"]["en"])

    def test_native_packs_expose_all_phase4_slots_and_group_mode(self):
        for lang in LANGS:
            library = json.loads(
                (ROOT / f"data/services/native/library_{lang}.json").read_text(encoding="utf-8")
            )
            service = next(item for item in library["services"] if item["id"] == "divine_liturgy")
            slots = {segment.get("dynamic_slot") for segment in service["segments"] if isinstance(segment, dict)}
            self.assertTrue(set(PHASE4_SLOTS).issubset(slots), (lang, set(PHASE4_SLOTS) - slots))
            grouped = [segment for segment in service["segments"] if segment.get("dynamic_slot_mode") == "replace_group_if_present"]
            self.assertGreaterEqual(len(grouped), 4, lang)
            for slot in ("first_antiphon", "second_antiphon", "third_antiphon", "entrance_hymn", "trisagion_hymn"):
                members = [segment for segment in grouped if segment.get("dynamic_slot") == slot]
                self.assertTrue(members, (lang, slot))
                self.assertEqual(1, sum(bool(segment.get("dynamic_slot_group_emit")) for segment in members), (lang, slot))

    def test_android_composer_understands_group_replacement(self):
        source = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
        self.assertIn('"replace_group_if_present".equals(mode)', source)
        self.assertIn('dynamic_slot_group_emit', source)

    def test_main_liturgy_completion_claim_stays_blocked(self):
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
