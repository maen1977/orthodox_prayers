from __future__ import annotations

import importlib.util
import json
import os
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_updater():
    os.environ.setdefault("ORTHODOX_DISABLE_DISCOVERY_NETWORK", "1")
    path = ROOT / "scripts" / "update_liturgical_data.py"
    spec = importlib.util.spec_from_file_location("rolling_window_updater_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RollingWeekUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.update = load_updater()

    def test_contract_is_today_plus_eight_future_days(self):
        rules = json.loads((ROOT / "canonical/liturgy_service_rules.json").read_text(encoding="utf-8"))
        rolling = rules["rolling_window"]
        self.assertEqual("NINE_CONSECUTIVE_DAYS_STARTING_TODAY", rolling["policy"])
        self.assertEqual(9, rolling["day_count"])
        self.assertEqual(8, rolling["future_day_count"])
        self.assertFalse(rolling["annual_preload_required"])
        self.assertTrue(rolling["fail_closed"])

        update_source = (ROOT / "scripts/update.py").read_text(encoding="utf-8")
        builder_source = (ROOT / "scripts/build_rolling_week.py").read_text(encoding="utf-8")
        self.assertIn('"--days",\n        "9"', update_source)
        self.assertIn('default=9', builder_source)
        self.assertIn('NINE_CONSECUTIVE_DAYS_STARTING_TODAY', builder_source)

    def test_generated_payload_contains_today_plus_eight_consecutive_days(self):
        payload = self.update.build_day(date(2026, 7, 28))
        self.assertEqual(10, payload["schema_version"])
        self.assertEqual(8, len(payload["upcoming"]))
        expected = [date(2026, 7, 28) + timedelta(days=offset) for offset in range(9)]
        actual = [date.fromisoformat(payload["date_iso"])] + [
            date.fromisoformat(item["date"]) for item in payload["upcoming"]
        ]
        self.assertEqual(expected, actual)

        cards = [payload, *payload["upcoming"]]
        for item in cards:
            selection = item["liturgy_service_selection"]
            self.assertTrue(selection["service_type"])
            self.assertTrue(selection["service_form"])
            self.assertTrue(selection["reason"]["ar"])
            self.assertFalse(selection["wrong_liturgy_fallback_allowed"])
            self.assertEqual(
                "FROM_BEGINNING_TO_DISMISSAL_WITH_NATIVE_PREPARATION_AND_THANKSGIVING",
                selection["full_service_scope"],
            )

    def test_signed_last_trusted_release_remains_embedded_unchanged(self):
        trusted = ROOT / "data/calendar/today.json"
        trusted_signature = ROOT / "data/calendar/today.json.sig"
        embedded = ROOT / "app/src/main/assets/data/today.json"
        embedded_signature = ROOT / "app/src/main/assets/data/today.json.sig"
        self.assertEqual(trusted.read_bytes(), embedded.read_bytes())
        self.assertEqual(trusted_signature.read_bytes(), embedded_signature.read_bytes())

    def test_legacy_eight_day_unsigned_candidate_is_not_shipped(self):
        self.assertFalse((ROOT / "data/rolling-week/candidates/2026-07-28").exists())


if __name__ == "__main__":
    unittest.main()
