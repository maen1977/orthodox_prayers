#!/usr/bin/env python3
"""Validate nine-day windows across every year boundary and leap day through 2050."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / "canonical/internal_calendar_2026_2050.json"


def main() -> None:
    payload = json.loads(CALENDAR.read_text(encoding="utf-8"))
    records = {
        str(item.get("date_iso") or item.get("date")): item
        for item in payload.get("days") or []
        if isinstance(item, dict)
    }
    starts = [date(year, 12, 28) for year in range(2026, 2050)]
    starts += [date(year, 2, 25) for year in range(2028, 2051, 4)]
    checked = 0
    for start in starts:
        for offset in range(9):
            target = start + timedelta(days=offset)
            if target > date(2050, 12, 31):
                continue
            key = target.isoformat()
            item = records.get(key)
            if not item:
                raise SystemExit(f"calendar boundary date is missing: {key}")
            if item.get("date_iso") != key:
                raise SystemExit(f"calendar boundary key mismatch: {key}")
            if not item.get("julian_date"):
                raise SystemExit(f"julian date is missing: {key}")
            if not isinstance(item.get("fasting"), dict):
                raise SystemExit(f"fasting record is missing: {key}")
            if not isinstance(item.get("liturgy_service_selection"), dict):
                raise SystemExit(f"liturgy selection is missing: {key}")
            checked += 1
    print(
        f"CALENDAR_BOUNDARIES_2050_OK windows={len(starts)} checked_days={checked} "
        "year_transitions=24 leap_windows=6"
    )


if __name__ == "__main__":
    main()
