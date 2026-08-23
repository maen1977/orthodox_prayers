import copy
import json
import unittest
from pathlib import Path

from scripts.validate_native_commemorations import validate


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "canonical" / "jerusalem_jordan_fixed_commemorations_native.json"


class NativeCommemorationEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    def test_canonical_evidence_contract_is_valid(self):
        report = validate(self.payload)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(366, report["coverage"]["records"])
        self.assertEqual(366, report["coverage"]["expected_slots"])
        self.assertEqual(0, report["coverage"]["strict_local_three_language_slots"])
        self.assertEqual(366, report["coverage"]["comparative_lane_entries"])

    def test_leap_slot_keeps_arabic_and_comparative_english_separate(self):
        record = next(row for row in self.payload["records"] if row["old_calendar_month_day"] == "02-29")
        self.assertIn("ar", record["lanes"])
        self.assertIn("en", record["lanes"])
        self.assertIn("el", record["lanes"])
        self.assertEqual(record["lanes"]["el"]["text"], "Κασσιανοῦ ὁσίου")
        self.assertEqual(record["lanes"]["el"]["source_page"], 60)
        self.assertFalse(record["lanes"]["el"]["comparative"])
        self.assertNotEqual(record["lanes"]["ar"]["text"], record["lanes"]["en"]["text"])
        self.assertTrue(record["lanes"]["en"]["comparative"])

    def test_arabic_cannot_be_copied_into_english_lane(self):
        payload = copy.deepcopy(self.payload)
        record = next(row for row in payload["records"] if row["old_calendar_month_day"] == "01-01")
        record["lanes"]["en"]["text"] = record["lanes"]["ar"]["text"]
        report = validate(payload)
        self.assertFalse(report["ok"])
        self.assertTrue(any("identical text" in error for error in report["errors"]))

    def test_comparative_source_cannot_be_promoted_to_local(self):
        payload = copy.deepcopy(self.payload)
        record = next(row for row in payload["records"] if row["old_calendar_month_day"] == "01-01")
        english = record["lanes"]["en"]
        english["comparative"] = False
        english["jurisdiction"] = "jerusalem_patriarchate"
        english["evidence_status"] = "VERIFIED_NATIVE_LOCAL_ENGLISH_SOURCE"
        report = validate(payload)
        self.assertFalse(report["ok"])
        self.assertTrue(any("source jurisdiction" in error for error in report["errors"]))

    def test_missing_old_calendar_slot_is_rejected(self):
        payload = copy.deepcopy(self.payload)
        payload["records"] = [row for row in payload["records"] if row["old_calendar_month_day"] != "02-29"]
        report = validate(payload)
        self.assertFalse(report["ok"])
        self.assertTrue(any("records count" in error or "missing slots" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
