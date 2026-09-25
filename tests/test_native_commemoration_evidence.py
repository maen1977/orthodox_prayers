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
        self.assertEqual(310, report["coverage"]["strict_local_three_language_slots"])
        self.assertEqual(1, report["coverage"]["comparative_lane_entries"])

    def test_arabic_visual_review_promotions_are_source_backed_and_not_strict_gate(self):
        packet = json.loads((ROOT / "canonical/arabic_visual_review_promotions.json").read_text(encoding="utf-8"))
        self.assertEqual(366, packet["reviewed_count"])
        self.assertEqual(366, len(packet["records"]))
        self.assertFalse(packet["machine_translation_used"])
        self.assertFalse(packet["cross_language_fallback"])
        self.assertEqual(366, self.payload["coverage"]["arabic_visual_review_promoted_slots"])
        self.assertEqual(0, self.payload["coverage"]["arabic_visual_review_pending_slots"])
        self.assertFalse(self.payload["coverage"]["strict_named_local_gate"])
        for slot, text in packet["records"].items():
            record = next(row for row in self.payload["records"] if row["old_calendar_month_day"] == slot)
            arabic = record["lanes"]["ar"]
            self.assertEqual(text, arabic["text"], slot)
            self.assertEqual("VERIFIED_NATIVE_LOCAL_ARABIC_SOURCE", arabic["evidence_status"], slot)
            self.assertTrue(arabic["fixed_slot_eligible"], slot)
            self.assertFalse(arabic["comparative"], slot)
            self.assertEqual("jerusalem_patriarchate", arabic["jurisdiction"], slot)

    def test_jerusalem_english_timetable_covers_365_local_slots_only(self):
        local = [
            row["lanes"]["en"]
            for row in self.payload["records"]
            if row["lanes"]["en"]["source_id"] == "jerusalem_patriarchate_english_timetable_2019"
        ]
        self.assertEqual(365, len(local))
        self.assertTrue(all(entry["comparative"] is False for entry in local))
        self.assertTrue(all(entry["fixed_slot_eligible"] is True for entry in local))
        self.assertEqual(1, self.payload["coverage"]["en_comparative_records"])
        leap = next(row for row in self.payload["records"] if row["old_calendar_month_day"] == "02-29")
        self.assertEqual("holy_trinity_calendar_en_comparative", leap["lanes"]["en"]["source_id"])
        self.assertTrue(leap["lanes"]["en"]["comparative"])
        self.assertFalse(self.payload["coverage"]["strict_named_local_gate"])

    def test_pending_arabic_slots_remain_visual_review_only(self):
        expected_pending = []
        pending = []
        for record in self.payload["records"]:
            arabic = record["lanes"]["ar"]
            if arabic["evidence_status"] == "VERIFIED_NATIVE_LOCAL_ARABIC_SOURCE_REQUIRES_VISUAL_REVIEW":
                pending.append(record["old_calendar_month_day"])
                self.assertFalse(arabic["fixed_slot_eligible"], record["old_calendar_month_day"])
                self.assertFalse(arabic["comparative"], record["old_calendar_month_day"])
        self.assertEqual(expected_pending, sorted(pending))
        self.assertFalse(self.payload["coverage"]["strict_named_local_gate"])

    def test_greek_glyph_review_is_local_and_language_independent(self):
        expected = {
            "03-26": "Σύναξις Ἀρχαγγέλου Γαβριήλ",
            "05-25": "Τῶν Ψυχῶν, Γ’ Εὕρεσις τιμίας Κεφαλῆς Ἰωάννου Προδρόμου",
        }
        for slot, text in expected.items():
            record = next(row for row in self.payload["records"] if row["old_calendar_month_day"] == slot)
            greek = record["lanes"]["el"]
            self.assertEqual(text, greek["text"], slot)
            self.assertEqual("VERIFIED_NATIVE_LOCAL_GREEK_SOURCE", greek["evidence_status"], slot)
            self.assertTrue(greek["fixed_slot_eligible"], slot)
            self.assertFalse(greek["comparative"], slot)
            self.assertEqual("jerusalem_patriarchate", greek["jurisdiction"], slot)

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
        record = next(row for row in payload["records"] if row["old_calendar_month_day"] == "02-29")
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
