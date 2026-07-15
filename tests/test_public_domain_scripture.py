from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

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


class PublicDomainScriptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = load_module("public_domain_scripture_test", "scripts/public_domain_scripture.py")
        cls.fill = load_module("public_domain_fill_test", "scripts/fill_daily_from_native_corpora.py")
        cls.enforce = load_module("public_domain_enforce_test", "scripts/enforce_native_daily_lanes.py")
        cls.update = load_module("public_domain_update_test", "scripts/update_liturgical_data.py")
        cls.integrity = load_module("public_domain_integrity_test", "scripts/orthodox_integrity.py")

    @staticmethod
    def usfm(book: str, title: str, chapters: dict[int, range], prefix: str) -> str:
        lines = [f"\\id {book}", f"\\toc1 {title}"]
        for chapter, verses in chapters.items():
            lines.append(f"\\c {chapter}")
            lines.append("\\p")
            for verse in verses:
                # Include inline words, a footnote, and continuation markup to
                # exercise the exact display-text cleanup without translation.
                text = f"{prefix} {chapter}:{verse}"
                if verse == verses.start:
                    text += " \\w كلمة|lemma=demo\\w* \\f + \\ft note removed\\f*"
                lines.append(f"\\v {verse} {text}")
        return "\n".join(lines) + "\n"

    @classmethod
    def write_archives(cls, directory: Path) -> None:
        language_data = {
            "ar": ("نص عربي", "رسالة كورنثوس الأولى", "إنجيل متّى"),
            "en": ("English text", "First Corinthians", "Matthew"),
            "el": ("Ἑλληνικὸ κείμενο", "Πρὸς Κορινθίους Αʹ", "Κατὰ Ματθαῖον"),
        }
        for language, source in cls.public.SOURCES.items():
            prefix, epistle_title, gospel_title = language_data[language]
            with zipfile.ZipFile(directory / source["archive_name"], "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "46-1CO.usfm",
                    cls.usfm("1CO", epistle_title, {7: range(12, 25)}, prefix),
                )
                archive.writestr(
                    "41-MAT.usfm",
                    cls.usfm("MAT", gospel_title, {14: range(35, 37), 15: range(1, 12)}, prefix),
                )

    def test_usfm_parser_preserves_source_script_and_removes_markup(self):
        raw = "\\id MAT\n\\toc1 إنجيل متّى\n\\c 5\n\\p\n\\v 3 طُوبَى \\w لِلْمَسَاكِينِ|lemma=x\\w* \\f + \\ft هامش\\f*\n"
        book, title, verses = self.public.parse_usfm_document(raw)
        self.assertEqual("MAT", book)
        self.assertEqual("إنجيل متّى", title)
        self.assertEqual("طُوبَى لِلْمَسَاكِينِ", verses[(5, 3)])

    def test_human_discovery_reference_becomes_canonical_before_lane_enforcement(self):
        reading = {
            "kind": "gospel",
            "reference": {"ar": "متى 14:35-15:11", "en": "Matthew 14:35-15:11", "el": ""},
            "body": {"ar": "", "en": "", "el": ""},
            "source": {"ar": "", "en": "", "el": ""},
        }
        self.assertEqual("MAT.14.35-15.11", self.fill.canonical_reference(reading))

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_archives(directory)
            with mock.patch.dict(os.environ, {"ORTHODOX_SCRIPTURE_ARCHIVE_DIR": str(directory)}):
                corpora = {
                    language: self.public.load_public_domain_corpus(language)
                    for language in ("ar", "en", "el")
                }
            self.assertEqual(3, self.fill.fill_reading(reading, corpora))
        self.assertEqual("MAT.14.35-15.11", reading["integrity"]["canonical_reference"])
        self.assertTrue(all(reading["body"][language] for language in ("ar", "en", "el")))

        # The next security stage must retain the newly verified bodies even
        # when the official-date resolver is in partial mode and has no daily
        # source_evidence entries.
        data = {"date_iso": "2026-07-15", "source_evidence": []}
        self.enforce.enforce_reading(reading, data, data["date_iso"], self.fill.load_contract())
        self.assertEqual("MAT.14.35-15.11", reading["integrity"]["canonical_reference"])
        self.assertTrue(all(reading["body"][language] for language in ("ar", "en", "el")))
        rendered = self.update.reading_block_loc(reading)
        self.assertIn("English text", rendered["en"])
        self.assertIn("نص عربي", rendered["ar"])
        self.assertIn("Ἑλληνικὸ κείμενο", rendered["el"])

        epistle = {
            "kind": "epistle",
            "title": {"ar": "الرسالة", "en": "Epistle", "el": "Ἀπόστολος"},
            "reference": {"ar": "١ كورنثوس 7:12-24", "en": "1 Corinthians 7:12-24", "el": ""},
            "body": {"ar": "", "en": "", "el": ""},
            "source": {"ar": "", "en": "", "el": ""},
        }
        self.assertEqual(3, self.fill.fill_reading(epistle, corpora))
        self.enforce.enforce_reading(epistle, data, data["date_iso"], self.fill.load_contract())
        prokeimenon = {
            "kind": "prokeimenon",
            "title": {"ar": "البروكيمنن", "en": "Prokeimenon", "el": "Προκείμενον"},
            "reference": {"ar": "", "en": "", "el": ""},
            "body": {"ar": "", "en": "", "el": ""},
            "source": {"ar": "", "en": "", "el": ""},
        }
        self.enforce.enforce_reading(prokeimenon, data, data["date_iso"], self.fill.load_contract())
        readings = [prokeimenon, epistle, reading]
        service_data = {
            "date_iso": "2026-07-15",
            "readings": readings,
            "integrity_inputs": {"next_sunday": {"date_iso": "2026-07-19", "readings": copy.deepcopy(readings)}},
        }
        self.integrity.rebuild_services(service_data, readings, copy.deepcopy(readings))
        liturgy = next(service for service in service_data["services"] if service["id"] == "divine_liturgy")
        self.assertIn("English text", liturgy["segment_replacements"]["[فصل من رسالة اليوم]"]["en"])
        self.assertIn("English text", liturgy["segment_replacements"]["[فصل الإنجيل المعيّن لهذا اليوم]"]["en"])
        self.assertIn("نص عربي", liturgy["segment_replacements"]["[فصل من رسالة اليوم]"]["ar"])
        self.assertIn("Ἑλληνικὸ κείμενο", liturgy["segment_replacements"]["[فصل الإنجيل المعيّن لهذا اليوم]"]["el"])

    def test_current_cross_chapter_readings_fill_in_all_three_languages(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_archives(directory)
            with mock.patch.dict(os.environ, {"ORTHODOX_SCRIPTURE_ARCHIVE_DIR": str(directory)}):
                corpora = {
                    language: self.public.load_public_domain_corpus(language)
                    for language in ("ar", "en", "el")
                }

            epistle = {
                "kind": "epistle",
                "integrity": {"canonical_reference": "1CO.7.12-24"},
                "body": {"ar": "", "en": "", "el": ""},
                "reference": {"ar": "", "en": "", "el": ""},
                "source": {"ar": "", "en": "", "el": ""},
            }
            gospel = {
                "kind": "gospel",
                "integrity": {"canonical_reference": "MAT.14.35-15.11"},
                "body": {"ar": "", "en": "", "el": ""},
                "reference": {"ar": "", "en": "", "el": ""},
                "source": {"ar": "", "en": "", "el": ""},
            }
            self.assertEqual(3, self.fill.fill_reading(epistle, corpora))
            self.assertEqual(3, self.fill.fill_reading(gospel, corpora))

            for reading in (epistle, gospel):
                for language in ("ar", "en", "el"):
                    self.assertTrue(reading["reference"][language])
                    self.assertTrue(reading["body"][language])
                    evidence = reading["native_source_verification"][language]
                    self.assertEqual("IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS", evidence["status"])
                    self.assertTrue(evidence["text_available"])
                    self.assertFalse(evidence["machine_translation_used"])
                    self.assertFalse(evidence["automatic_diacritization_used"])
                    self.assertEqual(self.fill.sha256_text(reading["body"][language]), evidence["text_sha256"])

            self.assertIn("نص عربي", epistle["body"]["ar"])
            self.assertIn("English text", epistle["body"]["en"])
            self.assertIn("Ἑλληνικὸ κείμενο", epistle["body"]["el"])
            self.assertIn("14:35", gospel["body"]["en"])
            self.assertIn("15:11", gospel["body"]["en"])
            self.assertNotIn("note removed", gospel["body"]["en"])


    def test_missing_internal_verse_in_cross_chapter_passage_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = self.public.SOURCES["en"]
            gospel = self.usfm("MAT", "Matthew", {14: range(35, 37), 15: range(1, 12)}, "English text")
            gospel = "\n".join(
                line for line in gospel.splitlines()
                if not line.startswith("\\v 5 ")
            ) + "\n"
            with zipfile.ZipFile(directory / source["archive_name"], "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("41-MAT.usfm", gospel)
            with mock.patch.dict(os.environ, {"ORTHODOX_SCRIPTURE_ARCHIVE_DIR": str(directory)}):
                corpus = self.public.load_public_domain_corpus("en")
            reading = {
                "kind": "gospel",
                "integrity": {"canonical_reference": "MAT.14.35-15.11"},
                "body": {"ar": "", "en": "", "el": ""},
                "reference": {"ar": "", "en": "", "el": ""},
                "source": {"ar": "", "en": "", "el": ""},
            }
            self.assertEqual(0, self.fill.fill_reading(reading, {"ar": None, "en": corpus, "el": None}))
            self.assertEqual({"ar": "", "en": "", "el": ""}, reading["body"])

    def test_missing_end_verse_blocks_partial_publication(self):
        text = "Exact text"
        index = {
            ("MAT", 1, 1): {
                "book_id": "MAT",
                "book_name": "Matthew",
                "chapter": 1,
                "verse": 1,
                "text": text,
                "text_sha256": self.fill.sha256_text(text),
            }
        }
        manifest = {
            "status": "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
            "source_id": "ebible_world_english_bible",
            "source_url": "https://ebible.org/Scriptures/eng-web_usfm.zip",
            "machine_translation_used": False,
            "automatic_diacritization_used": False,
        }
        reading = {
            "kind": "gospel",
            "integrity": {"canonical_reference": "MAT.1.1-2"},
            "body": {"ar": "", "en": "", "el": ""},
            "reference": {"ar": "", "en": "", "el": ""},
            "source": {"ar": "", "en": "", "el": ""},
        }
        self.assertEqual(0, self.fill.fill_reading(reading, {"ar": None, "en": (manifest, index), "el": None}))
        self.assertEqual("", reading["body"]["en"])


if __name__ == "__main__":
    unittest.main()
