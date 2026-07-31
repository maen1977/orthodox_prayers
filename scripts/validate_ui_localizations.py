#!/usr/bin/env python3
"""Validate the app-owned Arabic, English, and Greek Android UI catalogs."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "app" / "src" / "main" / "res"
JAVA = ROOT / "app" / "src" / "main" / "java"
CATALOGS = {
    "ar": RES / "values" / "ui_strings.xml",
    "en": RES / "values-en" / "ui_strings.xml",
    "el": RES / "values-el" / "ui_strings.xml",
}
ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
RESOURCE_REFERENCE = re.compile(r"R\.string\.(ui_[A-Za-z0-9_]+)")
FORMAT_TOKEN = re.compile(r"%(\d+)\$([a-zA-Z])")
INTENTIONALLY_HIDDEN_UI_RESOURCES = {
    "ui_arabic_english_and_greek_are_three_independent_n_d97c4432",
    "ui_calendar_and_fasting_51a9bf84",
    "ui_calendar_and_reminders_acba78af",
    "ui_churches_and_live_services_53a37eff",
    "ui_current_native_official_text_coverage_english_0f60cec5",
    "ui_daily_readings_7f88fcc0",
    "ui_greek_1565698a",
    "ui_hide_source_text_d8f171c5",
    "ui_languages_409ca23f",
    "ui_manage_active_languages_9565aa55",
    "ui_open_the_complete_divine_liturgy_14695677",
    "ui_pinned_texts_5baad15c",
    "ui_quick_access_c927e8a2",
    "ui_reading_history_0a3be238",
    "ui_selection_reason_label",
    "ui_seven_day_fasting_table_9f1b0d97",
    "ui_show_seven_day_details_97f48507",
    "ui_show_source_text_f6b54117",
    "ui_today_7_complete_days_3057eb0c",
}

DIRECT_TRIPLE = re.compile(
    r"\blocal\s*\(\s*\"(?:\\.|[^\"\\])*\"(?:\s*\+\s*\"(?:\\.|[^\"\\])*\")*\s*,"
    r"\s*\"(?:\\.|[^\"\\])*\"(?:\s*\+\s*\"(?:\\.|[^\"\\])*\")*\s*,"
    r"\s*\"(?:\\.|[^\"\\])*\"(?:\s*\+\s*\"(?:\\.|[^\"\\])*\")*\s*\)",
    re.S,
)


def load_catalog(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    values: dict[str, str] = {}
    for element in root.findall("string"):
        name = element.attrib.get("name", "").strip()
        if not name or name in values:
            raise SystemExit(f"Invalid or duplicate UI string name in {path.relative_to(ROOT)}: {name!r}")
        values[name] = "".join(element.itertext())
    return values


def main() -> None:
    catalogs = {language: load_catalog(path) for language, path in CATALOGS.items()}
    expected = set(catalogs["ar"])
    if len(expected) < 300:
        raise SystemExit(f"UI resource migration is incomplete: only {len(expected)} entries")
    for language, values in catalogs.items():
        missing = expected - set(values)
        extra = set(values) - expected
        if missing or extra:
            raise SystemExit(
                f"UI catalog key mismatch for {language}: missing={sorted(missing)[:5]} extra={sorted(extra)[:5]}"
            )
        blanks = sorted(key for key, value in values.items() if not value.strip())
        if blanks:
            raise SystemExit(f"Blank UI strings in {language}: {blanks[:5]}")

    for key in sorted(expected):
        signatures = {
            language: sorted(FORMAT_TOKEN.findall(values[key]))
            for language, values in catalogs.items()
        }
        if len({tuple(signature) for signature in signatures.values()}) != 1:
            raise SystemExit(f"Format placeholder mismatch for {key}: {signatures}")

    for key, value in catalogs["en"].items():
        if ARABIC.search(value) or GREEK.search(value):
            raise SystemExit(f"Foreign-script leakage in English UI string {key}")
    for key, value in catalogs["el"].items():
        if ARABIC.search(value):
            raise SystemExit(f"Arabic leakage in Greek UI string {key}")
        if not GREEK.search(value) and not re.fullmatch(r"[A-Z0-9._:/+\- ]+", value):
            raise SystemExit(f"Greek UI string has no Greek text and is not a technical label: {key}")
    for key, value in catalogs["ar"].items():
        if GREEK.search(value):
            raise SystemExit(f"Greek leakage in Arabic UI string {key}")
        if not ARABIC.search(value):
            raise SystemExit(f"Arabic UI string has no Arabic text: {key}")

    java_text = "\n".join(path.read_text(encoding="utf-8") for path in JAVA.rglob("*.java"))
    direct = DIRECT_TRIPLE.search(java_text)
    if direct:
        raise SystemExit("A direct three-language Java literal remains; move it to ui_strings.xml")
    if "local(String ar, String en, String el)" in java_text:
        raise SystemExit("Legacy three-language Java localization helper remains")

    referenced = set(RESOURCE_REFERENCE.findall(java_text))
    missing_references = sorted(referenced - expected)
    if missing_references:
        raise SystemExit(f"Java references missing UI resources: {missing_references[:10]}")
    hidden_missing = sorted(INTENTIONALLY_HIDDEN_UI_RESOURCES - expected)
    if hidden_missing:
        raise SystemExit(f"Intentionally hidden UI resources are missing: {hidden_missing[:10]}")
    unused = sorted((expected - referenced) - INTENTIONALLY_HIDDEN_UI_RESOURCES)
    # A small number of shared format strings may be resolved indirectly; a large
    # unused catalog usually means a broken migration or stale duplicated text.
    if len(unused) > 12:
        raise SystemExit(f"Too many unused UI resources: {len(unused)}; examples={unused[:10]}")

    print(
        "UI_LOCALIZATION_OK "
        f"keys={len(expected)} references={len(referenced)} unused={len(unused)} "
        "languages=ar,en,el direct_java_triples=0"
    )


if __name__ == "__main__":
    main()
