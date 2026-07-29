import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")


def load_updater():
    path = ROOT / "scripts" / "update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("update_liturgical_data_phase5", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class R21Phase5AnnualPropersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_updater()
        cls.fixed = json.loads((ROOT / "canonical/daily_propers.json").read_text(encoding="utf-8"))
        cls.movable = json.loads((ROOT / "canonical/paschal_cycle_propers.json").read_text(encoding="utf-8"))
        cls.coverage = json.loads((ROOT / "canonical/liturgy_annual_coverage.json").read_text(encoding="utf-8"))

    def assert_hashed_native_entry(self, entry):
        for field in ("troparion", "kontakion", "communion"):
            for lang in LANGS:
                text = entry[field][lang].strip()
                evidence = entry["verification"][field][lang]
                self.assertGreater(len(text), 20, (entry["id"], field, lang))
                self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), evidence["text_sha256"])
                self.assertFalse(evidence["ai_translation_used"])
                self.assertFalse(evidence["automatic_diacritization_used"])
                self.assertTrue(evidence["source_id"])
                self.assertTrue(evidence["source_url"])

    def test_six_major_fixed_feasts_are_complete_and_hashed(self):
        expected = {"02-02", "03-25", "08-06", "08-15", "09-08", "11-21"}
        self.assertTrue(expected.issubset(self.fixed["fixed_feasts"]))
        for key in expected:
            entry = self.fixed["fixed_feasts"][key]
            self.assert_hashed_native_entry(entry)
            self.assertIn("prokeimenon", entry)
            for lang in LANGS:
                self.assertTrue(entry["prokeimenon"]["body"][lang].strip())

    def test_fixed_feasts_resolve_on_old_calendar_dates(self):
        expected = {
            (2, 2): "meeting_of_the_lord",
            (3, 25): "annunciation_theotokos",
            (8, 6): "transfiguration_lord",
            (8, 15): "dormition_theotokos",
            (9, 8): "nativity_theotokos",
            (11, 21): "entry_theotokos_temple",
        }
        for (month, day_num), proper_id in expected.items():
            civil = self.update.julian_to_gregorian_date(2026, month, day_num)
            info = self.update.day_info(civil)
            inserts = self.update.feast_inserts(info, civil)
            self.assertEqual(proper_id, inserts["proper_id"])
            self.assertEqual("fixed", inserts["proper_provenance"])
            for slot in ("troparion", "kontakion", "communion"):
                for lang in LANGS:
                    self.assertTrue(inserts[slot][lang].strip(), (proper_id, slot, lang))
            prok = self.update.exact_or_sunday_prokeimenon(civil, info)
            self.assertEqual(f"fixed_feast:{proper_id}", prok["integrity"]["proper_provenance"])

    def test_palm_ascension_and_pentecost_resolve_from_pascha(self):
        pascha = self.update.orthodox_pascha_gregorian(2026)
        cases = {
            -7: "palm_sunday",
            39: "ascension_lord",
            49: "holy_pentecost",
        }
        for offset, proper_id in cases.items():
            civil = pascha + timedelta(days=offset)
            info = self.update.day_info(civil)
            inserts = self.update.feast_inserts(info, civil)
            self.assertEqual(f"paschal:{proper_id}", inserts["proper_id"])
            self.assertEqual("paschal", inserts["proper_provenance"])
            for slot in ("troparion", "kontakion", "communion"):
                for lang in LANGS:
                    self.assertTrue(inserts[slot][lang].strip(), (proper_id, slot, lang))
            prok = self.update.exact_or_sunday_prokeimenon(civil, info)
            self.assertEqual(f"paschal_cycle:{proper_id}", prok["integrity"]["proper_provenance"])

    def test_movable_entries_are_hashed_and_native_locked(self):
        self.assertEqual({"-7", "39", "49"}, set(self.movable["offsets"]))
        for entry in self.movable["offsets"].values():
            self.assert_hashed_native_entry(entry)

    def test_phase5_variable_branches_win_over_ordinary_fallbacks(self):
        pascha = self.update.orthodox_pascha_gregorian(2026)
        palm = self.update.feast_inserts(self.update.day_info(pascha - timedelta(days=7)), pascha - timedelta(days=7))
        self.assertIn("palm_sunday", palm["variant_ids"])
        for lang in LANGS:
            self.assertTrue(palm["entrance_hymn"][lang].strip())

        ascension_day = pascha + timedelta(days=39)
        ascension = self.update.feast_inserts(self.update.day_info(ascension_day), ascension_day)
        self.assertIn("ascension", ascension["variant_ids"])
        for lang in LANGS:
            self.assertTrue(ascension["dismissal"][lang].strip())
        self.assertEqual("ascension", ascension["slot_provenance"]["dismissal"]["rule_id"])

        pentecost_day = pascha + timedelta(days=49)
        pentecost = self.update.feast_inserts(self.update.day_info(pentecost_day), pentecost_day)
        self.assertIn("pentecost", pentecost["variant_ids"])
        for lang in LANGS:
            self.assertTrue(pentecost["trisagion_hymn"][lang].strip())
            self.assertTrue(pentecost["dismissal"][lang].strip())

    def test_priority_resolver_rejects_equal_priority_conflicts(self):
        registry = self.update.LITURGY_VARIABLE_PARTS_REGISTRY
        original = copy.deepcopy(registry)
        try:
            empty = {slot: {lang: "" for lang in LANGS} for slot in self.update._empty_variable_parts()}
            first = copy.deepcopy(empty)
            second = copy.deepcopy(empty)
            first["dismissal"] = {lang: "First exact text" for lang in LANGS}
            second["dismissal"] = {lang: "Second exact text" for lang in LANGS}
            registry["variants"]["phase5_conflict_a"] = {"parts": first}
            registry["variants"]["phase5_conflict_b"] = {"parts": second}
            registry["rules"].extend([
                {"id": "phase5_conflict_a", "kind": "julian_fixed", "month": 7, "day": 14, "variant": "phase5_conflict_a", "priority": 999},
                {"id": "phase5_conflict_b", "kind": "julian_fixed", "month": 7, "day": 14, "variant": "phase5_conflict_b", "priority": 999},
            ])
            civil = self.update.julian_to_gregorian_date(2026, 7, 14)
            with self.assertRaisesRegex(ValueError, "Conflicting Liturgy variable parts"):
                self.update.variable_liturgy_parts(civil, self.update.day_info(civil), None)
        finally:
            registry.clear()
            registry.update(original)

    def test_higher_priority_rule_wins_per_slot_without_erasing_other_slots(self):
        registry = self.update.LITURGY_VARIABLE_PARTS_REGISTRY
        original = copy.deepcopy(registry)
        try:
            empty = {slot: {lang: "" for lang in LANGS} for slot in self.update._empty_variable_parts()}
            low = copy.deepcopy(empty)
            high = copy.deepcopy(empty)
            low["entrance_hymn"] = {lang: "Low entrance" for lang in LANGS}
            low["dismissal"] = {lang: "Low dismissal" for lang in LANGS}
            high["dismissal"] = {lang: "High dismissal" for lang in LANGS}
            registry["variants"]["phase5_low"] = {"parts": low}
            registry["variants"]["phase5_high"] = {"parts": high}
            registry["rules"].extend([
                {"id": "phase5_low", "kind": "julian_fixed", "month": 7, "day": 15, "variant": "phase5_low", "priority": 50},
                {"id": "phase5_high", "kind": "julian_fixed", "month": 7, "day": 15, "variant": "phase5_high", "priority": 60},
            ])
            civil = self.update.julian_to_gregorian_date(2026, 7, 15)
            parts = self.update.variable_liturgy_parts(civil, self.update.day_info(civil), None)
            self.assertEqual("Low entrance", parts["entrance_hymn"]["en"])
            self.assertEqual("High dismissal", parts["dismissal"]["en"])
            self.assertEqual("phase5_low", parts["slot_provenance"]["entrance_hymn"]["rule_id"])
            self.assertEqual("phase5_high", parts["slot_provenance"]["dismissal"]["rule_id"])
        finally:
            registry.clear()
            registry.update(original)

    def test_reference_sunday_remains_ordinary_tone_seven(self):
        civil = date(2026, 7, 26)
        info = self.update.day_info(civil)
        inserts = self.update.feast_inserts(info, civil)
        self.assertEqual("dated:2026-07-26", inserts["proper_id"])
        self.assertEqual(7, inserts["resurrection_tone"])
        self.assertEqual([], inserts["variant_ids"])
        for lang in LANGS:
            self.assertTrue(inserts["alleluia_verses"][lang].strip())

    def test_coverage_matrix_is_explicitly_partial(self):
        self.assertEqual("unproven_complete", self.coverage["completion_claim"])
        self.assertFalse(self.coverage["machine_translation_allowed"])
        self.assertGreaterEqual(len(self.coverage["fixed_major_feasts"]), 6)
        self.assertGreaterEqual(len(self.coverage["paschal_cycle"]), 3)
        self.assertIn("complete_menaion_for_every_day_and_saint", self.coverage["explicit_gaps"])
        self.assertIn("final_ecclesiastical_human_review", self.coverage["explicit_gaps"])

    def test_religious_completion_claim_remains_blocked(self):
        manifest = json.loads((ROOT / "canonical/religious_completeness_manifest.json").read_text(encoding="utf-8"))
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
