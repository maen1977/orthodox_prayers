#!/usr/bin/env python3
"""Validate the compact offline Jerusalem/Jordan calendar through 2050."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "canonical" / "internal_calendar_2026_2050.json"
INDEX = ROOT / "app" / "src" / "main" / "assets" / "data" / "calendar" / "calendar_index.json"
START = date(2026, 1, 1)
END = date(2050, 12, 31)
EXPECTED_DAYS = (END - START).days + 1


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    errors: list[str] = []
    if not CANONICAL.is_file():
        raise SystemExit(f"missing {CANONICAL.relative_to(ROOT)}")
    if not INDEX.is_file():
        raise SystemExit(f"missing {INDEX.relative_to(ROOT)}")
    canonical = load(CANONICAL)
    index = load(INDEX)
    civil = canonical.get("civil_range") or {}
    if civil.get("start") != START.isoformat() or civil.get("end") != END.isoformat():
        errors.append("canonical civil range must be 2026-01-01 through 2050-12-31")
    if civil.get("day_count") != EXPECTED_DAYS:
        errors.append(f"canonical day_count must be {EXPECTED_DAYS}")
    if canonical.get("visible_window_days") != 9:
        errors.append("visible_window_days must be exactly 9")
    schedule = canonical.get("update_schedule") or {}
    if schedule.get("timezone") != "Asia/Amman" or schedule.get("times") != ["04:23", "16:43"]:
        errors.append("update schedule must be Asia/Amman at 04:23 and 16:43")
    days = canonical.get("days") or []
    if len(days) != EXPECTED_DAYS:
        errors.append(f"canonical days length must be {EXPECTED_DAYS}")
    else:
        expected = START
        for item in days:
            iso = str(item.get("date_iso") or "")
            if iso != expected.isoformat():
                errors.append(f"non-consecutive date at {iso}; expected {expected.isoformat()}")
                break
            if not isinstance(item.get("feast"), dict) or not str((item.get("feast") or {}).get("ar") or "").strip():
                errors.append(f"missing Arabic fallback occasion for {iso}")
                break
            fasting = item.get("fasting") or {}
            if not fasting.get("code") or not isinstance(fasting.get("title"), dict):
                errors.append(f"missing fasting baseline for {iso}")
                break
            selection = item.get("liturgy_service_selection") or {}
            if not selection.get("service_type") or selection.get("wrong_liturgy_fallback_allowed") is not False:
                errors.append(f"invalid service selection for {iso}")
                break
            expected += timedelta(days=1)
    years = index.get("years") or {}
    if set(years) != {str(year) for year in range(2026, 2051)}:
        errors.append("asset index must contain every year from 2026 through 2050")
    asset_total = 0
    asset_days = 0
    for year in range(2026, 2051):
        meta = years.get(str(year)) or {}
        asset_name = str(meta.get("asset") or "")
        expected_name = f"data/calendar/calendar_{year}.json"
        if asset_name != expected_name:
            errors.append(f"year {year} asset path mismatch")
            continue
        path = ROOT / "app" / "src" / "main" / "assets" / asset_name
        if not path.is_file():
            errors.append(f"missing year asset {asset_name}")
            continue
        payload = load(path)
        year_days = payload.get("days") or []
        expected_count = 366 if date(year, 12, 31).timetuple().tm_yday == 366 else 365
        if len(year_days) != expected_count or meta.get("day_count") != expected_count:
            errors.append(f"year {year} must contain {expected_count} days")
        if year_days and (year_days[0].get("date_iso") != f"{year}-01-01" or year_days[-1].get("date_iso") != f"{year}-12-31"):
            errors.append(f"year {year} boundary mismatch")
        asset_total += path.stat().st_size
        asset_days += len(year_days)
    if asset_days != EXPECTED_DAYS:
        errors.append("year assets do not sum to canonical day count")
    expected_pascha = {
        "2026-04-12": "الفصح",
        "2027-05-02": "الفصح",
        "2050-04-17": "الفصح",
    }
    by_date = {str(item.get("date_iso")): item for item in days}
    for iso, token in expected_pascha.items():
        feast = str(((by_date.get(iso) or {}).get("feast") or {}).get("ar") or "")
        if token not in feast:
            errors.append(f"Pascha marker missing for {iso}")
    if errors:
        for error in errors:
            print(f"INTERNAL_CALENDAR_2050_ERROR {error}")
        raise SystemExit(1)
    print(
        "INTERNAL_CALENDAR_2050_OK "
        f"start={START.isoformat()} end={END.isoformat()} days={EXPECTED_DAYS} "
        f"years=25 asset_bytes={asset_total}"
    )


if __name__ == "__main__":
    main()
