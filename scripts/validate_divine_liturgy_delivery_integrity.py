#!/usr/bin/env python3
"""Validate the exact St John Chrysostom text delivered by Android and search.

The source override may be correct while a generated native pack or search index is
stale.  This gate compares every user-facing layer and rejects known OCR damage,
wrong-language text, duplicate dynamic content, invalid hashes, and Unicode control
characters.  It is a technical integrity gate, not ecclesiastical certification.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")
SERVICE_ID = "divine_liturgy"

DATA_NATIVE = ROOT / "data/services/native"
APP_NATIVE = ROOT / "app/src/main/assets/data/native"
DATA_SEARCH = ROOT / "data/search"
APP_SEARCH = ROOT / "app/src/main/assets/data/search"

KNOWN_BAD = {
    "ar": (
        "النص العربي الثابت المكمل من الطبعة المصدرية",
        "مملكة الب والبن",
        "مباركة مملكة الآب والابن",
        "الر' وح",
        "سلم ك ل العالم",
        "المق دسة",
        "المرفوق",
        "نحن الممثلين الشاروبيم",
        "لا لدينونة ولا لوقوع",
    ),
    "en": (
        "mystically emulate the Cherubim",
        "Onlybegotten",
        "onlybegotten",
    ),
    "el": (
        "ὁ Θεὸς ,",
        "Πρός....",
        "κατά...",
    ),
}

BIDI_CONTROLS = {
    "\u061c", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
}


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{path.relative_to(ROOT)}: invalid UTF-8 JSON: {exc}") from exc


def localized(value: Any, lang: str) -> str:
    return str(value.get(lang) or "") if isinstance(value, dict) else ""


def search_display_text(service: dict[str, Any], lang: str) -> str:
    pieces: list[str] = []
    for segment in service.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        text = localized(segment.get("text"), lang) or localized(segment.get("title"), lang)
        if text:
            pieces.append(text)
    return "\n".join(pieces)


def full_visible_text(service: dict[str, Any], lang: str) -> str:
    parts: list[str] = []
    for segment in service.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        for field in ("title", "speaker", "text"):
            text = localized(segment.get(field), lang)
            if text:
                parts.append(text)
    return "\n".join(parts)


def service_from_pack(pack: dict[str, Any], lang: str, source: str) -> dict[str, Any]:
    matches = [s for s in pack.get("services") or [] if isinstance(s, dict) and s.get("id") == SERVICE_ID]
    if len(matches) != 1:
        raise SystemExit(f"{source}: expected one {SERVICE_ID} service, found {len(matches)}")
    service = matches[0]
    if service.get("source_language") != lang:
        raise SystemExit(f"{source}: source_language must be {lang}")
    return service


def validate_text(label: str, text: str, lang: str, errors: list[str]) -> None:
    if unicodedata.normalize("NFC", text) != text:
        errors.append(f"{label}: text is not NFC-normalized")
    controls = sorted({f"U+{ord(ch):04X}" for ch in text if ch in BIDI_CONTROLS})
    if controls:
        errors.append(f"{label}: contains bidi control characters {', '.join(controls)}")
    for token in KNOWN_BAD[lang]:
        if token.casefold() in text.casefold():
            errors.append(f"{label}: known damaged wording returned: {token!r}")


def main() -> None:
    errors: list[str] = []
    metrics: list[str] = []
    for lang in LANGUAGES:
        data_native_path = DATA_NATIVE / f"library_{lang}.json"
        app_native_path = APP_NATIVE / f"library_{lang}.json"
        data_search_path = DATA_SEARCH / f"search_index_{lang}.json"
        app_search_path = APP_SEARCH / f"search_index_{lang}.json"

        if data_native_path.read_bytes() != app_native_path.read_bytes():
            errors.append(f"{lang}: data and Android native packs differ")
        if data_search_path.read_bytes() != app_search_path.read_bytes():
            errors.append(f"{lang}: data and Android search indexes differ")

        pack = read_json(data_native_path)
        service = service_from_pack(pack, lang, str(data_native_path.relative_to(ROOT)))
        visible = full_visible_text(service, lang)
        display = search_display_text(service, lang)
        validate_text(f"{lang}.native", visible, lang, errors)

        search = read_json(data_search_path)
        documents = search.get("documents") or []
        matches = [d for d in documents if isinstance(d, dict) and d.get("id") == "service:divine_liturgy"]
        if len(matches) != 1:
            errors.append(f"{lang}.search: expected one service:divine_liturgy document, found {len(matches)}")
            continue
        document = matches[0]
        search_text = str(document.get("display_text") or "")
        validate_text(f"{lang}.search", search_text, lang, errors)
        if search_text != display:
            errors.append(f"{lang}.search: displayed text is stale or differs from the native pack")
        digest = hashlib.sha256(search_text.encode("utf-8")).hexdigest()
        if document.get("display_sha256") != digest:
            errors.append(f"{lang}.search: display_sha256 mismatch")

        if lang == "ar":
            ordinary = "هذا هو اليوم الذي صنعه الرب، فلنفرح ونبتهج فيه."
            if display.count(ordinary) != 1:
                errors.append(f"ar.native: third-antiphon ordinary must appear once; found {display.count(ordinary)}")
            required = (
                "مباركة هي مملكة الآب والابن والروح القدس",
                "صلاة الأنتيفونا الأولى",
                "صلاة الأنتيفونا الثانية",
                "صلاة الأنتيفونا الثالثة",
                "خذوا كلوا",
                "اشربوا منه كلكم",
                "إياهما بروحك القدوس",
            )
            for marker in required:
                if marker not in visible:
                    errors.append(f"ar.native: required reviewed marker missing: {marker!r}")

        metrics.append(f"{lang}_segments={len(service.get('segments') or [])} {lang}_search_chars={len(search_text)}")

    if errors:
        for error in errors:
            print(f"LITURGY_DELIVERY_ERROR {error}")
        raise SystemExit(1)
    print("DIVINE_LITURGY_DELIVERY_OK " + " ".join(metrics))


if __name__ == "__main__":
    main()
