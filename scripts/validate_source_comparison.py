#!/usr/bin/env python3
"""Validate the automated source-comparison report used before data signing."""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from rolling_window_contract import resolve_day_count

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {
    "PUBLISH_AUTOMATED_MULTI_SOURCE",
    "PUBLISH_AUTOMATED_AUTHORITY",
    "PUBLISH_AUTOMATED_INTERNAL_FAILSAFE",
}
FIELD_ALLOWED = {
    "CONFIRMED_MULTI_SOURCE",
    "CONFIRMED_AUTHORITY",
    "CONFIRMED_CROSS_CHECK",
    "INTERNAL_FAILSAFE",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date")
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--path", default="data/sources/comparison/current.json")
    parser.add_argument("--require-no-internal-failsafe", action="store_true")
    args = parser.parse_args()

    day_count = resolve_day_count(args.days)
    path = ROOT / args.path
    payload = json.loads(path.read_text(encoding="utf-8"))
    start_text = args.start_date or str(payload.get("start_date") or "")
    try:
        start = date.fromisoformat(start_text)
    except ValueError as exc:
        raise SystemExit("source-comparison start date is missing or invalid") from exc
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("unsupported source-comparison schema")
    if payload.get("start_date") != start.isoformat():
        errors.append("source-comparison start date mismatch")
    if payload.get("end_date") != (start + timedelta(days=day_count - 1)).isoformat():
        errors.append("source-comparison end date mismatch")
    if payload.get("day_count") != day_count:
        errors.append("source-comparison day count mismatch")
    if payload.get("human_review_required") is not False:
        errors.append("human review must not be a publication dependency")

    days = payload.get("days") or []
    if len(days) != day_count:
        errors.append(f"expected {day_count} source-comparison days, found {len(days)}")
    for offset, item in enumerate(days):
        expected = (start + timedelta(days=offset)).isoformat()
        if item.get("date_iso") != expected:
            errors.append(f"date mismatch at offset {offset}")
        if item.get("decision") not in ALLOWED:
            errors.append(f"{expected}: blocked or unknown automated decision")
        if item.get("human_review_required") is not False:
            errors.append(f"{expected}: human review flag must be false")
        if item.get("errors"):
            errors.append(f"{expected}: automated comparison contains errors")
        if args.require_no_internal_failsafe and item.get("decision") == "PUBLISH_AUTOMATED_INTERNAL_FAILSAFE":
            errors.append(f"{expected}: internal failsafe is forbidden in strict source mode")
        fields = item.get("fields") or {}
        for field_name in ("epistle_reference", "gospel_reference"):
            field = fields.get(field_name) or {}
            if field.get("status") not in FIELD_ALLOWED:
                errors.append(f"{expected}: {field_name} status is not publishable")
            if not str(field.get("normalized_published") or ""):
                errors.append(f"{expected}: {field_name} published reference is empty")
            evidence = field.get("native_text_evidence") or {}
            languages = evidence.get("languages") or {}
            for language in ("ar", "en", "el"):
                item_evidence = languages.get(language) or {}
                if item_evidence.get("ai_translation_used") is not False:
                    errors.append(f"{expected}: {field_name}.{language} has invalid AI flag")
                if not str(item_evidence.get("text_sha256") or ""):
                    errors.append(f"{expected}: {field_name}.{language} text hash missing")

    if errors:
        for error in errors[:100]:
            print(f"SOURCE_COMPARISON_ERROR {error}")
        raise SystemExit(f"SOURCE_COMPARISON_INVALID errors={len(errors)}")
    print(
        f"SOURCE_COMPARISON_VALID start={start.isoformat()} end={(start + timedelta(days=day_count - 1)).isoformat()} "
        f"days={day_count} decision={payload.get('summary', {}).get('decision')}"
    )


if __name__ == "__main__":
    main()
