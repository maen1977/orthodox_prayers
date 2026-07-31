#!/usr/bin/env python3
"""Build a fail-closed moving package of complete liturgical days.

The current daily payload remains the package root for backwards compatibility.
Future payloads stay under ``weekly_days`` for wire compatibility, while schema v2
allows a configurable 9-42 day horizon. The publication workflow rebuilds the
window every day so new days and weeks enter automatically.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from rolling_window_contract import build_metadata, resolve_day_count
from validate_reader_services import compose_overlay, validate_payload

ROOT = Path(__file__).resolve().parents[1]
CALENDAR = ROOT / "data/calendar/today.json"
CACHE_DIR = ROOT / "build/rolling-window/days"
REQUIRED_LANGUAGES = ("ar", "en", "el")
NATIVE_LIBRARY_PATHS = {
    language: ROOT / f"app/src/main/assets/data/native/library_{language}.json"
    for language in REQUIRED_LANGUAGES
}

REQUIRED_SERVICES = (
    "divine_liturgy",
    "vespers",
    "orthros",
    "morning_prayer",
    "evening_prayer",
    "small_compline",
)


def run(*args: str, env: dict[str, str] | None = None, check: bool = True) -> int:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env)
    if check and result.returncode:
        raise SystemExit(result.returncode)
    return result.returncode


def clean_nested_week(payload: dict) -> dict:
    value = copy.deepcopy(payload)
    value.pop("rolling_week", None)
    value.pop("weekly_days", None)
    return value


def require_full_day(payload: dict, expected: date) -> None:
    expected_iso = expected.isoformat()
    if payload.get("date_iso") != expected_iso:
        raise SystemExit(f"rolling week date mismatch: expected={expected_iso} actual={payload.get('date_iso')}")
    publication = payload.get("publication") or {}
    if publication.get("daily_availability") != "FULL":
        raise SystemExit(f"rolling week day is not FULL: {expected_iso}")
    if payload.get("machine_translation_used") is not False:
        raise SystemExit(f"rolling week day enables machine translation: {expected_iso}")
    if payload.get("automatic_diacritization_used") is not False:
        raise SystemExit(f"rolling week day enables automatic diacritization: {expected_iso}")

    services = {item.get("id"): item for item in payload.get("services") or [] if isinstance(item, dict)}
    missing_services = [service_id for service_id in REQUIRED_SERVICES if service_id not in services]
    if missing_services:
        raise SystemExit(f"rolling week services missing for {expected_iso}: {','.join(missing_services)}")

    liturgy = services.get("divine_liturgy") or {}
    selection = payload.get("liturgy_service_selection") or {}
    selected_type = str(selection.get("service_type") or "")
    if not selected_type or not str(selection.get("service_form") or ""):
        raise SystemExit(f"rolling week appointed liturgy metadata missing for {expected_iso}")
    if not isinstance(selection.get("reason"), dict):
        raise SystemExit(f"rolling week appointed liturgy reason missing for {expected_iso}")
    if selection.get("wrong_liturgy_fallback_allowed") is not False:
        raise SystemExit(f"rolling week wrong-liturgy fallback enabled for {expected_iso}")
    if liturgy.get("selected_liturgy_type") != selected_type:
        raise SystemExit(f"rolling week appointed liturgy mismatch for {expected_iso}")

    if selected_type == "typikon_override_required":
        raise SystemExit(f"rolling week dated Typikon override required for {expected_iso}")
    if selected_type == "no_divine_liturgy":
        if liturgy.get("publication_status") != "NO_DIVINE_LITURGY_APPOINTED":
            raise SystemExit(f"rolling week no-liturgy status invalid for {expected_iso}")
    else:
        if selection.get("displayable") is not True:
            raise SystemExit(f"rolling week complete native appointed rite missing for {expected_iso}: {selected_type}")
        if liturgy.get("full_service_complete") is not True:
            raise SystemExit(f"rolling week appointed rite is not complete from beginning to end: {expected_iso}")
        if liturgy.get("publication_status") != "DISPLAYABLE_COMPLETE_NATIVE_SERVICE_FROM_BEGINNING_TO_END":
            raise SystemExit(f"rolling week appointed rite publication status invalid for {expected_iso}")
        for language in REQUIRED_LANGUAGES:
            library = validate_payload(NATIVE_LIBRARY_PATHS[language])
            composed = compose_overlay(
                liturgy,
                library,
                Path(f"rolling-window-{expected_iso}-{language}.json"),
            )
            segments = composed.get("segments") or []
            if len(segments) < 180:
                raise SystemExit(
                    f"rolling window divine_liturgy.{language} too short for {expected_iso}: "
                    f"{len(segments)} segments"
                )
            for index, segment in enumerate(segments):
                content_key = "title" if segment.get("type") == "section" else "text"
                localized = segment.get(content_key) if isinstance(segment, dict) else None
                if not isinstance(localized, dict) or not str(localized.get(language) or "").strip():
                    raise SystemExit(
                        f"rolling window divine_liturgy.{language}[{index}] is empty for {expected_iso}"
                    )

    readings = payload.get("readings") or []
    by_kind = {item.get("kind"): item for item in readings if isinstance(item, dict)}
    for kind in ("epistle", "gospel"):
        reading = by_kind.get(kind)
        if not isinstance(reading, dict):
            raise SystemExit(f"rolling week {kind} missing for {expected_iso}")
        body = reading.get("body") or {}
        verification = reading.get("native_source_verification") or {}
        for language in REQUIRED_LANGUAGES:
            text = str(body.get(language) or "").strip()
            if not text:
                raise SystemExit(f"rolling week {kind}.{language} text missing for {expected_iso}")
            evidence = verification.get(language) or {}
            if evidence.get("status") not in {
                "VERIFIED_EXACT_NATIVE_SOURCE",
                "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS",
                "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
            }:
                raise SystemExit(f"rolling week {kind}.{language} is unverified for {expected_iso}")
            if evidence.get("ai_translation_used") is not False:
                raise SystemExit(f"rolling week {kind}.{language} AI flag invalid for {expected_iso}")



def generator_fingerprint() -> str:
    """Fingerprint every local input that can change a generated daily payload."""
    paths = [
        ROOT / "scripts/update_liturgical_data.py",
        ROOT / "scripts/fill_daily_from_native_corpora.py",
        ROOT / "scripts/rebuild_daily_services.py",
        ROOT / "scripts/enforce_native_daily_lanes.py",
        ROOT / "canonical/jordan_2026_h2_lectionary.json",
        ROOT / "canonical/source_connectors.json",
        ROOT / "app/src/main/assets/data/library.json",
        ROOT / "app/src/main/assets/data/native/library_ar.json",
        ROOT / "app/src/main/assets/data/native/library_en.json",
        ROOT / "app/src/main/assets/data/native/library_el.json",
    ]
    for language in REQUIRED_LANGUAGES:
        paths.extend([
            ROOT / f"data/scripture/native/{language}/manifest.json",
            ROOT / f"data/scripture/native/{language}/verses.json",
        ])
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def cached_day_path(day: date) -> Path:
    return CACHE_DIR / f"{day.isoformat()}.json"


def load_cached_day(day: date, fingerprint: str) -> dict | None:
    path = cached_day_path(day)
    if not path.is_file():
        return None
    try:
        envelope = json.loads(path.read_text(encoding="utf-8"))
        if envelope.get("schema_version") != 1 or envelope.get("generator_fingerprint") != fingerprint:
            return None
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            return None
        require_full_day(payload, day)
        return clean_nested_week(payload)
    except (Exception, SystemExit):
        return None


def save_cached_day(day: date, fingerprint: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cached_day_path(day)
    temporary = path.with_suffix(".tmp")
    envelope = {
        "schema_version": 1,
        "date_iso": day.isoformat(),
        "generator_fingerprint": fingerprint,
        "payload": clean_nested_week(payload),
    }
    temporary.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)

def generate_future_day(day: date, offline: bool) -> dict:
    date_iso = day.isoformat()
    env = os.environ.copy()
    env["ORTHODOX_DATE"] = date_iso

    # External source health and the church directory describe the publication
    # run, not a future civil date. update.py collects them exactly once for the
    # anchor day. Reusing that verified snapshot for every member avoids 20-41
    # repeated network sweeps and keeps a 21-day GitHub Actions run comfortably
    # inside its timeout while preserving identical provenance on the package.
    # The ``offline`` parameter remains part of the cache/build API for backward
    # compatibility; future day composition itself is deterministic and local.
    _ = offline
    run("scripts/update_liturgical_data.py", env=env)
    run("scripts/attach_source_intelligence.py", "data/calendar/today.json", f"data/calendar/{date_iso}.json", env=env)
    integrity = run("scripts/orthodox_integrity.py", "--apply", env=env, check=False)
    mode = "full" if integrity == 0 else "partial"
    run("scripts/fill_daily_from_native_corpora.py", "data/calendar/today.json", f"data/calendar/{date_iso}.json", env=env)
    run("scripts/enforce_native_daily_lanes.py", "data/calendar/today.json", f"data/calendar/{date_iso}.json", env=env)
    run("scripts/rebuild_daily_services.py", "data/calendar/today.json", f"data/calendar/{date_iso}.json", env=env)
    run("scripts/enforce_native_daily_lanes.py", "data/calendar/today.json", f"data/calendar/{date_iso}.json", env=env)
    run("scripts/attach_source_intelligence.py", "data/calendar/today.json", f"data/calendar/{date_iso}.json", env=env)
    run("scripts/validate_daily_native_content.py", "data/calendar/today.json", "--require-complete", env=env)
    run("scripts/mark_partial_daily.py", "--date", date_iso, "--mode", mode, env=env)
    run(
        "scripts/validate_jordan_liturgical_contract.py",
        "data/calendar/today.json",
        "--expected-date",
        date_iso,
        "--require-jordan-authority",
        "--require-complete-liturgy",
        env=env,
    )
    run("scripts/validate_liturgical_schedule.py", "data/calendar/today.json", env=env)
    run("scripts/validate_fasting_guidance.py", "data/calendar/today.json", env=env)
    run("scripts/validate_daily_ui_localizations.py", "data/calendar/today.json", env=env)
    run("scripts/validate_scripture_translations.py", "data/calendar/today.json", env=env)
    run("scripts/quality_check.py", "data/calendar/today.json", "--skip-sync-check", env=env)

    payload = json.loads(CALENDAR.read_text(encoding="utf-8"))
    require_full_day(payload, day)
    return clean_nested_week(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--days", type=int, default=None)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    try:
        day_count = resolve_day_count(args.days)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    start = date.fromisoformat(args.start_date)
    if not CALENDAR.is_file():
        raise SystemExit("current validated daily payload is missing")

    anchor = clean_nested_week(json.loads(CALENDAR.read_text(encoding="utf-8")))
    require_full_day(anchor, start)

    # Future generation updates these shared snapshots. Preserve the anchor-day
    # copies because publication metadata should describe the package start day.
    mutable_snapshots = [
        ROOT / "data/source_health.json",
        ROOT / "data/churches.json",
        ROOT / "app/src/main/assets/data/source_health.json",
        ROOT / "app/src/main/assets/data/churches.json",
    ]
    saved = {path: path.read_bytes() for path in mutable_snapshots if path.is_file()}

    dated_anchor = ROOT / f"data/calendar/{start.isoformat()}.json"
    calendar_originals: dict[Path, bytes | None] = {
        CALENDAR: CALENDAR.read_bytes() if CALENDAR.is_file() else None,
        dated_anchor: dated_anchor.read_bytes() if dated_anchor.is_file() else None,
    }
    today_temp = CALENDAR.with_name(f".{CALENDAR.name}.rolling-window.tmp")
    dated_temp = dated_anchor.with_name(f".{dated_anchor.name}.rolling-window.tmp")

    def restore_calendar_inputs() -> None:
        for path, content in calendar_originals.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
        today_temp.unlink(missing_ok=True)
        dated_temp.unlink(missing_ok=True)

    fingerprint = generator_fingerprint()
    future_days: list[dict] = []
    try:
        for offset in range(1, day_count):
            day = start + timedelta(days=offset)
            payload = load_cached_day(day, fingerprint)
            if payload is None:
                payload = generate_future_day(day, args.offline)
                save_cached_day(day, fingerprint, payload)
                print(f"ROLLING_WEEK_DAY_CACHED date={day.isoformat()}", flush=True)
            else:
                print(f"ROLLING_WEEK_DAY_REUSED date={day.isoformat()}", flush=True)
            future_days.append(payload)

        end = start + timedelta(days=day_count - 1)
        generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        anchor["rolling_week"] = build_metadata(start, day_count, generated_at)
        anchor["rolling_week"]["language_lanes_required"] = list(REQUIRED_LANGUAGES)
        anchor["rolling_week"]["required_service_ids"] = list(REQUIRED_SERVICES)
        anchor["weekly_days"] = future_days

        output = json.dumps(anchor, ensure_ascii=False, indent=2) + "\n"
        today_temp.write_text(output, encoding="utf-8")
        dated_temp.write_text(output, encoding="utf-8")
        today_relative = today_temp.relative_to(ROOT).as_posix()
        run("scripts/validate_rolling_week.py", today_relative, "--expected-start", start.isoformat())
        run("scripts/validate_full_liturgy_services.py", today_relative)

        # Commit both files only after every day and every final validator passes.
        # os.replace/Path.replace is atomic on the repository filesystem.
        today_temp.replace(CALENDAR)
        dated_temp.replace(dated_anchor)
        print(
            f"ROLLING_WEEK_BUILT start={start.isoformat()} end={end.isoformat()} "
            f"days={day_count} bytes={len(output.encode('utf-8'))}"
        )
    except BaseException:
        restore_calendar_inputs()
        raise
    finally:
        for path, content in saved.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


if __name__ == "__main__":
    main()
