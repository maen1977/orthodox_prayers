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

    # Scan source files independently. This keeps the direct-literal check linear
    # and avoids pathological regex backtracking across one giant concatenated
    # Java string during long-lived test processes.
    referenced: set[str] = set()
    for path in sorted(JAVA.rglob("*.java")):
        java_text = path.read_text(encoding="utf-8")
        if DIRECT_TRIPLE.search(java_text):
            raise SystemExit(
                "A direct three-language Java literal remains in "
                f"{path.relative_to(ROOT)}; move it to ui_strings.xml"
            )
        if "local(String ar, String en, String el)" in java_text:
            raise SystemExit(
                "Legacy three-language Java localization helper remains in "
                f"{path.relative_to(ROOT)}"
            )
        referenced.update(RESOURCE_REFERENCE.findall(java_text))
    missing_references = sorted(referenced - expected)
    if missing_references:
        raise SystemExit(f"Java references missing UI resources: {missing_references[:10]}")
    unused = sorted(expected - referenced)
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
