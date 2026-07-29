#!/usr/bin/env python3
"""Reject generic guidance that stands in for actual liturgical text."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "canonical/source_policy.json").read_text(encoding="utf-8"))
BANNED = POLICY["liturgical_text_policy"]["banned_placeholder_phrases"]


def targets() -> list[Path]:
    result = {
        ROOT / "data/calendar/today.json",
        ROOT / "app/src/main/assets/data/today.json",
        ROOT / "app/src/main/assets/data/library.json",
        ROOT / "data/services/library.json",
    }
    result.update((ROOT / "data/calendar").glob("*.json"))
    result.update((ROOT / "data/services").glob("*.json"))
    return sorted(path for path in result if path.is_file())


def main() -> None:
    errors: list[str] = []
    for path in targets():
        text = path.read_text(encoding="utf-8")
        for phrase in BANNED:
            if phrase in text:
                errors.append(f"{path.relative_to(ROOT)} contains banned placeholder: {phrase}")
        count = text.count('"ar": "إرشاد"')
        if count:
            errors.append(f"{path.relative_to(ROOT)} still contains {count} generic إرشاد speaker labels")
    if errors:
        raise SystemExit("\n".join(errors))
    print("No generic review/church placeholders remain in calendar, service, or embedded content")


if __name__ == "__main__":
    main()
