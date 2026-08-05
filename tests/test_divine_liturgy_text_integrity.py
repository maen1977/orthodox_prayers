from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "liturgy_integrity", ROOT / "scripts/validate_divine_liturgy_text_integrity.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def load(lang: str) -> dict:
    return json.loads(
        (ROOT / f"data/services/native_overrides/{lang}/divine_liturgy.json").read_text(
            encoding="utf-8"
        )
    )


def native_text(payload: dict, lang: str) -> str:
    return MODULE.combined_native_text(payload, lang)


def test_arabic_ocr_appendix_is_quarantined() -> None:
    payload = load("ar")
    text = native_text(payload, "ar")
    assert "النص العربي الثابت المكمل من الطبعة المصدرية" not in text
    assert "الر' وح" not in text
    assert "المق دسة" not in text
    assert len(payload["segments"]) == 198
    assert payload["text_integrity_review"]["removed_corrupted_segments"] == 251


def test_arabic_anaphora_has_the_required_sequence() -> None:
    payload = load("ar")
    errors: list[str] = []
    positions = MODULE.validate_arabic_anaphora(payload, errors)
    assert errors == []
    assert positions == sorted(positions)


def test_reviewed_english_wording_and_hyphenation() -> None:
    text = native_text(load("en"), "en")
    assert "mystically represent the Cherubim" in text
    assert "mystically emulate the Cherubim" not in text
    assert "onlybegotten" not in text
    assert "only-begotten" in text


def test_greek_punctuation_damage_is_absent() -> None:
    text = native_text(load("el"), "el")
    assert "ὁ Θεὸς ," not in text
    assert "ὁ Θεὸς," in text


def test_full_integrity_validator_accepts_reviewed_files() -> None:
    errors: list[str] = []
    payloads = {lang: load(lang) for lang in MODULE.LANGUAGES}
    for lang, payload in payloads.items():
        MODULE.validate_language(lang, payload, errors)
    MODULE.validate_arabic_anaphora(payloads["ar"], errors)
    assert errors == []


def test_arabic_antiphon_prayers_are_distinct_and_ordered() -> None:
    payload = load("ar")
    sections = [
        (segment.get("title") or {}).get("ar", "")
        for segment in payload["segments"]
        if segment.get("type") == "section"
    ]
    required = [
        "صلاة الأنتيفونا الأولى",
        "صلاة الأنتيفونا الثانية",
        "صلاة الأنتيفونا الثالثة",
    ]
    assert [sections.index(title) for title in required] == sorted(sections.index(title) for title in required)
    text = native_text(payload, "ar")
    assert "الذي عزته لا توصف" in text
    assert "خلّص شعبك وبارك ميراثك" in text
    assert "إذا اتفق اثنان أو ثلاثة باسمه" in text
    assert text.count("هذا هو اليوم الذي صنعه الرب") == 1
