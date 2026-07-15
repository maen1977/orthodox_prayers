from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_reader_services",
    ROOT / "scripts" / "validate_reader_services.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ReaderServicePruningTests(unittest.TestCase):
    def test_empty_optional_proper_is_removed_after_overlay_composition(self) -> None:
        library_payload = json.loads(
            (ROOT / "app/src/main/assets/data/library.json").read_text(encoding="utf-8")
        )
        library = {
            item["id"]: item
            for item in library_payload["services"]
            if isinstance(item, dict) and item.get("id")
        }
        base = library["divine_liturgy"]
        marker = "[طروبارية اليوم]"
        self.assertTrue(
            any(
                isinstance(segment.get("text"), dict)
                and segment["text"].get("ar") == marker
                for segment in base["segments"]
            ),
            "The static Liturgy fixture no longer contains the expected optional proper marker",
        )

        overlay = {
            "id": "divine_liturgy",
            "extends_service_id": "divine_liturgy",
            "category": base["category"],
            "icon": base.get("icon", ""),
            "title": {"ar": "قداس اليوم", "en": "Today Liturgy", "el": "Θεία Λειτουργία"},
            "segments": [
                {
                    "type": "note",
                    "speaker": {"ar": "ملاحظة", "en": "Note", "el": "Σημείωση"},
                    "text": {"ar": "ملحق اليوم", "en": "Daily overlay", "el": "Ἡμερήσιο"},
                }
            ],
            "segment_replacements": {
                marker: {"ar": "", "en": "", "el": ""},
            },
            "inline_replacements": {},
        }

        composed = MODULE.compose_overlay(copy.deepcopy(overlay), library, ROOT / "data/calendar/today.json")
        for index, segment in enumerate(composed["segments"]):
            key = "title" if segment.get("type") == "section" else "text"
            self.assertTrue(
                MODULE.localized_nonempty(segment.get(key)),
                f"blank {key} remained at composed segment {index}",
            )
            rendered = " ".join(
                str((segment.get(key) or {}).get(lang) or "") for lang in ("ar", "en", "el")
            )
            self.assertNotIn(marker, rendered)

    def test_2026_07_16_ordinary_day_has_no_blank_composed_liturgy_rows(self) -> None:
        update_spec = importlib.util.spec_from_file_location(
            "update_liturgical_data", ROOT / "scripts" / "update_liturgical_data.py"
        )
        assert update_spec and update_spec.loader
        update = importlib.util.module_from_spec(update_spec)
        update_spec.loader.exec_module(update)

        day = date(2026, 7, 16)
        info = update.day_info(day)
        readings = update.reading_defaults(info, day)
        overlay = update.build_liturgy_service(
            "divine_liturgy", day, info, readings, "خدمة اليوم"
        )
        library_payload = json.loads(
            (ROOT / "app/src/main/assets/data/library.json").read_text(encoding="utf-8")
        )
        library = {item["id"]: item for item in library_payload["services"]}
        composed = MODULE.compose_overlay(overlay, library, ROOT / "data/calendar/today.json")
        self.assertGreater(len(composed["segments"]), 200)
        for index, segment in enumerate(composed["segments"]):
            key = "title" if segment.get("type") == "section" else "text"
            self.assertTrue(
                MODULE.localized_nonempty(segment.get(key)),
                f"2026-07-16 left blank {key} at segment {index}",
            )

    def test_unresolved_and_legacy_unavailable_rows_are_pruned(self) -> None:
        segments = [
            {"type": "section", "title": {"ar": "قطعة اختيارية", "en": "Optional", "el": "Προαιρετικό"}},
            {"type": "text", "text": {"ar": "[آية المناولة]", "en": "", "el": ""}},
            {"type": "section", "title": {"ar": "قطعة قديمة", "en": "Old", "el": "Παλαιό"}},
            {"type": "text", "text": {"ar": "النص غير متاح حاليًا", "en": "Not available", "el": ""}},
            {"type": "section", "title": {"ar": "موجود", "en": "Present", "el": "Παρόν"}},
            {"type": "text", "text": {"ar": "نص صحيح", "en": "Valid text", "el": "Ἔγκυρο κείμενο"}},
        ]
        pruned = MODULE._prune_unresolved_or_empty_segments(segments)
        self.assertEqual(2, len(pruned))
        self.assertEqual("موجود", pruned[0]["title"]["ar"])
        self.assertEqual("نص صحيح", pruned[1]["text"]["ar"])


if __name__ == "__main__":
    unittest.main()
