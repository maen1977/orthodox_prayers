#!/usr/bin/env python3
"""Keep date-sensitive services as compact overlays instead of copied books."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TODAY = ROOT / "data/calendar/today.json"
LIBRARY = ROOT / "app/src/main/assets/data/library.json"


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: root must be an object")
    return value


def main() -> None:
    today = load(TODAY)
    library = load(LIBRARY)
    if int(today.get("schema_version") or 0) < 8:
        raise SystemExit("Daily data must use schema_version 8 or newer")

    library_ids = {
        str(item.get("id")): item
        for item in library.get("services", [])
        if isinstance(item, dict) and item.get("id")
    }
    daily = {
        str(item.get("id")): item
        for item in today.get("services", [])
        if isinstance(item, dict) and item.get("id")
    }

    expected_bases = {
        "divine_liturgy": "divine_liturgy",
        "next_sunday_full_liturgy": "divine_liturgy",
        "vespers": "vespers",
        "orthros": "orthros",
        "morning_prayer": "morning_prayer",
        "evening_prayer": "evening_prayer",
        "small_compline": "small_compline",
    }
    for service_id, base_id in expected_bases.items():
        service = daily.get(service_id)
        if not service:
            raise SystemExit(f"Missing daily service: {service_id}")
        if service.get("extends_service_id") != base_id:
            raise SystemExit(f"{service_id} must extend {base_id}")
        if base_id not in library_ids:
            raise SystemExit(f"Missing static base service: {base_id}")

    for service_id in ("divine_liturgy", "next_sunday_full_liturgy"):
        count = len(daily[service_id].get("segments") or [])
        if count > 30:
            raise SystemExit(f"{service_id} contains {count} daily segments; expected a compact overlay")
        if not daily[service_id].get("segment_replacements"):
            raise SystemExit(f"{service_id} is missing segment_replacements")

    size = TODAY.stat().st_size
    if size > 300_000:
        raise SystemExit(f"today.json is unexpectedly large ({size} bytes); copied service content likely returned")
    print(f"Content deduplication passed: {len(daily)} overlays, today.json={size} bytes")


if __name__ == "__main__":
    main()
