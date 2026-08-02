#!/usr/bin/env python3
"""Fail-closed audit for the 2026-07-28..2026-12-31 old-calendar index."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from android_ui_resources import source_references_text
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fill_daily_from_native_corpora import parse_reference_parts  # noqa: E402

START = date(2026, 7, 28)
END = date(2026, 12, 31)
LANGUAGES = ("ar", "en", "el")
BLOCKED_TEXT = (
    "appointed for today",
    "النص المعيّن",
    "القراءة المعيّنة",
    "يقول المؤمن",
    "يقول الشعب الترنيمة",
    "[matins gospel appointed",
)


def load(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def body_audit() -> dict[str, Any]:
    payload = load("canonical/generated_daily/2026-07-28.review.json")
    expected_date = START.isoformat()
    blockers: list[str] = []
    if payload.get("date_iso") != expected_date:
        blockers.append("today_date_mismatch")
    checked = 0
    for reading in payload.get("readings") or []:
        if reading.get("kind") not in {"epistle", "gospel"}:
            continue
        canonical = str((reading.get("integrity") or {}).get("canonical_reference") or "")
        if parse_reference_parts(canonical) is None:
            blockers.append(f"invalid_today_reference:{reading.get('kind')}")
        for language in LANGUAGES:
            text = str((reading.get("body") or {}).get(language) or "")
            verification = (reading.get("native_source_verification") or {}).get(language) or {}
            checked += 1
            if not text.strip():
                blockers.append(f"missing_today_text:{reading.get('kind')}:{language}")
                continue
            lowered = text.casefold()
            if any(token.casefold() in lowered for token in BLOCKED_TEXT):
                blockers.append(f"placeholder_today_text:{reading.get('kind')}:{language}")
            if hashlib.sha256(text.encode("utf-8")).hexdigest() != verification.get("text_sha256"):
                blockers.append(f"today_hash_mismatch:{reading.get('kind')}:{language}")
            if verification.get("text_available") is not True:
                blockers.append(f"today_text_not_verified:{reading.get('kind')}:{language}")
            if verification.get("machine_translation_used") is not False:
                blockers.append(f"today_machine_translation_flag:{reading.get('kind')}:{language}")
    return {
        "date": expected_date,
        "language_passages_checked": checked,
        "complete": not blockers and checked == 6,
        "blockers": blockers,
    }


def build_report() -> dict[str, Any]:
    canonical = load("canonical/jordan_2026_h2_lectionary.json")
    asset = load("app/src/main/assets/data/calendar/calendar_2026.json")
    days = canonical.get("days") or []
    asset_days = [item for item in (asset.get("days") or []) if START.isoformat() <= str(item.get("date_iso") or item.get("date") or "") <= END.isoformat()]
    blockers: list[str] = []
    expected_count = (END - START).days + 1
    if len(days) != expected_count:
        blockers.append(f"canonical_day_count:{len(days)}")
    if len(asset_days) != expected_count:
        blockers.append(f"asset_day_count:{len(asset_days)}")
    expected_date = START
    seen: set[str] = set()
    sunday_count = 0
    feast_override_count = 0
    generic_commemoration_count = 0
    for index, item in enumerate(days):
        iso = str(item.get("date") or item.get("date_iso") or "")
        if iso != expected_date.isoformat():
            blockers.append(f"date_sequence:{index}:{iso}:{expected_date.isoformat()}")
        expected_date += timedelta(days=1)
        if iso in seen:
            blockers.append(f"duplicate_date:{iso}")
        seen.add(iso)
        feast = item.get("feast") or {}
        if not all(str(feast.get(lang) or "").strip() for lang in LANGUAGES):
            blockers.append(f"missing_feast_lane:{iso}")
        if str(feast.get("en") or "").startswith("Daily commemoration according"):
            generic_commemoration_count += 1
        refs = item.get("reading_references") or {}
        for kind in ("epistle", "gospel"):
            reading = refs.get(kind) or {}
            canonical_reference = str(reading.get("canonical_reference") or "")
            if parse_reference_parts(canonical_reference) is None:
                blockers.append(f"invalid_reference:{iso}:{kind}:{canonical_reference}")
            if not all(str((reading.get("reference") or {}).get(lang) or "").strip() for lang in LANGUAGES):
                blockers.append(f"missing_reference_lane:{iso}:{kind}")
        if item.get("is_sunday"):
            sunday_count += 1
            sunday = item.get("sunday") or {}
            if not 1 <= int(sunday.get("resurrection_tone") or 0) <= 8:
                blockers.append(f"invalid_tone:{iso}")
            if not 1 <= int(sunday.get("eothinon") or 0) <= 11:
                blockers.append(f"invalid_eothinon:{iso}")
            matins = refs.get("matins_gospel") or {}
            if parse_reference_parts(str(matins.get("canonical_reference") or "")) is None:
                blockers.append(f"invalid_matins_reference:{iso}")
        if (item.get("sources") or {}).get("override_id"):
            feast_override_count += 1
    if sunday_count != 22:
        blockers.append(f"sunday_count:{sunday_count}")
    if int(canonical.get("sunday_count") or 0) != sunday_count:
        blockers.append("canonical_sunday_summary_mismatch")
    if [x.get("date") for x in asset_days] != [x.get("date") for x in days]:
        blockers.append("asset_date_order_mismatch")
    today = body_audit()
    blockers.extend(f"today:{item}" for item in today["blockers"])
    java_day = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/ui/screens/CalendarDayScreen.java").read_text(encoding="utf-8")
    java_repo = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    for token in ("data.calendarDay(date)", "reading_references"):
        if token not in java_day:
            blockers.append(f"calendar_day_ui_missing:{token}")
    if not source_references_text(java_day, "فتح الخدمة الكاملة من البداية إلى النهاية", "ar"):
        blockers.append("calendar_day_ui_missing:فتح الخدمة الكاملة من البداية إلى النهاية")
    for token in ("calendar_index.json", "calendarDays(int year)", "calendarDay(String date)"):
        if token not in java_repo:
            blockers.append(f"repository_wiring_missing:{token}")
    return {
        "schema_version": 1,
        "range": {"start": START.isoformat(), "end": END.isoformat()},
        "expected_days": expected_count,
        "audited_days": len(days),
        "sundays": sunday_count,
        "major_or_special_overrides": feast_override_count,
        "named_commemoration_records": len(days) - generic_commemoration_count,
        "generic_commemoration_records": generic_commemoration_count,
        "commemoration_names_complete": generic_commemoration_count == 0,
        "references_complete": not any(
            value.startswith(("invalid_reference", "missing_reference_lane", "invalid_matins_reference"))
            for value in blockers
        ),
        "review_snapshot_native_text": today,
        "android_asset_bytes": (ROOT / "app/src/main/assets/data/calendar/calendar_2026.json").stat().st_size,
        "complete_for_current_delivery": not blockers,
        "blockers": blockers,
        "full_user_goal_complete": False,
        "full_goal_blockers": [
            f"{generic_commemoration_count} weekday records still use a generic commemoration label",
            "Future dates carry compact references, not all three-language Scripture bodies in the Android package",
            "Publishing the 2026-07-28 daily overlay requires the project owner's private signing key",
        ],
        "scope_note": "All 157 dates have pinned references. A three-language review snapshot is generated for 2026-07-28; publication into the Android daily overlay remains fail-closed until the owner signing key is used.",
    }


def main() -> None:
    report = build_report()
    out = ROOT / "build" / "reports" / "h2_2026_lectionary_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["complete_for_current_delivery"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
