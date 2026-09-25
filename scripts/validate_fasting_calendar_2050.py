#!/usr/bin/env python3
"""Semantic audit for the embedded Jerusalem/Jordan old-calendar fasting horizon."""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = date(2026, 1, 1)
END = date(2050, 12, 31)
LANGUAGES = ("ar", "en", "el")
FOOD_KEYS = ("meat", "dairy", "eggs", "fish", "wine", "oil")

sys.path.insert(0, str(ROOT))
from scripts import update_liturgical_data as update  # noqa: E402


def fail(message: str) -> None:
    raise SystemExit(f"FASTING_CALENDAR_2050_FAIL {message}")


def load_year(year: int) -> dict:
    path = ROOT / "app/src/main/assets/data/calendar" / f"calendar_{year}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"asset:{year}:{exc}")
    if payload.get("calendar") != "jerusalem_jordan_julian_old_calendar":
        fail(f"calendar_identity:{year}:{payload.get('calendar')!r}")
    profiles = payload.get("fasting_profiles")
    if not isinstance(profiles, dict) or not profiles:
        fail(f"fasting_profiles_missing:{year}")
    days = payload.get("days")
    if not isinstance(days, list):
        fail(f"days_missing:{year}")
    expected = 366 if date(year, 12, 31).timetuple().tm_yday == 366 else 365
    if len(days) != expected:
        fail(f"day_count:{year}:{len(days)}:{expected}")
    return payload


def resolve_fasting(item: dict, profiles: dict, year: int) -> dict:
    raw = item.get("fasting")
    if not isinstance(raw, dict):
        fail(f"fasting_missing:{year}:{item.get('date_iso')}")
    profile_id = str(raw.get("profile_id") or "").strip()
    if not profile_id or profile_id not in profiles:
        fail(f"profile_unresolved:{year}:{item.get('date_iso')}:{profile_id}")
    result = dict(profiles[profile_id])
    result.update({key: value for key, value in raw.items() if key != "profile_id"})
    return result


def assert_abstinence_contract(profile: dict, key: str, expected_rule: str | None) -> bool:
    abstinence = profile.get("abstinence")
    if not isinstance(abstinence, dict) or not abstinence.get("applies", False):
        return False
    rule = (profile.get("verification") or {}).get("rule")
    allowed_rules = {
        "great_friday_optional_total_abstinence",
        "first_week_lent_optional_total_abstinence",
    }
    if rule not in allowed_rules or rule != expected_rule:
        fail(f"unexpected_abstinence_rule:{key}:{rule}:{expected_rule}")
    if abstinence.get("optional") is not True:
        fail(f"abstinence_not_optional:{key}")
    if abstinence.get("kind") != "until_service_end":
        fail(f"abstinence_kind:{key}:{abstinence.get('kind')}")
    if abstinence.get("start_time") or abstinence.get("end_time"):
        fail(f"unverified_clock_time:{key}")
    verification = abstinence.get("verification") or {}
    if verification.get("status") != "DOCUMENTED_OPTIONAL":
        fail(f"abstinence_status:{key}:{verification.get('status')}")
    if not str(verification.get("source") or "").startswith("https://"):
        fail(f"abstinence_source_missing:{key}")
    for language in LANGUAGES:
        if not str((abstinence.get("end_condition") or {}).get(language) or "").strip():
            fail(f"abstinence_end_condition_missing:{key}:{language}")
        if not str((abstinence.get("detail") or {}).get(language) or "").strip():
            fail(f"abstinence_detail_missing:{key}:{language}")
    return True


def assert_food_contract(profile: dict, key: str) -> None:
    code = profile.get("code")
    if code not in update.FASTING_LEVELS:
        fail(f"unknown_code:{key}:{code}")
    expected_allowed = {
        food: food in update.FASTING_LEVELS[code]["allowed"] for food in FOOD_KEYS
    }
    actual_allowed = profile.get("allowed")
    if not isinstance(actual_allowed, dict):
        actual_allowed = {str(item.get("key")): bool(item.get("allowed")) for item in profile.get("items") or []}
    if actual_allowed != expected_allowed:
        fail(f"allowed_mismatch:{key}:{code}:{actual_allowed}")
    if bool(profile.get("is_fast")) != (code != "fast_free"):
        fail(f"is_fast_mismatch:{key}:{code}")
    items = profile.get("items")
    if not isinstance(items, list) or {item.get("key") for item in items} != set(FOOD_KEYS):
        fail(f"items_mismatch:{key}")
    for language in LANGUAGES:
        if not str((profile.get("title") or {}).get(language) or "").strip():
            fail(f"title_missing:{key}:{language}")
        if not str((profile.get("detail") or {}).get(language) or "").strip():
            fail(f"detail_missing:{key}:{language}")


def actual_allowed_for_asset(profile: dict) -> dict:
    allowed = profile.get("allowed")
    if isinstance(allowed, dict):
        return allowed
    return {str(item.get("key")): bool(item.get("allowed")) for item in profile.get("items") or []}


def assert_weekly_and_season_invariants(day: date, profile: dict, key: str) -> None:
    code = profile["code"]
    rule = (profile.get("verification") or {}).get("rule")
    pascha = update.orthodox_pascha_gregorian(day.year)
    old_month, old_day = update._old_calendar_key(day)
    apostles_start = pascha + timedelta(days=57)
    apostles_end = update.julian_to_gregorian_date(day.year, 6, 28)

    # Fast-free periods are explicit and must not leak a weekday fast.
    if pascha <= day <= pascha + timedelta(days=6):
        if code != "fast_free":
            fail(f"bright_week:{key}:{code}")
    if pascha + timedelta(days=50) <= day <= pascha + timedelta(days=56):
        if code != "fast_free":
            fail(f"pentecost_week:{key}:{code}")
    if (old_month == 12 and old_day >= 25) or (old_month == 1 and old_day <= 4):
        if code != "fast_free":
            fail(f"nativity_to_theophany:{key}:{code}")

    # Great Lent and Holy Week boundaries and weekend allowances.
    lent_start = pascha - timedelta(days=48)
    holy_saturday = pascha - timedelta(days=1)
    palm_sunday = pascha - timedelta(days=7)
    if lent_start <= day <= holy_saturday:
        if old_month == 3 and old_day == 25:
            if day in {pascha - timedelta(days=2), holy_saturday}:
                if code != "wine_only":
                    fail(f"annunciation_great_friday_or_saturday:{key}:{code}")
            elif pascha - timedelta(days=6) <= day <= pascha - timedelta(days=3):
                if code != "wine_oil":
                    fail(f"annunciation_first_four_holy_week_days:{key}:{code}")
            elif code != "fish_allowed":
                fail(f"great_lent_annunciation:{key}:{code}")
        elif day == palm_sunday:
            if code != "fish_allowed":
                fail(f"great_lent_palm_sunday:{key}:{code}")
        elif day == pascha - timedelta(days=2):
            if code != "strict":
                fail(f"great_friday:{key}:{code}")
        elif day.weekday() in (5, 6) and day != holy_saturday:
            if code != "wine_oil":
                fail(f"great_lent_weekend:{key}:{code}")
        elif code != "strict":
            fail(f"great_lent_weekday:{key}:{code}")

    # Apostles' Fast uses Paschal start and the old-calendar June 28 eve.
    if apostles_start <= day <= apostles_end:
        if old_month == 6 and old_day == 24 or day.weekday() in (5, 6):
            if code != "fish_allowed":
                fail(f"apostles_fish:{key}:{code}")
        elif day.weekday() in (1, 3):
            if code != "wine_oil":
                fail(f"apostles_tue_thu:{key}:{code}")
        elif code != "strict":
            fail(f"apostles_mon_wed_fri:{key}:{code}")

    # Dormition Fast is exactly August 1–14. The August 15 feast is outside
    # those fourteen days: it is fish-relaxed on Wednesday/Friday and fast-free
    # on other weekdays/weekend days.
    if old_month == 8 and 1 <= old_day <= 15:
        if old_day == 6:
            if code != "fish_allowed":
                fail(f"dormition_transfiguration:{key}:{code}")
        elif old_day == 15:
            expected = "fish_allowed" if day.weekday() in (2, 4) else "fast_free"
            expected_rule = "dormition_feast_fish" if expected == "fish_allowed" else "dormition_feast_fast_free"
            if code != expected or rule != expected_rule:
                fail(f"dormition_feast_rule:{key}:{code}:{rule}:expected={expected}:{expected_rule}")
        elif old_day <= 14 and day.weekday() in (5, 6):
            if code != "wine_oil":
                fail(f"dormition_weekend:{key}:{code}")
        elif old_day <= 14 and code != "strict":
            fail(f"dormition_weekday:{key}:{code}")

    # Nativity Fast and its fixed feast exception.
    if (old_month == 11 and old_day >= 15) or (old_month == 12 and old_day <= 24):
        if old_month == 11 and old_day == 21:
            if code != "fish_allowed":
                fail(f"nativity_entry:{key}:{code}")
        elif day.weekday() in (5, 6):
            expected = "wine_oil" if old_month == 12 and 20 <= old_day <= 24 else "fish_allowed"
            if code != expected:
                fail(f"nativity_weekend:{key}:{code}:{expected}")
        elif day.weekday() in (1, 3):
            if code != "wine_oil":
                fail(f"nativity_tue_thu:{key}:{code}")
        elif code != "strict":
            fail(f"nativity_mon_wed_fri:{key}:{code}")

    # Fixed one-day strict fast days remain strict even when they are weekdays.
    if (old_month, old_day) in {(1, 5), (8, 29), (9, 14)} and code != "strict":
        fail(f"single_day_strict:{key}:{code}")

    # The regular Wednesday/Friday rule must not be erased except by an explicit
    # fast-free season or a documented feast relaxation handled above.
    if day.weekday() in (2, 4) and code == "fast_free" and rule == "ordinary_fast_free":
        fail(f"weekday_fast_erased:{key}")


def main() -> None:
    if update.gregorian_to_julian_date(START) != (2025, 12, 19):
        fail("calendar_conversion_anchor")
    all_days = 0
    checked_fixed = 0
    abstinence_days = 0
    for year in range(2026, 2051):
        payload = load_year(year)
        profiles = payload["fasting_profiles"]
        by_date = {item.get("date_iso"): item for item in payload["days"]}
        for item in payload["days"]:
            iso = item.get("date_iso")
            try:
                day = date.fromisoformat(str(iso))
            except ValueError:
                fail(f"date_invalid:{year}:{iso}")
            if day.year != year:
                fail(f"year_mismatch:{year}:{iso}")
            expected = update.day_info(day)["fasting"]
            actual = resolve_fasting(item, profiles, year)
            key = f"{year}-{iso}"
            assert_food_contract(actual, key)
            pascha_for_abstinence = update.orthodox_pascha_gregorian(day.year)
            old_month, old_day = update._old_calendar_key(day)
            offset = (day - pascha_for_abstinence).days
            if offset in {-48, -47, -45}:
                expected_abstinence_rule = "first_week_lent_optional_total_abstinence"
            elif offset == -2 and (old_month, old_day) != (3, 25):
                expected_abstinence_rule = "great_friday_optional_total_abstinence"
            else:
                expected_abstinence_rule = None
            abstinence_found = assert_abstinence_contract(actual, key, expected_abstinence_rule)
            if abstinence_found != (expected_abstinence_rule is not None):
                fail(f"abstinence_day_mismatch:{key}:{abstinence_found}:{expected_abstinence_rule}")
            for field in ("code", "is_fast", "allowed"):
                if field == "allowed":
                    actual_value = actual_allowed_for_asset(actual)
                    expected_value = expected.get(field)
                else:
                    actual_value = actual.get(field)
                    expected_value = expected.get(field)
                if actual_value != expected_value:
                    fail(f"generator_asset_drift:{key}:{field}:{actual_value}:{expected_value}")
            expected_rule = (expected.get("verification") or {}).get("rule")
            actual_rule = (actual.get("verification") or {}).get("rule")
            if actual_rule != expected_rule:
                fail(f"generator_rule_drift:{key}:{actual_rule}:{expected_rule}")
            assert_weekly_and_season_invariants(day, actual, key)
            if abstinence_found:
                abstinence_days += 1
            all_days += 1

        # Every fixed date in the old calendar is checked in every year.
        for month, day_number in ((1, 1), (1, 6), (2, 2), (3, 25), (6, 24), (6, 29), (8, 6), (8, 15), (9, 8), (9, 14), (11, 21), (12, 25)):
            civil = update.julian_to_gregorian_date(year, month, day_number)
            if civil.year != year:
                continue
            item = by_date.get(civil.isoformat())
            if item is None:
                fail(f"fixed_day_missing:{civil}")
            actual = resolve_fasting(item, profiles, year)
            if (month, day_number) == (8, 15):
                expected_code = "fish_allowed" if civil.weekday() in (2, 4) else "fast_free"
                expected_rule = "dormition_feast_fish" if expected_code == "fish_allowed" else "dormition_feast_fast_free"
                actual_rule = (actual.get("verification") or {}).get("rule")
                if actual["code"] != expected_code or actual_rule != expected_rule:
                    fail(f"dormition_feast_rule:{civil}:{actual['code']}:{actual_rule}:expected={expected_code}:{expected_rule}")
            if (month, day_number) in {(8, 6), (11, 21)} and actual["code"] != "fish_allowed":
                fail(f"fixed_fish_feast_not_relaxed:{civil}:{actual['code']}")
            checked_fixed += 1

    print(
        "FASTING_CALENDAR_2050_OK "
        f"days={all_days} years=25 fixed_feast_dates={checked_fixed} abstinence_days={abstinence_days} "
        "calendar=jerusalem_jordan_julian_old_calendar "
        "dormition_fast=14_days feast=fish_on_wed_fri_else_fast_free weekday_overrides=checked seasons=checked"
    )


if __name__ == "__main__":
    main()
