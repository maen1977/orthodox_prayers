from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")


def load_module(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class H22026LectionaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = load_module("h2_2026_audit", "scripts/audit_2026_h2_lectionary.py")
        cls.payload = json.loads((ROOT / "canonical/jordan_2026_h2_lectionary.json").read_text(encoding="utf-8"))
        cls.days = cls.payload["days"]

    def test_range_is_consecutive_and_complete(self):
        self.assertEqual(157, len(self.days))
        expected = date(2026, 7, 28)
        for item in self.days:
            self.assertEqual(expected.isoformat(), item["date"])
            expected += timedelta(days=1)
        self.assertEqual(date(2027, 1, 1), expected)

    def test_all_dates_have_three_lane_epistle_and_gospel_references(self):
        for item in self.days:
            for kind in ("epistle", "gospel"):
                reading = item["reading_references"][kind]
                self.assertIsNotNone(self.audit.parse_reference_parts(reading["canonical_reference"]), (item["date"], kind))
                self.assertTrue(all(str(reading["reference"][language]).strip() for language in LANGUAGES), (item["date"], kind))

    def test_twenty_two_sundays_have_tone_eothinon_and_matins(self):
        sundays = [item for item in self.days if item["is_sunday"]]
        self.assertEqual(22, len(sundays))
        for item in sundays:
            sunday = item["sunday"]
            self.assertIn(sunday["resurrection_tone"], range(1, 9))
            self.assertIn(sunday["eothinon"], range(1, 12))
            self.assertIsNotNone(self.audit.parse_reference_parts(item["reading_references"]["matins_gospel"]["canonical_reference"]))

    def test_old_calendar_major_dates_are_overridden(self):
        by_date = {item["date"]: item for item in self.days}
        expected = {
            "2026-08-19": "transfiguration",
            "2026-08-28": "dormition",
            "2026-09-27": "exaltation_cross",
            "2026-12-04": "entry_theotokos",
            "2026-12-27": "sunday_forefathers",
        }
        for iso, override_id in expected.items():
            self.assertEqual(override_id, by_date[iso]["sources"]["override_id"])

    def test_today_epistle_and_gospel_have_exact_native_text_in_all_lanes(self):
        data = json.loads((ROOT / "canonical/generated_daily/2026-07-28.review.json").read_text(encoding="utf-8"))
        self.assertEqual("2026-07-28", data["date_iso"])
        scripture = [reading for reading in data["readings"] if reading.get("kind") in {"epistle", "gospel"}]
        self.assertEqual(2, len(scripture))
        for reading in scripture:
            for language in LANGUAGES:
                text = reading["body"][language]
                verification = reading["native_source_verification"][language]
                self.assertTrue(text.strip())
                self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), verification["text_sha256"])
                self.assertTrue(verification["text_available"])
                self.assertFalse(verification["machine_translation_used"])

    def test_compact_asset_and_android_wiring_pass_audit(self):
        report = self.audit.build_report()
        self.assertTrue(report["complete_for_current_delivery"], report["blockers"])
        self.assertLess(report["android_asset_bytes"], 500_000)


if __name__ == "__main__":
    unittest.main()
