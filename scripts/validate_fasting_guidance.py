#!/usr/bin/env python3
"""Validate novice-friendly fasting details and fail closed on invented hours."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data/calendar/today.json"
LANGUAGES = ("ar", "en", "el")
FOODS = ("meat", "dairy", "eggs", "fish", "wine", "oil")
EXPECTED_ALLOWED = {
    "fast_free": set(FOODS),
    "dairy_allowed": {"dairy", "eggs", "fish", "wine", "oil"},
    "fish_allowed": {"fish", "wine", "oil"},
    "wine_oil": {"wine", "oil"},
    "strict": set(),
}
CLOCK = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def text(value: Any) -> str:
    return str(value or "").strip()


def require_localized(value: Any, pointer: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{pointer}: localized object required")
        return
    for language in LANGUAGES:
        if not text(value.get(language)):
            errors.append(f"{pointer}.{language}: non-empty text required")


def validate_profile(profile: Any, pointer: str, errors: list[str]) -> None:
    if not isinstance(profile, dict):
        errors.append(f"{pointer}: fasting object required")
        return
    code = text(profile.get("code"))
    if code not in EXPECTED_ALLOWED:
        errors.append(f"{pointer}.code: unsupported {code!r}")
        return
    allowed = profile.get("allowed")
    if not isinstance(allowed, dict) or set(allowed) != set(FOODS):
        errors.append(f"{pointer}.allowed: exact food-category map required")
    else:
        actual = {food for food in FOODS if allowed.get(food) is True}
        if actual != EXPECTED_ALLOWED[code]:
            errors.append(f"{pointer}.allowed: contradicts fasting code {code}")

    guidance = profile.get("guidance")
    if not isinstance(guidance, dict):
        errors.append(f"{pointer}.guidance: required")
    else:
        for key in (
            "allowed_summary",
            "forbidden_summary",
            "duration",
            "beginner_explanation",
            "spiritual_note",
            "health_note",
        ):
            require_localized(guidance.get(key), f"{pointer}.guidance.{key}", errors)

    abstinence = profile.get("abstinence")
    if not isinstance(abstinence, dict):
        errors.append(f"{pointer}.abstinence: required")
        return
    applies = abstinence.get("applies")
    kind = text(abstinence.get("kind"))
    start = abstinence.get("start_time")
    end = abstinence.get("end_time")
    require_localized(abstinence.get("end_condition"), f"{pointer}.abstinence.end_condition", errors)
    require_localized(abstinence.get("detail"), f"{pointer}.abstinence.detail", errors)
    evidence = abstinence.get("verification") if isinstance(abstinence.get("verification"), dict) else {}
    status = text(evidence.get("status"))
    source = text(evidence.get("source"))
    if not source:
        errors.append(f"{pointer}.abstinence.verification.source: required")
    if applies is True:
        if kind not in {"documented_interval", "until_communion", "until_service_end"}:
            errors.append(f"{pointer}.abstinence.kind: documented kind required when applies=true")
        if status != "DOCUMENTED_OVERRIDE":
            errors.append(f"{pointer}.abstinence.verification.status: DOCUMENTED_OVERRIDE required")
        if kind == "documented_interval":
            if not isinstance(start, str) or not CLOCK.fullmatch(start):
                errors.append(f"{pointer}.abstinence.start_time: HH:MM required")
            if not isinstance(end, str) or not CLOCK.fullmatch(end):
                errors.append(f"{pointer}.abstinence.end_time: HH:MM required")
    elif applies is False:
        if kind != "not_indicated" or status != "NOT_INDICATED":
            errors.append(f"{pointer}.abstinence: unapplied baseline must be NOT_INDICATED")
        if start is not None or end is not None:
            errors.append(f"{pointer}.abstinence: unverified clock times are forbidden")
    else:
        errors.append(f"{pointer}.abstinence.applies: boolean required")


def validate(data: dict[str, Any]) -> list[str]:
    if data.get("fasting_guidance_version") != 1:
        return []
    errors: list[str] = []
    validate_profile(data.get("fasting"), "fasting", errors)
    upcoming = data.get("upcoming")
    if not isinstance(upcoming, list) or len(upcoming) != 7:
        errors.append("upcoming: exactly seven days required")
    else:
        for index, item in enumerate(upcoming):
            validate_profile(item.get("fasting") if isinstance(item, dict) else None, f"upcoming[{index}].fasting", errors)
    sunday = data.get("next_sunday")
    validate_profile(sunday.get("fasting") if isinstance(sunday, dict) else None, "next_sunday.fasting", errors)
    return errors


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    if not path.is_absolute():
        path = ROOT / path
    data = json.loads(path.read_text(encoding="utf-8"))
    legacy = data.get("fasting_guidance_version") != 1
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"::error title=Fasting guidance::{error}")
        raise SystemExit(f"Fasting guidance validation failed with {len(errors)} error(s)")
    if legacy:
        print("Legacy signed payload has no fasting guidance extension; generator contract is covered by source tests")
    else:
        print("Fasting guidance validated: permitted/forbidden foods, duration, novice notes, and documented abstinence are consistent")


if __name__ == "__main__":
    main()
