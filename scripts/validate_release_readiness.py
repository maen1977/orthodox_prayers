#!/usr/bin/env python3
"""Block production until the signed nine-day liturgical window is complete.

The release target is a moving window of today plus eight future days in
Asia/Amman. It intentionally does not preload or claim a 365-day liturgical
calendar. Every day must identify the appointed rite and service form, provide
exact same-language Scripture, and either expose the complete appointed service
from preparation through dismissal/thanksgiving or explicitly state that no
Divine Liturgy is appointed. Wrong-rite substitution is forbidden.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from native_text_contract import ROOT, LANGUAGES, load_contract, sha256_text, source_allowed, source_url_allowed

EXACT_STATUSES = {
    "VERIFIED_EXACT_NATIVE_SOURCE",
    "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS",
    "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
}
ROLLING_POLICY = "NINE_CONSECUTIVE_DAYS_STARTING_TODAY"


def run_gate(command: list[str], label: str, errors: list[str]) -> None:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        errors.append(f"{label}:\n{detail}")


def rolling_days(payload: dict[str, Any], errors: list[str]) -> list[dict[str, Any]]:
    rolling = payload.get("rolling_week")
    future = payload.get("weekly_days")
    if not isinstance(rolling, dict):
        errors.append("signed package has no rolling_week metadata")
        return []
    if rolling.get("policy") != ROLLING_POLICY:
        errors.append(f"rolling policy must be {ROLLING_POLICY}")
    if rolling.get("day_count") != 9:
        errors.append("rolling window must contain exactly 9 days")
    if rolling.get("status") != "COMPLETE" or rolling.get("fail_closed") is not True:
        errors.append("rolling window must be COMPLETE and fail closed")
    if not isinstance(future, list) or len(future) != 8:
        errors.append("rolling package must contain exactly 8 future days")
        return []
    days = [payload, *[item for item in future if isinstance(item, dict)]]
    if len(days) != 9:
        errors.append("rolling package contains invalid day objects")
        return []
    try:
        start = date.fromisoformat(str(rolling.get("start_date") or ""))
    except ValueError:
        errors.append("rolling start_date is invalid")
        return days
    expected_end = start + timedelta(days=8)
    if str(rolling.get("end_date") or "") != expected_end.isoformat():
        errors.append("rolling end_date must be start_date + 8 days")
    for offset, day_payload in enumerate(days):
        expected = (start + timedelta(days=offset)).isoformat()
        if str(day_payload.get("date_iso") or "") != expected:
            errors.append(f"rolling day {offset} must be {expected}")
    return days


def validate_scripture_day(day_payload: dict[str, Any], contract: dict[str, Any], errors: list[str]) -> None:
    day_iso = str(day_payload.get("date_iso") or "unknown-date")
    readings = day_payload.get("readings")
    if not isinstance(readings, list):
        errors.append(f"{day_iso}: readings are missing")
        return
    by_kind = {
        str(item.get("kind") or ""): item
        for item in readings
        if isinstance(item, dict)
    }
    for kind in ("epistle", "gospel"):
        reading = by_kind.get(kind)
        if not isinstance(reading, dict):
            errors.append(f"{day_iso}: missing {kind}")
            continue
        verification = reading.get("native_source_verification") or {}
        body = reading.get("body") or {}
        reference = reading.get("reference") or {}
        for language in LANGUAGES:
            text = str(body.get(language) or "").strip()
            ref = str(reference.get(language) or "").strip()
            evidence = verification.get(language) or {}
            status = str(evidence.get("status") or "")
            source_id = str(evidence.get("source_id") or "")
            source_url = str(evidence.get("source_url") or "")
            if not text or not ref or evidence.get("text_available") is not True:
                errors.append(f"{day_iso} {kind}: exact {language} text/reference is unavailable")
                continue
            if status not in EXACT_STATUSES:
                errors.append(f"{day_iso} {kind}: {language} evidence status {status!r} is not exact")
            if not source_allowed(language, source_id, contract):
                errors.append(f"{day_iso} {kind}: {language} source {source_id!r} is outside its lane")
            if not source_url_allowed(source_id, source_url, contract):
                errors.append(f"{day_iso} {kind}: {language} source URL is outside the registered domain")
            if evidence.get("text_sha256") != sha256_text(text):
                errors.append(f"{day_iso} {kind}: {language} text hash mismatch")
            if evidence.get("ai_translation_used") is not False:
                errors.append(f"{day_iso} {kind}: {language} AI translation flag must be false")
            if evidence.get("automatic_diacritization_used") is not False:
                errors.append(f"{day_iso} {kind}: {language} automatic diacritization flag must be false")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--daily-path", type=Path, default=Path("data/calendar/today.json"))
    args = parser.parse_args()
    daily_path = args.daily_path if args.daily_path.is_absolute() else ROOT / args.daily_path
    errors: list[str] = []

    run_gate(
        [sys.executable, "scripts/validate_native_language_packs.py", "--require-complete"],
        "Native service packs are incomplete",
        errors,
    )
    run_gate(
        [sys.executable, "scripts/validate_follow_along_liturgy.py"],
        "The focused follow-along Liturgy profile is incomplete",
        errors,
    )
    relative = str(daily_path.relative_to(ROOT)) if daily_path.is_relative_to(ROOT) else str(daily_path)
    run_gate(
        [sys.executable, "scripts/validate_rolling_week.py", relative, "--expected-start", json.loads(daily_path.read_text(encoding="utf-8")).get("date_iso", "")],
        "The nine-day rolling package is invalid",
        errors,
    )
    run_gate(
        [sys.executable, "scripts/validate_full_liturgy_services.py", relative],
        "An appointed Liturgy is incomplete or substituted",
        errors,
    )

    payload = json.loads(daily_path.read_text(encoding="utf-8"))
    days = rolling_days(payload, errors)
    contract = load_contract()
    for day_payload in days:
        validate_scripture_day(day_payload, contract, errors)

    if errors:
        raise SystemExit("Production release is blocked:\n- " + "\n- ".join(dict.fromkeys(errors)))
    print(
        f"Production release readiness validated for {daily_path}: "
        "9/9 consecutive days, exact Arabic/English/Greek Scripture, appointed-rite selection, "
        "complete beginning-to-end services, and no wrong-rite fallback"
    )


if __name__ == "__main__":
    main()
