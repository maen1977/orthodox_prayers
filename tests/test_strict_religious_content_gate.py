from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "strict_gate", ROOT / "scripts/validate_strict_religious_content.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_generic_commemoration_is_truthfully_absent() -> None:
    assert MODULE.is_generic_commemoration("تذكار اليوم بحسب التقويم الكنسي القديم")
    assert MODULE.is_generic_commemoration("Today’s commemoration according to the old church calendar")
    assert not MODULE.is_generic_commemoration("عيد الظهور الإلهي المقدس")


def test_scripture_hash_and_verse_hashes_are_enforced() -> None:
    body = "First verse\nSecond verse"
    reading = {
        "kind": "gospel",
        "translation_locked": True,
        "integrity": {
            "status": "NATIVE_LANGUAGE_LANES_ENFORCED",
            "canonical_reference": "MAT.1.1-2",
            "ai_translation_used": False,
            "automatic_diacritization_used": False,
        },
        "reference": {"en": "Matthew 1:1-2"},
        "body": {"en": body},
        "native_source_verification": {
            "en": {
                "status": "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
                "source_id": "ebible_world_english_bible",
                "source_url": "https://ebible.org/Scriptures/engwebp_usfm.zip",
                "canonical_reference": "MAT.1.1-2",
                "reference_available": True,
                "text_available": True,
                "text_sha256": MODULE.sha256_text(body),
                "verse_count": 2,
                "verse_hashes": [MODULE.sha256_text("First verse"), MODULE.sha256_text("Second verse")],
                "ai_translation_used": False,
                "automatic_diacritization_used": False,
            }
        },
    }
    errors: list[str] = []
    MODULE.validate_reference_and_hashes(reading, "gospel", "reading", ("en",), True, errors)
    assert errors == []
    reading["native_source_verification"]["en"]["verse_hashes"][1] = "bad"
    MODULE.validate_reference_and_hashes(reading, "gospel", "reading", ("en",), True, errors)
    assert any("verse_hashes" in item for item in errors)


def test_calendar_lock_lists_full_2026_2050_assets() -> None:
    lock = json.loads((ROOT / "canonical/calendar_2026_2050_lock.json").read_text(encoding="utf-8"))
    paths = {item["path"] for item in lock["files"]}
    for year in range(2026, 2051):
        assert f"app/src/main/assets/data/calendar/calendar_{year}.json" in paths
    assert "canonical/internal_calendar_2026_2050.json" in paths
    assert lock["civil_range"]["end"] == "2050-12-31"
