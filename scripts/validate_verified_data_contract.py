#!/usr/bin/env python3
"""Preflight the published-data branch against the current nine-day runtime contract.

This validator is intentionally structural. Detached signatures are verified by the
normal publication verifier after import. The preflight prevents an older, authentic
but incompatible eight-day publication from overwriting the current application
contract and producing dozens of misleading downstream errors.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

LANGUAGES = ("ar", "en", "el")
POLICY = "NINE_CONSECUTIVE_DAYS_STARTING_TODAY"
FULL_SCOPE = "FROM_BEGINNING_TO_DISMISSAL_WITH_NATIVE_PREPARATION_AND_THANKSGIVING"
DISPLAYABLE = "DISPLAYABLE_COMPLETE_NATIVE_SERVICE_FROM_BEGINNING_TO_END"
NO_LITURGY = "NO_DIVINE_LITURGY_APPOINTED"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise SystemExit(f"invalid JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"JSON root must be an object: {path}")
    return value


def localized_reason_present(value: object, language: str | None) -> bool:
    if not isinstance(value, dict):
        return False
    if language:
        return bool(str(value.get(language) or "").strip())
    return all(bool(str(value.get(item) or "").strip()) for item in LANGUAGES)


def rolling_window_shape_errors(
    payload: dict[str, Any],
    expected_start: str,
) -> list[str]:
    """Return contract-shape errors shared by import and preservation guards."""
    errors: list[str] = []
    try:
        start = date.fromisoformat(expected_start)
    except ValueError:
        return [f"invalid expected start date: {expected_start}"]

    if int(payload.get("schema_version") or 0) < 10:
        errors.append("schema_version must be at least 10")
    meta = payload.get("rolling_week")
    if not isinstance(meta, dict):
        return [*errors, "rolling_week metadata is missing"]
    if meta.get("schema_version") != 1:
        errors.append("rolling_week.schema_version must be 1")
    if meta.get("policy") != POLICY:
        errors.append("rolling_week.policy is not the nine-day policy")
    if meta.get("start_date") != expected_start:
        errors.append("rolling_week.start_date mismatch")
    if meta.get("end_date") != (start + timedelta(days=8)).isoformat():
        errors.append("rolling_week.end_date mismatch")
    if meta.get("day_count") != 9:
        errors.append("rolling_week.day_count must be 9")
    if meta.get("status") != "COMPLETE":
        errors.append("rolling_week.status must be COMPLETE")
    if meta.get("fail_closed") is not True:
        errors.append("rolling_week.fail_closed must be true")

    weekly = payload.get("weekly_days")
    if not isinstance(weekly, list) or len(weekly) != 8:
        errors.append("weekly_days must contain exactly eight future days")
        return errors

    days = [payload, *weekly]
    for offset, item in enumerate(days):
        expected = (start + timedelta(days=offset)).isoformat()
        if not isinstance(item, dict):
            errors.append(f"day {offset} is not an object")
        elif item.get("date_iso") != expected:
            errors.append(f"day {offset} date mismatch")
    return errors


def published_payload_errors(
    payload: dict[str, Any],
    expected_start: str,
    language: str | None = None,
) -> list[str]:
    errors = rolling_window_shape_errors(payload, expected_start)
    weekly = payload.get("weekly_days")
    if not isinstance(weekly, list) or len(weekly) != 8:
        return errors

    days = [payload, *weekly]
    for item in days:
        if not isinstance(item, dict):
            continue
        iso = str(item.get("date_iso") or "unknown")
        selection = item.get("liturgy_service_selection")
        if not isinstance(selection, dict):
            errors.append(f"{iso}: liturgy_service_selection is missing")
            continue
        service_type = str(selection.get("service_type") or "").strip()
        if not service_type:
            errors.append(f"{iso}: service_type is missing")
        if not str(selection.get("service_form") or "").strip():
            errors.append(f"{iso}: service_form is missing")
        if not localized_reason_present(selection.get("reason"), language):
            errors.append(f"{iso}: localized selection reason is missing")
        if selection.get("wrong_liturgy_fallback_allowed") is not False:
            errors.append(f"{iso}: wrong-liturgy fallback must be false")
        if selection.get("full_service_scope") != FULL_SCOPE:
            errors.append(f"{iso}: full-service scope is invalid")

        services = {
            str(service.get("id") or ""): service
            for service in item.get("services") or []
            if isinstance(service, dict)
        }
        liturgy = services.get("divine_liturgy")
        if not isinstance(liturgy, dict):
            errors.append(f"{iso}: divine_liturgy service is missing")
            continue
        if liturgy.get("selected_liturgy_type") != service_type:
            errors.append(f"{iso}: selected liturgy type does not match the service")
        if service_type == "no_divine_liturgy":
            if liturgy.get("publication_status") != NO_LITURGY:
                errors.append(f"{iso}: no-liturgy publication status is invalid")
        else:
            if selection.get("displayable") is not True:
                errors.append(f"{iso}: selected liturgy is not displayable")
            if liturgy.get("full_service_complete") is not True:
                errors.append(f"{iso}: full service is not complete")
            if liturgy.get("publication_status") != DISPLAYABLE:
                errors.append(f"{iso}: publication status is not displayable-complete")
    return errors


def validate_root(root: Path, expected_date: str | None = None) -> tuple[str, list[str]]:
    today_path = root / "data/calendar/today.json"
    if not today_path.is_file():
        return "", ["data/calendar/today.json is missing"]
    today = load_json(today_path)
    published_date = str(today.get("date_iso") or "")
    if not published_date:
        return "", ["published date is missing"]
    if expected_date and published_date != expected_date:
        return published_date, [
            f"published date mismatch expected={expected_date} actual={published_date}"
        ]

    errors = [f"calendar: {error}" for error in published_payload_errors(today, published_date)]
    lanes_found = 0
    for language in LANGUAGES:
        lane_path = root / f"data/daily/{published_date}/{language}.json"
        current_path = root / f"data/daily/current/{language}.json"
        if not lane_path.is_file() and not current_path.is_file():
            continue
        lanes_found += 1
        if not lane_path.is_file() or not current_path.is_file():
            errors.append(f"{language}: dated/current lane pair is incomplete")
            continue
        lane = load_json(lane_path)
        errors.extend(
            f"{language}: {error}"
            for error in published_payload_errors(lane, published_date, language)
        )
        if lane_path.read_bytes() != current_path.read_bytes():
            errors.append(f"{language}: dated/current lane mismatch")
    if lanes_found == 0:
        errors.append("no published language lanes were found")
    return published_date, errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-date")
    args = parser.parse_args()

    published_date, errors = validate_root(args.root.resolve(), args.expected_date)
    if errors:
        for error in errors:
            print(f"VERIFIED_DATA_CONTRACT_ERROR {error}")
        raise SystemExit(
            "VERIFIED_DATA_UPGRADE_REQUIRED "
            f"date={published_date or 'unknown'}; run Rolling Week Update in update mode "
            "from current main, then rerun Build"
        )
    print(f"VERIFIED_DATA_CONTRACT_OK date={published_date} days=9")


if __name__ == "__main__":
    main()
