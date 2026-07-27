from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("ORTHODOX_DISABLE_DISCOVERY_NETWORK", "1")
LANGS = ("ar", "en", "el")


def load_updater():
    path = ROOT / "scripts" / "update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("update_liturgical_data_phase6", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class R21Phase6LiturgyServiceSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_updater()
        cls.rules = json.loads((ROOT / "canonical/liturgy_service_rules.json").read_text(encoding="utf-8"))
        cls.editions = json.loads((ROOT / "canonical/liturgy_service_editions.json").read_text(encoding="utf-8"))
        cls.pascha = cls.update.orthodox_pascha_gregorian(2026)

    def select(self, civil: date):
        return self.update.liturgy_service_selection(civil, self.update.day_info(civil))

    def test_pascha_and_five_lenten_sundays_select_basil(self):
        self.assertEqual(date(2026, 4, 12), self.pascha)
        for offset in (-42, -35, -28, -21, -14):
            selected = self.select(self.pascha + timedelta(days=offset))
            self.assertEqual("basil", selected["service_type"], offset)
            self.assertEqual("great_lent_sunday", selected["rule_id"], offset)
            self.assertFalse(selected["displayable"])

    def test_saint_basil_holy_thursday_and_holy_saturday(self):
        saint_basil = self.update.julian_to_gregorian_date(2026, 1, 1)
        self.assertEqual("basil", self.select(saint_basil)["service_type"])
        self.assertEqual("basil", self.select(self.pascha - timedelta(days=3))["service_type"])
        self.assertEqual("basil", self.select(self.pascha - timedelta(days=1))["service_type"])

    def test_presanctified_weekdays_and_holy_week(self):
        cases = (
            date(2026, 2, 25),  # Wednesday of the Fast
            date(2026, 2, 27),  # Friday of the Fast
            self.pascha - timedelta(days=6),  # Great Monday
            self.pascha - timedelta(days=4),  # Great Wednesday
        )
        for civil in cases:
            selected = self.select(civil)
            self.assertEqual("presanctified", selected["service_type"], civil)
            self.assertFalse(selected["displayable"], civil)

    def test_annunciation_exception_and_great_friday(self):
        annunciation = self.update.julian_to_gregorian_date(2026, 3, 25)
        self.assertEqual(date(2026, 4, 7), annunciation)
        selected = self.select(annunciation)
        self.assertEqual("chrysostom", selected["service_type"])
        self.assertEqual("annunciation_chrysostom_exception", selected["rule_id"])
        great_friday = self.select(self.pascha - timedelta(days=2))
        self.assertEqual("no_divine_liturgy", great_friday["service_type"])
        self.assertFalse(great_friday["displayable"])

        # Annunciation combined with a Lenten Sunday retains Basil.
        sunday_annunciation = self.update.julian_to_gregorian_date(2024, 3, 25)
        self.assertEqual(-28, (sunday_annunciation - self.update.orthodox_pascha_gregorian(2024)).days)
        self.assertEqual("basil", self.select(sunday_annunciation)["service_type"])

        # A Paschal-Triduum collision is never guessed from the generic rules.
        friday_collision = self.update.julian_to_gregorian_date(2034, 3, 25)
        collision = self.select(friday_collision)
        self.assertEqual("typikon_override_required", collision["service_type"])
        collision_service = self.update.build_liturgy_service(
            "divine_liturgy", friday_collision, self.update.day_info(friday_collision), [], "خدمة اليوم"
        )
        self.assertEqual(
            "BLOCKED_REQUIRES_DATED_OFFICIAL_TYPIKON_OVERRIDE",
            collision_service["publication_status"],
        )
        self.assertNotIn("extends_service_id", collision_service)

    def test_ordinary_reference_sunday_keeps_chrysostom(self):
        civil = date(2026, 7, 26)
        selected = self.select(civil)
        self.assertEqual("chrysostom", selected["service_type"])
        self.assertTrue(selected["displayable"])
        service = self.update.build_liturgy_service(
            "divine_liturgy", civil, self.update.day_info(civil), [], "خدمة اليوم"
        )
        self.assertEqual("divine_liturgy", service["extends_service_id"])
        self.assertEqual("library:divine_liturgy", service["template_id"])
        self.assertEqual("chrysostom", service["selected_liturgy_type"])
        self.assertFalse(service["wrong_liturgy_fallback_allowed"])

    def test_missing_basil_and_presanctified_editions_fail_closed(self):
        for civil, expected in (
            (self.pascha - timedelta(days=42), "basil"),
            (date(2026, 2, 25), "presanctified"),
        ):
            service = self.update.build_liturgy_service(
                "divine_liturgy", civil, self.update.day_info(civil), [], "خدمة اليوم"
            )
            self.assertEqual(expected, service["selected_liturgy_type"])
            self.assertNotIn("extends_service_id", service)
            self.assertNotIn("template_id", service)
            self.assertNotIn("slot_replacements", service)
            self.assertNotIn("segment_replacements", service)
            self.assertEqual(
                "BLOCKED_MISSING_COMPLETE_NATIVE_SERVICE_EDITION",
                service["publication_status"],
            )
            self.assertFalse(service["wrong_liturgy_fallback_allowed"])
            serialized = json.dumps(service, ensure_ascii=False)
            self.assertNotIn("ملاحظة اختيارية", serialized)

    def test_great_friday_never_gets_a_liturgy_template(self):
        civil = self.pascha - timedelta(days=2)
        service = self.update.build_liturgy_service(
            "divine_liturgy", civil, self.update.day_info(civil), [], "خدمة اليوم"
        )
        self.assertEqual("NO_DIVINE_LITURGY_APPOINTED", service["publication_status"])
        self.assertNotIn("extends_service_id", service)
        self.assertNotIn("template_id", service)

    def test_dated_override_requires_documented_evidence(self):
        civil = date(2026, 7, 26)
        with self.assertRaisesRegex(RuntimeError, "DOCUMENTED_OVERRIDE"):
            self.update.liturgy_service_selection(
                civil,
                {"liturgy_service_override": {"service_type": "basil", "evidence": {}}},
            )
        selected = self.update.liturgy_service_selection(
            civil,
            {
                "liturgy_service_override": {
                    "service_type": "basil",
                    "evidence": {
                        "status": "DOCUMENTED_OVERRIDE",
                        "source_id": "official_test_calendar",
                        "source_url": "https://example.invalid/official-calendar",
                    },
                }
            },
        )
        self.assertEqual("basil", selected["service_type"])
        self.assertEqual("dated_official_jordan_override", selected["rule_id"])
        self.assertFalse(selected["displayable"])

    def test_build_day_exposes_today_upcoming_and_next_sunday_selection(self):
        payload = self.update.build_day(date(2026, 7, 26))
        self.assertEqual("chrysostom", payload["liturgy_service_selection"]["service_type"])
        self.assertFalse(payload["wrong_liturgy_fallback_allowed"])
        self.assertIn("liturgy_service_selection", payload["next_sunday"])
        self.assertTrue(payload["upcoming"])
        for card in payload["upcoming"]:
            self.assertIn("liturgy_service_selection", card)

    def test_contracts_register_sources_and_remain_partial(self):
        self.assertTrue(self.rules["fail_closed"])
        self.assertFalse(self.rules["machine_translation_allowed"])
        self.assertFalse(self.editions["wrong_liturgy_fallback_allowed"])
        self.assertFalse(self.editions["machine_translation_allowed"])
        self.assertFalse(self.editions["editions"]["basil"]["displayable"])
        self.assertFalse(self.editions["editions"]["presanctified"]["displayable"])
        source_urls = " ".join(item["url"] for item in self.rules["sources"])
        self.assertIn("goarch.org", source_urls)
        self.assertIn("orthodoxjordan.org", source_urls)
        for service_type in ("basil", "presanctified"):
            for lang in LANGS:
                self.assertNotEqual(
                    "IMPORTED_COMPLETE_NATIVE_EDITION",
                    self.editions["editions"][service_type].get(lang),
                )


if __name__ == "__main__":
    unittest.main()
