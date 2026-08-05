#!/usr/bin/env python3
"""Validate the reviewed St John Chrysostom liturgy in Arabic, English, and Greek.

This gate is deliberately narrow: it prevents known OCR damage, language leakage,
and a reversed Eucharistic-anaphora sequence from returning to the user-facing text.
It does not claim ecclesiastical approval or replace a qualified liturgical editor.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERRIDES = ROOT / "data/services/native_overrides"
LANGUAGES = ("ar", "en", "el")

FILES = {lang: OVERRIDES / lang / "divine_liturgy.json" for lang in LANGUAGES}

KNOWN_BAD_SUBSTRINGS = {
    "ar": (
        "النص العربي الثابت المكمل من الطبعة المصدرية",
        "مملكة الب والبن",
        "مباركة مملكة الآب والابن",
        "الر' وح",
        "سلم ك ل العالم",
        "المق دسة",
        "المرفوق",
        "أتيت بكل شيء من العدم إلى الوجود",
        "نحن الممثلين الشاروبيم",
    ),
    "en": (
        "mystically emulate the Cherubim",
        "onlybegotten",
        "all ...",
    ),
    "el": (
        "ὁ Θεὸς ,",
    ),
}

FORBIDDEN_CODEPOINTS = ("\ufffd", "Ž", "£", "•")

ARABIC_ANAPHORA_ANCHORS = (
    "خذوا كلوا",
    "اشربوا منه كلكم",
    "التي لك مما لك",
    "أرسل روحك القدوس",
    "هذا الخبز",
    "هذه الكأس",
    "إياهما بروحك القدوس",
)


def native_value(segment: dict, field: str, lang: str) -> str:
    value = segment.get(field)
    return str(value.get(lang) or "") if isinstance(value, dict) else ""


def combined_native_text(payload: dict, lang: str) -> str:
    lines: list[str] = []
    for segment in payload.get("segments") or []:
        for field in ("title", "speaker", "text"):
            value = native_value(segment, field, lang).strip()
            if value:
                lines.append(value)
    return "\n".join(lines)


def load(lang: str) -> dict:
    path = FILES[lang]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{path}: cannot load valid UTF-8 JSON: {exc}") from exc
    if payload.get("id") != "divine_liturgy":
        raise SystemExit(f"{path}: expected service id divine_liturgy")
    if payload.get("source_language") != lang:
        raise SystemExit(f"{path}: source_language must be {lang}")
    if not isinstance(payload.get("segments"), list):
        raise SystemExit(f"{path}: segments must be a list")
    return payload


def validate_language(lang: str, payload: dict, errors: list[str]) -> dict[str, int]:
    path = FILES[lang].relative_to(ROOT)
    segments = payload["segments"]
    section_count = sum(1 for segment in segments if segment.get("type") == "section")
    text = combined_native_text(payload, lang)

    minimum_segments = {"ar": 180, "en": 300, "el": 300}[lang]
    maximum_segments = {"ar": 260, "en": 380, "el": 380}[lang]
    minimum_sections = {"ar": 25, "en": 25, "el": 25}[lang]
    if not minimum_segments <= len(segments) <= maximum_segments:
        errors.append(
            f"{path}: unexpected segment count {len(segments)}; expected {minimum_segments}-{maximum_segments}"
        )
    if section_count < minimum_sections:
        errors.append(f"{path}: only {section_count} sections; expected at least {minimum_sections}")

    for token in FORBIDDEN_CODEPOINTS:
        if token in text:
            errors.append(f"{path}: forbidden OCR/mojibake character {token!r}")
    for token in KNOWN_BAD_SUBSTRINGS[lang]:
        if token.casefold() in text.casefold():
            errors.append(f"{path}: known damaged wording returned: {token!r}")

    if re.search(r"\s{3,}", text):
        errors.append(f"{path}: contains runs of three or more spaces")
    if re.search(r"[ \t]+[،؛؟,.!?;:]", text):
        errors.append(f"{path}: contains a space before punctuation")

    if lang == "ar":
        if re.search(r"[A-Za-zΑ-Ωα-ω]", text):
            errors.append(f"{path}: Arabic native fields contain Latin or Greek letters")
        if re.search(r"[\u0600-\u06ff]'\s+[\u0600-\u06ff]", text):
            errors.append(f"{path}: contains an OCR-style apostrophe splitting an Arabic word")
        if re.search(r"\b[\u0600-\u06ff]\s+[\u0600-\u06ff]\s+[\u0600-\u06ff]\b", text):
            errors.append(f"{path}: contains an Arabic word split into isolated letters")
    elif lang == "en":
        if re.search(r"[\u0600-\u06ff]", text):
            errors.append(f"{path}: English native fields contain Arabic letters")
    elif lang == "el":
        if re.search(r"[\u0600-\u06ff]", text):
            errors.append(f"{path}: Greek native fields contain Arabic letters")

    if lang == "ar":
        opening = "مباركة هي مملكة الآب والابن والروح القدس"
        if text.count(opening) != 1:
            errors.append(f"{path}: reviewed opening formula must appear exactly once")
        section_titles = [native_value(segment, "title", lang) for segment in segments if segment.get("type") == "section"]
        required_sections = (
            "صلاة الأنتيفونا الأولى",
            "صلاة الأنتيفونا الثانية",
            "صلاة الأنتيفونا الثالثة",
            "الأنافورا المقدسة",
            "كلام التأسيس واستدعاء الروح القدس",
        )
        positions = []
        for title in required_sections:
            if section_titles.count(title) != 1:
                errors.append(f"{path}: section {title!r} must appear exactly once")
                positions.append(-1)
            else:
                positions.append(section_titles.index(title))
        if all(position >= 0 for position in positions) and positions != sorted(positions):
            errors.append(f"{path}: reviewed Arabic section order is invalid")
        ordinary = "هذا هو اليوم الذي صنعه الرب، فلنفرح ونبتهج فيه."
        if text.count(ordinary) != 1:
            errors.append(f"{path}: third-antiphon ordinary must appear exactly once")

    return {"segments": len(segments), "sections": section_count}


def validate_arabic_anaphora(payload: dict, errors: list[str]) -> list[int]:
    text_segments = [native_value(segment, "text", "ar") for segment in payload["segments"]]
    positions: list[int] = []
    for anchor in ARABIC_ANAPHORA_ANCHORS:
        hits = [index for index, value in enumerate(text_segments) if anchor in value]
        if len(hits) != 1:
            errors.append(
                f"Arabic anaphora anchor {anchor!r} must appear exactly once; found {len(hits)}"
            )
            positions.append(-1)
        else:
            positions.append(hits[0])
    valid_positions = [position for position in positions if position >= 0]
    if len(valid_positions) == len(positions) and positions != sorted(positions):
        errors.append(
            "Arabic anaphora order is invalid; expected institution words, anamnesis/offering, "
            "invocation, consecration of bread, consecration of cup, and change by the Holy Spirit"
        )
    return positions


def main() -> None:
    errors: list[str] = []
    metrics: dict[str, dict[str, int]] = {}
    payloads = {lang: load(lang) for lang in LANGUAGES}
    for lang, payload in payloads.items():
        metrics[lang] = validate_language(lang, payload, errors)
    anaphora_positions = validate_arabic_anaphora(payloads["ar"], errors)

    review = payloads["ar"].get("text_integrity_review") or {}
    if review.get("removed_corrupted_segments") != 251:
        errors.append("Arabic text_integrity_review must record 251 quarantined OCR segments")
    if review.get("anaphora_sequence_verified") is not True:
        errors.append("Arabic text_integrity_review must record anaphora_sequence_verified=true")
    if review.get("machine_translation_used") is not False:
        errors.append("Arabic text_integrity_review must record machine_translation_used=false")
    if review.get("ecclesiastical_review_required") is not True:
        errors.append("Arabic text_integrity_review must retain ecclesiastical_review_required=true")
    if review.get("word_for_word_ecclesiastical_certification") is not False:
        errors.append("Arabic text_integrity_review must not claim word-for-word ecclesiastical certification")

    if errors:
        for error in errors:
            print(f"LITURGY_TEXT_ERROR {error}")
        raise SystemExit(1)

    metric_text = " ".join(
        f"{lang}_segments={metrics[lang]['segments']} {lang}_sections={metrics[lang]['sections']}"
        for lang in LANGUAGES
    )
    print(
        "DIVINE_LITURGY_TEXT_INTEGRITY_OK "
        f"{metric_text} ar_anaphora_positions={','.join(map(str, anaphora_positions))}"
    )


if __name__ == "__main__":
    main()
