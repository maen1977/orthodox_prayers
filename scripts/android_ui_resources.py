#!/usr/bin/env python3
"""Helpers for validating Android UI strings after resource extraction.

The project intentionally keeps all user-facing static UI text in per-language
Android resource catalogs. Source-contract checks should therefore verify both
that the expected localized text exists and that the relevant Java surface
references its resource key, rather than looking for raw prose in Java files.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATHS = {
    "ar": ROOT / "app/src/main/res/values/ui_strings.xml",
    "en": ROOT / "app/src/main/res/values-en/ui_strings.xml",
    "el": ROOT / "app/src/main/res/values-el/ui_strings.xml",
}


@lru_cache(maxsize=None)
def load_catalog(language: str) -> dict[str, str]:
    try:
        path = CATALOG_PATHS[language]
    except KeyError as exc:
        raise ValueError(f"unsupported UI language: {language}") from exc
    root = ET.parse(path).getroot()
    return {
        element.attrib["name"]: "".join(element.itertext())
        for element in root.findall("string")
        if element.attrib.get("name")
    }


def keys_for_text(text: str, language: str = "ar", *, exact: bool = False) -> list[str]:
    """Return UI resource keys whose localized value matches or contains text."""
    if not text:
        return []
    catalog = load_catalog(language)
    if exact:
        return [key for key, value in catalog.items() if value == text]
    return [key for key, value in catalog.items() if text in value]


def source_references_text(
    source: str,
    text: str,
    language: str = "ar",
    *,
    exact: bool = False,
) -> bool:
    """True when Java source references a resource containing expected text."""
    return any(f"R.string.{key}" in source for key in keys_for_text(text, language, exact=exact))


def source_omits_text(
    source: str,
    text: str,
    language: str = "ar",
    *,
    exact: bool = False,
) -> bool:
    """True when neither a raw literal nor its resource key appears in source."""
    return text not in source and not source_references_text(source, text, language, exact=exact)
