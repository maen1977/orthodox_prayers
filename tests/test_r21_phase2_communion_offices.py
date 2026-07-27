from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("ar", "en", "el")


def pack(language: str) -> dict:
    return json.loads(
        (ROOT / f"data/services/native/library_{language}.json").read_text(encoding="utf-8")
    )


def service(language: str, service_id: str) -> dict:
    return next(item for item in pack(language)["services"] if item["id"] == service_id)


def lane_text(item: dict, language: str) -> str:
    parts: list[str] = []
    for segment in item.get("segments", []):
        for field in ("title", "speaker", "text"):
            localized = segment.get(field)
            if isinstance(localized, dict):
                value = str(localized.get(language) or "").strip()
                if value:
                    parts.append(value)
    return "\n".join(parts)


class R21Phase2CommunionOfficeTests(unittest.TestCase):
    def test_arabic_pre_communion_is_full_office_not_placeholder(self):
        item = service("ar", "pre_communion_prayers")
        text = lane_text(item, "ar")
        self.assertIn("المزمور الثاني والعشرون", text)
        self.assertIn("المزمور الثالث والعشرون", text)
        self.assertIn("المزمور المائة والخامس عشر", text)
        for number in ("الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس", "السابع", "الثامن", "التاسع", "العاشر", "الحادي عشر"):
            self.assertIn(f"الإفشين {number}", text)
        self.assertIn("اقبلني اليوم شريكاً في عشائك السري", text)
        self.assertNotIn("النص قيد الإضافة", text)
        self.assertNotIn("استيراد النسخة", text)
        self.assertGreater(len(text), 12000)

    def test_arabic_thanksgiving_has_all_liturgy_specific_branches(self):
        item = service("ar", "thanksgiving_after_communion")
        text = lane_text(item, "ar")
        self.assertIn("القديس يوحنا الذهبي الفم", text)
        self.assertIn("القديس باسيليوس الكبير", text)
        self.assertIn("السابق تقديسه", text)
        self.assertIn("الآن تطلق عبدك", text)
        self.assertIn("بصلوات آبائنا القديسين", text)
        self.assertGreater(len(text), 6000)

    def test_english_and_greek_registered_selections_are_present(self):
        markers = {
            "en": ("I believe and confess", "Receive me today", "We thank You, loving Master"),
            "el": ("Πιστεύω, Κύριε", "Τοῦ Δείπνου", "Εὐχαριστοῦμέν Σοι"),
        }
        for language, expected in markers.items():
            combined = lane_text(service(language, "pre_communion_prayers"), language)
            combined += "\n" + lane_text(service(language, "thanksgiving_after_communion"), language)
            for marker in expected:
                self.assertIn(marker, combined, (language, marker))
            self.assertNotIn("unavailable", combined.casefold())

    def test_no_cross_language_leakage_in_communion_services(self):
        for language in LANGS:
            for service_id in ("pre_communion_prayers", "thanksgiving_after_communion"):
                item = service(language, service_id)
                for segment in item.get("segments", []):
                    for field in ("title", "speaker", "text"):
                        localized = segment.get(field)
                        if not isinstance(localized, dict):
                            continue
                        self.assertTrue(str(localized.get(language) or "").strip())
                        for other in set(LANGS) - {language}:
                            self.assertEqual("", str(localized.get(other) or ""))

    def test_main_liturgy_is_still_not_falsely_marked_complete(self):
        manifest = json.loads(
            (ROOT / "canonical/religious_completeness_manifest.json").read_text(encoding="utf-8")
        )
        for language in LANGS:
            self.assertNotEqual(
                manifest["production_complete_status"],
                manifest["languages"][language]["chrysostom_liturgy"],
            )


if __name__ == "__main__":
    unittest.main()
