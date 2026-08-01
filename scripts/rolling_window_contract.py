#!/usr/bin/env python3
"""Shared contract for the signed moving liturgical-data horizon.

Schema v1 is the original fixed nine-day package. Schema v2 keeps the same
``weekly_days`` member field for wire compatibility but allows a configurable,
validated horizon. New publishers should emit schema v2; readers continue to
accept schema v1 during the migration.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

LEGACY_SCHEMA_VERSION = 1
SCHEMA_VERSION = 2
LEGACY_POLICY = "NINE_CONSECUTIVE_DAYS_STARTING_TODAY"
POLICY = "ROLLING_FUTURE_WINDOW"
DEFAULT_DAY_COUNT = 9
MIN_DAY_COUNT = 9
MAX_DAY_COUNT = 9
TIMEZONE = "Asia/Amman"
MEMBERS_FIELD = "weekly_days"


def resolve_day_count(value: int | str | None = None) -> int:
    raw = value
    if raw is None:
        raw = os.getenv("ORTHODOX_ROLLING_WINDOW_DAYS", str(DEFAULT_DAY_COUNT))
    try:
        count = int(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"rolling window day count is not an integer: {raw!r}") from error
    if not MIN_DAY_COUNT <= count <= MAX_DAY_COUNT:
        raise ValueError(
            f"rolling window day count must be between {MIN_DAY_COUNT} and {MAX_DAY_COUNT}: {count}"
        )
    return count


def is_supported_metadata(metadata: Any) -> bool:
    if not isinstance(metadata, dict):
        return False
    schema = metadata.get("schema_version")
    policy = metadata.get("policy")
    if schema == LEGACY_SCHEMA_VERSION and policy == LEGACY_POLICY:
        return metadata.get("day_count") == 9
    if schema == SCHEMA_VERSION and policy == POLICY:
        try:
            resolve_day_count(metadata.get("day_count"))
        except ValueError:
            return False
        return True
    return False


def metadata_errors(metadata: Any, start: date, member_count: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(metadata, dict):
        return ["rolling_window metadata is missing"]
    if not is_supported_metadata(metadata):
        errors.append("rolling_window schema/policy is unsupported")
        return errors

    count = int(metadata.get("day_count") or 0)
    expected_end = start + timedelta(days=count - 1)
    if metadata.get("start_date") != start.isoformat():
        errors.append("rolling_window.start_date mismatch")
    if metadata.get("end_date") != expected_end.isoformat():
        errors.append("rolling_window.end_date mismatch")
    if metadata.get("future_day_count", count - 1) != count - 1:
        errors.append("rolling_window.future_day_count mismatch")
    if metadata.get("end_offset_days", count - 1) != count - 1:
        errors.append("rolling_window.end_offset_days mismatch")
    if member_count != count - 1:
        errors.append(
            f"rolling_window members mismatch: expected={count - 1} actual={member_count}"
        )
    if metadata.get("status") != "COMPLETE" or metadata.get("fail_closed") is not True:
        errors.append("rolling_window must be COMPLETE and fail_closed")
    if metadata.get("timezone", TIMEZONE) != TIMEZONE:
        errors.append(f"rolling_window timezone must be {TIMEZONE}")
    return errors


def build_metadata(start: date, day_count: int, generated_at_utc: str) -> dict[str, Any]:
    count = resolve_day_count(day_count)
    end = start + timedelta(days=count - 1)
    return {
        "schema_version": SCHEMA_VERSION,
        "policy": POLICY,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "day_count": count,
        "future_day_count": count - 1,
        "end_offset_days": count - 1,
        "timezone": TIMEZONE,
        "status": "COMPLETE",
        "fail_closed": True,
        "members_field": MEMBERS_FIELD,
        "refresh_policy": "DAILY_REBUILD_SLIDING_HORIZON",
        "refresh_times_local": ["04:23", "16:43"],
        "generated_at_utc": generated_at_utc,
    }
