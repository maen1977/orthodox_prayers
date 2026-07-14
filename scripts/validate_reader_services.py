#!/usr/bin/env python3
"""Fail closed when a prayer/liturgy entry could render as a blank reader."""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY_PATHS = (
    ROOT / "data/calendar/today.json",
    ROOT / "app/src/main/assets/data/today.json",
)
LIBRARY_PATH = ROOT / "app/src/main/assets/data/library.json"
REQUIRED_DAILY = {
    "divine_liturgy",
    "vespers",
    "orthros",
    "morning_prayer",
    "evening_prayer",
    "small_compline",
    "next_sunday_full_liturgy",
}


def localized_nonempty(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return any(isinstance(item, str) and item.strip() for item in value.values())


def validate_service(service: object, source: Path) -> str:
    if not isinstance(service, dict):
        raise SystemExit(f"{source}: service is not an object")
    service_id = str(service.get("id", "")).strip()
    if not service_id:
        raise SystemExit(f"{source}: service id missing")
    if not str(service.get("category", "")).strip():
        raise SystemExit(f"{source}: category missing for {service_id}")
    if not localized_nonempty(service.get("title")):
        raise SystemExit(f"{source}: localized title missing for {service_id}")
    segments = service.get("segments")
    if not isinstance(segments, list) or not segments:
        raise SystemExit(f"{source}: no renderable segments for {service_id}")
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            raise SystemExit(f"{source}: invalid segment {service_id}[{index}]")
        content_key = "title" if segment.get("type") == "section" else "text"
        if not localized_nonempty(segment.get(content_key)):
            raise SystemExit(f"{source}: blank {content_key} in {service_id}[{index}]")
    return service_id


def validate_payload(path: Path, required: set[str] | None = None) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    services = payload.get("services")
    if not isinstance(services, list):
        raise SystemExit(f"{path}: services array missing")
    indexed: dict[str, dict] = {}
    for service in services:
        service_id = validate_service(service, path)
        if service_id in indexed:
            raise SystemExit(f"{path}: duplicate service id {service_id}")
        indexed[service_id] = service
    if required:
        missing = sorted(required - indexed.keys())
        if missing:
            raise SystemExit(f"{path}: required services missing: {', '.join(missing)}")
    return indexed


def _apply_replacements(value: object, exact: dict[str, object], inline: dict[str, object]) -> None:
    if isinstance(value, dict):
        if "ar" in value and ("en" in value or "el" in value):
            arabic = str(value.get("ar") or "")
            replacement = exact.get(arabic)
            if isinstance(replacement, dict):
                for lang in ("ar", "en", "el"):
                    value[lang] = str(replacement.get(lang) or "")
                return
            for marker, localized in inline.items():
                if marker not in arabic or not isinstance(localized, dict):
                    continue
                for lang in ("ar", "en", "el"):
                    current = str(value.get(lang) or "")
                    replacement_text = str(localized.get(lang) or "")
                    if current and replacement_text:
                        value[lang] = current.replace(marker, replacement_text)
            return
        for child in value.values():
            _apply_replacements(child, exact, inline)
    elif isinstance(value, list):
        for child in value:
            _apply_replacements(child, exact, inline)


def compose_overlay(service: dict, library: dict[str, dict], source: Path) -> dict:
    base_id = str(service.get("extends_service_id") or "").strip()
    if not base_id:
        return service
    base = library.get(base_id)
    if not base:
        raise SystemExit(f"{source}: overlay {service.get('id')} references missing library service {base_id}")
    if service.get("category") != base.get("category"):
        raise SystemExit(f"{source}: overlay {service.get('id')} category differs from library base {base_id}")
    composed = copy.deepcopy(base)
    base_segments = copy.deepcopy(base.get("segments", []))
    _apply_replacements(
        base_segments,
        service.get("segment_replacements") if isinstance(service.get("segment_replacements"), dict) else {},
        service.get("inline_replacements") if isinstance(service.get("inline_replacements"), dict) else {},
    )
    composed["segments"] = copy.deepcopy(service.get("segments", [])) + base_segments
    for key, value in service.items():
        if key not in {"segments", "extends_service_id", "segment_replacements", "inline_replacements"}:
            composed[key] = copy.deepcopy(value)
    composed["composed_from"] = [f"daily:{service.get('id')}", f"library:{base_id}"]
    validate_service(composed, source)
    return composed


def main() -> None:
    library = validate_payload(LIBRARY_PATH)
    canonical = validate_payload(TODAY_PATHS[0], REQUIRED_DAILY)
    embedded = validate_payload(TODAY_PATHS[1], REQUIRED_DAILY)

    if TODAY_PATHS[0].read_bytes() != TODAY_PATHS[1].read_bytes():
        raise SystemExit("Embedded today.json differs from canonical today.json")

    composed = {
        service_id: compose_overlay(service, library, TODAY_PATHS[0])
        for service_id, service in canonical.items()
    }
    embedded_composed = {
        service_id: compose_overlay(service, library, TODAY_PATHS[1])
        for service_id, service in embedded.items()
    }

    for service_id in ("divine_liturgy", "next_sunday_full_liturgy"):
        count = len(composed[service_id]["segments"])
        if count < 200:
            raise SystemExit(f"{service_id}: expected complete reader content, found only {count} segments")
        if len(embedded_composed[service_id]["segments"]) != count:
            raise SystemExit(f"{service_id}: embedded segment count mismatch")

    total = sum(len(item["segments"]) for item in composed.values())
    overlays = sum(1 for item in canonical.values() if item.get("extends_service_id"))
    print(
        f"Reader service validation passed: {len(canonical)} daily services, "
        f"{overlays} library overlays, {total} composed segments, complete liturgies renderable"
    )


if __name__ == "__main__":
    main()
