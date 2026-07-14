#!/usr/bin/env python3
"""Validate fasting profiles, seven-day cards, and the next-Sunday service."""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "calendar" / "today.json"
FAST_CODES = {"fast_free", "dairy_allowed", "fish_allowed", "wine_oil", "strict"}
FOODS = {"meat", "dairy", "eggs", "fish", "wine", "oil"}

PLACEHOLDER_REFS = {
    "رسالة اليوم", "إنجيل اليوم", "انجيل اليوم",
    "Daily Epistle", "Daily Gospel",
}


def localized_ar(value: Any) -> str:
    return str(value.get("ar") or "").strip() if isinstance(value, dict) else ""


def validate_fasting(profile: Any, pointer: str, errors: list[str]) -> None:
    if not isinstance(profile, dict):
        errors.append(f"{pointer}: missing fasting object")
        return
    code = str(profile.get("code") or "")
    if code not in FAST_CODES:
        errors.append(f"{pointer}.code: unsupported value {code!r}")
    if not localized_ar(profile.get("title")):
        errors.append(f"{pointer}.title.ar: required")
    if not localized_ar(profile.get("detail")):
        errors.append(f"{pointer}.detail.ar: required")
    allowed = profile.get("allowed")
    if not isinstance(allowed, dict) or set(allowed) != FOODS:
        errors.append(f"{pointer}.allowed: must contain exactly {sorted(FOODS)}")
    elif any(not isinstance(allowed[key], bool) for key in FOODS):
        errors.append(f"{pointer}.allowed: every value must be boolean")
    icons = profile.get("display_icons")
    if not isinstance(icons, list) or not icons or any(not str(icon).strip() for icon in icons):
        errors.append(f"{pointer}.display_icons: at least one non-empty icon is required")
    verification = profile.get("verification")
    if not isinstance(verification, dict) or verification.get("status") not in {"TYPICON_BASELINE", "DOCUMENTED_OVERRIDE"}:
        errors.append(f"{pointer}.verification.status: invalid or missing")
    if code == "fast_free" and profile.get("is_fast") is not False:
        errors.append(f"{pointer}.is_fast: fast_free must be false")
    if code != "fast_free" and profile.get("is_fast") is not True:
        errors.append(f"{pointer}.is_fast: fasting level must be true")


def get_ref(container: Any, kind: str) -> str:
    if not isinstance(container, dict):
        return ""
    item = container.get(kind)
    if not isinstance(item, dict):
        return ""
    return localized_ar(item.get("reference")) or str((item.get("reference") or {}).get("en") or "").strip()


def validate(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        today = date.fromisoformat(str(data.get("date_iso") or data.get("date") or ""))
    except Exception:
        return ["date_iso: invalid or missing"]

    validate_fasting(data.get("fasting"), "fasting", errors)
    top_fasting = data.get("fasting") if isinstance(data.get("fasting"), dict) else {}
    if localized_ar(data.get("fast")) != localized_ar(top_fasting.get("title")):
        errors.append("fast.ar must equal fasting.title.ar")
    if localized_ar(data.get("fast_detail")) != localized_ar(top_fasting.get("detail")):
        errors.append("fast_detail.ar must equal fasting.detail.ar")

    upcoming = data.get("upcoming")
    if not isinstance(upcoming, list) or len(upcoming) != 7:
        errors.append("upcoming must contain exactly seven days")
        upcoming = []
    by_date: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(upcoming):
        pointer = f"upcoming[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{pointer}: must be an object")
            continue
        expected = today + timedelta(days=index + 1)
        actual = str(item.get("date") or "")
        if actual != expected.isoformat():
            errors.append(f"{pointer}.date: expected {expected.isoformat()}, got {actual!r}")
        by_date[actual] = item
        validate_fasting(item.get("fasting"), f"{pointer}.fasting", errors)
        if localized_ar(item.get("status")) != localized_ar((item.get("fasting") or {}).get("title")):
            errors.append(f"{pointer}.status.ar must equal fasting.title.ar")
        refs = item.get("reading_references")
        epistle_ref = get_ref(refs, "epistle")
        gospel_ref = get_ref(refs, "gospel")
        if not epistle_ref:
            errors.append(f"{pointer}.reading_references.epistle.reference is missing")
        elif epistle_ref in PLACEHOLDER_REFS:
            errors.append(f"{pointer}.reading_references.epistle.reference is a placeholder")
        if not gospel_ref:
            errors.append(f"{pointer}.reading_references.gospel.reference is missing")
        elif gospel_ref in PLACEHOLDER_REFS:
            errors.append(f"{pointer}.reading_references.gospel.reference is a placeholder")
        if item.get("is_sunday") is not (expected.weekday() == 6):
            errors.append(f"{pointer}.is_sunday is incorrect")

    sunday = data.get("next_sunday")
    if not isinstance(sunday, dict):
        errors.append("next_sunday: missing object")
    else:
        sunday_iso = str(sunday.get("date_iso") or "")
        try:
            sunday_date = date.fromisoformat(sunday_iso)
            if sunday_date <= today:
                errors.append("next_sunday.date_iso must be after today")
            if sunday_date.weekday() != 6:
                errors.append("next_sunday.date_iso is not a Sunday")
        except Exception:
            errors.append("next_sunday.date_iso is invalid")
            sunday_date = None
        validate_fasting(sunday.get("fasting"), "next_sunday.fasting", errors)
        if localized_ar(sunday.get("fast")) != localized_ar((sunday.get("fasting") or {}).get("title")):
            errors.append("next_sunday.fast.ar must equal next_sunday.fasting.title.ar")
        refs = sunday.get("reading_references")
        sunday_epistle = get_ref(refs, "epistle")
        sunday_gospel = get_ref(refs, "gospel")
        if not sunday_epistle or not sunday_gospel:
            errors.append("next_sunday must contain epistle and Gospel references")
        elif sunday_epistle in PLACEHOLDER_REFS or sunday_gospel in PLACEHOLDER_REFS:
            errors.append("next_sunday contains placeholder reading references")
        upcoming_sunday = by_date.get(sunday_iso)
        if not upcoming_sunday:
            errors.append("next_sunday must also appear in the seven-day list")
        else:
            if upcoming_sunday.get("fasting") != sunday.get("fasting"):
                errors.append("next_sunday fasting profile differs from its upcoming card")
            if upcoming_sunday.get("reading_references") != sunday.get("reading_references"):
                errors.append("next_sunday reading references differ from its upcoming card")

        service_id = str(sunday.get("service_id") or "")
        services = data.get("services") if isinstance(data.get("services"), list) else []
        service = next((s for s in services if isinstance(s, dict) and s.get("id") == service_id), None)
        if not service:
            errors.append(f"next_sunday.service_id {service_id!r} is missing from services")
        elif str(service.get("dynamic_date") or "") != sunday_iso:
            errors.append("next Sunday service dynamic_date does not match next_sunday.date_iso")

    required_daily = {"vespers", "orthros", "morning_prayer", "evening_prayer", "small_compline"}
    service_map = {
        str(service.get("id")): service
        for service in (data.get("services") if isinstance(data.get("services"), list) else [])
        if isinstance(service, dict)
    }
    for service_id in required_daily:
        service = service_map.get(service_id)
        if not service:
            errors.append(f"daily service {service_id} is missing")
        elif str(service.get("dynamic_date") or "") != today.isoformat():
            errors.append(f"daily service {service_id} is stale")

    return errors


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    if not path.is_absolute():
        path = ROOT / path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"Cannot read {path}: {exc}")
    errors = validate(data)
    if errors:
        for error in errors:
            print(f"::error title=Liturgical schedule validation::{error}")
        raise SystemExit("Liturgical schedule validation failed with " + str(len(errors)) + " error(s)")
    print("Liturgical schedule validation passed: fasting profiles, seven upcoming days, next Sunday, and daily services are current")


if __name__ == "__main__":
    main()
