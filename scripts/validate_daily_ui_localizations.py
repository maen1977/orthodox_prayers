#!/usr/bin/env python3
"""Require complete Arabic, English, and Greek UI metadata for a daily payload.

Scripture and prayer-body verification is handled by the native-language gates.
This check covers deterministic UI text: dates, fasting descriptions, reading
labels/references, upcoming cards, and generated daily service overlays.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")


def _text(value: Any) -> str:
    return str(value or "").strip()


def require_localized(value: Any, pointer: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{pointer} is not a localized object")
        return
    for language in LANGUAGES:
        if not _text(value.get(language)):
            errors.append(f"{pointer}.{language} is empty")


def validate_fasting(profile: Any, pointer: str, errors: list[str]) -> None:
    if not isinstance(profile, dict):
        errors.append(f"{pointer} is missing")
        return
    for key in ("season", "title", "level", "detail"):
        require_localized(profile.get(key), f"{pointer}.{key}", errors)
    items = profile.get("items")
    if not isinstance(items, list) or not items:
        errors.append(f"{pointer}.items is empty")
    else:
        for index, item in enumerate(items):
            if isinstance(item, dict):
                require_localized(item.get("label"), f"{pointer}.items[{index}].label", errors)
    verification = profile.get("verification") if isinstance(profile.get("verification"), dict) else {}
    require_localized(verification.get("note"), f"{pointer}.verification.note", errors)


def validate_reading_labels(readings: Any, pointer: str, errors: list[str], require_reference: bool = True) -> None:
    if not isinstance(readings, list):
        errors.append(f"{pointer} is not a list")
        return
    scripture_seen = set()
    for index, reading in enumerate(readings):
        if not isinstance(reading, dict):
            continue
        kind = _text(reading.get("kind"))
        if kind not in {"prokeimenon", "epistle", "gospel"}:
            continue
        require_localized(reading.get("title"), f"{pointer}[{index}].title", errors)
        if require_reference:
            require_localized(reading.get("reference"), f"{pointer}[{index}].reference", errors)
        if kind in {"epistle", "gospel"}:
            scripture_seen.add(kind)
    if require_reference and scripture_seen != {"epistle", "gospel"}:
        errors.append(f"{pointer} must include epistle and gospel")


def validate_reference_block(block: Any, pointer: str, errors: list[str]) -> None:
    if not isinstance(block, dict):
        errors.append(f"{pointer} is missing")
        return
    for kind in ("epistle", "gospel"):
        entry = block.get(kind)
        if not isinstance(entry, dict):
            errors.append(f"{pointer}.{kind} is missing")
            continue
        require_localized(entry.get("title"), f"{pointer}.{kind}.title", errors)
        require_localized(entry.get("reference"), f"{pointer}.{kind}.reference", errors)


def validate_service_overlays(services: Any, errors: list[str]) -> None:
    if not isinstance(services, list) or not services:
        errors.append("services is empty")
        return
    for service_index, service in enumerate(services):
        if not isinstance(service, dict):
            continue
        pointer = f"services[{service_index}]"
        for key in ("title", "summary", "notice"):
            if key in service:
                require_localized(service.get(key), f"{pointer}.{key}", errors)
        inline = service.get("inline_replacements")
        if isinstance(inline, dict):
            evangelist = inline.get("[اسم الإنجيلي]")
            if isinstance(evangelist, dict) and any(_text(evangelist.get(lang)) for lang in LANGUAGES):
                require_localized(evangelist, f"{pointer}.inline_replacements.[اسم الإنجيلي]", errors)
        segments = service.get("segments")
        if not isinstance(segments, list):
            continue
        for segment_index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                continue
            segment_pointer = f"{pointer}.segments[{segment_index}]"
            for key in ("title", "speaker", "text"):
                value = segment.get(key)
                if isinstance(value, dict) and any(_text(value.get(lang)) for lang in LANGUAGES):
                    require_localized(value, f"{segment_pointer}.{key}", errors)


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in (
        "app_title",
        "patriarchate",
        "date_label",
        "calendar_label",
        "fast",
        "fast_detail",
        "feast",
        "source_note",
        "translation_notice",
    ):
        require_localized(data.get(key), key, errors)
    validate_fasting(data.get("fasting"), "fasting", errors)
    validate_reading_labels(data.get("readings"), "readings", errors)

    sunday = data.get("next_sunday")
    if not isinstance(sunday, dict):
        errors.append("next_sunday is missing")
    else:
        for key in ("day", "feast", "fast"):
            require_localized(sunday.get(key), f"next_sunday.{key}", errors)
        validate_fasting(sunday.get("fasting"), "next_sunday.fasting", errors)
        validate_reference_block(sunday.get("reading_references"), "next_sunday.reading_references", errors)

    upcoming = data.get("upcoming")
    if not isinstance(upcoming, list) or len(upcoming) != 7:
        errors.append("upcoming must contain seven days")
    else:
        for index, item in enumerate(upcoming):
            if not isinstance(item, dict):
                errors.append(f"upcoming[{index}] is invalid")
                continue
            for key in ("day", "feast", "status", "note"):
                require_localized(item.get(key), f"upcoming[{index}].{key}", errors)
            validate_fasting(item.get("fasting"), f"upcoming[{index}].fasting", errors)
            validate_reference_block(item.get("reading_references"), f"upcoming[{index}].reading_references", errors)

    validate_service_overlays(data.get("services"), errors)
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="data/calendar/today.json")
    args = parser.parse_args()
    path = Path(args.path)
    if not path.is_absolute():
        path = ROOT / path
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate(data)
    if errors:
        raise SystemExit("Daily UI localization validation failed:\n- " + "\n- ".join(errors))
    print(f"Daily UI localization validated for Arabic, English, and Greek: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")


if __name__ == "__main__":
    main()
