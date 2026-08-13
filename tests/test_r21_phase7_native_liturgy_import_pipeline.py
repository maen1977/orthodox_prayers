from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")


def load_module(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class R21Phase7NativeLiturgyImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.importer = load_module("phase7_native_importer", "scripts/import_native_liturgy_service.py")
        cls.promoter = load_module("phase7_native_promoter", "scripts/promote_native_liturgy_service.py")
        cls.update = load_module("phase7_updater", "scripts/update_liturgical_data.py")
        cls.contract = json.loads((ROOT / "canonical/liturgy_native_import_contracts.json").read_text(encoding="utf-8"))
        cls.editions = json.loads((ROOT / "canonical/liturgy_service_editions.json").read_text(encoding="utf-8"))
        cls.evidence = json.loads((ROOT / "canonical/source_evidence/presanctified_ar_2018.json").read_text(encoding="utf-8"))

    def test_atomic_three_language_and_no_translation_contract(self):
        rules = self.contract["global_rules"]
        self.assertTrue(rules["all_published_languages_required"])
        self.assertFalse(rules["machine_translation_allowed"])
        self.assertFalse(rules["ai_rewriting_or_correction_allowed"])
        self.assertFalse(rules["automatic_ocr_publication_allowed"])
        self.assertTrue(rules["ecclesiastical_human_review_required"])
        self.assertTrue(rules["candidate_is_never_displayable"])

    def test_arabic_presanctified_pdf_evidence_is_hash_locked_and_blocked(self):
        self.assertEqual(152, self.evidence["pdf_pages"])
        self.assertEqual(
            "ace55aed85ca4ac9437bae5e7d3ebe2baab1a7cf4480c481602a64425077907e",
            self.evidence["source_file_sha256"],
        )
        probe = self.evidence["text_extraction_probe"]
        self.assertGreater(probe["unicode_replacement_characters"], 8000)
        self.assertFalse(probe["acceptable_for_liturgical_publication"])
        self.assertTrue(probe["normalization_or_guessing_forbidden"])

    def test_replacement_characters_are_rejected(self):
        service = self.contract["services"]["presanctified"]
        lane = service["lanes"]["ar"]
        text = ("القداس السابق تقديسه لتستقم صلاتي الآن القوات السماوية ذوقوا وانظروا \ufffd " * 2000)
        report = self.importer.analyze_text(text, "ar", lane, service)
        self.assertFalse(report["acceptable_candidate_extraction"])
        self.assertTrue(any(item.startswith("UNICODE_REPLACEMENT_CHARACTERS") for item in report["failures"]))

    def test_destroyed_arabic_word_boundaries_are_rejected(self):
        service = dict(self.contract["services"]["presanctified"])
        service["minimum_characters"] = {"ar": 1000}
        service["minimum_segments"] = {"ar": 1}
        lane = service["lanes"]["ar"]
        text = "القداسالسابقِتقديسه" * 2000 + " لتستقم صلاتي الآن القوات السماوية ذوقوا وانظروا"
        report = self.importer.analyze_text(text, "ar", lane, service)
        self.assertFalse(report["acceptable_candidate_extraction"])
        self.assertTrue(any(item.startswith("ARABIC_WORD_BOUNDARIES_CORRUPTED") for item in report["failures"]))

    def test_clean_same_language_source_can_pass_candidate_health(self):
        service = dict(self.contract["services"]["presanctified"])
        service["minimum_characters"] = {"ar": 500}
        service["minimum_segments"] = {"ar": 5}
        lane = service["lanes"]["ar"]
        paragraph = "القداس السابق تقديسه. لتستقم صلاتي أمامك كالبخور. الآن القوات السماوية. ذوقوا وانظروا ما أطيب الرب."
        text = "\n\n".join(paragraph for _ in range(20))
        report = self.importer.analyze_text(text, "ar", lane, service)
        self.assertTrue(report["acceptable_candidate_extraction"], report["failures"])

    def test_promotion_rejects_pending_ecclesiastical_review(self):
        service = self.contract["services"]["basil"]
        payload = {
            "status": "CANDIDATE_REQUIRES_ECCLESIASTICAL_REVIEW",
            "service_type": "basil",
            "service_id": service["service_id"],
            "language": "en",
            "machine_translation_used": False,
            "ai_rewriting_or_correction_used": False,
            "source": {"source_id": service["lanes"]["en"]["source_id"]},
            "extraction_health": {"acceptable_candidate_extraction": True, "failures": []},
            "ecclesiastical_review": {"status": "PENDING", "reviewer": "", "reviewed_at": "", "source_page_verification": False, "candidate_sha256": ""},
            "service": {"segments": [{}] * 100},
        }
        errors = self.promoter.validate_candidate(payload, "basil", "en", self.contract)
        self.assertTrue(any("not APPROVED" in item for item in errors))
        self.assertTrue(any("source verification" in item for item in errors))

    def test_promotion_requires_all_three_candidate_files(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate_dir = Path(directory)
            (candidate_dir / "ar.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "missing candidate"):
                self.promoter.load_candidates("basil", candidate_dir)

    def test_recovered_native_rites_are_lane_specific_and_overall_fail_closed(self):
        manifest = json.loads(
            (ROOT / "canonical/religious_completeness_manifest.json").read_text(encoding="utf-8")
        )
        complete = manifest["production_complete_status"]
        self.assertEqual(complete, manifest["languages"]["en"]["basil_liturgy"])
        self.assertEqual(complete, manifest["languages"]["en"]["presanctified_liturgy"])
        self.assertEqual(complete, manifest["languages"]["el"]["presanctified_liturgy"])
        self.assertNotEqual(complete, manifest["languages"]["ar"]["basil_liturgy"])
        self.assertNotEqual(complete, manifest["languages"]["ar"]["presanctified_liturgy"])
        self.assertNotEqual(complete, manifest["languages"]["el"]["basil_liturgy"])

        minimums = {
            ("en", "divine_liturgy_basil"): 100,
            ("en", "presanctified_liturgy"): 100,
            ("el", "presanctified_liturgy"): 100,
        }
        for (language, service_id), minimum in minimums.items():
            for relative in (
                f"data/services/native/library_{language}.json",
                f"app/src/main/assets/data/native/library_{language}.json",
            ):
                payload = json.loads((ROOT / relative).read_text(encoding="utf-8"))
                item = next(service for service in payload["services"] if service.get("id") == service_id)
                self.assertGreater(len(item.get("segments") or []), minimum, relative)
                self.assertEqual("RECOVERED_EXACT_NATIVE_IMPORT", item.get("recovery_status"), relative)

    def test_basil_and_presanctified_remain_fail_closed(self):
        for service_type in ("basil", "presanctified"):
            edition = self.editions["editions"][service_type]
            self.assertFalse(edition["displayable"])
            self.assertIn("availability_note", edition)
            self.assertEqual("canonical/liturgy_native_import_contracts.json", edition["import_contract"])

    def test_blocked_service_card_exposes_native_import_status_without_prayer_fallback(self):
        basil_day = self.update.orthodox_pascha_gregorian(2026)
        basil_day = basil_day.replace()  # keep a date object for clarity
        from datetime import timedelta
        basil_day -= timedelta(days=42)
        service = self.update.build_liturgy_service("divine_liturgy", basil_day, self.update.day_info(basil_day), [], "خدمة اليوم")
        self.assertEqual("basil", service["selected_liturgy_type"])
        self.assertEqual("BLOCKED_MISSING_COMPLETE_NATIVE_SERVICE_EDITION", service["publication_status"])
        self.assertNotIn("extends_service_id", service)
        self.assertEqual("canonical/liturgy_native_import_contracts.json", service["liturgy_service_contract"]["import_contract"])
        serialized = json.dumps(service, ensure_ascii=False)
        self.assertIn("حالة استيراد الطبعة الأصلية", serialized)
        self.assertNotIn("library:divine_liturgy", serialized)


if __name__ == "__main__":
    unittest.main()
