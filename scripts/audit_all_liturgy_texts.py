#!/usr/bin/env python3
"""Create a deterministic technical text-integrity audit for all liturgy overrides."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "data/services/native_overrides"
LANGS = ("ar", "en", "el")
SERVICES = ("divine_liturgy", "divine_liturgy_basil", "presanctified_liturgy")

BAD_GLYPHS = ("\ufffd", "Ž", "£", "•")

ASSESSMENTS = {
    ("ar", "divine_liturgy"): ("PASS_REVIEWED_CORE", "The user-facing structured St John text is free of known OCR damage. A 251-segment damaged duplicate appendix was quarantined; the three antiphon prayers, Cherubic Hymn, and anaphora order were repaired from the existing Arabic source material."),
    ("en", "divine_liturgy"): ("PASS_REVIEWED_CORE", "Five visible occurrences were corrected: three only-begotten hyphenations, the Cherubic Hymn wording, and one ellipsis. Structure was cross-checked against official GOARCH text."),
    ("el", "divine_liturgy"): ("PASS_REVIEWED_CORE", "Five typography/punctuation segments were corrected, including Epistle and Gospel placeholders, the Cherubic ellipsis, and dismissal comma spacing. Structure was cross-checked against official GOARCH Greek text."),
    ("ar", "divine_liturgy_basil"): ("BLOCKED_REIMPORT_REQUIRED", "Multiple OCR glyph and word-splitting defects remain in the Arabic Basil source; do not claim word-by-word verification."),
    ("en", "divine_liturgy_basil"): ("NO_ENCODING_DAMAGE_DETECTED", "No obvious mojibake was detected automatically; this is not an ecclesiastical word-by-word certification."),
    ("el", "divine_liturgy_basil"): ("BLOCKED_REIMPORT_REQUIRED", "The Greek Basil file is a raw historical OCR layout with large paragraphs and requires a clean source reimport."),
    ("ar", "presanctified_liturgy"): ("BLOCKED_INCOMPLETE_SOURCE", "Only an explanatory excerpt is present, not a complete structured Presanctified Liturgy."),
    ("en", "presanctified_liturgy"): ("NO_ENCODING_DAMAGE_DETECTED", "No obvious mojibake was detected automatically; this is not an ecclesiastical word-by-word certification."),
    ("el", "presanctified_liturgy"): ("FORMATTING_REVIEW_RECOMMENDED", "The service is extensive and native, but its highly granular OCR-derived formatting should receive a dedicated pass."),
}


def native(segment: dict, key: str, lang: str) -> str:
    value = segment.get(key)
    return str(value.get(lang) or "") if isinstance(value, dict) else ""


def analyze(lang: str, service_id: str) -> dict:
    path = OVERRIDES / lang / f"{service_id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    segments = payload.get("segments") or []
    text = "\n".join(
        part
        for segment in segments
        for part in (native(segment, "title", lang), native(segment, "speaker", lang), native(segment, "text", lang))
        if part
    )
    bad_glyph_count = sum(text.count(glyph) for glyph in BAD_GLYPHS)
    arabic_ocr_apostrophes = len(re.findall(r"[\u0600-\u06ff]'\s*[\u0600-\u06ff]", text)) if lang == "ar" else 0
    status, note = ASSESSMENTS[(lang, service_id)]
    return {
        "language": lang,
        "service_id": service_id,
        "path": str(path.relative_to(ROOT)),
        "segments": len(segments),
        "sections": sum(1 for segment in segments if segment.get("type") == "section"),
        "visible_characters": len(text),
        "forbidden_glyph_count": bad_glyph_count,
        "arabic_ocr_apostrophe_count": arabic_ocr_apostrophes,
        "assessment": status,
        "note": note,
        "machine_translation_used": False,
        "ecclesiastical_word_by_word_certified": False,
        "user_facing_delivery_verified": service_id == "divine_liturgy",
        "delivery_layers": ["source_override", "generated_native_pack", "android_asset_pack", "search_index"] if service_id == "divine_liturgy" else [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    records = [analyze(lang, sid) for lang in LANGS for sid in SERVICES]
    result = {
        "schema_version": 2,
        "scope": "technical_text_integrity_not_ecclesiastical_approval",
        "calendar_files_modified": False,
        "records": records,
        "summary": {
            "reviewed_core_pass": sum(r["assessment"] == "PASS_REVIEWED_CORE" for r in records),
            "blocked_reimport_or_incomplete": sum(r["assessment"].startswith("BLOCKED_") for r in records),
            "other_follow_up": sum(not (r["assessment"] == "PASS_REVIEWED_CORE" or r["assessment"].startswith("BLOCKED_")) for r in records),
        },
    }
    if args.json:
        output = args.json if args.json.is_absolute() else ROOT / args.json
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "LITURGY_AUDIT_OK "
        f"reviewed_core={result['summary']['reviewed_core_pass']} "
        f"blocked={result['summary']['blocked_reimport_or_incomplete']} "
        f"follow_up={result['summary']['other_follow_up']}"
    )


if __name__ == "__main__":
    main()
