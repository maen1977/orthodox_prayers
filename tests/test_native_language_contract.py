from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class NativeLanguageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fill = load_module("fill_daily_native_test", "scripts/fill_daily_from_native_corpora.py")
        cls.contract = load_module("native_contract_test", "scripts/native_text_contract.py")

    def test_cross_chapter_reference_is_parsed(self):
        self.assertEqual(("1CO", 6, 20, 7, 12), self.fill.parse_reference("1CO.6.20-7.12"))
        self.assertEqual(("MAT", 14, 1, 14, 13), self.fill.parse_reference("MAT.14.1-13"))
        self.assertIsNone(self.fill.parse_reference("Matthew 14:1-13"))

    def test_exact_native_passage_is_filled_without_text_mutation(self):
        arabic_1 = "طُوبَى لِلْمَسَاكِينِ بِالرُّوحِ"
        arabic_2 = "لِأَنَّ لَهُمْ مَلَكُوتَ السَّمَاوَاتِ"
        verses = {
            ("MAT", 5, 3): {"book_id": "MAT", "book_name": "إنجيل متّى", "chapter": 5, "verse": 3, "text": arabic_1, "text_sha256": self.contract.sha256_text(arabic_1)},
            ("MAT", 5, 4): {"book_id": "MAT", "book_name": "إنجيل متّى", "chapter": 5, "verse": 4, "text": arabic_2, "text_sha256": self.contract.sha256_text(arabic_2)},
        }
        manifest = {"source_id": "orthodox_jordan", "source_url": "https://orthodoxjordan.org/bible"}
        reading = {"kind": "gospel", "integrity": {"canonical_reference": "MAT.5.3-4"}, "body": {"ar": "", "en": "", "el": ""}, "reference": {"ar": "", "en": "", "el": ""}, "source": {"ar": "", "en": "", "el": ""}}
        count = self.fill.fill_reading(reading, {"ar": (manifest, verses), "en": None, "el": None})
        self.assertEqual(1, count)
        self.assertEqual(arabic_1 + "\n" + arabic_2, reading["body"]["ar"])
        self.assertEqual(self.contract.sha256_text(reading["body"]["ar"]), reading["native_source_verification"]["ar"]["text_sha256"])
        self.assertFalse(reading["native_source_verification"]["ar"]["machine_translation_used"])
        self.assertFalse(reading["native_source_verification"]["ar"]["automatic_diacritization_used"])
        self.assertEqual("", reading["body"]["en"])
        self.assertEqual("", reading["body"]["el"])

    def test_incomplete_passage_is_never_partially_published(self):
        text = "In the beginning"
        verses = {("JHN", 1, 1): {"book_id": "JHN", "book_name": "John", "chapter": 1, "verse": 1, "text": text, "text_sha256": self.contract.sha256_text(text)}}
        manifest = {"source_id": "goarch_online_chapel", "source_url": "https://www.goarch.org/chapel"}
        reading = {"kind": "gospel", "integrity": {"canonical_reference": "JHN.1.1-2"}, "body": {"ar": "", "en": "", "el": ""}, "reference": {"ar": "", "en": "", "el": ""}, "source": {"ar": "", "en": "", "el": ""}}
        self.assertEqual(0, self.fill.fill_reading(reading, {"ar": None, "en": (manifest, verses), "el": None}))
        self.assertEqual("", reading["body"]["en"])

    def test_script_detection_rejects_cross_language_content(self):
        self.assertTrue(self.contract.script_errors("el", "This is English text"))
        self.assertTrue(self.contract.script_errors("ar", "Greek Ελληνικά"))
        self.assertEqual([], self.contract.script_errors("el", "Ἐν ἀρχῇ ἦν ὁ Λόγος"))

    def test_search_indexes_hash_exact_display_text(self):
        for language in ("ar", "en", "el"):
            path = ROOT / "app/src/main/assets/data/search" / f"search_index_{language}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            for document in payload["documents"]:
                self.assertEqual(self.contract.sha256_text(document["display_text"]), document["display_sha256"])
                self.assertNotEqual("", document["search_text"])

    def test_imported_manifest_declares_codepoint_preservation(self):
        importer = (ROOT / "scripts/import_native_scripture_corpus.py").read_text(encoding="utf-8")
        self.assertIn("PRESERVE_SOURCE_UNICODE_CODEPOINTS_EXACTLY", importer)
        self.assertNotIn("EXACT_SOURCE_TEXT_NFC_ONLY", importer)


if __name__ == "__main__":
    unittest.main()
