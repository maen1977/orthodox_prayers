from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RANGE = re.compile(r"^([1-3]?[A-Z]+)\.(\d+)\.(\d+)-(?:([1-3]?[A-Z]+)\.)?(?:(\d+)\.)?(\d+)$")
LANGUAGES = ("ar", "en", "el")
REQUIRED_SERVICES = {
    "divine_liturgy",
    "vespers",
    "orthros",
    "morning_prayer",
    "evening_prayer",
    "small_compline",
}


def fail(message: str) -> None:
    raise SystemExit(f"LOCAL_DAILY_ENGINE_FAIL {message}")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"json:{path.relative_to(ROOT)}:{exc}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_calendar() -> dict[int, dict[str, dict]]:
    years: dict[int, dict[str, dict]] = {}
    for year in range(2026, 2051):
        path = ROOT / f"app/src/main/assets/data/calendar/calendar_{year}.json"
        if not path.is_file():
            fail(f"calendar_missing:{year}")
        payload = load_json(path)
        days = payload.get("days") or []
        expected = 366 if date(year, 12, 31).timetuple().tm_yday == 366 else 365
        if len(days) != expected:
            fail(f"calendar_day_count:{year}:{len(days)}:{expected}")
        by_date = {item.get("date_iso", item.get("date", "")): item for item in days}
        if len(by_date) != expected:
            fail(f"calendar_duplicate_dates:{year}")
        cursor = date(year, 1, 1)
        for _ in range(expected):
            if cursor.isoformat() not in by_date:
                fail(f"calendar_gap:{cursor}")
            cursor += timedelta(days=1)
        years[year] = by_date
    return years


def verify_scripture_assets() -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    ids: dict[str, set[str]] = {}
    references: dict[str, set[str]] = {}
    omissions: dict[str, set[str]] = {}
    for language in LANGUAGES:
        source = ROOT / f"data/scripture/native/{language}/verses.json"
        asset = ROOT / f"app/src/main/assets/data/scripture/verses_{language}.json"
        manifest_source = ROOT / f"data/scripture/native/{language}/manifest.json"
        manifest_asset = ROOT / f"app/src/main/assets/data/scripture/manifest_{language}.json"
        for path in (source, asset, manifest_source, manifest_asset):
            if not path.is_file():
                fail(f"scripture_asset_missing:{path.relative_to(ROOT)}")
        if sha256(source) != sha256(asset):
            fail(f"scripture_asset_drift:{language}")
        if sha256(manifest_source) != sha256(manifest_asset):
            fail(f"scripture_manifest_drift:{language}")
        verses = load_json(asset)
        verse_ids = {item.get("id", "") for item in verses}
        if "" in verse_ids or len(verse_ids) != len(verses):
            fail(f"scripture_ids_invalid:{language}")
        ids[language] = verse_ids
        manifest = load_json(manifest_asset)
        if manifest.get("coverage_status") != "ALL_EMBEDDED_CALENDAR_REFERENCES_2026_2050":
            fail(f"scripture_calendar_coverage_status:{language}")
        references[language] = {
            str(item).strip().upper()
            for item in manifest.get("supported_canonical_references", [])
            if str(item).strip()
        }
        omissions[language] = {
            str(item).strip().upper()
            for item in manifest.get("allowed_source_verse_omissions", [])
            if str(item).strip()
        }
    return ids, references, omissions


def endpoints_available(reference: str, verse_ids: set[str], allowed_omissions: set[str] | None = None) -> bool:
    allowed_omissions = allowed_omissions or set()
    if not reference:
        return False
    for raw in reference.split(";"):
        match = RANGE.fullmatch(raw.strip())
        if not match:
            return False
        start_book, start_chapter, start_verse, end_book, end_chapter, end_verse = match.groups()
        end_book = end_book or start_book
        end_chapter = end_chapter or start_chapter
        if start_book != end_book:
            return False
        if f"{start_book}.{start_chapter}.{start_verse}" not in verse_ids | allowed_omissions:
            return False
        if f"{end_book}.{end_chapter}.{end_verse}" not in verse_ids | allowed_omissions:
            return False
    return True


def verify_reference_window(years: dict[int, dict[str, dict]], ids: dict[str, set[str]], start: date) -> int:
    complete = 0
    for offset in range(9):
        current = start + timedelta(days=offset)
        day = years.get(current.year, {}).get(current.isoformat())
        if day is None:
            fail(f"window_day_missing:{current}")
        refs = day.get("reading_references") or {}
        if offset == 0 and not {"epistle", "gospel"}.issubset(refs):
            fail(f"anchor_readings_missing:{current}")
        for item in refs.values():
            canonical = item.get("canonical_reference", "")
            if canonical and all(endpoints_available(canonical, ids[language]) for language in LANGUAGES):
                complete += 1
    if complete < 2:
        fail(f"anchor_native_scripture_coverage_too_low:{complete}")
    return complete


def verify_all_calendar_references(
        years: dict[int, dict[str, dict]],
        ids: dict[str, set[str]],
        supported: dict[str, set[str]],
        omissions: dict[str, set[str]],
) -> int:
    calendar_references: set[str] = set()
    for days in years.values():
        for day in days.values():
            for item in (day.get("reading_references") or {}).values():
                canonical = str(item.get("canonical_reference") or "").strip().upper()
                if canonical:
                    calendar_references.add(canonical)
    if not calendar_references:
        fail("calendar_references_empty")
    for language in LANGUAGES:
        missing = calendar_references - supported[language]
        extra = supported[language] - calendar_references
        if missing or extra:
            fail(f"scripture_reference_manifest_drift:{language}:missing={len(missing)}:extra={len(extra)}")
        unavailable = sorted(
            reference for reference in calendar_references
            if not endpoints_available(reference, ids[language], omissions[language])
        )
        if unavailable:
            fail(f"scripture_reference_endpoints:{language}:{unavailable[0]}")
    return len(calendar_references)


def verify_native_services() -> None:
    for language in LANGUAGES:
        payload = load_json(ROOT / f"app/src/main/assets/data/native/library_{language}.json")
        available = {item.get("id") for item in payload.get("services", [])}
        missing = sorted(REQUIRED_SERVICES - available)
        if missing:
            fail(f"native_service_missing:{language}:{','.join(missing)}")


def verify_android_wiring() -> None:
    engine = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/LocalDailyContentEngine.java").read_text(encoding="utf-8")
    repository = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/data/DataRepository.java").read_text(encoding="utf-8")
    coordinator = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/update/UpdateCoordinator.java").read_text(encoding="utf-8")
    worker = (ROOT / "app/src/main/java/com/orthodoxprayers/privateapp/work/DailyUpdateWorker.java").read_text(encoding="utf-8")
    build = (ROOT / "app/build.gradle.kts").read_text(encoding="utf-8")

    required_engine = (
        "WINDOW_DAYS = 9",
        "FIRST_CALENDAR_YEAR = 2026",
        "LAST_CALENDAR_YEAR = 2050",
        "buildCurrentWindow",
        "EXACT_BUNDLED_NATIVE_SCRIPTURE",
        "network_required",
    )
    for token in required_engine:
        if token not in engine:
            fail(f"engine_contract_missing:{token}")
    if "HttpURLConnection" in engine or "new URL" in engine:
        fail("engine_has_network_dependency")
    for token in ("LocalDailyContentEngine", "buildCurrentWindow", 'trustSource = "local_offline_engine"'):
        if token not in repository:
            fail(f"repository_local_wiring_missing:{token}")
    for token in ("LOCAL_REFRESH_HOUR = 0", "LOCAL_REFRESH_MINUTE = 3", "setInitialDelay", "LOCAL_SCHEDULE_WORK"):
        if token not in coordinator:
            fail(f"coordinator_contract_missing:{token}")
    if "NetworkType" in coordinator or "setRequiredNetworkType" in coordinator:
        fail("coordinator_still_requires_network")
    if "Result.retry" in worker:
        fail("worker_retries_deterministic_local_failure")
    if 'versionName = "5.6.3"' not in build or "versionCode = 50603" not in build:
        fail("version_not_5_6_3")


def verify_resources() -> None:
    for folder in ("values", "values-en", "values-el"):
        path = ROOT / f"app/src/main/res/{folder}/ui_strings.xml"
        try:
            tree = ET.parse(path)
        except Exception as exc:
            fail(f"resource_xml:{folder}:{exc}")
        names = {item.attrib.get("name") for item in tree.getroot() if item.tag == "string"}
        for name in (
            "ui_local_daily_update_ready",
            "ui_local_daily_update_current",
            "ui_local_daily_update_unavailable",
            "ui_local_offline_engine_source",
        ):
            if name not in names:
                fail(f"resource_missing:{folder}:{name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-08-06")
    args = parser.parse_args()
    try:
        anchor = date.fromisoformat(args.date)
    except ValueError as exc:
        fail(f"date_invalid:{exc}")
    if not (2026 <= anchor.year <= 2050):
        fail(f"date_outside_embedded_range:{anchor}")

    years = verify_calendar()
    ids, supported, omissions = verify_scripture_assets()
    complete = verify_reference_window(years, ids, anchor)
    reference_count = verify_all_calendar_references(years, ids, supported, omissions)
    verify_native_services()
    verify_android_wiring()
    verify_resources()
    print(
        "LOCAL_DAILY_ENGINE_OK "
        f"date={anchor} window=9 calendar=2026-2050 languages=ar,en,el "
        f"native_window_references={complete} calendar_references={reference_count} "
        "network_required=false version=5.6.3"
    )


if __name__ == "__main__":
    main()
