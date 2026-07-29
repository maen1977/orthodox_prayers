#!/usr/bin/env python3
"""Validate the signed-package shape for today plus seven complete days."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path

from validate_reader_services import compose_overlay, validate_payload

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "el")
NATIVE_LIBRARY_PATHS = {
    language: ROOT / f"app/src/main/assets/data/native/library_{language}.json"
    for language in LANGUAGES
}
REQUIRED_SERVICES = {
    "divine_liturgy",
    "vespers",
    "orthros",
    "morning_prayer",
    "evening_prayer",
    "small_compline",
}
PLACEHOLDER_PATTERNS = (
    re.compile(r"يقال\s+(?:النص|اللحن|الترنيمة|القنداق|الطروبارية)\s+(?:المعين|المناسبة)", re.I),
    re.compile(r"تضاف\s+هنا\s+طروباريات", re.I),
    re.compile(r"(?:read|say|chant)\s+the\s+(?:appointed|proper|appropriate)\s+(?:text|hymn|troparion|kontakion)", re.I),
    re.compile(r"(?:troparia|hymns?)\s+are\s+inserted\s+here", re.I),
    re.compile(r"(?:λέγεται|ψάλλεται)\s+τὸ\s+(?:ὡρισμένο|πρέπον)", re.I),
    re.compile(r"Ἐνταῦθα\s+τίθενται", re.I),
)

UNREVIEWED_PROPER_PATTERNS = (
    re.compile(r"تذكار اليوم بحسب التقويم الكنسي القديم", re.I),
    re.compile(
        r"(?:Today[’']s|Daily) commemoration according to the old "
        r"(?:church|ecclesiastical) calendar",
        re.I,
    ),
    re.compile(
        r"(?:Ἡ σημερινὴ μνήμη|Μνήμη τῆς ἡμέρας) κατὰ τὸ παλαιὸ "
        r"ἐκκλησιαστικὸ ἡμερολόγιο",
        re.I,
    ),
)


def localized_text(value: object, language: str) -> str:
    if isinstance(value, dict):
        return str(value.get(language) or "").strip()
    return str(value or "").strip()


def check_no_placeholders(value: object, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            check_no_placeholders(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_no_placeholders(child, f"{path}[{index}]", errors)
    elif isinstance(value, str):
        text = value.strip()
        for pattern in PLACEHOLDER_PATTERNS:
            if pattern.search(text):
                errors.append(f"placeholder text at {path}: {text[:100]}")
                break



def check_reviewed_propers(value: object, path: str, errors: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            check_reviewed_propers(child, f"{path}.{key}", errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            check_reviewed_propers(child, f"{path}[{index}]", errors)
    elif isinstance(value, str):
        text = value.strip()
        for pattern in UNREVIEWED_PROPER_PATTERNS:
            if pattern.search(text):
                errors.append(f"unreviewed daily proper at {path}: {text[:100]}")
                break

def validate_composed_liturgy(
    liturgy: dict,
    iso: str,
    languages: tuple[str, ...],
    native_libraries: dict[str, dict[str, dict]],
    errors: list[str],
) -> None:
    if not liturgy:
        errors.append(f"{iso}: Divine Liturgy service is missing")
        return
    for language in languages:
        source = Path(f"rolling-week-{iso}-{language}.json")
        try:
            composed = compose_overlay(liturgy, native_libraries[language], source)
        except SystemExit as error:
            errors.append(f"{iso}: divine_liturgy.{language} composition failed: {error}")
            continue
        segments = composed.get("segments") or []
        if len(segments) < 180:
            errors.append(
                f"{iso}: divine_liturgy.{language} is too short after composition "
                f"({len(segments)} segments)"
            )
            continue
        for index, segment in enumerate(segments):
            if not isinstance(segment, dict):
                errors.append(f"{iso}: divine_liturgy.{language}[{index}] is invalid")
                continue
            content_key = "title" if segment.get("type") == "section" else "text"
            localized = segment.get(content_key)
            if not isinstance(localized, dict) or not str(localized.get(language) or "").strip():
                errors.append(
                    f"{iso}: divine_liturgy.{language}[{index}].{content_key} is empty"
                )
        check_no_placeholders(
            composed,
            f"days[{iso}].composed_divine_liturgy.{language}",
            errors,
        )


def validate_day(
    payload: dict,
    expected: date,
    languages: tuple[str, ...],
    native_libraries: dict[str, dict[str, dict]],
    errors: list[str],
) -> None:
    iso = expected.isoformat()
    if payload.get("date_iso") != iso:
        errors.append(f"date mismatch expected={iso} actual={payload.get('date_iso')}")
        return
    publication = payload.get("publication") or {}
    if publication.get("daily_availability") != "FULL":
        errors.append(f"{iso}: daily_availability is not FULL")
    if payload.get("machine_translation_used") is not False:
        errors.append(f"{iso}: machine_translation_used must be false")
    if payload.get("automatic_diacritization_used") is not False:
        errors.append(f"{iso}: automatic_diacritization_used must be false")

    services = {item.get("id"): item for item in payload.get("services") or [] if isinstance(item, dict)}
    missing = sorted(REQUIRED_SERVICES - set(services))
    if missing:
        errors.append(f"{iso}: missing services {','.join(missing)}")
    validate_composed_liturgy(
        services.get("divine_liturgy") or {},
        iso,
        languages,
        native_libraries,
        errors,
    )

    readings = {item.get("kind"): item for item in payload.get("readings") or [] if isinstance(item, dict)}
    for kind in ("epistle", "gospel"):
        item = readings.get(kind)
        if not item:
            errors.append(f"{iso}: {kind} is missing")
            continue
        body = item.get("body") or {}
        verification = item.get("native_source_verification") or {}
        for language in languages:
            if not localized_text(body, language):
                errors.append(f"{iso}: {kind}.{language} body is missing")
            evidence = verification.get(language) or {}
            if evidence.get("status") not in {
                "VERIFIED_EXACT_NATIVE_SOURCE",
                "IMPORTED_EXACT_OFFICIAL_NATIVE_CORPUS",
                "IMPORTED_EXACT_PUBLIC_DOMAIN_NATIVE_CORPUS",
            }:
                errors.append(f"{iso}: {kind}.{language} verification is missing")
            if evidence.get("ai_translation_used") is not False:
                errors.append(f"{iso}: {kind}.{language} AI translation flag invalid")

    check_no_placeholders(payload.get("services") or [], f"days[{iso}].services", errors)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--expected-start", required=True)
    parser.add_argument("--language", choices=LANGUAGES)
    parser.add_argument(
        "--require-reviewed-propers",
        action="store_true",
        help="Block signing/publication when a daily commemoration or variable proper is still generic.",
    )
    args = parser.parse_args()

    payload = json.loads((ROOT / args.path).read_text(encoding="utf-8"))
    start = date.fromisoformat(args.expected_start)
    meta = payload.get("rolling_week") or {}
    errors: list[str] = []

    if meta.get("schema_version") != 1:
        errors.append("rolling_week.schema_version must be 1")
    if meta.get("policy") != "TODAY_PLUS_SEVEN_COMPLETE_DAYS":
        errors.append("rolling_week.policy is invalid")
    if meta.get("start_date") != start.isoformat():
        errors.append("rolling_week.start_date mismatch")
    if meta.get("end_date") != (start + timedelta(days=7)).isoformat():
        errors.append("rolling_week.end_date mismatch")
    if meta.get("day_count") != 8:
        errors.append("rolling_week.day_count must be 8")
    if meta.get("status") != "COMPLETE" or meta.get("fail_closed") is not True:
        errors.append("rolling_week must be COMPLETE and fail_closed")

    languages = (args.language,) if args.language else LANGUAGES
    native_libraries = {
        language: validate_payload(NATIVE_LIBRARY_PATHS[language])
        for language in languages
    }

    days = [payload] + [item for item in payload.get("weekly_days") or [] if isinstance(item, dict)]
    if len(days) != 8:
        errors.append(f"rolling package must contain 8 days, found {len(days)}")
    for offset, day_payload in enumerate(days[:8]):
        validate_day(
            day_payload,
            start + timedelta(days=offset),
            languages,
            native_libraries,
            errors,
        )
        if args.language:
            lane = day_payload.get("language")
            if lane and lane != args.language:
                errors.append(f"{start + timedelta(days=offset)}: lane mismatch {lane}")
        if args.require_reviewed_propers:
            check_reviewed_propers(day_payload, f"days[{offset}]", errors)

    if errors:
        for error in errors[:80]:
            print(f"ROLLING_WEEK_ERROR {error}")
        raise SystemExit(f"ROLLING_WEEK_INVALID errors={len(errors)}")
    print(
        f"ROLLING_WEEK_OK start={start.isoformat()} end={(start + timedelta(days=7)).isoformat()} "
        f"days=8 language={args.language or 'all'}"
    )


if __name__ == "__main__":
    main()
