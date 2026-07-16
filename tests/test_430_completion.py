from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import fill_daily_from_native_corpora as fill
import validate_daily_ui_localizations as ui_localizations


class Completion430Tests(unittest.TestCase):
    def test_checked_in_public_domain_corpora_are_used_without_network(self):
        contract = fill.load_contract()
        with mock.patch.object(fill, "load_public_domain_corpus", side_effect=AssertionError("network fallback used")):
            for language in ("ar", "en", "el"):
                corpus = fill.load_corpus(language, contract)
                self.assertIsNotNone(corpus)
                manifest, index = corpus
                self.assertEqual("IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS", manifest["status"])
                self.assertEqual(22, len(index))

    def test_required_references_include_next_sunday_passages(self):
        data = json.loads((ROOT / "data/calendar/candidates/2026-07-16.json").read_text(encoding="utf-8"))
        references = {canonical for canonical, _ in fill.required_references(data)}
        self.assertIn("1CO.7.24-35", references)
        self.assertIn("MAT.15.12-21", references)
        self.assertIn("ROM.15.1-7", references)
        self.assertIn("MAT.9.27-35", references)

    def test_missing_next_sunday_passage_loads_complete_registered_corpus(self):
        contract = fill.load_contract()
        partial_manifest = {
            "status": "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
            "source_id": "ebible_world_english_bible",
            "source_url": "https://ebible.org/find/details.php?id=engwebp",
            "machine_translation_used": False,
            "automatic_diacritization_used": False,
        }
        partial_index = {
            ("1CO", 7, 24): {"book_id": "1CO", "book_name": "1 Corinthians", "chapter": 7, "verse": 24, "text": "Existing", "text_sha256": fill.sha256_text("Existing")},
        }
        full_manifest = {
            "status": "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
            "source_id": "ebible_world_english_bible",
            "source_url": "https://ebible.org/Scriptures/engwebp_usfm.zip",
            "machine_translation_used": False,
            "automatic_diacritization_used": False,
        }
        full_index = {
            ("ROM", 15, verse): {
                "book_id": "ROM",
                "book_name": "Romans",
                "chapter": 15,
                "verse": verse,
                "text": f"Romans verse {verse}",
                "text_sha256": fill.sha256_text(f"Romans verse {verse}"),
            }
            for verse in range(1, 8)
        }
        required = [("ROM.15.1-7", fill.parse_reference("ROM.15.1-7"))]
        with mock.patch.object(fill, "load_public_domain_corpus", return_value=(full_manifest, full_index)) as loader:
            manifest, index = fill.ensure_corpus_coverage("en", (partial_manifest, partial_index), required, contract)
        loader.assert_called_once_with("en")
        self.assertEqual(full_manifest, manifest)
        self.assertEqual(7, len(fill.passage_verses(index, required[0][1])))

    def test_current_candidate_has_exact_epistle_and_gospel_in_three_languages(self):
        data = json.loads((ROOT / "data/calendar/candidates/2026-07-16.json").read_text(encoding="utf-8"))
        self.assertEqual("2026-07-16", data["date_iso"])
        self.assertEqual("AUTOMATIC_NATIVE_LANGUAGE_POLICY_ENFORCED", data["publication"]["status"])
        self.assertEqual(
            "COMPLETE_UNSIGNED_CANDIDATE_AWAITING_PROTECTED_SIGNATURE",
            data["publication"]["candidate_state"],
        )
        self.assertEqual("PENDING_PROTECTED_RELEASE_SIGNER", data["integrity"]["signature_state"])
        self.assertEqual(
            "THREE_STRICTLY_INDEPENDENT_OFFICIAL_NATIVE_LANGUAGE_LANES",
            data["language_content_mode"],
        )
        readings = {item["kind"]: item for item in data["readings"]}
        self.assertEqual("1CO.7.24-35", readings["epistle"]["integrity"]["canonical_reference"])
        self.assertEqual("MAT.15.12-21", readings["gospel"]["integrity"]["canonical_reference"])
        for kind in ("epistle", "gospel"):
            for language in ("ar", "en", "el"):
                self.assertTrue(readings[kind]["body"][language].strip())
                evidence = readings[kind]["native_source_verification"][language]
                self.assertEqual("IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS", evidence["status"])
                self.assertTrue(evidence["text_available"])
                self.assertFalse(evidence["ai_translation_used"])

    def test_current_candidate_has_complete_three_language_ui_metadata(self):
        data = json.loads((ROOT / "data/calendar/candidates/2026-07-16.json").read_text(encoding="utf-8"))
        self.assertEqual([], ui_localizations.validate(data))

    def test_native_service_libraries_are_complete(self):
        for language in ("ar", "en", "el"):
            payload = json.loads((ROOT / f"app/src/main/assets/data/native/library_{language}.json").read_text(encoding="utf-8"))
            self.assertTrue(payload["native_content_status"]["complete"])
            self.assertEqual(100.0, payload["native_content_status"]["percent"])
            self.assertTrue(payload["services"])


if __name__ == "__main__":
    unittest.main()
